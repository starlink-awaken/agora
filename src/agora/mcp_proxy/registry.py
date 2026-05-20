"""ProxyRegistry — maps tool names to downstream services and manages client connections."""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from agora.mcp_proxy.client import MCPClient, create_client
from agora.registry import ServiceRegistry

logger = structlog.get_logger(__name__)


@dataclass
class ProxyEntry:
    """A registered downstream tool in the proxy."""

    tool_name: str           # Full name: "kos.semantic_search"
    service_name: str        # Downstream service name
    original_name: str       # Original tool name in the downstream service
    description: str         # Tool description from schema
    parameters: dict         # JSON Schema for parameters
    client: MCPClient       # The client instance to use for calling


class ProxyRegistry:
    """Registry of all downstream tools available through the proxy.

    Maps tool names (with service prefix) to client connections,
    and provides dispatch logic for routing tool calls.
    """

    def __init__(self):
        self._entries: dict[str, ProxyEntry] = {}  # tool_name → entry
        self._clients: dict[str, MCPClient] = {}   # service_name → client

    @property
    def entries(self) -> dict[str, ProxyEntry]:
        return dict(self._entries)

    @property
    def connected_services(self) -> list[str]:
        return list(self._clients.keys())

    def get_entry(self, tool_name: str) -> ProxyEntry | None:
        """Resolve a tool name to its ProxyEntry.

        Supports exact match first, then prefix match.
        E.g. "kos.semantic_search" → exact match on "kos.semantic_search"
        E.g. "kos" → prefix match (no service registered with just "kos")
        """
        if tool_name in self._entries:
            return self._entries[tool_name]
        # Prefix match: try "kos" prefix for "kos.semantic_search"
        parts = tool_name.split(".", 1)
        if len(parts) > 1 and parts[0] in self._clients:
            # Find by service prefix
            return self._entries.get(tool_name)
        return None

    async def register_service(self, service_name: str, client: MCPClient) -> bool:
        """Connect to a service, discover its tools, and register them."""
        if not await client.connect():
            logger.error("proxy_connect_failed", service=service_name)
            return False

        tools = await client.list_tools()
        if not tools:
            logger.warning("proxy_no_tools_found", service=service_name)
            return False

        count = 0
        for tool in tools:
            original_name = tool.get("name", "")
            full_name = f"{service_name}.{original_name}"
            description = tool.get("description", "")
            parameters = tool.get("inputSchema", tool.get("parameters", {}))

            entry = ProxyEntry(
                tool_name=full_name,
                service_name=service_name,
                original_name=original_name,
                description=description,
                parameters=parameters,
                client=client,
            )
            self._entries[full_name] = entry
            count += 1

        self._clients[service_name] = client
        logger.info("proxy_service_registered",
                     service=service_name, tools=count)
        return True

    async def unregister_service(self, service_name: str):
        """Disconnect and remove all tools for a service."""
        # Remove all entries for this service
        to_remove = [
            name for name, entry in self._entries.items()
            if entry.service_name == service_name
        ]
        for name in to_remove:
            del self._entries[name]

        # Disconnect and remove client
        client = self._clients.pop(service_name, None)
        if client:
            await client.disconnect()

        logger.info("proxy_service_unregistered",
                     service=service_name, tools_removed=len(to_remove))

    async def register_from_registry(self, service_registry: ServiceRegistry):
        """Register all services from the existing ServiceRegistry."""
        services = service_registry.list_all()
        for svc in services:
            # Determine transport type
            if svc.mcp_endpoint == "stdio" or svc.mcp_endpoint == "":
                # Can't auto-register stdio services without command/args
                logger.info("proxy_skipping_stdio",
                             service=svc.name,
                             reason="no command/args configured")
                continue

            if svc.mcp_endpoint.startswith("http"):
                client = create_client(svc.name, svc.mcp_endpoint)
                await self.register_service(svc.name, client)

        logger.info("proxy_registry_sync_complete",
                     services=len(self._clients))

    async def dispatch(self, tool_name: str, arguments: dict) -> dict:
        """Route a tool call to the correct downstream service.

        Args:
            tool_name: Full tool name (e.g. "kos.semantic_search")
            arguments: Tool arguments as a dict

        Returns:
            Tool result as a dict
        """
        entry = self.get_entry(tool_name)
        if not entry:
            return {"status": "error", "error": f"Tool '{tool_name}' not found in proxy"}

        try:
            result = await entry.client.call_tool(entry.original_name, arguments)
            return result if isinstance(result, dict) else {"status": "ok", "data": result}
        except Exception as e:
            logger.error("proxy_dispatch_failed",
                         tool=tool_name, service=entry.service_name, error=str(e))
            return {"status": "error", "error": str(e)}

    def get_tool_schemas(self) -> list[dict]:
        """Get all registered tool schemas for dynamic registration.

        Returns a list of dicts compatible with FastMCP tool registration:
        {name, description, parameters, handler}
        """
        schemas = []
        for entry in self._entries.values():
            schemas.append({
                "name": entry.tool_name,
                "description": entry.description,
                "parameters": entry.parameters,
                "service_name": entry.service_name,
                "original_name": entry.original_name,
            })
        return schemas

    async def disconnect_all(self):
        """Disconnect all downstream clients."""
        for service_name in list(self._clients.keys()):
            await self.unregister_service(service_name)
        self._entries.clear()
        self._clients.clear()
