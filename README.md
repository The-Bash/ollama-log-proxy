# ollama-log-proxy

[![CI](https://github.com/The-Bash/ollama-log-proxy/actions/workflows/ci.yml/badge.svg)](https://github.com/The-Bash/ollama-log-proxy/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

HTTP reverse proxy for [Ollama](https://ollama.com) that logs every inference call to a configurable backend. Zero-config start with SQLite. Built-in dashboard. Prometheus metrics.

## Architecture

```
                        ┌──────────────────────────┐
  Clients               │  ollama-log-proxy         │         Ollama
  (curl, apps,   ──────>│  :11433                   │────────> :11434
   libraries)           │                           │
                        │  ┌─────────────────────┐  │
                        │  │ Streaming Proxy      │  │
                        │  │ (chunked forwarding) │  │
                        │  └────────┬────────────┘  │
                        │           │               │
                        │  ┌────────▼────────────┐  │
                        │  │ Request Parser       │  │
                        │  │ Token Counter        │  │
                        │  │ Usage Logger         │  │
                        │  └────────┬────────────┘  │
                        │           │               │
                        │  ┌────────▼────────────┐  │
                        │  │ Log Backend          │  │
                        │  │ (sqlite/pg/jsonl)    │  │
                        │  └─────────────────────┘  │
                        │                           │
                        │  Dashboard :8080          │
                        │  Metrics   :9090          │
                        └──────────────────────────┘
```

Response data is streamed chunk-by-chunk from Ollama to the client in real time. Token usage is extracted from the accumulated buffer after the response completes, so clients see output immediately during long generations.

## Features

- **Transparent streaming proxy** -- forwards response chunks in real time, never buffers entire responses
- **Token counting** -- extracts prompt and completion tokens from all inference endpoints
- **Streaming support** -- correctly parses ndjson streaming responses
- **Smart filtering** -- only logs inference calls, ignores health checks and model listing
- **Full header forwarding** -- forwards all request/response headers except hop-by-hop
- **Real client IP** -- reads X-Forwarded-For for correct IPs behind reverse proxies
- **4 backends** -- SQLite (default), PostgreSQL, JSONL, stdout
- **Built-in dashboard** -- vanilla HTML + Chart.js, no npm required
- **Prometheus metrics** -- request counts, token totals, duration histograms, caller tracking
- **Grafana dashboard** -- pre-built JSON dashboard included
- **Docker ready** -- multi-stage build, non-root user, compose file included
- **12-factor config** -- all settings via CLI args or environment variables
- **Extensible** -- `LogBackend` is a Protocol, bring your own implementation

## Install

```bash
pip install git+https://github.com/The-Bash/ollama-log-proxy.git
```

With PostgreSQL support:

```bash
pip install "ollama-log-proxy[postgres] @ git+https://github.com/The-Bash/ollama-log-proxy.git"
```

Or clone and install locally:

```bash
git clone https://github.com/The-Bash/ollama-log-proxy.git
cd ollama-log-proxy
pip install .
```

## Quick Start

### 1. Zero-config (SQLite)

```bash
ollama-log-proxy
```

Point your apps at `http://localhost:11433` instead of `http://localhost:11434`. Logs are written to `./ollama-logs.db`.

### 2. With Dashboard and Metrics

```bash
ollama-log-proxy --dashboard 8080 --metrics-port 9090
```

Open `http://localhost:8080` for the dashboard. Prometheus scrapes from `http://localhost:9090/metrics`.

### 3. Docker

```bash
git clone https://github.com/The-Bash/ollama-log-proxy.git
cd ollama-log-proxy
docker build -t ollama-log-proxy .
docker run -p 11433:11433 -p 8080:8080 -p 9090:9090 ollama-log-proxy \
  --ollama-url http://host.docker.internal:11434 \
  --dashboard 8080 --metrics-port 9090
```

Or use the included Compose file for a full stack (proxy + Ollama + Grafana):

```bash
docker compose up -d
```

This starts Ollama, the proxy, and Grafana:

| Service | Port | Description |
|---------|------|-------------|
| Proxy | 11433 | Point your apps here |
| Dashboard | 8080 | Built-in usage dashboard |
| Metrics | 9090 | Prometheus endpoint |
| Grafana | 3000 | Pre-configured dashboards |
| Ollama | 11434 | Upstream Ollama instance |

## Usage

### CLI Reference

```
ollama-log-proxy [OPTIONS]
ollama-log-proxy report [OPTIONS]
```

**Proxy options:**

| Flag | Env Var | Default | Description |
|------|---------|---------|-------------|
| `--port` | `OLP_PORT` | `11433` | Proxy listen port |
| `--ollama-url` | `OLP_OLLAMA_URL` | `http://localhost:11434` | Upstream Ollama URL |
| `--backend` | `OLP_BACKEND` | `sqlite` | Backend: sqlite, postgres, jsonl, stdout |
| `--db-path` | `OLP_DB_PATH` | `./ollama-logs.db` | SQLite database path |
| `--dsn` | `OLP_DSN` | -- | PostgreSQL connection string |
| `--log-file` | `OLP_LOG_FILE` | `./ollama.jsonl` | JSONL output file |
| `--dashboard` | `OLP_DASHBOARD_PORT` | -- | Dashboard server port |
| `--metrics-port` | `OLP_METRICS_PORT` | -- | Prometheus metrics port |
| `--bind` | `OLP_BIND` | `0.0.0.0` | Bind address for all servers |
| `--dashboard-token` | `OLP_DASHBOARD_TOKEN` | -- | Token to protect dashboard |
| `--metrics-token` | `OLP_METRICS_TOKEN` | -- | Token to protect metrics endpoint |
| `--max-request-size` | `OLP_MAX_REQUEST_SIZE` | `104857600` | Max request body size (bytes) |
| `--log-level` | -- | `INFO` | Logging verbosity |

**Report options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--last` | `30d` | Time range (e.g. `7d`, `24h`) |
| `--format` | `table` | Output format: table, json, csv |

### Authentication

The dashboard and metrics endpoints can be protected with tokens:

```bash
ollama-log-proxy \
  --dashboard 8080 --dashboard-token my-dashboard-secret \
  --metrics-port 9090 --metrics-token my-metrics-secret
```

Access the dashboard with a query parameter:

```
http://localhost:8080/?token=my-dashboard-secret
```

Or use the `Authorization` header:

```bash
curl -H "Authorization: Bearer my-metrics-secret" http://localhost:9090/metrics
```

When no token is set, the endpoints are open (backward compatible).

### Security Considerations

**Bind address**: By default the proxy binds to `0.0.0.0` (all interfaces). For local-only access, use `--bind 127.0.0.1`.

**Request size limits**: The `--max-request-size` flag (default 100MB) rejects oversized requests with HTTP 413. This prevents memory exhaustion from malicious or accidental large payloads.

**Authentication**: Use `--dashboard-token` and `--metrics-token` in production to prevent unauthorized access to usage data. These tokens can also be set via environment variables `OLP_DASHBOARD_TOKEN` and `OLP_METRICS_TOKEN`.

**Reverse proxy**: When running behind nginx or Docker, the proxy reads `X-Forwarded-For` to log the real client IP instead of the proxy container's IP.

### Sample Log Entry

```json
{
  "timestamp": "2024-12-01T10:30:00.123456+00:00",
  "caller_ip": "192.168.1.100",
  "model": "llama3.2",
  "endpoint": "/api/chat",
  "request_type": "inference",
  "status_code": 200,
  "duration_ms": 1523.45,
  "prompt_tokens": 156,
  "completion_tokens": 89,
  "total_tokens": 245,
  "metadata": {}
}
```

### Generate a Report

```bash
# Table format (default)
ollama-log-proxy report --last 7d

# JSON output
ollama-log-proxy report --last 24h --format json

# CSV for spreadsheets
ollama-log-proxy report --last 30d --format csv > usage.csv
```

## Backend Comparison

| Feature | SQLite | PostgreSQL | JSONL | stdout |
|---------|--------|------------|-------|--------|
| Zero-config | Yes | No | Yes | Yes |
| Queryable | Yes | Yes | Yes | In-memory only |
| Concurrent writes | WAL mode | Native | File lock | N/A |
| Report support | Yes | Yes | Yes | Session only |
| Production ready | Single node | Multi node | Append only | Dev only |
| Dependencies | None | psycopg2 | None | None |
| Endpoint filter | Yes | Yes | No | No |

## Prometheus Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `ollama_requests_total` | counter | model, endpoint, status | Total inference requests |
| `ollama_tokens_total` | counter | model, type | Total tokens (prompt/completion) |
| `ollama_request_duration_ms` | histogram | model | Request duration distribution |

## Endpoints Tracked

The proxy classifies requests into three categories:

- **Inference** (logged): `/api/generate`, `/api/chat`, `/api/embeddings`, `/api/embed`
- **Poll** (skipped): `/api/tags`, `/api/ps`, `/api/version`, `/api/show`
- **Other** (skipped): `/api/pull`, `/api/push`, health checks

## Custom Backend

Implement the `LogBackend` protocol to add your own storage:

```python
from ollama_log_proxy.parser import LogEntry

class MyBackend:
    def log(self, entry: LogEntry) -> None:
        # Store the entry
        ...

    def query(self, filters: dict) -> list[LogEntry]:
        # Return matching entries
        ...

    def close(self) -> None:
        # Clean up resources
        ...
```

## Development

```bash
git clone https://github.com/The-Bash/ollama-log-proxy.git
cd ollama-log-proxy
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/ tests/
```

## License

[MIT](LICENSE)
