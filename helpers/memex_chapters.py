import os
import uuid
import time
import datetime
import sqlite3
from helpers import files

_DB_FILE      = "usr/plugins/memex/data/session_index.db"
_CHAPTERS_DIR = "usr/plugins/memex/data/chapters"

# Internal DB helpers

def _db_path() -> str:
    return files.get_abs_path(_DB_FILE)


def _get_conn() -> sqlite3.Connection:
    path = _db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    _ensure_table(conn)
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chapters (
            id               TEXT PRIMARY KEY,
            context_id       TEXT NOT NULL,
            project_name     TEXT DEFAULT '',
            chapter_index    INTEGER DEFAULT 1,
            parent_chapter_id TEXT,
            token_count      INTEGER DEFAULT 0,
            message_count    INTEGER DEFAULT 0,
            compressed_at    REAL NOT NULL
        )
    """)
    conn.commit()


# Public API

def get_latest_chapter_id(context_id: str) -> str | None:
    """Return the most recent chapter id for a context, or None."""
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT id FROM chapters WHERE context_id = ? ORDER BY compressed_at DESC LIMIT 1",
            (context_id,),
        ).fetchone()
        conn.close()
        return row["id"] if row else None
    except Exception:
        return None


def _next_chapter_index(conn: sqlite3.Connection, context_id: str) -> int:
    row = conn.execute(
        "SELECT MAX(chapter_index) FROM chapters WHERE context_id = ?",
        (context_id,),
    ).fetchone()
    max_idx = row[0] if row and row[0] is not None else 0
    return max_idx + 1


def save_chapter(
    context_id: str,
    project_name: str,
    history_text: str,
    token_count: int,
    message_count: int,
) -> str:
    """Snapshot the current conversation and persist it. Returns new chapter id."""
    chapter_id = str(uuid.uuid4())

    # Save text
    chapters_dir = files.get_abs_path(_CHAPTERS_DIR)
    os.makedirs(chapters_dir, exist_ok=True)
    txt_path = os.path.join(chapters_dir, f"{chapter_id}.txt")
    files.write_file(txt_path, history_text)

    # Save metadata
    conn = _get_conn()
    parent_id    = get_latest_chapter_id(context_id)
    chapter_idx  = _next_chapter_index(conn, context_id)
    now          = time.time()

    conn.execute(
        """INSERT INTO chapters
               (id, context_id, project_name, chapter_index,
                parent_chapter_id, token_count, message_count, compressed_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (chapter_id, context_id, project_name, chapter_idx,
         parent_id, token_count, message_count, now),
    )
    conn.commit()
    conn.close()
    return chapter_id


def get_stats(project_name: str = "") -> dict:
    """Return aggregate chapter stats, optionally filtered by project."""
    try:
        conn = _get_conn()
        if project_name:
            rows = conn.execute(
                "SELECT token_count, compressed_at FROM chapters WHERE project_name = ?",
                (project_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT token_count, compressed_at FROM chapters",
            ).fetchall()
        conn.close()

        total          = len(rows)
        total_tokens   = sum(r["token_count"] for r in rows)
        last_ts        = max((r["compressed_at"] for r in rows), default=None)
        last_compressed = (
            datetime.datetime.fromtimestamp(last_ts, tz=datetime.timezone.utc).isoformat()
            if last_ts else None
        )

        return {
            "total":                  total,
            "total_tokens_preserved": total_tokens,
            "last_compressed":        last_compressed,
        }
    except Exception:
        return {"total": 0, "total_tokens_preserved": 0, "last_compressed": None}
