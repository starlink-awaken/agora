# Agora Documentation

> API Gateway for AI Agents · v1.3.0

## Quick Links

- [Quickstart Guide](../QUICKSTART.md) — 5 minutes to a working hub
- [User Guide](USER_GUIDE.md) — 10 real-world scenarios
- [API Reference](API_REFERENCE.md) — CLI, MCP, REST endpoints
- [Installation](../INSTALL.md) — pip, Docker, Homebrew
- [Product Plan](../PRODUCT_PLAN.md) — roadmap and vision
- [Infrastructure Plan](../INFRA_PLAN.md) — reliability and operations
- [Release Guide](../RELEASE.md) — publishing to PyPI

## Architecture

Agora is a Hub-Spoke MCP service convergence hub. All services register with Agora; Agora routes calls, checks health, and orchestrates pipelines.

## Key Features

- **20+ CLI commands** — register (multi-protocol), discover, health, pipeline, event, market, tenant, instance
- **14 MCP tools** — 5 proxy + 3 registry + 3 route + 3 event bus
- **16 REST endpoints** — Web Dashboard + Prometheus /metrics/history + event-log/publish
- **Multi-protocol support** — MCP (full), REST/gRPC/WebSocket/stdio (reserved with extension points)
- **Circuit breaker** — CLOSED/OPEN/HALF_OPEN with gradual recovery + webhook alerts
- **Auto-discovery** — 4 strategies to find MCP services
- **MCP Tool Market** — 18 built-in services
- **Multi-tenant** — API token auth + rate limiting

## Demo

```bash
bash demos/demo-recording.sh
```
