"""Stdout logging backend for development and debugging."""

from __future__ import annotations

import sys

from ollama_log_proxy.parser import LogEntry


class StdoutBackend:
    """Logging backend that prints entries to stderr for development use."""

    def __init__(self) -> None:
        self._entries: list[LogEntry] = []

    def log(self, entry: LogEntry) -> None:
        """Print a formatted log line to stderr and keep the entry in memory."""
        self._entries.append(entry)
        line = (
            f"[{entry.timestamp}] {entry.caller_ip} "
            f"{entry.endpoint} model={entry.model} "
            f"status={entry.status_code} duration={entry.duration_ms:.0f}ms "
            f"tokens={entry.total_tokens} "
            f"(prompt={entry.prompt_tokens} completion={entry.completion_tokens})"
        )
        print(line, file=sys.stderr)

    def query(self, filters: dict) -> list[LogEntry]:
        """Filter the in-memory entry list by since and model."""
        results = []
        since = filters.get("since")
        model_filter = filters.get("model")

        for entry in self._entries:
            if entry.request_type != "inference":
                continue
            if since and entry.timestamp < since:
                continue
            if model_filter and entry.model != model_filter:
                continue
            results.append(entry)

        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results

    def close(self) -> None:
        """No-op; nothing to release."""
        pass
