"""Configuration management via CLI args and environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    """Proxy configuration populated from CLI args and environment variables."""

    port: int = field(default_factory=lambda: int(os.environ.get("OLP_PORT", "11433")))
    ollama_url: str = field(
        default_factory=lambda: os.environ.get("OLP_OLLAMA_URL", "http://localhost:11434")
    )
    backend: str = field(default_factory=lambda: os.environ.get("OLP_BACKEND", "sqlite"))
    db_path: str = field(default_factory=lambda: os.environ.get("OLP_DB_PATH", "./ollama-logs.db"))
    dsn: str = field(default_factory=lambda: os.environ.get("OLP_DSN", ""))
    log_file: str = field(default_factory=lambda: os.environ.get("OLP_LOG_FILE", "./ollama.jsonl"))
    dashboard_port: int = field(
        default_factory=lambda: int(os.environ.get("OLP_DASHBOARD_PORT", "0"))
    )
    metrics_port: int = field(default_factory=lambda: int(os.environ.get("OLP_METRICS_PORT", "0")))
    bind: str = field(default_factory=lambda: os.environ.get("OLP_BIND", "0.0.0.0"))
    dashboard_token: str = field(default_factory=lambda: os.environ.get("OLP_DASHBOARD_TOKEN", ""))
    metrics_token: str = field(default_factory=lambda: os.environ.get("OLP_METRICS_TOKEN", ""))
    max_request_size: int = field(
        default_factory=lambda: int(os.environ.get("OLP_MAX_REQUEST_SIZE", str(100 * 1024 * 1024)))
    )

    def validate(self) -> None:
        """Raise ValueError if the configuration contains invalid or conflicting values."""
        if self.backend == "postgres" and not self.dsn:
            raise ValueError("PostgreSQL backend requires --dsn or OLP_DSN")
        if self.backend not in ("sqlite", "postgres", "jsonl", "stdout"):
            raise ValueError(f"Unknown backend: {self.backend}")
        if not self.ollama_url.startswith(("http://", "https://")):
            raise ValueError(f"Invalid Ollama URL: {self.ollama_url}")
        if self.max_request_size <= 0:
            raise ValueError("--max-request-size must be positive")
