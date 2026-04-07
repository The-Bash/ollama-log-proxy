"""PostgreSQL logging backend using psycopg2."""

from __future__ import annotations

import json
from typing import Any

from ollama_log_proxy.parser import LogEntry

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS inference_logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    caller_ip TEXT NOT NULL,
    model TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_type TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    duration_ms DOUBLE PRECISION NOT NULL,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    metadata JSONB DEFAULT '{}'
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON inference_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_logs_model ON inference_logs(model);
"""


class PostgresBackend:
    """PostgreSQL-backed log storage using psycopg2."""

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg2
        except ImportError as exc:
            raise ImportError(
                "PostgreSQL backend requires psycopg2. "
                "Install with: pip install ollama-log-proxy[postgres]"
            ) from exc

        self._conn = psycopg2.connect(dsn)
        self._conn.autocommit = True
        with self._conn.cursor() as cur:
            cur.execute(_CREATE_TABLE)
            cur.execute(_CREATE_INDEX)

    def log(self, entry: LogEntry) -> None:
        """Insert a log entry into the inference_logs table."""
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO inference_logs
                (timestamp, caller_ip, model, endpoint, request_type,
                 status_code, duration_ms, prompt_tokens, completion_tokens,
                 total_tokens, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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

    def query(self, filters: dict[str, Any]) -> list[LogEntry]:
        """Query inference logs, optionally filtered by since, model, or endpoint."""
        clauses = ["request_type = 'inference'"]
        params: list[Any] = []

        if "since" in filters:
            clauses.append("timestamp >= %s")
            params.append(filters["since"])
        if "model" in filters:
            clauses.append("model = %s")
            params.append(filters["model"])
        if "endpoint" in filters:
            clauses.append("endpoint = %s")
            params.append(filters["endpoint"])

        where = " AND ".join(clauses)
        sql = f"SELECT * FROM inference_logs WHERE {where} ORDER BY timestamp DESC"

        with self._conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

        entries = []
        for row in rows:
            meta = row[11] if row[11] else {}
            if isinstance(meta, str):
                meta = json.loads(meta)
            entries.append(
                LogEntry(
                    timestamp=str(row[1]),
                    caller_ip=row[2],
                    model=row[3],
                    endpoint=row[4],
                    request_type=row[5],
                    status_code=row[6],
                    duration_ms=row[7],
                    prompt_tokens=row[8],
                    completion_tokens=row[9],
                    total_tokens=row[10],
                    metadata=meta,
                )
            )
        return entries

    def close(self) -> None:
        """Close the PostgreSQL connection."""
        self._conn.close()
