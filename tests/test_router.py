"""Tests for Agora request router."""
from agora.registry import ServiceRegistry, Service
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
