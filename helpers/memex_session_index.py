import sqlite3
import hashlib
import json
import os
from datetime import datetime, timezone
from helpers import files
from helpers.print_style import PrintStyle
from usr.plugins.memex.helpers.memex_db import get_session_db_path, get_session_connection

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    context_id    TEXT PRIMARY KEY,
    project_name  TEXT,
    agent_name    TEXT DEFAULT 'agent0',
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    message_count INTEGER DEFAULT 0,
    summary       TEXT,
    tags          TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS session_messages USING fts5(
    context_id,
    role,
    content,
    timestamp,
    message_index,
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS index_state (
    context_id    TEXT PRIMARY KEY,
    indexed_at    TEXT NOT NULL,
    message_hash  TEXT NOT NULL
);
"""


class SessionIndex:

    def __init__(self):
        self.db_path = get_session_db_path()
        self._ensure_db()

    def _ensure_db(self):
        conn = get_session_connection()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    def index_conversation(
        self,
        context_id: str,
        messages: list[dict],
        project_name: str = "",
        agent_name: str = "agent0",
    ) -> bool:
        content_hash = hashlib.sha256(
            json.dumps(
                [m.get("content", "") for m in messages],
                default=str,
            ).encode()
        ).hexdigest()

        conn = sqlite3.connect(self.db_path)
        try:
            existing = conn.execute(
                "SELECT message_hash FROM index_state WHERE context_id = ?",
                (context_id,),
            ).fetchone()

            if existing and existing[0] == content_hash:
                return False

            conn.execute(
                "DELETE FROM session_messages WHERE context_id = ?",
                (context_id,),
            )

            now = datetime.now(timezone.utc).isoformat()
            for i, msg in enumerate(messages):
                role = "agent" if msg.get("ai") else "user"
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        part.get("text", "")
                        for part in content
                        if isinstance(part, dict)
                    )
                elif isinstance(content, dict):
                    content = content.get("text", "") or content.get("raw_content", "")
                if not isinstance(content, str):
                    content = str(content)

                conn.execute(
                    "INSERT INTO session_messages(context_id, role, content, timestamp, message_index) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (context_id, role, content, now, str(i)),
                )

            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                (context_id, project_name, agent_name, started_at, ended_at, message_count)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (context_id, project_name, agent_name, now, now, len(messages)),
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO index_state (context_id, indexed_at, message_hash)
                VALUES (?, ?, ?)
                """,
                (context_id, now, content_hash),
            )

            conn.commit()
            return True
        finally:
            conn.close()

    def search(
        self,
        query: str,
        project_name: str = "",
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            sql = """
                SELECT
                    sm.context_id,
                    sm.role,
                    snippet(session_messages, 2, '<mark>', '</mark>', '...', 32) as snippet,
                    sm.timestamp,
                    sm.message_index,
                    s.project_name,
                    s.started_at,
                    rank
                FROM session_messages sm
                JOIN sessions s ON sm.context_id = s.context_id
                WHERE session_messages MATCH ?
            """
            # Scope to content column to avoid FTS5 interpreting words as column names.
            # Quote each token to prevent FTS5 special chars (:, *, +, etc.) from
            # being misinterpreted as operators or column prefixes.
            safe_tokens = [
                '"' + tok.replace('"', '""') + '"'
                for tok in query.split()
                if tok
            ]
            fts_query = "content:" + " ".join(safe_tokens) if safe_tokens else query
            params: list = [fts_query]

            if project_name:
                sql += " AND s.project_name = ?"
                params.append(project_name)

            sql += " ORDER BY rank LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            rows = conn.execute(sql, params).fetchall()

            return [
                {
                    "context_id": row[0],
                    "role": row[1],
                    "snippet": row[2],
                    "timestamp": row[3],
                    "message_index": int(row[4]),
                    "project_name": row[5],
                    "session_started": row[6],
                    "relevance": -row[7],
                }
                for row in rows
            ]
        except Exception as e:
            PrintStyle.error(f"[SessionSearch] Search error: {e}")
            return []
        finally:
            conn.close()

    def get_session_context(
        self, context_id: str, around_index: int, window: int = 3
    ) -> list[dict]:
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT role, content, timestamp, message_index
                FROM session_messages
                WHERE context_id = ?
                AND CAST(message_index AS INTEGER) BETWEEN ? AND ?
                ORDER BY CAST(message_index AS INTEGER)
                """,
                (context_id, max(0, around_index - window), around_index + window),
            ).fetchall()

            return [
                {"role": r[0], "content": r[1], "timestamp": r[2], "index": int(r[3])}
                for r in rows
            ]
        finally:
            conn.close()

    def get_stats(self, project_name: str = "") -> dict:
        conn = sqlite3.connect(self.db_path)
        try:
            if project_name:
                session_count = conn.execute(
                    "SELECT COUNT(*) FROM sessions WHERE project_name = ?",
                    (project_name,),
                ).fetchone()[0]
                message_count = conn.execute(
                    """SELECT COUNT(*) FROM session_messages sm
                       JOIN sessions s ON sm.context_id = s.context_id
                       WHERE s.project_name = ?""",
                    (project_name,),
                ).fetchone()[0]
                last_updated = conn.execute(
                    """SELECT MAX(is2.indexed_at) FROM index_state is2
                       JOIN sessions s ON is2.context_id = s.context_id
                       WHERE s.project_name = ?""",
                    (project_name,),
                ).fetchone()[0]
            else:
                session_count = conn.execute(
                    "SELECT COUNT(*) FROM sessions"
                ).fetchone()[0]
                message_count = conn.execute(
                    "SELECT COUNT(*) FROM session_messages"
                ).fetchone()[0]
                last_updated = conn.execute(
                    "SELECT MAX(indexed_at) FROM index_state"
                ).fetchone()[0]
            return {
                "sessions": session_count,
                "messages": message_count,
                "last_updated": last_updated,
            }
        finally:
            conn.close()
