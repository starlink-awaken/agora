"""Tests for Agora request router."""
from agora.registry import Service, ServiceRegistry
from agora.router import Router


class TestRouter:
    def setup_method(self):
        self.registry = ServiceRegistry()
        self.registry.register(Service("minerva", mcp_endpoint="http://192.0.2.1:8765"))
        self.registry.register(Service("sophia", mcp_endpoint="http://192.0.2.2:9001"))
        self.router = Router(self.registry)

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
