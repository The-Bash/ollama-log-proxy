"""Tests for the response parser and request classifier."""

from __future__ import annotations

import json

from ollama_log_proxy.parser import (
    classify_request,
    extract_model_from_body,
    extract_usage_from_response,
)


class TestClassifyRequest:
    def test_inference_endpoints(self):
        assert classify_request("/api/generate") == "inference"
        assert classify_request("/api/chat") == "inference"
        assert classify_request("/api/embeddings") == "inference"
        assert classify_request("/api/embed") == "inference"

    def test_poll_endpoints(self):
        assert classify_request("/api/tags") == "poll"
        assert classify_request("/api/ps") == "poll"
        assert classify_request("/api/version") == "poll"
        assert classify_request("/api/show") == "poll"

    def test_other_endpoints(self):
        assert classify_request("/api/pull") == "other"
        assert classify_request("/api/push") == "other"
        assert classify_request("/") == "other"
        assert classify_request("/health") == "other"


class TestExtractModel:
    def test_extracts_model(self):
        body = json.dumps({"model": "llama3.2", "prompt": "hello"}).encode()
        assert extract_model_from_body(body) == "llama3.2"

    def test_missing_model(self):
        body = json.dumps({"prompt": "hello"}).encode()
        assert extract_model_from_body(body) == ""

    def test_empty_body(self):
        assert extract_model_from_body(b"") == ""

    def test_invalid_json(self):
        assert extract_model_from_body(b"not json") == ""


class TestExtractUsage:
    def test_generate_response(self, generate_response_bytes):
        prompt, completion, total = extract_usage_from_response(
            generate_response_bytes, "/api/generate"
        )
        assert prompt == 26
        assert completion == 42
        assert total == 68

    def test_chat_response(self, chat_response_bytes):
        prompt, completion, total = extract_usage_from_response(chat_response_bytes, "/api/chat")
        assert prompt == 18
        assert completion == 35
        assert total == 53

    def test_streaming_response(self, streaming_response_bytes):
        prompt, completion, total = extract_usage_from_response(
            streaming_response_bytes, "/api/chat"
        )
        assert prompt == 12
        assert completion == 28
        assert total == 40

    def test_embeddings_response(self, embeddings_response_bytes):
        prompt, completion, total = extract_usage_from_response(
            embeddings_response_bytes, "/api/embeddings"
        )
        assert prompt == 8
        assert completion == 0
        assert total == 8

    def test_empty_response(self):
        prompt, completion, total = extract_usage_from_response(b"", "/api/chat")
        assert prompt == 0
        assert completion == 0
        assert total == 0

    def test_invalid_json_lines(self):
        data = b"not json\nalso not json\n"
        prompt, completion, total = extract_usage_from_response(data, "/api/chat")
        assert prompt == 0
        assert completion == 0
        assert total == 0

    def test_usage_field_override(self):
        data = json.dumps(
            {
                "prompt_eval_count": 10,
                "eval_count": 20,
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 25,
                    "total_tokens": 40,
                },
            }
        ).encode()
        prompt, completion, total = extract_usage_from_response(data, "/api/chat")
        assert prompt == 15
        assert completion == 25
        assert total == 40
