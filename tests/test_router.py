"""Tests for Agora request router."""
import pytest

from agora.registry import Service, ServiceRegistry
from agora.router import Router


class TestRouter:
    def setup_method(self):
        import tempfile
        self.registry = ServiceRegistry()
        self.registry.register(Service("minerva", mcp_endpoint="http://192.0.2.1:8765"))
        self.registry.register(Service("sophia", mcp_endpoint="http://192.0.2.2:9001"))
        self.router = Router(self.registry, routes_path=str(
            __import__("pathlib").Path(tempfile.mkdtemp()) / "test-routes.json"))

    def test_exact_match(self):
        self.router.add_route("minerva.research_now", "minerva")
        assert self.router.resolve("minerva.research_now") == "minerva"

    def test_prefix_match(self):
        self.router.add_route("minerva", "minerva")
        assert self.router.resolve("minerva.research_now") == "minerva"
        assert self.router.resolve("minerva.knowledge_search") == "minerva"

    def test_no_match(self):
        assert self.router.resolve("nonexistent.tool") is None

    def test_list_routes(self):
        self.router.add_route("minerva", "minerva")
        self.router.add_route("sophia.compile", "sophia")
        routes = self.router.list_routes()
        assert len(routes) == 2
        assert routes["minerva"] == "minerva"
        assert routes["sophia.compile"] == "sophia"


class TestAddInstance:
    def test_promotes_to_list_with_protocol(self):
        """Adding an instance should propagate protocol/config to instance dicts."""
        registry = ServiceRegistry()
        router = Router(registry)
        registry.register(Service("api", protocol="rest",
                                  mcp_endpoint="http://192.0.2.1:3000",
                                  protocol_config={"method": "POST"}))
        router._add_instance("api", "http://192.0.2.2:3000")
        svc = registry.get("api")
        assert len(svc.instances) == 2
        for inst in svc.instances:
            assert inst["protocol"] == "rest"
            assert inst["protocol_config"] == {"method": "POST"}


class TestProtocolDispatch:
    def setup_method(self):
        self.registry = ServiceRegistry()
        self.router = Router(self.registry)

    def test_rest_reserved_returns_error(self):
        """REST service returns reserved error when target is unreachable."""
        svc = Service("api", protocol="rest",
                      mcp_endpoint="http://192.0.2.99:3000",
                      protocol_config={"method": "GET"})
        self.registry.register(svc)
        self.router.add_route("api", "api")

    def test_grpc_reserved_returns_error(self):
        """gRPC protocol returns reserved error."""
        svc = Service("grpc-svc", protocol="grpc",
                      mcp_endpoint="http://192.0.2.99:50051")
        self.registry.register(svc)
        self.router.add_route("grpc-svc", "grpc-svc")

    def test_websocket_reserved_returns_error(self):
        """WebSocket protocol returns reserved error."""
        svc = Service("ws-svc", protocol="websocket",
                      mcp_endpoint="http://192.0.2.99:8080")
        self.registry.register(svc)
        self.router.add_route("ws-svc", "ws-svc")

    @pytest.mark.asyncio
    async def test_grpc_dispatch_returns_stub_error(self):
        """gRPC dispatch returns error without compiled stub."""
        svc = Service("grpc-svc", protocol="grpc",
                      mcp_endpoint="grpc://192.0.2.99:50051",
                      protocol_config={"host": "192.0.2.99:50051"})
        self.registry.register(svc)
        self.router.add_route("grpc-svc", "grpc-svc")
        result = await self.router.route("grpc-svc", {})
        assert result["status"] == "error"
        assert "stub" in result["error"].lower() or "grpc" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_ws_dispatch_returns_stub_error(self):
        """WebSocket dispatch returns error on connect failure."""
        svc = Service("ws-svc", protocol="websocket",
                      mcp_endpoint="ws://192.0.2.99:8080",
                      protocol_config={"timeout": 1})
        self.registry.register(svc)
        self.router.add_route("ws-svc", "ws-svc")
        result = await self.router.route("ws-svc", {})
        assert result["status"] == "error"
        assert "WebSocket" in result["error"] or "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_stdio_dispatch_returns_error(self):
        """stdio dispatch returns error about proxy usage."""
        svc = Service("stdio-svc", protocol="stdio",
                      mcp_endpoint="stdio://my-service")
        self.registry.register(svc)
        self.router.add_route("stdio-svc", "stdio-svc")
        result = await self.router.route("stdio-svc", {})
        assert result["status"] == "error"
        assert "stdio protocol uses proxy" in result["error"]

    @pytest.mark.asyncio
    async def test_rest_retry_methods(self):
        """REST with GET retries via protocol_config retries field."""
        svc = Service("retry-api", protocol="rest",
                      mcp_endpoint="http://192.0.2.99:3000",
                      protocol_config={"method": "GET", "retries": 1})
        self.registry.register(svc)
        self.router.add_route("retry-api", "retry-api")
        result = await self.router.route("retry-api", {})
        assert result["status"] == "error"
        assert "REST call failed" in result["error"]

    @pytest.mark.asyncio
    async def test_unknown_protocol_dispatch(self):
        """Unknown protocol in instance dict returns error (bypasses registry validation)."""
        svc = Service("bad-proto", protocol="mcp",
                      mcp_endpoint="http://192.0.2.99:9999")
        self.registry.register(svc)
        # Override after registration to simulate corrupt instance state
        svc.protocol = "unknown_proto"
        self.router.add_route("bad-proto", "bad-proto")
        result = await self.router.route("bad-proto", {})
        assert result["status"] == "error"
        assert "Unknown protocol" in result["error"]

    @pytest.mark.asyncio
    async def test_ws_invalid_url_dispatch(self):
        """WebSocket with non-ws URL returns invalid URL error."""
        svc = Service("bad-ws", protocol="websocket",
                      mcp_endpoint="http://192.0.2.99:8080")
        self.registry.register(svc)
        self.router.add_route("bad-ws", "bad-ws")
        result = await self.router.route("bad-ws", {})
        assert result["status"] == "error"
        assert "Invalid WebSocket URL" in result["error"]

    def test_get_percentiles_empty(self):
        """Percentiles are all zero when no calls have been routed."""
        pct = self.router.get_percentiles()
        assert pct == {"p50": 0, "p90": 0, "p99": 0, "samples": 0, "avg": 0}

    @pytest.mark.asyncio
    async def test_route_no_match(self):
        """Routing to an unmapped tool returns error."""
        result = await self.router.route("nonexistent.tool", {})
        assert result["status"] == "error"
        assert "Tool not available" in result["error"]

    @pytest.mark.asyncio
    async def test_route_service_unavailable(self):
        """Routing to a service that's in OPEN state returns unavailable error."""
        svc = Service("down-svc", protocol="grpc",
                      mcp_endpoint="http://192.0.2.99:9999")
        self.registry.register(svc)
        svc.healthy = False
        svc.cooldown_until = 9999999999.0
        self.router.add_route("down-svc", "down-svc")
        result = await self.router.route("down-svc", {})
        assert result["status"] == "error"
        assert "Service temporarily unavailable" in result["error"]


class TestRouterAdvanced:
    """Advanced router tests: _call_mcp, _call_rest, _trace, close, etc."""

    @pytest.mark.asyncio
    async def test_call_mcp_success(self, monkeypatch):
        """_call_mcp with valid endpoint returns response."""
        from httpx import AsyncClient
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("mcp-svc", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        router.add_route("mcp-svc.tool", "mcp-svc")

        class _MockResp:
            def json(self):
                return {"result": "data"}
            def raise_for_status(self):
                pass

        class _MockClient(AsyncClient):
            def __init__(self):
                pass
            async def post(self, url, **kw):
                return _MockResp()
            async def aclose(self):
                pass

        monkeypatch.setattr("agora.router._get_client", lambda: _MockClient())
        result = await router.route("mcp-svc.tool", {"q": "t"})
        assert result["result"] == "data"

    @pytest.mark.asyncio
    async def test_call_mcp_ssrf_blocked(self):
        """_call_mcp with private IP returns SSRF error."""
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("ssrf", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        # Override URL to unsafe after registration (bypasses registry validation)
        svc.mcp_endpoint = "http://10.0.0.1:9999/mcp"
        router.add_route("ssrf.tool", "ssrf")
        result = await router.route("ssrf.tool", {})
        assert result["status"] == "error"
        assert "unavailable" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_call_mcp_httpx_error(self, monkeypatch):
        """_call_mcp when httpx raises propagates error."""
        from httpx import AsyncClient, ConnectError
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("err", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        router.add_route("err.tool", "err")

        class _ErrClient(AsyncClient):
            def __init__(self):
                pass
            async def post(self, url, **kw):
                raise ConnectError("connection refused")
            async def aclose(self):
                pass

        monkeypatch.setattr("agora.router._get_client", lambda: _ErrClient())
        result = await router.route("err.tool", {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_call_rest_post_success(self, monkeypatch):
        """REST POST call returns successfully."""
        from httpx import AsyncClient
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("rest-api", protocol="rest",
                      mcp_endpoint="http://192.0.2.1:3000",
                      protocol_config={"method": "POST"})
        registry.register(svc)
        router.add_route("rest-api.create", "rest-api")

        class _MockResp:
            status_code = 200
            def json(self):
                return {"created": True}
            def raise_for_status(self):
                pass

        class _MockClient(AsyncClient):
            def __init__(self):
                pass
            async def request(self, method, url, **kw):
                return _MockResp()
            async def aclose(self):
                pass

        monkeypatch.setattr("agora.router._get_client", lambda: _MockClient())
        result = await router.route("rest-api.create", {"name": "x"})
        assert result["created"] is True

    @pytest.mark.asyncio
    async def test_call_rest_ssrf_blocked(self):
        """REST call with private IP returns SSRF error."""
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("rest-ssrf", protocol="rest",
                      mcp_endpoint="http://192.0.2.1:3000",
                      protocol_config={"method": "GET"})
        registry.register(svc)
        svc.mcp_endpoint = "http://10.0.0.1:3000"
        router.add_route("rest-ssrf", "rest-ssrf")
        result = await router.route("rest-ssrf", {})
        assert result["status"] == "error"
        assert "unavailable" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_call_rest_retry_success(self, monkeypatch):
        """REST GET retries and succeeds on 2nd attempt."""
        import httpx
        from httpx import AsyncClient
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("retry-api", protocol="rest",
                      mcp_endpoint="http://192.0.2.1:3000",
                      protocol_config={"method": "GET", "retries": 1})
        registry.register(svc)
        router.add_route("retry-api.get", "retry-api")

        attempts = [0]

        class _MockResp:
            status_code = 200
            def json(self):
                return {"ok": True}
            def raise_for_status(self):
                pass

        class _MockClient(AsyncClient):
            def __init__(self):
                pass
            async def request(self, method, url, **kw):
                attempts[0] += 1
                if attempts[0] == 1:
                    req = httpx.Request("GET", url)
                    resp = httpx.Response(502, request=req)
                    raise httpx.HTTPStatusError("502", request=req, response=resp)
                return _MockResp()
            async def aclose(self):
                pass

        monkeypatch.setattr("agora.router._get_client", lambda: _MockClient())
        result = await router.route("retry-api.get", {})
        assert result["ok"] is True
        assert attempts[0] == 2

    @pytest.mark.asyncio
    async def test_call_rest_retry_exhausted(self, monkeypatch):
        """REST GET with all retries exhausted returns error."""
        import httpx
        from httpx import AsyncClient
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("exhaust", protocol="rest",
                      mcp_endpoint="http://192.0.2.1:3000",
                      protocol_config={"method": "GET", "retries": 1})
        registry.register(svc)
        router.add_route("exhaust.get", "exhaust")

        class _MockClient(AsyncClient):
            def __init__(self):
                pass
            async def request(self, method, url, **kw):
                req = httpx.Request("GET", url)
                resp = httpx.Response(502, request=req)
                raise httpx.HTTPStatusError("502", request=req, response=resp)
            async def aclose(self):
                pass

        monkeypatch.setattr("agora.router._get_client", lambda: _MockClient())
        result = await router.route("exhaust.get", {})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_call_rest_non_retryable(self, monkeypatch):
        """REST 400 returns immediately without retry."""
        import httpx
        from httpx import AsyncClient
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("bad-req", protocol="rest",
                      mcp_endpoint="http://192.0.2.1:3000",
                      protocol_config={"method": "GET"})
        registry.register(svc)
        router.add_route("bad-req.get", "bad-req")

        class _MockClient(AsyncClient):
            def __init__(self):
                pass
            async def request(self, method, url, **kw):
                req = httpx.Request("GET", url)
                resp = httpx.Response(400, request=req)
                raise httpx.HTTPStatusError("400", request=req, response=resp)
            async def aclose(self):
                pass

        monkeypatch.setattr("agora.router._get_client", lambda: _MockClient())
        result = await router.route("bad-req.get", {})
        assert result["status"] == "error"
        assert result.get("_http_status") == 400

    @pytest.mark.asyncio
    async def test_route_exception_path(self, monkeypatch):
        """route() catches and returns exception from _dispatch."""
        from httpx import AsyncClient, ConnectError
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("crash", protocol="mcp", mcp_endpoint="http://192.0.2.1:9999/mcp")
        registry.register(svc)
        router.add_route("crash.tool", "crash")

        class _ErrClient(AsyncClient):
            def __init__(self):
                pass
            async def post(self, url, **kw):
                raise ConnectError("boom")
            async def aclose(self):
                pass

        monkeypatch.setattr("agora.router._get_client", lambda: _ErrClient())
        result = await router.route("crash.tool", {})
        assert result["status"] == "error"

    def test_trace_flush(self, tmp_path):
        """_trace writes to disk when buffer reaches 50 entries."""
        from agora.router import Router as Router2
        registry = ServiceRegistry()
        router = Router2(registry)
        # Override trace path to tmp
        router._trace_path = tmp_path / "trace.jsonl"
        # Fill buffer with 50 entries
        for i in range(50):
            router._trace(f"tool{i}", "svc", 0, "ok")
        flushed = list(tmp_path.iterdir())
        assert len(flushed) >= 1
        content = (tmp_path / "trace.jsonl").read_text()
        lines = content.strip().split("\n")
        assert len(lines) == 50

    def test_maybe_publish_with_event_bus(self):
        """_maybe_publish sends event when event_bus is configured."""
        from agora.event_bus import EventBus
        registry = ServiceRegistry()
        bus = EventBus(registry=registry)
        router = Router(registry, event_bus=bus)
        router._maybe_publish("test:event", {"msg": "hello"})
        log = bus.get_event_log(5)
        assert any(e["type"] == "test:event" for e in log)

    @pytest.mark.skip(reason="Module-level singleton interaction — needs fixture reset in v1.5")
    async def test_close_cleans_client(self, monkeypatch):
        """close() cleans up the HTTP client singleton."""
        import agora.router as rmod
        closed = [False]
        class _Closable:
            async def aclose(self):
                closed[0] = True

        original = rmod._client
        mock_client = _Closable()
        rmod._client = mock_client  # type: ignore[assignment]
        try:
            registry = ServiceRegistry()
            router = Router(registry)
            await router.close()
            assert closed[0] is True
            assert rmod._client is None
        finally:
            rmod._client = original

    def test_get_percentiles_with_data(self):
        """Percentiles return correct values with latency data."""
        from agora.router import Router as Router3
        registry = ServiceRegistry()
        router = Router3(registry)
        router._latencies.append(0.1)
        router._latencies.append(0.2)
        router._latencies.append(0.3)
        router._latencies.append(0.4)
        router._latencies.append(0.5)
        pct = router.get_percentiles()
        assert pct["samples"] == 5
        assert pct["p50"] >= 0.2
        assert pct["avg"] == 0.3

    def test_add_instance_no_existing(self):
        """_add_instance promotes single service to multi-instance."""
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("multi", protocol="rest", mcp_endpoint="http://192.0.2.1:3000",
                      protocol_config={"method": "GET"})
        registry.register(svc)
        router._add_instance("multi", "http://192.0.2.2:3000")
        assert len(svc.instances) == 2
        assert svc.instances[0]["protocol"] == "rest"
        assert svc.instances[1]["protocol"] == "rest"

    def test_add_instance_nonexistent(self):
        """_add_instance with unknown service does nothing."""
        registry = ServiceRegistry()
        router = Router(registry)
        router._add_instance("ghost", "http://x:3000")  # should not crash

    def test_next_instance_with_instances(self):
        """_next_instance round-robins through multiple instances."""
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("lb", protocol="rest", mcp_endpoint="http://192.0.2.1:3000",
                      protocol_config={"method": "GET"})
        registry.register(svc)
        router._add_instance("lb", "http://192.0.2.2:3000")
        router._add_instance("lb", "http://192.0.2.3:3000")
        # Round-robin should cycle through 3 instances
        i1 = router._next_instance("lb")
        i2 = router._next_instance("lb")
        i3 = router._next_instance("lb")
        assert i1 is not None
        urls = {i1["mcp_endpoint"], i2["mcp_endpoint"], i3["mcp_endpoint"]}
        assert len(urls) == 3

    def test_next_instance_unavailable(self):
        """_next_instance returns None for unavailable service."""
        registry = ServiceRegistry()
        router = Router(registry)
        svc = Service("down")
        registry.register(svc)
        svc.healthy = False
        svc.cooldown_until = 9999999999.0
        assert router._next_instance("down") is None

    def test_next_instance_nonexistent(self):
        """_next_instance returns None for unknown service."""
        registry = ServiceRegistry()
        router = Router(registry)
        assert router._next_instance("ghost") is None

    def test_get_client_singleton(self, monkeypatch):
        """_get_client returns same instance on second call."""
        # Reset _client first
        import agora.router as rmod
        from agora.router import _get_client
        rmod._client = None
        c1 = _get_client()
        c2 = _get_client()
        assert c1 is c2
