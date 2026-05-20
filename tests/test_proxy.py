"""Tests for Agora MCP proxy manager and client helpers."""
from agora.mcp_proxy.client import (
    _make_request,
    _make_request_dict,
    _make_tool_call,
    _make_tool_call_dict,
)
from agora.mcp_proxy.manager import ProxyManager
from agora.mcp_proxy.registry import ProxyRegistry


class TestClientHelpers:
    def test_make_request_returns_string(self):
        result = _make_request("tools/list")
        assert isinstance(result, str)
        assert '"method":"tools/list"' in result.replace(" ", "").replace("\n", "")

    def test_make_request_dict_returns_dict(self):
        result = _make_request_dict("tools/list")
        assert isinstance(result, dict)
        assert result["method"] == "tools/list"
        assert result["jsonrpc"] == "2.0"
        assert "id" in result

    def test_make_tool_call_returns_string(self):
        result = _make_tool_call("minerva.research_now", {"query": "test"})
        assert isinstance(result, str)
        assert "minerva.research_now" in result

    def test_make_tool_call_dict_returns_dict(self):
        result = _make_tool_call_dict("minerva.research_now", {"query": "test"})
        assert isinstance(result, dict)
        assert result["method"] == "tools/call"
        assert result["params"]["name"] == "minerva.research_now"


class TestProxyRegistryNoCopy:
    def test_entries_returns_same_dict(self):
        reg = ProxyRegistry()
        entries = reg.entries
        assert entries is reg._entries  # no defensive copy


class TestProxyManager:
    def setup_method(self):
        self.manager = ProxyManager()

    def test_initial_status_idle(self):
        status = self.manager.status()
        assert status["status"] == "idle"
        assert status["tools"] == 0
        assert status["connected_services"] == []

    def test_start_no_services(self):
        import asyncio
        results = asyncio.run(self.manager.start([]))
        assert results == {}

    def test_add_bad_service_returns_error(self):
        import asyncio
        results = asyncio.run(self.manager.start([
            {"name": "bad-svc", "mcp_endpoint": "http://192.0.2.99:19999"}
        ]))
        assert "bad-svc" in results
        assert "error" in results["bad-svc"] or "ok" in results["bad-svc"]

    def test_status_after_connect(self):
        import asyncio
        asyncio.run(self.manager.start([
            {"name": "echo-svc", "mcp_endpoint": "http://192.0.2.99:19999"}
        ]))
        status = self.manager.status()
        assert "status" in status
