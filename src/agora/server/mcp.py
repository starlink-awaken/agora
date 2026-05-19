"""Agora MCP Server — unified entry point for all services."""

from __future__ import annotations

import json

from fastmcp import FastMCP

from agora.registry import ServiceRegistry, _is_safe_url
from agora.router import Router
from agora.event_bus import EventBus

mcp = FastMCP(
    "Agora — Service Convergence Hub",
    mask_error_details=True,
)
registry = ServiceRegistry()
_bus = EventBus(registry=registry)
router = Router(registry, event_bus=_bus)


# ── Service management tools ─────────────────────────────────────

@mcp.tool()
def register_service(name: str, description: str = "", mcp_endpoint: str = "",
                     health_endpoint: str = "", port: int = 0, tags: str = "") -> str:
    """Register a service with the Agora hub.

    Args:
        name: Unique service name (e.g. 'minerva', 'kos', 'sophia')
        description: Human-readable description
        mcp_endpoint: MCP server URL (e.g. 'http://localhost:8765/mcp')
        health_endpoint: Health check URL (e.g. 'http://localhost:8765/health')
        port: Service port
        tags: Comma-separated tags
    """
    from agora.registry import Service

    # Validate URLs against SSRF
    if health_endpoint and not _is_safe_url(health_endpoint):
        return json.dumps({"status": "error", "error": "Health endpoint URL targets internal network"})
    if mcp_endpoint and not _is_safe_url(mcp_endpoint):
        return json.dumps({"status": "error", "error": "MCP endpoint URL targets internal network"})
    if not (0 <= port <= 65535):
        return json.dumps({"status": "error", "error": "Port must be 0-65535"})

    svc = Service(name=name, description=description, mcp_endpoint=mcp_endpoint,
                  health_endpoint=health_endpoint, port=port,
                  tags=[t.strip() for t in tags.split(",") if t.strip()])
    registry.register(svc)
    return json.dumps({"status": "registered", "name": name})


@mcp.tool()
def list_services() -> str:
    """List all registered services and their health status."""
    return json.dumps(registry.to_dict(), ensure_ascii=False, indent=2)


@mcp.tool()
def check_health() -> str:
    """Probe all registered services' health endpoints."""
    import asyncio
    asyncio.run(registry.health_check_all())
    return json.dumps({
        "total": len(registry.list_all()),
        "healthy": len(registry.list_healthy()),
        "services": registry.to_dict(),
    }, ensure_ascii=False, indent=2)


@mcp.tool()
def add_route(tool_name: str, service_name: str) -> str:
    """Map a tool name to a service for routing.

    Args:
        tool_name: The tool name (e.g. 'minerva.research_now' or just 'minerva' for prefix)
        service_name: The registered service name
    """
    if not tool_name.strip() or not service_name.strip():
        return json.dumps({"status": "error", "error": "Tool name and service name required"})
    router.add_route(tool_name, service_name)
    return json.dumps({"status": "routed", "tool": tool_name, "service": service_name})


@mcp.tool()
def list_routes() -> str:
    """List all tool → service route mappings."""
    return json.dumps(router.list_routes(), ensure_ascii=False, indent=2)


@mcp.tool()
def route_call(tool_name: str, arguments: str = "{}") -> str:
    """Route a tool call to the appropriate service.

    Args:
        tool_name: The tool to call (e.g. 'minerva.research_now')
        arguments: JSON string of arguments
    """
    import asyncio
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        args = {}
    result = asyncio.run(router.route(tool_name, args))
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Event Bus tools (Phase 1, spec §4.2) ──────────────────────────────


def _get_bus():
    return _bus  # Module-level bus, initialized alongside registry/router


@mcp.tool()
def publish_event(event_type: str, payload: str, source: str = "") -> str:
    """Publish an event to the bus. payload is a JSON string.

    Args:
        event_type: Event type (e.g. 'index:done', 'registry:tools.updated')
        payload: JSON string with event data
        source: Source service name (e.g. 'kos', 'claude-code')
    """
    bus = _get_bus()
    try:
        data = json.loads(payload) if isinstance(payload, str) else payload
    except json.JSONDecodeError:
        data = {"raw": payload}
    event_id = bus.publish(event_type, data, source)
    return json.dumps({"event_id": event_id, "status": "published"})


@mcp.tool()
def subscribe_event(pattern: str, callback_url: str = "") -> str:
    """Subscribe to events matching pattern.

    Args:
        pattern: Event pattern ('index:*', 'index:done', '*')
        callback_url: Optional HTTP callback URL for push delivery
    """
    bus = _get_bus()
    sub_id = bus.subscribe("mcp-caller", pattern, callback_url)
    return json.dumps({"subscription_id": sub_id, "pattern": pattern})


@mcp.tool()
def get_event_log(limit: int = 50, since: str = "") -> str:
    """Query historical events.

    Args:
        limit: Max events to return (default 50)
        since: ISO timestamp, only return events after this time
    """
    bus = _get_bus()
    events = bus.get_event_log(limit, since)
    return json.dumps(events, ensure_ascii=False, indent=2)


def main():
    print("Agora MCP Server starting...")
    mcp.run()


if __name__ == "__main__":
    main()
