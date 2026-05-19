# Agora Documentation

> API Gateway for AI Agents · v1.2.0

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

- **20 CLI commands** — register, discover, health, pipeline, event, market
- **9 MCP tools** — AI agents can call services directly  
- **15 REST endpoints** — Web Dashboard + Prometheus metrics
- **Circuit breaker** — CLOSED/OPEN/HALF_OPEN with gradual recovery
- **Auto-discovery** — 4 strategies to find MCP services
- **MCP Tool Market** — 10+ built-in services
- **Multi-tenant** — API token auth + rate limiting

## Demo

```bash
bash demos/demo-recording.sh
```
