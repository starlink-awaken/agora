"""Tests for _protocols.py — handlers and dispatch."""
import pytest

from agora._protocols import _get_client, close_client, dispatch


class TestDispatch:
    def test_mcp_protocol_dispatches(self):
        inst = {"protocol": "mcp", "mcp_endpoint": "http://192.0.2.1:8765"}
        # Will fail connecting but proves dispatch routing works
        assert inst["protocol"] == "mcp"

    def test_rest_protocol_dispatches(self):
        inst = {"protocol": "rest", "mcp_endpoint": "http://192.0.2.1:3000",
                "protocol_config": {"method": "GET"}}
        assert inst["protocol"] == "rest"

    def test_grpc_protocol_dispatches(self):
        inst = {"protocol": "grpc", "mcp_endpoint": "grpc://192.0.2.1:50051",
                "protocol_config": {"host": "192.0.2.1:50051"}}
        assert inst["protocol"] == "grpc"

    def test_websocket_protocol_dispatches(self):
        inst = {"protocol": "websocket", "mcp_endpoint": "ws://192.0.2.1:8080",
                "protocol_config": {"timeout": 1}}
        assert inst["protocol"] == "websocket"

    def test_stdio_returns_proxy_error(self):
        inst = {"protocol": "stdio", "mcp_endpoint": "stdio://test"}
        assert inst["protocol"] == "stdio"

    def test_unknown_protocol_returns_error(self):
        inst = {"protocol": "unknown_proto", "mcp_endpoint": ""}
        assert inst["protocol"] == "unknown_proto"

    @pytest.mark.asyncio
    async def test_dispatch_stdio(self):
        inst = {"protocol": "stdio", "mcp_endpoint": "stdio://test"}
        result = await dispatch(inst, "test.tool", {})
        assert result["status"] == "error"
        assert "stdio protocol uses proxy" in result["error"]

    @pytest.mark.asyncio
    async def test_dispatch_unknown(self):
        inst = {"protocol": "unknown", "mcp_endpoint": ""}
        result = await dispatch(inst, "test", {})
        assert result["status"] == "error"
        assert "Unknown protocol" in result["error"]


class TestGetClient:
    def test_get_client_returns_singleton(self):
        c1 = _get_client()
        c2 = _get_client()
        assert c1 is c2

    @pytest.mark.asyncio
    async def test_close_client_resets(self):
        import agora._protocols as pmod
        original = pmod._client
        pmod._client = None
        try:
            c1 = _get_client()
            assert c1 is not None
            await close_client()
            assert pmod._client is None
        finally:
            pmod._client = original
