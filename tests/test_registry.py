"""Tests for Agora service registry."""
from agora.registry import ServiceRegistry, Service


class TestService:
    def test_service_creation(self):
        s = Service("minerva", mcp_endpoint="http://192.0.2.1:8765", port=8765)
        assert s.name == "minerva"
        assert s.healthy is True
        assert s.is_available is True

    def test_circuit_breaker(self):
        s = Service("test")
        s.failure_count = 2
        assert s.is_available is True
        s.failure_count = 3
        s.healthy = False
        s.cooldown_until = 9999999999.0
        assert s.is_available is False


class TestServiceRegistry:
    def test_register_and_get(self):
        r = ServiceRegistry()
        r.register(Service("minerva", port=8765))
        r.register(Service("sophia", port=9001))
        assert len(r.list_all()) == 2
        assert r.get("minerva").port == 8765
        assert r.get("nonexistent") is None

    def test_list_healthy(self):
        r = ServiceRegistry()
        r.register(Service("minerva", port=8765))
        r.register(Service("sophia", port=9001))
        assert len(r.list_healthy()) == 2
        r.mark_failure("minerva"); r.mark_failure("minerva"); r.mark_failure("minerva")
        assert len(r.list_healthy()) == 1

    def test_mark_success_recovery(self):
        r = ServiceRegistry()
        r.register(Service("test"))
        r.mark_failure("test"); r.mark_failure("test"); r.mark_failure("test")
        assert not r.get("test").is_available
        r.mark_success("test")
        assert r.get("test").is_available

    def test_unregister(self):
        r = ServiceRegistry()
        r.register(Service("test"))
        r.unregister("test")
        assert r.get("test") is None

    def test_to_dict(self):
        r = ServiceRegistry()
        r.register(Service("minerva", mcp_endpoint="http://192.0.2.1:8765"))
        d = r.to_dict()
        assert len(d) == 1
        assert d[0]["name"] == "minerva"
        assert "healthy" in d[0]
