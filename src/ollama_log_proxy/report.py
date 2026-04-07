"""Generate usage reports from logged data."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ollama_log_proxy.backends import LogBackend


def parse_duration(duration_str: str) -> timedelta:
    """Parse a human-friendly duration string like '30d', '24h', '7d'."""
    if not duration_str or len(duration_str) < 2:
        raise ValueError("Duration must be a number followed by d(ays), h(ours), or m(inutes).")
    unit = duration_str[-1].lower()
    try:
        value = int(duration_str[:-1])
    except ValueError:
        raise ValueError(
            f"Invalid duration: {duration_str!r}. Use format like '30d', '24h', '10m'."
        ) from None
    if unit == "d":
        return timedelta(days=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "m":
        return timedelta(minutes=value)
    raise ValueError(f"Unknown duration unit: {unit}. Use d(ays), h(ours), or m(inutes).")


def generate_report(
    backend: LogBackend,
    last: str = "30d",
    output_format: str = "table",
) -> str:
    """Query the backend and return a formatted usage report (table, JSON, or CSV)."""
    delta = parse_duration(last)
    since = (datetime.now(timezone.utc) - delta).isoformat()
    entries = backend.query({"since": since})

    if not entries:
        return "No inference logs found in the specified time range."

    models: dict[str, dict[str, int | float]] = {}
    total_requests = 0
    total_prompt = 0
    total_completion = 0
    total_tokens = 0

    for entry in entries:
        model = entry.model
        if model not in models:
            models[model] = {
                "requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "avg_duration_ms": 0.0,
                "total_duration_ms": 0.0,
            }
        m = models[model]
        m["requests"] = int(m["requests"]) + 1
        m["prompt_tokens"] = int(m["prompt_tokens"]) + entry.prompt_tokens
        m["completion_tokens"] = int(m["completion_tokens"]) + entry.completion_tokens
        m["total_tokens"] = int(m["total_tokens"]) + entry.total_tokens
        m["total_duration_ms"] = float(m["total_duration_ms"]) + entry.duration_ms

        total_requests += 1
        total_prompt += entry.prompt_tokens
        total_completion += entry.completion_tokens
        total_tokens += entry.total_tokens

    for m in models.values():
        req = int(m["requests"])
        if req > 0:
            m["avg_duration_ms"] = round(float(m["total_duration_ms"]) / req, 1)

    if output_format == "json":
        return json.dumps(
            {
                "period": last,
                "total_requests": total_requests,
                "total_prompt_tokens": total_prompt,
                "total_completion_tokens": total_completion,
                "total_tokens": total_tokens,
                "models": models,
            },
            indent=2,
        )

    if output_format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "model",
                "requests",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "avg_duration_ms",
            ]
        )
        for name, m in sorted(models.items()):
            writer.writerow(
                [
                    name,
                    m["requests"],
                    m["prompt_tokens"],
                    m["completion_tokens"],
                    m["total_tokens"],
                    m["avg_duration_ms"],
                ]
            )
        return buf.getvalue()

    # Table format
    lines = [
        f"Ollama Usage Report (last {last})",
        "=" * 70,
        "",
        f"Total Requests:         {total_requests}",
        f"Total Prompt Tokens:    {total_prompt}",
        f"Total Completion Tokens: {total_completion}",
        f"Total Tokens:           {total_tokens}",
        "",
        f"{'Model':<30} {'Requests':>10} {'Prompt':>10} {'Completion':>10} {'Avg ms':>10}",
        "-" * 70,
    ]
    for name, m in sorted(models.items()):
        lines.append(
            f"{name:<30} {m['requests']:>10} {m['prompt_tokens']:>10} "
            f"{m['completion_tokens']:>10} {m['avg_duration_ms']:>10}"
        )
    return "\n".join(lines)
