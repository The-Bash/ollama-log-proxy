"""Command-line interface for ollama-log-proxy."""

from __future__ import annotations

import argparse
import logging
import signal
import sys

from ollama_log_proxy import __version__
from ollama_log_proxy.backends import create_backend
from ollama_log_proxy.config import Config
from ollama_log_proxy.metrics import get_collector, start_metrics_server
from ollama_log_proxy.proxy import ProxyServer
from ollama_log_proxy.report import generate_report


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser with 'serve' and 'report' subcommands."""
    parser = argparse.ArgumentParser(
        prog="ollama-log-proxy",
        description="HTTP reverse proxy for Ollama that logs inference usage.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    # Serve (default)
    serve = subparsers.add_parser("serve", help="Start the proxy server (default)")
    _add_serve_args(serve)
    _add_serve_args(parser)

    # Report
    report = subparsers.add_parser("report", help="Generate a usage report")
    report.add_argument("--last", default="30d", help="Time range (e.g. 30d, 24h)")
    report.add_argument(
        "--format",
        dest="output_format",
        choices=["json", "csv", "table"],
        default="table",
    )
    report.add_argument("--backend", default=None)
    report.add_argument("--db-path", default=None)
    report.add_argument("--dsn", default=None)
    report.add_argument("--log-file", default=None)

    return parser


def _add_serve_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--ollama-url", default=None)
    parser.add_argument(
        "--backend",
        choices=["sqlite", "postgres", "jsonl", "stdout"],
        default=None,
    )
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--log-file", default=None)
    parser.add_argument("--dashboard", type=int, default=None, metavar="PORT")
    parser.add_argument("--metrics-port", type=int, default=None, metavar="PORT")
    parser.add_argument("--bind", default=None, help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--dashboard-token", default=None, help="Dashboard auth token")
    parser.add_argument("--metrics-token", default=None, help="Metrics endpoint auth token")
    parser.add_argument(
        "--max-request-size",
        type=int,
        default=None,
        help="Max request body size in bytes (default: 100MB)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
    )


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ollama-log-proxy CLI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "report":
        return _handle_report(args)

    return _handle_serve(args)


def _handle_serve(args: argparse.Namespace) -> int:
    config = Config()
    if args.port is not None:
        config.port = args.port
    if args.ollama_url is not None:
        config.ollama_url = args.ollama_url
    if args.backend is not None:
        config.backend = args.backend
    if args.db_path is not None:
        config.db_path = args.db_path
    if args.dsn is not None:
        config.dsn = args.dsn
    if args.log_file is not None:
        config.log_file = args.log_file
    if args.dashboard is not None:
        config.dashboard_port = args.dashboard
    if args.metrics_port is not None:
        config.metrics_port = args.metrics_port
    if args.bind is not None:
        config.bind = args.bind
    if args.dashboard_token is not None:
        config.dashboard_token = args.dashboard_token
    if args.metrics_token is not None:
        config.metrics_token = args.metrics_token
    if args.max_request_size is not None:
        config.max_request_size = args.max_request_size

    try:
        config.validate()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger("ollama-log-proxy")

    backend = create_backend(
        config.backend,
        db_path=config.db_path,
        dsn=config.dsn,
        log_file=config.log_file,
    )
    log.info("Backend: %s", config.backend)

    collector = get_collector()

    if config.metrics_port:
        start_metrics_server(
            config.metrics_port,
            collector,
            bind=config.bind,
            metrics_token=config.metrics_token,
        )
        log.info("Metrics server on :%d", config.metrics_port)

    if config.dashboard_port:
        from ollama_log_proxy.dashboard.server import start_dashboard

        start_dashboard(
            config.dashboard_port,
            backend,
            collector,
            bind=config.bind,
            dashboard_token=config.dashboard_token,
        )
        log.info("Dashboard on :%d", config.dashboard_port)

    proxy = ProxyServer(
        config.port,
        config.ollama_url,
        backend,
        collector,
        bind=config.bind,
        max_request_size=config.max_request_size,
    )

    def _shutdown(signum, frame):
        log.info("Shutting down...")
        proxy.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("ollama-log-proxy v%s starting", __version__)
    log.info("Proxying %s:%d -> %s", config.bind, config.port, config.ollama_url)

    try:
        proxy.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        backend.close()

    return 0


def _handle_report(args: argparse.Namespace) -> int:
    config = Config()
    if args.backend is not None:
        config.backend = args.backend
    if args.db_path is not None:
        config.db_path = args.db_path
    if args.dsn is not None:
        config.dsn = args.dsn
    if args.log_file is not None:
        config.log_file = args.log_file

    backend = create_backend(
        config.backend,
        db_path=config.db_path,
        dsn=config.dsn,
        log_file=config.log_file,
    )

    try:
        output = generate_report(backend, last=args.last, output_format=args.output_format)
        print(output)
    finally:
        backend.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
