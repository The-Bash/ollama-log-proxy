"""HTTP reverse proxy that forwards requests to Ollama and logs inference usage."""

from __future__ import annotations

import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ollama_log_proxy.backends import LogBackend
from ollama_log_proxy.metrics import MetricsCollector
from ollama_log_proxy.parser import (
    LogEntry,
    classify_request,
    extract_model_from_body,
    extract_usage_from_response,
    now_iso,
)

logger = logging.getLogger("ollama-log-proxy")

# Hop-by-hop headers that must not be forwarded between proxies (RFC 2616 sec 13.5.1)
_HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "proxy-authorization",
        "proxy-authenticate",
    }
)

_STREAM_CHUNK_SIZE = 8192


def _get_caller_ip(handler: BaseHTTPRequestHandler) -> str:
    """Extract the real client IP, preferring X-Forwarded-For."""
    forwarded = handler.headers.get("X-Forwarded-For")
    if forwarded:
        # Leftmost entry is the original client
        return forwarded.split(",")[0].strip()
    return handler.client_address[0]


def _make_handler(
    ollama_url: str,
    backend: LogBackend,
    collector: MetricsCollector | None,
    max_request_size: int = 100 * 1024 * 1024,
) -> type[BaseHTTPRequestHandler]:

    class ProxyHandler(BaseHTTPRequestHandler):
        """Request handler that proxies to Ollama and logs inference calls."""

        def _proxy(self) -> None:
            parsed = urlparse(self.path)
            endpoint = parsed.path
            request_type = classify_request(endpoint)
            target_url = f"{ollama_url}{self.path}"

            content_length = int(self.headers.get("Content-Length", 0))

            if content_length > max_request_size:
                self.send_error(413, "Payload Too Large")
                return

            body = self.rfile.read(content_length) if content_length > 0 else b""

            model = extract_model_from_body(body) if body else ""

            # Forward all headers except hop-by-hop
            headers: dict[str, str] = {}
            for key, value in self.headers.items():
                if key.lower() not in _HOP_BY_HOP:
                    headers[key] = value

            # Set X-Forwarded-For: preserve existing chain, append direct peer
            caller_ip = _get_caller_ip(self)
            existing_xff = self.headers.get("X-Forwarded-For", "")
            peer_ip = self.client_address[0]
            if existing_xff:
                headers["X-Forwarded-For"] = f"{existing_xff}, {peer_ip}"
            else:
                headers["X-Forwarded-For"] = peer_ip

            start = time.monotonic()
            try:
                req = Request(
                    target_url, data=body if body else None, headers=headers, method=self.command
                )
                response = urlopen(req, timeout=600)
                status_code = response.status
                response_headers = dict(response.getheaders())

                # Stream the response in chunks to avoid buffering large responses
                self.send_response(status_code)
                for key, value in response_headers.items():
                    if key.lower() not in _HOP_BY_HOP:
                        self.send_header(key, value)
                self.end_headers()

                chunks: list[bytes] = []
                while True:
                    chunk = response.read(_STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    if request_type == "inference":
                        chunks.append(chunk)

                response_body = b"".join(chunks) if request_type == "inference" else b""

            except HTTPError as e:
                status_code = e.code
                response_headers = dict(e.headers.items()) if e.headers else {}
                response_body = e.read()

                self.send_response(status_code)
                for key, value in response_headers.items():
                    if key.lower() not in _HOP_BY_HOP:
                        self.send_header(key, value)
                self.send_header("Content-Length", str(len(response_body)))
                self.end_headers()
                self.wfile.write(response_body)
            except (URLError, OSError) as e:
                self.send_error(502, f"Bad Gateway: {e}")
                return

            duration_ms = (time.monotonic() - start) * 1000

            if request_type == "inference":
                self._log_async(
                    endpoint, model, status_code, duration_ms, body, response_body, caller_ip
                )

        def _log_async(
            self,
            endpoint: str,
            model: str,
            status_code: int,
            duration_ms: float,
            request_body: bytes,
            response_body: bytes,
            caller_ip: str,
        ) -> None:
            def _do_log() -> None:
                prompt_tokens, completion_tokens, total_tokens = extract_usage_from_response(
                    response_body, endpoint
                )
                entry = LogEntry(
                    timestamp=now_iso(),
                    caller_ip=caller_ip,
                    model=model,
                    endpoint=endpoint,
                    request_type="inference",
                    status_code=status_code,
                    duration_ms=round(duration_ms, 2),
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                )
                try:
                    backend.log(entry)
                except Exception:
                    logger.exception("Failed to log entry")

                if collector:
                    collector.record_request(model, endpoint, str(status_code), caller_ip=caller_ip)
                    collector.record_tokens(model, prompt_tokens, completion_tokens)
                    collector.record_duration(model, duration_ms)

            thread = threading.Thread(target=_do_log, daemon=True)
            thread.start()

        def do_GET(self) -> None:  # noqa: N802
            self._proxy()

        def do_POST(self) -> None:  # noqa: N802
            self._proxy()

        def do_PUT(self) -> None:  # noqa: N802
            self._proxy()

        def do_DELETE(self) -> None:  # noqa: N802
            self._proxy()

        def do_HEAD(self) -> None:  # noqa: N802
            self._proxy()

        def log_message(self, format: str, *args: Any) -> None:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(format, *args)

    return ProxyHandler


class ProxyServer:
    """HTTP reverse proxy server that intercepts Ollama requests and logs inference usage.

    Wraps a stdlib HTTPServer with a custom handler that forwards all requests
    to the upstream Ollama instance, extracts token counts from inference
    responses, and writes log entries to the configured backend.
    """

    def __init__(
        self,
        port: int,
        ollama_url: str,
        backend: LogBackend,
        collector: MetricsCollector | None = None,
        bind: str = "0.0.0.0",
        max_request_size: int = 100 * 1024 * 1024,
    ) -> None:
        self.port = port
        self.ollama_url = ollama_url
        self.backend = backend
        handler = _make_handler(ollama_url, backend, collector, max_request_size)
        self._server = HTTPServer((bind, port), handler)

    def serve_forever(self) -> None:
        """Start accepting requests and block until shutdown() is called."""
        logger.info("Proxy listening on :%d -> %s", self.port, self.ollama_url)
        self._server.serve_forever()

    def shutdown(self) -> None:
        """Stop the server loop and close the logging backend."""
        self._server.shutdown()
        self.backend.close()
