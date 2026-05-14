"""Request Router — routes incoming calls to the correct service."""

from __future__ import annotations

import structlog

from agora.registry import ServiceRegistry, _is_safe_url

logger = structlog.get_logger(__name__)


class Router:
    """Routes MCP tool calls to the appropriate registered service."""

    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self._routes: dict[str, str] = {}  # tool_name → service_name

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

    async def route(self, tool_name: str, arguments: dict) -> dict:
        """Route a tool call to the target service and return the result."""
        service_name = self.resolve(tool_name)
        if not service_name:
            logger.warning("route_not_found", tool=tool_name)
            return {"status": "error", "error": "Tool not available"}

        service = self.registry.get(service_name)
        if not service:
            logger.warning("service_not_found", service=service_name)
            return {"status": "error", "error": "Service not available"}
        if not service.is_available:
            return {"status": "error", "error": "Service temporarily unavailable"}

        # SSRF check for HTTP endpoints
        if service.mcp_endpoint.startswith("http") and not _is_safe_url(service.mcp_endpoint):
            logger.warning("ssrf_blocked", service=service_name, url=service.mcp_endpoint)
            return {"status": "error", "error": "Service unavailable"}

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    service.mcp_endpoint,
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
