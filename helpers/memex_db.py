import sqlite3
import os
from helpers import files

_DB_DIR = "usr/plugins/memex/data"


def _ensure_data_dir():
    path = files.get_abs_path(_DB_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def get_session_db_path() -> str:
    data_dir = _ensure_data_dir()
    return os.path.join(data_dir, "sessions.db")


def get_meta_db_path() -> str:
    data_dir = _ensure_data_dir()
    return os.path.join(data_dir, "memory.db")


def get_session_connection() -> sqlite3.Connection:
    path = get_session_db_path()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn
