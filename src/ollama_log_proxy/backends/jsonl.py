"""JSONL (JSON Lines) file logging backend."""

from __future__ import annotations

import json
import threading
from pathlib import Path

from ollama_log_proxy.parser import LogEntry


class JSONLBackend:
    """Append-only JSON Lines file backend."""

    def __init__(self, log_file: str = "./ollama.jsonl") -> None:
        self._path = Path(log_file)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, entry: LogEntry) -> None:
        """Append a JSON-serialized log entry as a single line."""
        line = json.dumps(entry.to_dict()) + "\n"
        with self._lock:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line)

    def query(self, filters: dict) -> list[LogEntry]:
        """Read and filter log entries from the JSONL file."""
        if not self._path.exists():
            return []

        entries = []
        since = filters.get("since")
        model_filter = filters.get("model")

        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if data.get("request_type") != "inference":
                    continue
                if since and data.get("timestamp", "") < since:
                    continue
                if model_filter and data.get("model") != model_filter:
                    continue

                entries.append(
                    LogEntry(
                        timestamp=data.get("timestamp", ""),
                        caller_ip=data.get("caller_ip", ""),
                        model=data.get("model", ""),
                        endpoint=data.get("endpoint", ""),
                        request_type=data.get("request_type", ""),
                        status_code=data.get("status_code", 0),
                        duration_ms=data.get("duration_ms", 0.0),
                        prompt_tokens=data.get("prompt_tokens", 0),
                        completion_tokens=data.get("completion_tokens", 0),
                        total_tokens=data.get("total_tokens", 0),
                        metadata=data.get("metadata", {}),
                    )
                )

        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries

    def close(self) -> None:
        """No-op; file handles are opened and closed per write."""
        pass
