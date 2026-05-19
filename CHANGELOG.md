# Changelog

## [1.2.0] — 2026-05-19

### Added
- **Event Bus**: publish/subscribe/log with pattern matching + JSON persistence (event_bus.py)
- **MCP Market**: 10 built-in services, search/list/install/publish (market.py)
- **Auto-Discovery**: 4-strategy engine with --watch mode (discovery.py)
- **Web Dashboard**: FastAPI + embedded HTML at localhost:7430 (web/app.py)
- **Streaming Pipeline**: run_stream() + run_parallel() with dependency grouping
- **Circuit Breaker**: CLOSED/OPEN/HALF_OPEN states with configurable thresholds
- **Call Trace**: trace_log.jsonl with atexit flush + P50/P90/P99 latency percentiles
- **Prometheus /metrics**: gauge + summary metrics endpoint
- **Multi-tenant**: API token auth + rate limiting (tenant.py)
- **Guided Setup**: `agora init` 4-step interactive wizard
- **agora config**: show paths, service count, health status
- **Shared Persistence**: json_load/json_save utility (persistence.py)
- **MCP Tools**: 7→9 (publish_event, subscribe_event, get_event_log)
- **CLI Commands**: 12→20 (init, config, discover, instance, tenant, market, event, web)
- **E2E Tests**: 9 cross-project integration tests

### Changed
- **Version**: 0.1.1 → 1.2.0 (Beta)
- **Python**: runtime discovery (shutil.which) replaces hard import deps
- **SSRF**: unified _is_safe_url in registry.py, removed duplicate in mcp.py
- **Circuit Breaker**: gradual failure decay instead of instant zero
- **Dashboard**: CORS restricted to localhost, API Key auth middleware
- **Prometheus**: gauges created at module level (no per-scrape allocation)
- **Persistence**: all modules use shared json_load/json_save
- **Error Handling**: friendly CLI messages replace raw tracebacks
- **router.py**: deque(maxlen=1000) replaces list reallocation, buffered trace writes

### Fixed
- Coupling matrix: ARCHITECTURE.md corrected (minerva→sophia is production import)
- Tenant typo: DEFUALT_TOKEN_ENV → DEFAULT_TOKEN_ENV
- Webhook SSRF: _is_safe_url check before HTTP POST
- Instance SSRF: URL validation before add
- Test isolation: temp storage paths to prevent persistence cross-contamination
- ontoderive test: absolute path for build_from_project

### Tests
- 17 → 58 passed (registry 7, router 4, integration 6, event_bus 14, pipeline 9, discovery 4, market 5, E2E 9)

## [0.1.1] — 2026-05-15

### Fixed
- SSRF: URL validation blocks private/internal IPs for health endpoints & routing
- DoS: health check rate limiting (10s cooldown, 10 max concurrent, 50 service limit)
- Error sanitization: generic messages (no internal tool names or paths)
- Port validation: enforce 0-65535 range

### Added
- SECURITY.md
- PyPI classifiers + project.urls + py.typed
- CI: pip-audit dependency vulnerability scan + mypy type checking
- `mask_error_details=True` on MCP server

## [0.1.0] — 2026-05-13

### Added
- ServiceRegistry with register/unregister/health_check_all/circuit_breaker
- Router with add_route/resolve/route (prefix + exact matching)
- 6 CLI commands (register/list/health/route/routes/mcp)
- 7 MCP tools for service governance
- 17 tests (registry 7 + router 4 + integration 6)
- Hub-Spoke topology convergence: N×(N-1) → N edges
- Graceful degradation on service failure
