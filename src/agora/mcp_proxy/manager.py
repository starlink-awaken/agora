"""ProxyManager — manages lifecycle of downstream MCP client connections.

Orchestrates connecting, disconnecting, and routing to multiple
downstream MCP services through the proxy layer.
"""

from __future__ import annotations

import structlog

from agora.mcp_proxy.client import create_client
from agora.mcp_proxy.registry import ProxyRegistry

logger = structlog.get_logger(__name__)


class ProxyManager:
    """Manages downstream MCP service connections and tool dispatch.

    Responsible for:
    - Starting/stopping connections to downstream MCP services
    - Registering/unregistering services dynamically
    - Dispatching tool calls to the correct service
    - Providing status information for observability
    """

    def __init__(self):
        self.registry = ProxyRegistry()
        self._configs: dict[str, dict] = {}  # service_name → config dict

    async def start(self, services: list[dict]) -> dict[str, str]:
        """Connect to all configured downstream services in parallel.

        Args:
            services: List of service config dicts, each containing:
                - name: Service name
                - mcp_endpoint: HTTP endpoint URL or 'stdio'
                - command: Command for stdio transport
                - args: List of command arguments

        Returns:
            Dict mapping service_name → result string
        """
        import asyncio

        async def _connect_one(svc: dict) -> tuple[str, str]:
            name = svc.get("name", "unknown")
            try:
                result = await self.add_service(svc)
                return name, result
            except Exception as e:
                logger.error("proxy_start_failed", service=name, error=str(e))
                return name, f"error: {str(e)[:100]}"

        tasks = [_connect_one(svc) for svc in services]
        gathered = await asyncio.gather(*tasks)
        return dict(gathered)

    async def add_service(self, svc: dict) -> str:
        """Connect and register a single downstream service.

        Args:
            svc: Service config dict with name, mcp_endpoint/command/args.

        Returns:
            Result string: "ok: N tools registered" or error message.
        """
        name = svc.get("name", "unknown")
        mcp_endpoint = svc.get("mcp_endpoint", "")
        command = svc.get("command", "")
        args = svc.get("args", [])
        cwd = svc.get("cwd")

        # Save config
        self._configs[name] = dict(svc)

        # Remove existing if reconnecting
        if name in self.registry._clients:
            await self.registry.unregister_service(name)

        try:
            client = create_client(name, mcp_endpoint, command, args, cwd=cwd)
        except ValueError as e:
            logger.error("proxy_create_client_failed", service=name, error=str(e))
            return f"error: {str(e)[:100]}"

        ok = await self.registry.register_service(name, client)
        if ok:
            count = len([e for e in self.registry.entries.values()
                         if e.service_name == name])
            logger.info("proxy_service_connected", service=name, tools=count)
            return f"ok: {count} tools registered"
        else:
            logger.error("proxy_service_connect_failed", service=name)
            return "error: connection failed"

    async def remove_service(self, name: str) -> str:
        """Disconnect and remove a downstream service.

        Args:
            name: Service name to remove.

        Returns:
            "removed" or error message.
        """
        if name not in self.registry._clients:
            return "not_found"
        await self.registry.unregister_service(name)
        self._configs.pop(name, None)
        return "removed"

    async def dispatch(self, tool_name: str, arguments: dict) -> dict:
        """Dispatch a tool call to the correct downstream service.

        Args:
            tool_name: Full tool name (e.g. 'kos.semantic_search').
            arguments: Dict of tool arguments.

        Returns:
            Tool result dict.
        """
        return await self.registry.dispatch(tool_name, arguments)

    def status(self) -> dict:
        """Get current proxy status.

        Returns dict with:
        - connected_services: list of connected service names
        - tools: total registered tool count
        - services: dict of service → tool count
        """
        if not self.registry._clients:
            return {"status": "idle", "connected_services": [], "tools": 0, "services": {}}

        services_info = {}
        for name, client in self.registry._clients.items():
            tool_count = len([
                e for e in self.registry.entries.values()
                if e.service_name == name
            ])
            services_info[name] = {
                "connected": client.connected,
                "tools": tool_count,
            }

        return {
            "status": "running",
            "connected_services": list(self.registry._clients.keys()),
            "tools": len(self.registry.entries),
            "services": services_info,
        }

    async def shutdown(self):
        """Disconnect all downstream services."""
        await self.registry.disconnect_all()
        self._configs.clear()
