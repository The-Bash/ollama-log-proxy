"""SQLite logging backend with WAL mode for concurrent access."""

from __future__ import annotations

import json
import sqlite3
import threading

from ollama_log_proxy.parser import LogEntry

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS inference_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    caller_ip TEXT NOT NULL,
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_type TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms REAL NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    metadata TEXT DEFAULT '{}'
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON inference_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_model ON inference_logs(model);
"""


class SQLiteBackend:
    """SQLite-backed log storage using WAL mode for safe concurrent writes."""

    def __init__(self, db_path: str = "./ollama-logs.db") -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._conn.executescript(_CREATE_TABLE + _CREATE_INDEX)
        self._conn.commit()

    def log(self, entry: LogEntry) -> None:
        """Insert a log entry into the inference_logs table."""
        with self._lock:
            self._conn.execute(
                """INSERT INTO inference_logs
                (timestamp, caller_ip, model, endpoint, request_type,
                 status_code, duration_ms, prompt_tokens, completion_tokens,
                 total_tokens, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entry.timestamp,
                    entry.caller_ip,
                    entry.model,
                    entry.endpoint,
                    entry.request_type,
                    entry.status_code,
                    entry.duration_ms,
                    entry.prompt_tokens,
                    entry.completion_tokens,
                    entry.total_tokens,
                    json.dumps(entry.metadata),
                ),
            )
            self._conn.commit()

    def query(self, filters: dict) -> list[LogEntry]:
        """Query inference logs, optionally filtered by since, model, or endpoint."""
        clauses = ["request_type = 'inference'"]
        params: list = []

        if "since" in filters:
            clauses.append("timestamp >= ?")
            params.append(filters["since"])
        if "model" in filters:
            clauses.append("model = ?")
            params.append(filters["model"])
        if "endpoint" in filters:
            clauses.append("endpoint = ?")
            params.append(filters["endpoint"])

        where = " AND ".join(clauses)
        sql = f"SELECT * FROM inference_logs WHERE {where} ORDER BY timestamp DESC"

        with self._lock:
            cursor = self._conn.execute(sql, params)
            rows = cursor.fetchall()

        entries = []
        for row in rows:
            entries.append(
                LogEntry(
                    timestamp=row[1],
                    caller_ip=row[2],
                    model=row[3],
                    endpoint=row[4],
                    request_type=row[5],
                    status_code=row[6],
                    duration_ms=row[7],
                    prompt_tokens=row[8],
                    completion_tokens=row[9],
                    total_tokens=row[10],
                    metadata=json.loads(row[11]) if row[11] else {},
                )
            )
        return entries

    def close(self) -> None:
        """Close the SQLite connection."""
        self._conn.close()
