"""Tests for metrics collection and exposition."""

from __future__ import annotations

from ollama_log_proxy.metrics import MetricsCollector


class TestMetricsCollector:
    def test_record_request(self):
        collector = MetricsCollector()
        collector.record_request("llama3.2", "/api/chat", "200")
        collector.record_request("llama3.2", "/api/chat", "200")
        collector.record_request("mistral", "/api/generate", "200")

        output = collector.format_prometheus()
        assert (
            'ollama_requests_total{model="llama3.2",endpoint="/api/chat",status="200"} 2' in output
        )
        assert (
            'ollama_requests_total{model="mistral",endpoint="/api/generate",status="200"} 1'
            in output
        )

    def test_record_tokens(self):
        collector = MetricsCollector()
        collector.record_tokens("llama3.2", 100, 200)
        collector.record_tokens("llama3.2", 50, 75)

        output = collector.format_prometheus()
        assert 'ollama_tokens_total{model="llama3.2",type="prompt"} 150' in output
        assert 'ollama_tokens_total{model="llama3.2",type="completion"} 275' in output

    def test_record_duration(self):
        collector = MetricsCollector()
        collector.record_duration("llama3.2", 100.0)
        collector.record_duration("llama3.2", 500.0)

        output = collector.format_prometheus()
        assert 'ollama_request_duration_ms_count{model="llama3.2"} 2' in output
        assert 'ollama_request_duration_ms_sum{model="llama3.2"} 600.0' in output

    def test_histogram_buckets(self):
        collector = MetricsCollector()
        collector.record_duration("llama3.2", 5.0)
        collector.record_duration("llama3.2", 75.0)
        collector.record_duration("llama3.2", 5000.0)

        output = collector.format_prometheus()
        assert 'ollama_request_duration_ms_bucket{model="llama3.2",le="10"} 1' in output
        assert 'ollama_request_duration_ms_bucket{model="llama3.2",le="100"} 2' in output
        assert 'ollama_request_duration_ms_bucket{model="llama3.2",le="+Inf"} 3' in output

    def test_get_stats(self):
        collector = MetricsCollector()
        collector.record_request("llama3.2", "/api/chat", "200")
        collector.record_tokens("llama3.2", 100, 200)

        stats = collector.get_stats()
        assert stats["total_requests"] == 1
        assert stats["total_tokens"] == 300
        assert "llama3.2" in stats["models"]

    def test_empty_stats(self):
        collector = MetricsCollector()
        stats = collector.get_stats()
        assert stats["total_requests"] == 0
        assert stats["total_tokens"] == 0
        assert stats["models"] == {}

    def test_prometheus_format_headers(self):
        collector = MetricsCollector()
        output = collector.format_prometheus()
        assert "# HELP ollama_requests_total" in output
        assert "# TYPE ollama_requests_total counter" in output
        assert "# HELP ollama_tokens_total" in output
        assert "# TYPE ollama_tokens_total counter" in output


class TestCallersTracking:
    def test_callers_populated_in_stats(self):
        collector = MetricsCollector()
        collector.record_request("llama3.2", "/api/chat", "200", caller_ip="192.168.1.10")
        collector.record_request("llama3.2", "/api/chat", "200", caller_ip="192.168.1.10")
        collector.record_request("mistral", "/api/generate", "200", caller_ip="10.0.0.1")

        stats = collector.get_stats()
        assert stats["callers"] == {"192.168.1.10": 2, "10.0.0.1": 1}

    def test_callers_empty_when_no_ip(self):
        collector = MetricsCollector()
        collector.record_request("llama3.2", "/api/chat", "200")
        stats = collector.get_stats()
        assert stats["callers"] == {}

    def test_callers_across_models(self):
        collector = MetricsCollector()
        collector.record_request("llama3.2", "/api/chat", "200", caller_ip="1.2.3.4")
        collector.record_request("mistral", "/api/chat", "200", caller_ip="1.2.3.4")
        stats = collector.get_stats()
        assert stats["callers"]["1.2.3.4"] == 2
