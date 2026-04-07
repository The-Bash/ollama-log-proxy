"""Logging backends for ollama-log-proxy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ollama_log_proxy.parser import LogEntry


@runtime_checkable
class LogBackend(Protocol):
    """Protocol that all logging backends must implement."""

    def log(self, entry: LogEntry) -> None:
        """Persist a single inference log entry."""
        ...

    def query(self, filters: dict) -> list[LogEntry]:
        """Return log entries matching the given filters."""
        ...

    def close(self) -> None:
        """Release backend resources (connections, file handles)."""
        ...


def create_backend(backend_type: str, **kwargs) -> LogBackend:
    """Instantiate a LogBackend by name (sqlite, postgres, jsonl, stdout)."""
    if backend_type == "sqlite":
        from ollama_log_proxy.backends.sqlite import SQLiteBackend

        return SQLiteBackend(db_path=kwargs.get("db_path", "./ollama-logs.db"))
    if backend_type == "postgres":
        from ollama_log_proxy.backends.postgres import PostgresBackend

        return PostgresBackend(dsn=kwargs["dsn"])
    if backend_type == "jsonl":
        from ollama_log_proxy.backends.jsonl import JSONLBackend

        return JSONLBackend(log_file=kwargs.get("log_file", "./ollama.jsonl"))
    if backend_type == "stdout":
        from ollama_log_proxy.backends.stdout import StdoutBackend

        return StdoutBackend()
    raise ValueError(f"Unknown backend: {backend_type}")
