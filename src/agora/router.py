"""Request Router — routes incoming calls to the correct service.

Phase 3: Load balancing — supports multiple instances per service
with round-robin routing strategy.
"""

from __future__ import annotations

import structlog

from agora.registry import ServiceRegistry, _is_safe_url

logger = structlog.get_logger(__name__)


class Router:
    """Routes MCP tool calls to the appropriate registered service.

    Supports:
    - Exact and prefix-based route resolution
    - Circuit breaker awareness (skips OPEN services)
    - Load balancing with round-robin across service instances
    """

    def __init__(self, registry: ServiceRegistry, strategy: str = "round-robin"):
        self.registry = registry
        self._routes: dict[str, str] = {}  # tool_name → service_name
        self._strategy = strategy
        self._rr_index: dict[str, int] = {}  # service_name → next instance index

    def add_route(self, tool_name: str, service_name: str):
        """Register a tool → service mapping."""
        self._routes[tool_name] = service_name

    def resolve(self, tool_name: str) -> str | None:
        """Find which service handles a tool. Supports prefix matching."""
        if tool_name in self._routes:
            return self._routes[tool_name]
        # Prefix match: "minerva.research_now" → try "minerva" prefix
        parts = tool_name.split(".", 1)
        if parts[0] in self._routes:
            return self._routes[parts[0]]
        return None

    def _next_instance(self, service_name: str) -> dict | None:
        """Get the next available instance using current strategy (round-robin).

        Skips services in OPEN circuit state.
        """
        svc = self.registry.get(service_name)
        if not svc:
            return None
        if not svc.is_available:
            return None

        result = {  # single instance mode
            "mcp_endpoint": svc.mcp_endpoint,
            "health_endpoint": svc.health_endpoint,
            "port": svc.port,
        }

        # Check if this service has multiple instances
        instances = svc.instances
        if instances:
            idx = self._rr_index.get(service_name, 0)
            instance = instances[idx % len(instances)]
            self._rr_index[service_name] = idx + 1
            result = instance

        return result

    def _add_instance(self, service_name: str, mcp_endpoint: str,
                      health_endpoint: str = "", port: int = 0):
        """Add a load-balanced instance to an existing service."""
        svc = self.registry.get(service_name)
        if not svc:
            return
        if not svc.instances:
            # First instance: promote existing to list
            svc.instances.append({
                "mcp_endpoint": svc.mcp_endpoint,
                "health_endpoint": svc.health_endpoint,
                "port": svc.port,
            })
        svc.instances.append({
            "mcp_endpoint": mcp_endpoint,
            "health_endpoint": health_endpoint or "",
            "port": port or 0,
        })

    async def route(self, tool_name: str, arguments: dict) -> dict:
        """Route a tool call to the target service and return the result."""
        service_name = self.resolve(tool_name)
        if not service_name:
            logger.warning("route_not_found", tool=tool_name)
            return {"status": "error", "error": "Tool not available"}

        instance = self._next_instance(service_name)
        if not instance:
            return {"status": "error", "error": "Service temporarily unavailable"}

        mcp_endpoint = instance["mcp_endpoint"]

        # SSRF check for HTTP endpoints
        if mcp_endpoint.startswith("http") and not _is_safe_url(mcp_endpoint):
            logger.warning("ssrf_blocked", service=service_name, url=mcp_endpoint)
            return {"status": "error", "error": "Service unavailable"}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    mcp_endpoint,
                    json={"method": "tools/call", "params": {"name": tool_name, "arguments": arguments}},
                )
                resp.raise_for_status()
                self.registry.mark_success(service_name)
                return resp.json()
        except Exception as e:
            logger.warning("route_failed", tool=tool_name, service=service_name, error=str(e))
            self.registry.mark_failure(service_name)
            return {"status": "error", "error": "Routing failed"}

    def list_routes(self) -> dict[str, str]:
        return dict(self._routes)
