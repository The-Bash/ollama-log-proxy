"""Tests for the proxy server functionality."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ollama_log_proxy.backends.stdout import StdoutBackend
from ollama_log_proxy.proxy import ProxyServer, _get_caller_ip


def _start_mock_ollama(port: int, handler_class=None) -> HTTPServer:
    """Start a mock Ollama server that echoes requests."""

    if handler_class is None:

        class MockHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > 0:
                    self.rfile.read(content_length)

                response = json.dumps(
                    {
                        "model": "llama3.2",
                        "response": "Test response",
                        "done": True,
                        "prompt_eval_count": 10,
                        "eval_count": 20,
                    }
                ).encode()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def do_GET(self):  # noqa: N802
                response = json.dumps({"status": "ok"}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response)))
                self.end_headers()
                self.wfile.write(response)

            def log_message(self, format, *args):
                pass

        handler_class = MockHandler

    server = HTTPServer(("127.0.0.1", port), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class TestProxyServer:
    def test_proxy_forwards_get(self):
        mock = _start_mock_ollama(18434)
        backend = StdoutBackend()
        proxy = ProxyServer(18435, "http://127.0.0.1:18434", backend, bind="127.0.0.1")
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18435/api/tags")
            resp = urlopen(req, timeout=5)
            data = json.loads(resp.read())
            assert data["status"] == "ok"
        finally:
            proxy.shutdown()
            mock.shutdown()

    def test_proxy_forwards_post_and_logs(self):
        mock = _start_mock_ollama(18436)
        backend = StdoutBackend()
        proxy = ProxyServer(18437, "http://127.0.0.1:18436", backend, bind="127.0.0.1")
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            body = json.dumps({"model": "llama3.2", "prompt": "hello"}).encode()
            req = Request(
                "http://127.0.0.1:18437/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            resp = urlopen(req, timeout=5)
            data = json.loads(resp.read())
            assert data["model"] == "llama3.2"

            # Wait for async logging
            time.sleep(0.5)
            entries = backend.query({})
            assert len(entries) == 1
            assert entries[0].model == "llama3.2"
            assert entries[0].prompt_tokens == 10
            assert entries[0].completion_tokens == 20
        finally:
            proxy.shutdown()
            mock.shutdown()

    def test_proxy_skips_poll_logging(self):
        mock = _start_mock_ollama(18438)
        backend = StdoutBackend()
        proxy = ProxyServer(18439, "http://127.0.0.1:18438", backend, bind="127.0.0.1")
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18439/api/tags")
            urlopen(req, timeout=5)
            time.sleep(0.3)

            entries = backend.query({})
            assert len(entries) == 0
        finally:
            proxy.shutdown()
            mock.shutdown()


class TestStreamingProxy:
    def test_chunked_streaming_response(self):
        """Verify the proxy streams chunked ndjson responses."""

        class StreamingHandler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > 0:
                    self.rfile.read(content_length)

                # Build multi-chunk ndjson response
                lines = []
                for i in range(5):
                    lines.append(
                        json.dumps({"model": "llama3.2", "response": f"tok{i}", "done": False})
                    )
                lines.append(
                    json.dumps(
                        {
                            "model": "llama3.2",
                            "response": "",
                            "done": True,
                            "prompt_eval_count": 12,
                            "eval_count": 28,
                        }
                    )
                )
                body = ("\n".join(lines) + "\n").encode()

                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, format, *args):
                pass

        mock = _start_mock_ollama(18440, StreamingHandler)
        backend = StdoutBackend()
        proxy = ProxyServer(18441, "http://127.0.0.1:18440", backend, bind="127.0.0.1")
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            body = json.dumps({"model": "llama3.2", "prompt": "hi"}).encode()
            req = Request(
                "http://127.0.0.1:18441/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            resp = urlopen(req, timeout=5)
            data = resp.read().decode()
            lines = [line for line in data.strip().split("\n") if line.strip()]
            assert len(lines) == 6

            time.sleep(0.5)
            entries = backend.query({})
            assert len(entries) == 1
            assert entries[0].prompt_tokens == 12
            assert entries[0].completion_tokens == 28
        finally:
            proxy.shutdown()
            mock.shutdown()


class TestXForwardedFor:
    def test_get_caller_ip_from_xff(self):
        """_get_caller_ip should prefer X-Forwarded-For over client_address."""

        class FakeHandler:
            headers = {"X-Forwarded-For": "203.0.113.50, 10.0.0.1"}
            client_address = ("10.0.0.1", 54321)

        ip = _get_caller_ip(FakeHandler())
        assert ip == "203.0.113.50"

    def test_get_caller_ip_fallback(self):
        """Fall back to client_address when no X-Forwarded-For."""

        class FakeHandler:
            headers = {}
            client_address = ("192.168.1.10", 54321)

        ip = _get_caller_ip(FakeHandler())
        assert ip == "192.168.1.10"

    def test_xff_forwarded_to_upstream(self):
        """Proxy should set X-Forwarded-For on outgoing requests."""
        received_headers = {}

        class HeaderCapture(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                received_headers["X-Forwarded-For"] = self.headers.get("X-Forwarded-For", "")
                resp = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, format, *args):
                pass

        mock = _start_mock_ollama(18442, HeaderCapture)
        backend = StdoutBackend()
        proxy = ProxyServer(18443, "http://127.0.0.1:18442", backend, bind="127.0.0.1")
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18443/api/tags")
            urlopen(req, timeout=5)
            assert received_headers.get("X-Forwarded-For") == "127.0.0.1"
        finally:
            proxy.shutdown()
            mock.shutdown()


class TestFullHeaderForwarding:
    def test_custom_headers_forwarded(self):
        """All non-hop-by-hop request headers should be forwarded."""
        received_headers = {}

        class HeaderCapture(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                received_headers["X-Custom-Header"] = self.headers.get("X-Custom-Header", "")
                received_headers["X-Request-Id"] = self.headers.get("X-Request-Id", "")
                resp = b'{"status":"ok"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.send_header("X-Response-Custom", "resp-value")
                self.end_headers()
                self.wfile.write(resp)

            def log_message(self, format, *args):
                pass

        mock = _start_mock_ollama(18444, HeaderCapture)
        backend = StdoutBackend()
        proxy = ProxyServer(18445, "http://127.0.0.1:18444", backend, bind="127.0.0.1")
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18445/api/tags")
            req.add_header("X-Custom-Header", "test-value")
            req.add_header("X-Request-Id", "abc-123")
            resp = urlopen(req, timeout=5)
            resp.read()

            assert received_headers["X-Custom-Header"] == "test-value"
            assert received_headers["X-Request-Id"] == "abc-123"
        finally:
            proxy.shutdown()
            mock.shutdown()


class TestRequestSizeLimit:
    def test_reject_oversized_request(self):
        """Requests exceeding max_request_size should be rejected with 413."""
        mock = _start_mock_ollama(18446)
        backend = StdoutBackend()
        # Set a tiny limit for testing
        proxy = ProxyServer(
            18447, "http://127.0.0.1:18446", backend, bind="127.0.0.1", max_request_size=100
        )
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            # Send a body larger than 100 bytes
            body = b"x" * 200
            req = Request(
                "http://127.0.0.1:18447/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            try:
                urlopen(req, timeout=5)
                assert False, "Should have raised HTTPError"
            except HTTPError as e:
                assert e.code == 413
        finally:
            proxy.shutdown()
            mock.shutdown()

    def test_allow_small_request(self):
        """Requests within max_request_size should be forwarded normally."""
        mock = _start_mock_ollama(18448)
        backend = StdoutBackend()
        proxy = ProxyServer(
            18449,
            "http://127.0.0.1:18448",
            backend,
            bind="127.0.0.1",
            max_request_size=10 * 1024,
        )
        thread = threading.Thread(target=proxy.serve_forever, daemon=True)
        thread.start()
        time.sleep(0.3)

        try:
            body = json.dumps({"model": "llama3.2", "prompt": "hi"}).encode()
            req = Request(
                "http://127.0.0.1:18449/api/generate",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            resp = urlopen(req, timeout=5)
            assert resp.status == 200
        finally:
            proxy.shutdown()
            mock.shutdown()
