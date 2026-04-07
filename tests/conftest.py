"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from ollama_log_proxy.backends.sqlite import SQLiteBackend
from ollama_log_proxy.backends.stdout import StdoutBackend
from ollama_log_proxy.parser import LogEntry

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def generate_response_bytes(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "generate_response.json").read_bytes()


@pytest.fixture
def chat_response_bytes(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "chat_response.json").read_bytes()


@pytest.fixture
def streaming_response_bytes(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "chat_streaming.ndjson").read_bytes()


@pytest.fixture
def embeddings_response_bytes(fixtures_dir: Path) -> bytes:
    return (fixtures_dir / "embeddings_response.json").read_bytes()


@pytest.fixture
def sqlite_backend(tmp_path: Path) -> SQLiteBackend:
    db_path = str(tmp_path / "test.db")
    backend = SQLiteBackend(db_path=db_path)
    yield backend
    backend.close()


@pytest.fixture
def stdout_backend() -> StdoutBackend:
    return StdoutBackend()


@pytest.fixture
def sample_entry() -> LogEntry:
    return LogEntry(
        timestamp="2024-12-01T10:00:00+00:00",
        caller_ip="127.0.0.1",
        model="llama3.2",
        endpoint="/api/chat",
        request_type="inference",
        status_code=200,
        duration_ms=1234.56,
        prompt_tokens=18,
        completion_tokens=35,
        total_tokens=53,
    )
