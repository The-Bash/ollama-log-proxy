# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-07

### Added

- Streaming response forwarding: chunks are sent to clients in real time instead of buffering the entire response in memory
- X-Forwarded-For support for correct client IP detection behind reverse proxies and Docker
- Full header forwarding: all request and response headers are forwarded except hop-by-hop headers (RFC 2616)
- Caller IP tracking in MetricsCollector, populated in get_stats()
- PostgreSQL backend endpoint filter support to match SQLite's query capabilities
- `--dashboard-token` and `--metrics-token` CLI flags for optional authentication on dashboard and metrics endpoints
- `--max-request-size` CLI flag (default 100MB) to reject oversized request bodies with HTTP 413
- `--bind` CLI flag to configure the bind address for all servers (proxy, dashboard, metrics)
- Environment variables: OLP_BIND, OLP_DASHBOARD_TOKEN, OLP_METRICS_TOKEN, OLP_MAX_REQUEST_SIZE
- Tests for streaming proxy, X-Forwarded-For, header forwarding, callers tracking, Postgres endpoint filter, dashboard auth, request size limits, and dashboard server

### Fixed

- Callers dict in MetricsCollector.get_stats() was always empty; now tracks per-IP request counts
- PostgreSQL backend query() lacked endpoint filter, causing inconsistency with SQLite backend
- Only 4 headers were forwarded (Content-Type, Authorization, Accept, User-Agent); now all non-hop-by-hop headers are forwarded

### Changed

- Proxy response forwarding switched from full-buffer to chunked streaming (8192-byte chunks)
- Caller IP extraction now prefers X-Forwarded-For header over direct TCP peer address
- Dashboard path matching strips query parameters before comparison (needed for token auth)

## [0.1.0] - 2026-04-01

### Added

- HTTP reverse proxy for Ollama with transparent request forwarding
- Token counting for all inference endpoints (generate, chat, embeddings)
- Streaming ndjson response parsing
- SQLite backend with WAL mode (default, zero-config)
- PostgreSQL backend for multi-node deployments
- JSONL file backend for simple append-only logging
- Stdout backend for development and debugging
- Built-in web dashboard with Chart.js visualizations
- Prometheus metrics endpoint with request counters, token counters, and duration histograms
- Grafana dashboard JSON for pre-configured monitoring
- CLI with argparse for all configuration options
- Usage report generation in table, JSON, and CSV formats
- Docker multi-stage build with non-root user
- Docker Compose stack with Ollama, proxy, and Grafana
- 12-factor configuration via CLI args and environment variables
- Smart request classification (inference, poll, other)
- Async logging to avoid adding latency to proxied requests
- LogBackend Protocol for extensible backend implementations

[0.2.0]: https://github.com/The-Bash/ollama-log-proxy/releases/tag/v0.2.0
[0.1.0]: https://github.com/The-Bash/ollama-log-proxy/releases/tag/v0.1.0
