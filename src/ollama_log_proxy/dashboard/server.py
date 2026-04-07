"""Built-in dashboard HTTP server."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from ollama_log_proxy.backends import LogBackend
from ollama_log_proxy.metrics import MetricsCollector, _check_token

_DASHBOARD_HTML = Path(__file__).parent / "index.html"


def _make_handler(
    backend: LogBackend,
    collector: MetricsCollector,
    dashboard_token: str = "",
) -> type[BaseHTTPRequestHandler]:

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            if not _check_token(self, dashboard_token):
                self.send_error(401, "Unauthorized")
                return

            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                self._serve_html()
            elif path == "/api/stats":
                self._serve_stats()
            else:
                self.send_error(404)

        def _serve_html(self) -> None:
            content = _DASHBOARD_HTML.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def _serve_stats(self) -> None:
            stats = collector.get_stats()
            body = json.dumps(stats).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    return DashboardHandler


def start_dashboard(
    port: int,
    backend: LogBackend,
    collector: MetricsCollector,
    bind: str = "0.0.0.0",
    dashboard_token: str = "",
) -> HTTPServer:
    """Launch the dashboard web server on a daemon thread."""
    handler = _make_handler(backend, collector, dashboard_token)
    server = HTTPServer((bind, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
