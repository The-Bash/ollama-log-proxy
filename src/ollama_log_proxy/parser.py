"""Parse Ollama API responses for token usage and model information."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

INFERENCE_ENDPOINTS = {"/api/generate", "/api/chat", "/api/embeddings", "/api/embed"}
POLL_ENDPOINTS = {"/api/tags", "/api/ps", "/api/version", "/api/show"}


@dataclass
class LogEntry:
    """Single inference log record with timing and token counts."""

    timestamp: str
    caller_ip: str
    model: str
    endpoint: str
    request_type: str
    status_code: int
    duration_ms: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entry to a plain dict for JSON encoding."""
        return {
            "timestamp": self.timestamp,
            "caller_ip": self.caller_ip,
            "model": self.model,
            "endpoint": self.endpoint,
            "request_type": self.request_type,
            "status_code": self.status_code,
            "duration_ms": self.duration_ms,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "metadata": self.metadata,
        }


def classify_request(endpoint: str) -> str:
    """Classify an Ollama API endpoint as 'inference', 'poll', or 'other'."""
    if endpoint in INFERENCE_ENDPOINTS:
        return "inference"
    if endpoint in POLL_ENDPOINTS:
        return "poll"
    return "other"


def extract_model_from_body(body: bytes) -> str:
    """Return the 'model' field from a JSON request body, or empty string on failure."""
    if not body:
        return ""
    try:
        data = json.loads(body)
        return data.get("model", "")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return ""


def _extract_from_obj(
    obj: dict,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> tuple[int, int, int]:
    if "prompt_eval_count" in obj:
        prompt_tokens = obj.get("prompt_eval_count", 0) or 0
    if "eval_count" in obj:
        completion_tokens = obj.get("eval_count", 0) or 0

    if "usage" in obj:
        usage = obj["usage"]
        prompt_tokens = usage.get("prompt_tokens", prompt_tokens) or prompt_tokens
        completion_tokens = usage.get("completion_tokens", completion_tokens) or completion_tokens
        total_tokens = usage.get("total_tokens", 0) or 0

    return prompt_tokens, completion_tokens, total_tokens


def extract_usage_from_response(response_bytes: bytes, endpoint: str) -> tuple[int, int, int]:
    """Extract (prompt, completion, total) token counts from an Ollama response.

    Handles both single JSON objects and streaming ndjson responses.
    """
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    text = response_bytes.decode("utf-8", errors="replace").strip()
    if not text:
        return 0, 0, 0

    # Try parsing as a single JSON object first (non-streaming responses)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            prompt_tokens, completion_tokens, total_tokens = _extract_from_obj(
                obj, prompt_tokens, completion_tokens, total_tokens
            )
            if not total_tokens:
                total_tokens = prompt_tokens + completion_tokens
            return prompt_tokens, completion_tokens, total_tokens
    except json.JSONDecodeError:
        pass

    # Fall back to line-by-line parsing for ndjson streaming responses
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        if isinstance(obj, dict):
            prompt_tokens, completion_tokens, total_tokens = _extract_from_obj(
                obj, prompt_tokens, completion_tokens, total_tokens
            )

    if not total_tokens:
        total_tokens = prompt_tokens + completion_tokens

    return prompt_tokens, completion_tokens, total_tokens


def now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()
