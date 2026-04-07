"""Tests for PostgreSQL backend endpoint filter using mock."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestPostgresEndpointFilter:
    def test_query_with_endpoint_filter(self):
        """PostgresBackend.query() should include endpoint in WHERE clause."""
        with patch(
            "ollama_log_proxy.backends.postgres.PostgresBackend.__init__", return_value=None
        ):
            from ollama_log_proxy.backends.postgres import PostgresBackend

            backend = PostgresBackend.__new__(PostgresBackend)
            mock_conn = MagicMock()
            backend._conn = mock_conn

            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_cursor.fetchall.return_value = []

            backend.query({"endpoint": "/api/chat"})

            call_args = mock_cursor.execute.call_args
            sql = call_args[0][0]
            params = call_args[0][1]

            assert "endpoint = %s" in sql
            assert "/api/chat" in params

    def test_query_without_endpoint(self):
        """Without endpoint filter, the clause should not appear."""
        with patch(
            "ollama_log_proxy.backends.postgres.PostgresBackend.__init__", return_value=None
        ):
            from ollama_log_proxy.backends.postgres import PostgresBackend

            backend = PostgresBackend.__new__(PostgresBackend)
            mock_conn = MagicMock()
            backend._conn = mock_conn

            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_cursor.fetchall.return_value = []

            backend.query({"model": "llama3.2"})

            call_args = mock_cursor.execute.call_args
            sql = call_args[0][0]

            assert "endpoint = %s" not in sql
            assert "model = %s" in sql

    def test_query_combines_all_filters(self):
        """All filters should be combined in WHERE clause."""
        with patch(
            "ollama_log_proxy.backends.postgres.PostgresBackend.__init__", return_value=None
        ):
            from ollama_log_proxy.backends.postgres import PostgresBackend

            backend = PostgresBackend.__new__(PostgresBackend)
            mock_conn = MagicMock()
            backend._conn = mock_conn

            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_cursor.fetchall.return_value = []

            backend.query(
                {
                    "since": "2024-01-01T00:00:00+00:00",
                    "model": "llama3.2",
                    "endpoint": "/api/generate",
                }
            )

            call_args = mock_cursor.execute.call_args
            sql = call_args[0][0]
            params = call_args[0][1]

            assert "timestamp >= %s" in sql
            assert "model = %s" in sql
            assert "endpoint = %s" in sql
            assert len(params) == 3
