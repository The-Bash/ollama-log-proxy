"""Prometheus-compatible metrics exposition."""

from __future__ import annotations

import threading
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


class MetricsCollector:
    """Thread-safe collector for request counts, token totals, and duration histograms."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: dict[tuple[str, str, str], int] = defaultdict(int)
        self._tokens: dict[tuple[str, str], int] = defaultdict(int)
        self._durations: dict[str, list[float]] = defaultdict(list)
        self._callers: dict[str, int] = defaultdict(int)

    def record_request(
        self, model: str, endpoint: str, status: str, *, caller_ip: str = ""
    ) -> None:
        """Increment the request counter for a (model, endpoint, status) triple."""
        with self._lock:
            self._requests[(model, endpoint, status)] += 1
            if caller_ip:
                self._callers[caller_ip] += 1

    def record_tokens(self, model: str, prompt: int, completion: int) -> None:
        """Add prompt and completion token counts for the given model."""
        with self._lock:
            self._tokens[(model, "prompt")] += prompt
            self._tokens[(model, "completion")] += completion

    def record_duration(self, model: str, duration_ms: float) -> None:
        """Append a request duration sample for histogram bucketing."""
        with self._lock:
            self._durations[model].append(duration_ms)

    def format_prometheus(self) -> str:
        """Render all collected metrics in Prometheus text exposition format."""
        lines: list[str] = []

        lines.append("# HELP ollama_requests_total Total number of Ollama requests")
        lines.append("# TYPE ollama_requests_total counter")
        with self._lock:
            for (model, endpoint, status), count in sorted(self._requests.items()):
                lines.append(
                    f'ollama_requests_total{{model="{model}",endpoint="{endpoint}",'
                    f'status="{status}"}} {count}'
                )

        lines.append("# HELP ollama_tokens_total Total tokens processed")
        lines.append("# TYPE ollama_tokens_total counter")
        with self._lock:
            for (model, token_type), count in sorted(self._tokens.items()):
                lines.append(f'ollama_tokens_total{{model="{model}",type="{token_type}"}} {count}')

        lines.append("# HELP ollama_request_duration_ms Request duration in milliseconds")
        lines.append("# TYPE ollama_request_duration_ms histogram")
        buckets = [10, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000]
        with self._lock:
            for model in sorted(self._durations.keys()):
                durations = self._durations[model]
                total = sum(durations)
                count = len(durations)
                for b in buckets:
                    le_count = sum(1 for d in durations if d <= b)
                    lines.append(
                        f'ollama_request_duration_ms_bucket{{model="{model}",le="{b}"}} {le_count}'
                    )
                lines.append(
                    f'ollama_request_duration_ms_bucket{{model="{model}",le="+Inf"}} {count}'
                )
                lines.append(f'ollama_request_duration_ms_sum{{model="{model}"}} {total:.1f}')
                lines.append(f'ollama_request_duration_ms_count{{model="{model}"}} {count}')

        return "\n".join(lines) + "\n"

    def get_stats(self) -> dict[str, Any]:
        """Return a summary dict of requests, tokens, model breakdowns, and caller IPs."""
        with self._lock:
            total_requests = sum(self._requests.values())
            total_tokens = sum(self._tokens.values())
            models: dict[str, dict[str, int]] = {}

            for (model, token_type), count in self._tokens.items():
                if model not in models:
                    models[model] = {"prompt": 0, "completion": 0, "requests": 0}
                models[model][token_type] = count

            for (model, _, _), count in self._requests.items():
                if model not in models:
                    models[model] = {"prompt": 0, "completion": 0, "requests": 0}
                models[model]["requests"] += count

            callers: dict[str, int] = dict(self._callers)

            return {
                "total_requests": total_requests,
                "total_tokens": total_tokens,
                "models": models,
                "callers": callers,
            }


_collector = MetricsCollector()


def get_collector() -> MetricsCollector:
    """Return the process-global MetricsCollector singleton."""
    return _collector


def _check_token(handler: BaseHTTPRequestHandler, token: str) -> bool:
    """Return True if the request is authorized, False otherwise."""
    if not token:
        return True

    # Check query parameter
    parsed = urlparse(handler.path)
    params = parse_qs(parsed.query)
    if params.get("token", [None])[0] == token:
        return True

    # Check Authorization: Bearer header
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth[7:] == token:
        return True

    return False


class _MetricsHandler(BaseHTTPRequestHandler):
    collector: MetricsCollector
    metrics_token: str = ""

    def do_GET(self) -> None:  # noqa: N802
        if not _check_token(self, self.metrics_token):
            self.send_error(401, "Unauthorized")
            return

        path = self.path.split("?")[0]
        if path != "/metrics":
            self.send_error(404, "Not Found")
            return

        body = self.collector.format_prometheus().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        pass


def start_metrics_server(
    port: int,
    collector: MetricsCollector | None = None,
    bind: str = "0.0.0.0",
    metrics_token: str = "",
) -> HTTPServer:
    """Launch the Prometheus metrics HTTP server on a daemon thread."""
    handler = type(
        "MetricsHandler",
        (_MetricsHandler,),
        {"collector": collector or _collector, "metrics_token": metrics_token},
    )
    server = HTTPServer((bind, port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
