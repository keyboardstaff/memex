import math
import re
import sqlite3
from datetime import datetime, timezone
from helpers import files
from usr.plugins.memex.helpers.memex_db import get_meta_db_path

_SCHEMA_INIT = False


def _get_connection() -> sqlite3.Connection:
    path = get_meta_db_path()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    global _SCHEMA_INIT
    if not _SCHEMA_INIT:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS memory_access (
                memory_id     TEXT NOT NULL,
                memory_subdir TEXT NOT NULL DEFAULT 'default',
                area          TEXT NOT NULL DEFAULT 'main',
                created_at    TEXT NOT NULL,
                last_accessed TEXT,
                access_count  INTEGER DEFAULT 0,
                importance    REAL DEFAULT 0.5,
                boosted_until TEXT,
                PRIMARY KEY (memory_id, memory_subdir)
            );
            CREATE INDEX IF NOT EXISTS idx_access_subdir ON memory_access(memory_subdir);
            CREATE INDEX IF NOT EXISTS idx_access_last ON memory_access(last_accessed);
        """)
        _SCHEMA_INIT = True
    return conn


def compute_priority_score(
    similarity: float,
    access_count: int = 0,
    last_accessed: datetime | None = None,
    created_at: datetime | None = None,
    importance: float = 0.5,
    *,
    decay_half_life_days: float = 14.0,
    access_weight: float = 0.15,
    importance_weight: float = 0.10,
    recency_weight: float = 0.20,
    similarity_weight: float = 0.55,
) -> float:
    now = datetime.now(timezone.utc)

    ref_time = last_accessed or created_at or now
    if isinstance(ref_time, str):
        try:
            ref_time = datetime.fromisoformat(ref_time)
        except Exception:
            ref_time = now
    if ref_time.tzinfo is None:
        ref_time = ref_time.replace(tzinfo=timezone.utc)

    days_elapsed = max(0, (now - ref_time).total_seconds() / 86400)
    recency = math.exp(-math.log(2) * days_elapsed / max(decay_half_life_days, 0.01))

    access_factor = 1 - math.exp(-0.3 * access_count)

    score = (
        similarity_weight * similarity
        + recency_weight * recency
        + access_weight * access_factor
        + importance_weight * importance
    )
    return max(0.0, min(1.0, score))


def record_access(memory_ids: list[str], memory_subdir: str = "default"):
    if not memory_ids:
        return
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()
    try:
        for mid in memory_ids:
            conn.execute("""
                INSERT INTO memory_access (memory_id, memory_subdir, created_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(memory_id, memory_subdir) DO UPDATE SET
                    last_accessed = excluded.last_accessed,
                    access_count = access_count + 1
            """, (mid, memory_subdir, now, now))
        conn.commit()
    finally:
        conn.close()


def get_access_data(memory_ids: list[str], memory_subdir: str = "default") -> dict[str, dict]:
    if not memory_ids:
        return {}
    conn = _get_connection()
    try:
        placeholders = ",".join("?" for _ in memory_ids)
        rows = conn.execute(
            f"SELECT * FROM memory_access WHERE memory_id IN ({placeholders}) AND memory_subdir = ?",
            [*memory_ids, memory_subdir],
        ).fetchall()
        return {r["memory_id"]: dict(r) for r in rows}
    finally:
        conn.close()


def expire_boosts():
    conn = _get_connection()
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute(
            "UPDATE memory_access SET boosted_until = NULL WHERE boosted_until IS NOT NULL AND boosted_until < ?",
            (now,),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats(memory_subdir: str | None = None) -> dict:
    conn = _get_connection()
    try:
        if memory_subdir:
            row = conn.execute(
                "SELECT COUNT(*) as total, AVG(access_count) as avg_access, MAX(access_count) as max_access, MAX(last_accessed) as last_updated FROM memory_access WHERE memory_subdir = ?",
                (memory_subdir,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) as total, AVG(access_count) as avg_access, MAX(access_count) as max_access, MAX(last_accessed) as last_updated FROM memory_access",
            ).fetchone()
        return dict(row) if row else {"total": 0, "avg_access": 0, "max_access": 0, "last_updated": None}
    finally:
        conn.close()


def extract_memory_ids_from_text(text: str) -> list[str]:
    """Extract memory IDs from formatted memory output (id: xxx lines)."""
    return re.findall(r"^id:\s*(.+)$", text, re.MULTILINE)


async def rerank_memories(agent, memories_text: str, config: dict) -> str:
    """Rerank rendered memories text by decay priority score."""
    ids = extract_memory_ids_from_text(memories_text)
    if not ids:
        return memories_text

    from plugins._memory.helpers.memory import Memory
    db = await Memory.get(agent)
    subdir = db.memory_subdir if hasattr(db, "memory_subdir") else "default"

    access_data = get_access_data(ids, subdir)

    # Parse individual memory blocks from text
    blocks = re.split(r"\n\n(?=id:\s)", memories_text)
    if len(blocks) <= 1:
        return memories_text

    scored = []
    for block in blocks:
        mid_match = re.search(r"^id:\s*(.+)$", block, re.MULTILINE)
        mid = mid_match.group(1).strip() if mid_match else ""
        ad = access_data.get(mid, {})
        score = compute_priority_score(
            similarity=0.8,
            access_count=ad.get("access_count", 0),
            last_accessed=ad.get("last_accessed"),
            created_at=ad.get("created_at"),
            importance=ad.get("importance", 0.5),
            decay_half_life_days=config.get("decay_half_life_days", 14.0),
            similarity_weight=config.get("decay_similarity_weight", 0.55),
            recency_weight=config.get("decay_recency_weight", 0.20),
            access_weight=config.get("decay_access_weight", 0.15),
            importance_weight=config.get("decay_importance_weight", 0.10),
        )
        scored.append((score, block))

    scored.sort(key=lambda x: -x[0])
    return "\n\n".join(block for _, block in scored)
