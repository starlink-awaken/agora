# Changelog

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
