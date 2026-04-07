"""Tests for logging backends."""

from __future__ import annotations

import json

from ollama_log_proxy.backends import LogBackend, create_backend
from ollama_log_proxy.backends.jsonl import JSONLBackend
from ollama_log_proxy.backends.sqlite import SQLiteBackend
from ollama_log_proxy.backends.stdout import StdoutBackend
from ollama_log_proxy.parser import LogEntry


class TestSQLiteBackend:
    def test_implements_protocol(self, sqlite_backend):
        assert isinstance(sqlite_backend, LogBackend)

    def test_log_and_query(self, sqlite_backend, sample_entry):
        sqlite_backend.log(sample_entry)
        results = sqlite_backend.query({})
        assert len(results) == 1
        assert results[0].model == "llama3.2"
        assert results[0].prompt_tokens == 18
        assert results[0].completion_tokens == 35

    def test_query_by_model(self, sqlite_backend, sample_entry):
        sqlite_backend.log(sample_entry)

        other = LogEntry(
            timestamp="2024-12-01T11:00:00+00:00",
            caller_ip="127.0.0.1",
            model="mistral",
            endpoint="/api/chat",
            request_type="inference",
            status_code=200,
            duration_ms=500.0,
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        sqlite_backend.log(other)

        results = sqlite_backend.query({"model": "mistral"})
        assert len(results) == 1
        assert results[0].model == "mistral"

    def test_query_by_since(self, sqlite_backend, sample_entry):
        sqlite_backend.log(sample_entry)
        results = sqlite_backend.query({"since": "2024-12-01T09:00:00+00:00"})
        assert len(results) == 1

        results = sqlite_backend.query({"since": "2025-01-01T00:00:00+00:00"})
        assert len(results) == 0

    def test_empty_query(self, sqlite_backend):
        results = sqlite_backend.query({})
        assert results == []


class TestJSONLBackend:
    def test_implements_protocol(self, tmp_path):
        backend = JSONLBackend(log_file=str(tmp_path / "test.jsonl"))
        assert isinstance(backend, LogBackend)

    def test_log_and_query(self, tmp_path, sample_entry):
        backend = JSONLBackend(log_file=str(tmp_path / "test.jsonl"))
        backend.log(sample_entry)

        results = backend.query({})
        assert len(results) == 1
        assert results[0].model == "llama3.2"

    def test_file_contains_valid_json(self, tmp_path, sample_entry):
        path = tmp_path / "test.jsonl"
        backend = JSONLBackend(log_file=str(path))
        backend.log(sample_entry)

        lines = path.read_text().strip().split("\n")
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["model"] == "llama3.2"

    def test_query_empty_file(self, tmp_path):
        backend = JSONLBackend(log_file=str(tmp_path / "nonexistent.jsonl"))
        results = backend.query({})
        assert results == []


class TestStdoutBackend:
    def test_implements_protocol(self, stdout_backend):
        assert isinstance(stdout_backend, LogBackend)

    def test_log_and_query(self, stdout_backend, sample_entry, capsys):
        stdout_backend.log(sample_entry)

        results = stdout_backend.query({})
        assert len(results) == 1

        captured = capsys.readouterr()
        assert "llama3.2" in captured.err

    def test_query_filters_non_inference(self, stdout_backend):
        entry = LogEntry(
            timestamp="2024-12-01T10:00:00+00:00",
            caller_ip="127.0.0.1",
            model="",
            endpoint="/api/tags",
            request_type="poll",
            status_code=200,
            duration_ms=10.0,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
        )
        stdout_backend.log(entry)
        results = stdout_backend.query({})
        assert results == []


class TestCreateBackend:
    def test_create_sqlite(self, tmp_path):
        backend = create_backend("sqlite", db_path=str(tmp_path / "test.db"))
        assert isinstance(backend, SQLiteBackend)
        backend.close()

    def test_create_jsonl(self, tmp_path):
        backend = create_backend("jsonl", log_file=str(tmp_path / "test.jsonl"))
        assert isinstance(backend, JSONLBackend)

    def test_create_stdout(self):
        backend = create_backend("stdout")
        assert isinstance(backend, StdoutBackend)

    def test_unknown_backend(self):
        try:
            create_backend("unknown")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass
