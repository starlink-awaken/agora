"""Agora MCP Server — unified entry point for all services."""

from __future__ import annotations

import json
from pathlib import Path

from fastmcp import FastMCP

from agora.event_bus import EventBus
from agora.mcp_proxy.manager import ProxyManager
from agora.registry import ServiceRegistry, _parse_protocol_config, _parse_tags
from agora.router import Router

mcp = FastMCP(
    "Agora — Service Convergence Hub",
    mask_error_details=True,
)
registry = ServiceRegistry()
_bus = EventBus(registry=registry)
router = Router(registry, event_bus=_bus)

# ── MCP Proxy ───────────────────────────────────────────────────────

_proxy_manager: ProxyManager | None = None

# Path to enriched service config (with command/args for stdio services)
# Resolved relative to project root (same convention as registry.py's agora-services.json)
_PROXY_CONFIG_PATH = Path(__file__).resolve().parents[3] / "agora-proxy-services.json"  # 等价于 config 目录


def _load_proxy_services() -> list[dict]:
    """Load proxy service configs from the enriched config file."""
    from agora.persistence import json_load
    data = json_load(_PROXY_CONFIG_PATH, default={})
    return data if isinstance(data, list) else data.get("services", [])


async def _init_proxy():
    """Initialize the proxy manager and connect to all configured downstream services."""
    global _proxy_manager
    if _proxy_manager is not None:
        return

    _proxy_manager = ProxyManager()
    services = _load_proxy_services()

    if not services:
        return

    await _proxy_manager.start(services)
    # Re-register: for each connected proxy service, add to the existing registry
    for name, client in _proxy_manager.registry._clients.items():
        svc = registry.get(name)
        if svc:
            svc.healthy = client.connected
            svc.mcp_endpoint = f"proxy:{name}"
    registry._save()


@mcp.tool()
async def proxy_connect() -> str:
    """Connect to all configured downstream MCP services via the proxy.

    Reads from agora-proxy-services.json for service definitions.
    Returns connection results for each service.
    """
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()

    services = _load_proxy_services()
    if not services:
        return json.dumps({
            "status": "warning",
            "message": "No proxy services configured in agora-proxy-services.json",
        }, ensure_ascii=False)

    results = await _proxy_manager.start(services)
    return json.dumps({
        "status": "done",
        "services": results,
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def proxy_call(tool_name: str, arguments: str = "{}") -> str:
    """Call a downstream service tool through the MCP proxy.

    The proxy connects to registered downstream MCP services (via stdio or HTTP)
    and forwards tool calls. Supports both exact and prefix tool name matching.

    Args:
        tool_name: Full tool name (e.g. 'kos.semantic_search', 'minerva.research_now')
        arguments: JSON string of tool arguments
    """
    if _proxy_manager is None:
        return json.dumps({
            "status": "error", "error": "Proxy not initialized. Call proxy_connect first."
        }, ensure_ascii=False)

    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        args = {}

    try:
        result = await _proxy_manager.dispatch(tool_name, args)
        return json.dumps(result, ensure_ascii=False, indent=2)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "status": "error", "error": f"Proxy call failed: {str(e)[:200]}"
        }, ensure_ascii=False)


@mcp.tool()
async def proxy_status() -> str:
    """Show current proxy connection status and available tools."""
    if _proxy_manager is None:
        return json.dumps({"status": "not_initialized"}, ensure_ascii=False)

    status = _proxy_manager.status()
    return json.dumps(status, ensure_ascii=False, indent=2)


@mcp.tool()
async def proxy_add_service(
    name: str,
    mcp_endpoint: str = "",
    command: str = "",
    args: str = "",
) -> str:
    """Add and connect a downstream MCP service to the proxy.

    Args:
        name: Service name (e.g. 'kos', 'minerva')
        mcp_endpoint: HTTP endpoint URL (e.g. 'http://localhost:7420/mcp')
                      Leave empty for stdio services
        command: Command for stdio services (e.g. 'python3')
        args: Space-separated arguments for stdio command
    """
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()

    svc: dict = {"name": name}
    if mcp_endpoint:
        svc["mcp_endpoint"] = mcp_endpoint
    if command:
        svc["command"] = command
    if args:
        svc["args"] = args.split()

    result = await _proxy_manager.add_service(svc)
    return json.dumps({"status": result}, ensure_ascii=False)


@mcp.tool()
async def proxy_remove_service(name: str) -> str:
    """Disconnect and remove a downstream service from the proxy."""
    if _proxy_manager is None:
        return json.dumps({"status": "not_initialized"}, ensure_ascii=False)
    await _proxy_manager.remove_service(name)
    return json.dumps({"status": "removed", "service": name}, ensure_ascii=False)


# ── Service management tools ─────────────────────────────────────


@mcp.tool()
def register_service(name: str, description: str = "", protocol: str = "mcp",
                     protocol_config: str = "{}", mcp_endpoint: str = "",
                     health_endpoint: str = "", port: int = 0, tags: str = "",
                     command: str = "", mcp_args: str = "") -> str:
    """Register a service with the Agora hub.

    Args:
        name: Unique service name (e.g. 'minerva', 'kos', 'sophia')
        description: Human-readable description
        protocol: Service protocol — mcp | rest | grpc | stdio | websocket (default: mcp)
        protocol_config: JSON string of protocol-specific settings (default: {})
        mcp_endpoint: Server URL (e.g. 'http://localhost:8765/mcp'), also used for REST endpoints
        health_endpoint: Health check URL (e.g. 'http://localhost:8765/health')
        port: Service port
        tags: Comma-separated tags
        command: Command for proxy/stdio connection (e.g. 'python3')
        mcp_args: Space-separated args for proxy/stdio command
    """
    from agora.registry import Service, ServiceConfig

    cfg = ServiceConfig(name=name, description=description, protocol=protocol,
                        protocol_config=protocol_config, mcp_endpoint=mcp_endpoint,
                        health_endpoint=health_endpoint, port=port, tags=tags,
                        command=command, mcp_args=mcp_args)
    if not (0 <= cfg.port <= 65535):
        return json.dumps({"status": "error", "error": "Port must be 0-65535"})

    proto_cfg, err = _parse_protocol_config(cfg.protocol_config)
    if err:
        return json.dumps({"status": "error", "error": f"protocol_config is not valid JSON: {err}"})

    svc = Service(name=cfg.name, description=cfg.description, protocol=cfg.protocol,
                  protocol_config=proto_cfg, mcp_endpoint=cfg.mcp_endpoint,
                  health_endpoint=cfg.health_endpoint, port=cfg.port,
                  tags=_parse_tags(cfg.tags))
    try:
        registry.register(svc)
    except ValueError as e:
        return json.dumps({"status": "error", "error": str(e)})

    if cfg.command:
        _save_proxy_service({
            "name": cfg.name, "command": cfg.command,
            "args": cfg.mcp_args.split() if cfg.mcp_args else [],
            "mcp_endpoint": cfg.mcp_endpoint,
        })

    return json.dumps({"status": "registered", "name": name})


def _save_proxy_service(svc: dict):
    """Append a service config to the proxy services file."""
    from agora.persistence import json_save
    existing = _load_proxy_services()
    # Replace if exists, else append
    existing = [s for s in existing if s.get("name") != svc.get("name")]
    existing.append(svc)
    json_save(_PROXY_CONFIG_PATH, existing)


@mcp.tool()
def list_services() -> str:
    """List all registered services and their health status."""
    return json.dumps(registry.to_dict(), ensure_ascii=False, indent=2)


@mcp.tool()
async def check_health() -> str:
    """Probe all registered services' health endpoints."""
    await registry.health_check_all()
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
async def route_call(tool_name: str, arguments: str = "{}") -> str:
    """Route a tool call to the appropriate service.

    Args:
        tool_name: The tool to call (e.g. 'minerva.research_now')
        arguments: JSON string of arguments
    """
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        args = {}
    result = await router.route(tool_name, args)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ── Event Bus tools (Phase 1, spec §4.2) ──────────────────────────────


@mcp.tool()
def publish_event(event_type: str, payload: str, source: str = "") -> str:
    """Publish an event to the bus. payload is a JSON string.

    Args:
        event_type: Event type (e.g. 'index:done', 'registry:tools.updated')
        payload: JSON string with event data
        source: Source service name (e.g. 'kos', 'claude-code')
    """
    bus = _bus
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
    bus = _bus
    sub_id = bus.subscribe("mcp-caller", pattern, callback_url)
    return json.dumps({"subscription_id": sub_id, "pattern": pattern})


@mcp.tool()
def get_event_log(limit: int = 50, since: str = "") -> str:
    """Query historical events.

    Args:
        limit: Max events to return (default 50)
        since: ISO timestamp, only return events after this time
    """
    bus = _bus
    events = bus.get_event_log(limit, since)
    return json.dumps(events, ensure_ascii=False, indent=2)


def main():
    print("Agora MCP Server starting...")
    mcp.run()


def http_main():
    """Start the Agora MCP server in HTTP mode with proxy initialization."""
    import asyncio

    async def _start():
        services = _load_proxy_services()
        if services:
            global _proxy_manager
            _proxy_manager = ProxyManager()
            results = await _proxy_manager.start(services)
            for name, client in _proxy_manager.registry._clients.items():
                svc = registry.get(name)
                if svc:
                    svc.healthy = client.connected
                    svc.mcp_endpoint = f"proxy:{name}"
            registry._save()
            print(f"Proxy connected: {json.dumps(results, indent=2)}")
        await mcp.run_http_async(host="127.0.0.1", port=7422)

    asyncio.run(_start())


if __name__ == "__main__":
    http_main()
