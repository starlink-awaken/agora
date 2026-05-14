# Changelog

## [0.1.0] — 2026-05-13

### Added
- ServiceRegistry with register/unregister/health_check_all/circuit_breaker
- Router with add_route/resolve/route (prefix + exact matching)
- 6 CLI commands (register/list/health/route/routes/mcp)
- 7 MCP tools for service governance
- 17 tests (registry 7 + router 4 + integration 6)
- Hub-Spoke topology convergence: N×(N-1) → N edges
- Graceful degradation on service failure
