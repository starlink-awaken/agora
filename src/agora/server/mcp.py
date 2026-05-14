"""Agora MCP Server — unified entry point for all services."""

from __future__ import annotations

import json

from fastmcp import FastMCP

from agora.registry import ServiceRegistry
from agora.router import Router

mcp = FastMCP(
    "Agora — Service Convergence Hub",
    mask_error_details=True,
)
registry = ServiceRegistry()
router = Router(registry)


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


def _is_safe_url(url: str) -> bool:
    """Validate URL does not target internal/private network resources."""
    from urllib.parse import urlparse
    import ipaddress
    import socket

    BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"}
    BLOCKED_NETWORKS = [
        ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("172.16.0.0/12"),
        ipaddress.ip_network("192.168.0.0/16"), ipaddress.ip_network("169.254.0.0/16"),
        ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fc00::/7"),
    ]

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname.lower() in BLOCKED_HOSTS:
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        return not any(ip in net for net in BLOCKED_NETWORKS)
    except ValueError:
        pass
    try:
        resolved = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved)
        return not any(ip in net for net in BLOCKED_NETWORKS)
    except Exception:
        return False
    return True


def main():
    print("Agora MCP Server starting...")
    mcp.run()


if __name__ == "__main__":
    main()
