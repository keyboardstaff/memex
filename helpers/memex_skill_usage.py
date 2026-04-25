import json
import os
from datetime import datetime, timezone
from helpers import files

_USAGE_FILE = "usr/plugins/memex/data/skill_usage.json"
_STATS_KEY = "_recall_stats"


def _load() -> dict:
    path = files.get_abs_path(_USAGE_FILE)
    if not os.path.isfile(path):
        return {}
    try:
        return json.loads(files.read_file(path)) or {}
    except Exception:
        return {}


def _save(data: dict) -> None:
    files.write_file(files.get_abs_path(_USAGE_FILE), json.dumps(data, ensure_ascii=False))


def record(skill_name: str) -> None:
    """Increment recall count for skill_name."""
    data = _load()
    entry = data.get(skill_name, {"count": 0, "last_recalled": None})
    entry["count"] = entry.get("count", 0) + 1
    entry["last_recalled"] = datetime.now(timezone.utc).isoformat()
    data[skill_name] = entry
    _save(data)


def record_attempt(hit: bool) -> None:
    """Record one recall attempt.  hit=True when at least one skill was injected."""
    data = _load()
    stats = data.get(_STATS_KEY, {"attempts": 0, "hits": 0})
    stats["attempts"] = stats.get("attempts", 0) + 1
    if hit:
        stats["hits"] = stats.get("hits", 0) + 1
    data[_STATS_KEY] = stats
    _save(data)


def get_counts() -> dict[str, int]:
    """Return {skill_name: count} for all tracked skills (excludes _recall_stats)."""
    return {k: v.get("count", 0) for k, v in _load().items() if k != _STATS_KEY}


def get_recall_stats() -> dict:
    """Return {"attempts": N, "hits": M, "rate": float 0-1}."""
    data = _load()
    stats = data.get(_STATS_KEY, {"attempts": 0, "hits": 0})
    attempts = stats.get("attempts", 0)
    hits = stats.get("hits", 0)
    rate = round(hits / attempts, 3) if attempts > 0 else 0.0
    return {"attempts": attempts, "hits": hits, "rate": rate}
