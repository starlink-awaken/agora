# Changelog

## [1.4.0] — 2026-05-20

### Added
- **gRPC handler**: `_call_grpc()` stub with proto/config guidance
- **REST handler enhancement**: PUT/DELETE/PATCH + auto-retry (GET/HEAD, max 2)
- **WebSocket handler**: `_call_ws()` stub for ws/wss endpoints
- **HTTP connection pool**: module-level httpx.AsyncClient singleton (`_get_client`)
- **Dashboard WebSocket**: `/ws` endpoint with real-time push (2s interval)
- **Service topology SVG**: Hub-Spoke visualization + protocol color coding
- **CLI register**: `--proto` (gRPC proto path) + `--rest-method` (REST method)

### Changed
- Router._dispatch: grpc/websocket/stdio call specific handlers
- Dashboard: WebSocket real-time updates with polling fallback
- Registry: grpc_health_check() stub for gRPC services

### Fixed
- Unknown protocol dispatch test (registry pre-validation bypass)
- atexit registration deduplication
- Connection pool cleanup via FastAPI shutdown

### Test Coverage
- **203 tests** (↑ from 84) — 119 new: _call_mcp SSRF/httpx/retry, _call_rest POST/retry/SSRF, pipeline run_stream/run_parallel, MCP proxy tools, _trace flush, _maybe_publish, close cleanup, get_percentiles

## [1.3.0] — 2026-05-20

### Added
- **Multi-protocol Support**: Service model now supports mcp/rest/grpc/stdio/websocket protocols (registry.py)
- **REST Protocol Handler**: `_call_rest()` in router.py — REST APIs can be routed via Agora
- **Protocol Config Extension**: `protocol_config` dict for custom headers/methods/paths per service
- **KNOWN_PROTOCOLS**: shared frozenset constant + `_parse_protocol_config`/`_parse_tags` utilities
- **MCP Proxy Tools**: 5 new tools — proxy_connect/call/status/add_service/remove_service (server/mcp.py)
- **Event Bus Tools**: publish_event/subscribe_event/get_event_log (3 tools)
- **Dashboard**: protocol selector + advanced config panel (collapsible) + auto-detect protocol type
- **Service Detail Modal**: click-to-expand with protocol info + config display
- **Dashboard Change Detection**: skip DOM rebuild when data unchanged (polling optimization)
- **Registry.clear_all()**: batch unregister with single disk write
- **ProxyManager.start()**: parallel `asyncio.gather` instead of serial connections
- **Agora Skill**: `/agora` skill registered in `~/.claude/skills/agora/`

### Changed
- **SSRF validation**: centralized in registry.register(); removed duplicate checks from server/mcp.py
- **Proxy persistence**: `_load_proxy_services`/`_save_proxy_service` now use shared `json_load`/`json_save`
- **Hot-path imports**: `httpx`/`time` promoted to module-level in router.py
- **`_dispatch`**: protocol detection from instance dict (no redundant registry lookup)
- **`_try_half_open`**: accepts Service object directly (no redundant name lookup)
- **`persistence.json_load`**: EAFP pattern (catch FileNotFoundError) instead of TOCTOU `exists()` check
- **Web EventBus**: module-level `_bus` singleton instead of per-request instantiation
- **API_REFERENCE.md**: full rewrite with 14 tools + protocol extension docs

### Fixed
- **Ruff**: 0 errors across all code + tests (linted E702 semicolons, I001 imports, E501 line length)
- **AGENTS.md**: outdated counts (9→14 MCP, 20→20+ CLI)
- **docs/index.md**: outdated feature counts
- **CAPABILITIES.md**: Agora section rewritten (7→14 tools, +Proxy/+Event/+Market rows)

### Test Coverage
- **84 tests** (↑ from 61) — 23 new: parse_tags/protocol_config/known_protocols/clear_all/protocol validation/rest dispatch/proxy manager

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

### Docs
- AGENTS.md: AI agent entry point
- USER_GUIDE.md: 10 user scenarios with code examples
- QUICKSTART.md: 5-minute getting started guide
- INSTALL.md: installation + Claude Code integration
- 6 demo scripts: fault-injection, mcp-integration, tenant, observability, alert, benchmark

### Tests
- 17 → 61 passed (registry 7, router 4, integration 6, event_bus 14, pipeline 9, discovery 4, market 5, E2E 9, circuit_breaker 3)

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
