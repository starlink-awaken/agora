"""Tests for Agora MCP Server tools — direct function imports."""
import json

from agora.server.mcp import (
    add_route,
    check_health,
    get_event_log,
    list_routes,
    list_services,
    publish_event,
    register_service,
    subscribe_event,
)


class TestRegisterService:
    def test_register_mcp_service(self):
        result = json.loads(register_service(
            name="mcp-test",
            mcp_endpoint="http://192.0.2.50:8765",
            tags="test,mcp",
        ))
        assert result["status"] == "registered"
        assert result["name"] == "mcp-test"

    def test_register_rest_service(self):
        result = json.loads(register_service(
            name="rest-test",
            protocol="rest",
            protocol_config='{"method":"GET"}',
            mcp_endpoint="http://192.0.2.51:3000",
        ))
        assert result["status"] == "registered"

    def test_register_invalid_protocol(self):
        result = json.loads(register_service(
            name="bad-proto",
            protocol="invalid",
        ))
        assert result["status"] == "error"
        assert "Unknown protocol" in result["error"]

    def test_register_bad_port(self):
        result = json.loads(register_service(
            name="bad-port", port=99999,
        ))
        assert result["status"] == "error"

    def test_register_bad_protocol_config(self):
        result = json.loads(register_service(
            name="bad-cfg",
            protocol_config="not json",
        ))
        assert result["status"] == "error"


class TestListServices:
    def test_list_returns_array(self):
        result = json.loads(list_services())
        assert isinstance(result, list)

    def test_list_includes_registered(self):
        register_service(name="list-test", mcp_endpoint="http://192.0.2.60:8765")
        result = json.loads(list_services())
        names = [s["name"] for s in result]
        assert "list-test" in names


class TestHealthCheck:
    def test_health_returns_counts(self):
        import asyncio
        result = json.loads(asyncio.run(check_health()))
        assert "total" in result
        assert "healthy" in result


class TestRoutes:
    def test_add_and_list_routes(self):
        add_route("test.tool", "test-svc")
        routes = json.loads(list_routes())
        assert "test.tool" in routes
        assert routes["test.tool"] == "test-svc"


class TestEventBus:
    def test_publish_and_read_event(self):
        publish_event("test:mcp", '{"msg":"hello"}', "mcp-test")
        log = json.loads(get_event_log(limit=5))
        assert isinstance(log, list)
        if log:
            assert log[-1]["type"] == "test:mcp"

    def test_subscribe_event(self):
        result = json.loads(subscribe_event("test:*"))
        assert "subscription_id" in result
        assert result["pattern"] == "test:*"
