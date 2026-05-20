"""Agora MCP Proxy — unified downstream service aggregation.

Connects to multiple MCP services (stdio + HTTP), aggregates their
tool schemas, and exposes them through a single MCP entry point.
"""

from agora.mcp_proxy.client import (
    HttpMCPClient,
    MCPClient,
    StdioMCPClient,
    create_client,
)
from agora.mcp_proxy.manager import ProxyManager
from agora.mcp_proxy.registry import ProxyEntry, ProxyRegistry

__all__ = [
    "MCPClient",
    "StdioMCPClient",
    "HttpMCPClient",
    "create_client",
    "ProxyRegistry",
    "ProxyEntry",
    "ProxyManager",
]
