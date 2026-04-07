"""Tests for the dashboard server and authentication."""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ollama_log_proxy.backends.stdout import StdoutBackend
from ollama_log_proxy.dashboard.server import start_dashboard
from ollama_log_proxy.metrics import MetricsCollector, start_metrics_server


class TestDashboardServer:
    def test_serves_stats_api(self):
        collector = MetricsCollector()
        collector.record_request("llama3.2", "/api/chat", "200", caller_ip="127.0.0.1")
        collector.record_tokens("llama3.2", 100, 200)
        backend = StdoutBackend()

        server = start_dashboard(18460, backend, collector, bind="127.0.0.1")
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18460/api/stats")
            resp = urlopen(req, timeout=5)
            data = json.loads(resp.read())
            assert data["total_requests"] == 1
            assert data["total_tokens"] == 300
            assert "llama3.2" in data["models"]
        finally:
            server.shutdown()

    def test_serves_index_html(self):
        collector = MetricsCollector()
        backend = StdoutBackend()
        server = start_dashboard(18461, backend, collector, bind="127.0.0.1")
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18461/")
            resp = urlopen(req, timeout=5)
            assert resp.status == 200
            content_type = resp.headers.get("Content-Type", "")
            assert "text/html" in content_type
        finally:
            server.shutdown()

    def test_404_for_unknown_path(self):
        collector = MetricsCollector()
        backend = StdoutBackend()
        server = start_dashboard(18462, backend, collector, bind="127.0.0.1")
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18462/unknown")
            try:
                urlopen(req, timeout=5)
                assert False, "Should have raised HTTPError"
            except HTTPError as e:
                assert e.code == 404
        finally:
            server.shutdown()


class TestDashboardTokenAuth:
    def test_open_when_no_token_set(self):
        collector = MetricsCollector()
        backend = StdoutBackend()
        server = start_dashboard(18463, backend, collector, bind="127.0.0.1", dashboard_token="")
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18463/api/stats")
            resp = urlopen(req, timeout=5)
            assert resp.status == 200
        finally:
            server.shutdown()

    def test_reject_without_token(self):
        collector = MetricsCollector()
        backend = StdoutBackend()
        server = start_dashboard(
            18464, backend, collector, bind="127.0.0.1", dashboard_token="secret123"
        )
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18464/api/stats")
            try:
                urlopen(req, timeout=5)
                assert False, "Should have raised HTTPError"
            except HTTPError as e:
                assert e.code == 401
        finally:
            server.shutdown()

    def test_accept_query_param_token(self):
        collector = MetricsCollector()
        backend = StdoutBackend()
        server = start_dashboard(
            18465, backend, collector, bind="127.0.0.1", dashboard_token="secret123"
        )
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18465/api/stats?token=secret123")
            resp = urlopen(req, timeout=5)
            assert resp.status == 200
        finally:
            server.shutdown()

    def test_accept_bearer_token(self):
        collector = MetricsCollector()
        backend = StdoutBackend()
        server = start_dashboard(
            18466, backend, collector, bind="127.0.0.1", dashboard_token="secret123"
        )
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18466/api/stats")
            req.add_header("Authorization", "Bearer secret123")
            resp = urlopen(req, timeout=5)
            assert resp.status == 200
        finally:
            server.shutdown()


class TestMetricsTokenAuth:
    def test_reject_without_token(self):
        collector = MetricsCollector()
        server = start_metrics_server(
            18467, collector, bind="127.0.0.1", metrics_token="metricskey"
        )
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18467/metrics")
            try:
                urlopen(req, timeout=5)
                assert False, "Should have raised HTTPError"
            except HTTPError as e:
                assert e.code == 401
        finally:
            server.shutdown()

    def test_accept_with_bearer(self):
        collector = MetricsCollector()
        server = start_metrics_server(
            18468, collector, bind="127.0.0.1", metrics_token="metricskey"
        )
        time.sleep(0.3)

        try:
            req = Request("http://127.0.0.1:18468/metrics")
            req.add_header("Authorization", "Bearer metricskey")
            resp = urlopen(req, timeout=5)
            assert resp.status == 200
        finally:
            server.shutdown()
