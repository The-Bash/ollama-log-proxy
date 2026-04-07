"""Tests for CLI argument parsing."""

from __future__ import annotations

from ollama_log_proxy.cli import build_parser


class TestCLI:
    def test_default_args(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.port is None
        assert args.ollama_url is None
        assert args.backend is None

    def test_custom_port(self):
        parser = build_parser()
        args = parser.parse_args(["--port", "9999"])
        assert args.port == 9999

    def test_backend_choices(self):
        parser = build_parser()
        for backend in ["sqlite", "postgres", "jsonl", "stdout"]:
            args = parser.parse_args(["--backend", backend])
            assert args.backend == backend

    def test_report_subcommand(self):
        parser = build_parser()
        args = parser.parse_args(["report", "--last", "7d", "--format", "json"])
        assert args.command == "report"
        assert args.last == "7d"
        assert args.output_format == "json"

    def test_report_default_format(self):
        parser = build_parser()
        args = parser.parse_args(["report"])
        assert args.command == "report"
        assert args.last == "30d"
        assert args.output_format == "table"

    def test_dashboard_port(self):
        parser = build_parser()
        args = parser.parse_args(["--dashboard", "8080"])
        assert args.dashboard == 8080

    def test_metrics_port(self):
        parser = build_parser()
        args = parser.parse_args(["--metrics-port", "9090"])
        assert args.metrics_port == 9090

    def test_bind_address(self):
        parser = build_parser()
        args = parser.parse_args(["--bind", "127.0.0.1"])
        assert args.bind == "127.0.0.1"

    def test_dashboard_token(self):
        parser = build_parser()
        args = parser.parse_args(["--dashboard-token", "mysecret"])
        assert args.dashboard_token == "mysecret"

    def test_metrics_token(self):
        parser = build_parser()
        args = parser.parse_args(["--metrics-token", "metricskey"])
        assert args.metrics_token == "metricskey"

    def test_max_request_size(self):
        parser = build_parser()
        args = parser.parse_args(["--max-request-size", "52428800"])
        assert args.max_request_size == 52428800

    def test_default_bind_is_none(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.bind is None

    def test_default_tokens_are_none(self):
        parser = build_parser()
        args = parser.parse_args([])
        assert args.dashboard_token is None
        assert args.metrics_token is None

    def test_all_args(self):
        parser = build_parser()
        args = parser.parse_args(
            [
                "--port",
                "11433",
                "--ollama-url",
                "http://remote:11434",
                "--backend",
                "postgres",
                "--dsn",
                "postgresql://localhost/ollama",
                "--dashboard",
                "8080",
                "--metrics-port",
                "9090",
                "--log-level",
                "DEBUG",
                "--bind",
                "127.0.0.1",
                "--dashboard-token",
                "dt",
                "--metrics-token",
                "mt",
                "--max-request-size",
                "1048576",
            ]
        )
        assert args.port == 11433
        assert args.ollama_url == "http://remote:11434"
        assert args.backend == "postgres"
        assert args.dsn == "postgresql://localhost/ollama"
        assert args.dashboard == 8080
        assert args.metrics_port == 9090
        assert args.log_level == "DEBUG"
        assert args.bind == "127.0.0.1"
        assert args.dashboard_token == "dt"
        assert args.metrics_token == "mt"
        assert args.max_request_size == 1048576
