"""Tests for Agora service registry."""
import tempfile
from pathlib import Path

import pytest

from agora.registry import (
    KNOWN_PROTOCOLS,
    Service,
    ServiceRegistry,
    _parse_protocol_config,
    _parse_tags,
)


def _new_registry():
    """Create a fresh registry with temp storage (no persistence cross-contamination)."""
    return ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))


class TestParseTags:
    def test_single_tag(self):
        assert _parse_tags("research") == ["research"]

    def test_multiple_tags(self):
        assert _parse_tags("research, search,knowledge") == ["research", "search", "knowledge"]

    def test_empty(self):
        assert _parse_tags("") == []

    def test_whitespace_only(self):
        assert _parse_tags("  ,  , ") == []


class TestParseProtocolConfig:
    def test_dict_passthrough(self):
        cfg, err = _parse_protocol_config({"key": "val"})
        assert cfg == {"key": "val"}
        assert err is None

    def test_valid_json(self):
        cfg, err = _parse_protocol_config('{"method":"GET"}')
        assert cfg == {"method": "GET"}
        assert err is None

    def test_invalid_json(self):
        cfg, err = _parse_protocol_config("not json")
        assert cfg == {}
        assert err is not None

    def test_empty_default(self):
        cfg, err = _parse_protocol_config("{}")
        assert cfg == {}
        assert err is None


class TestKnownProtocols:
    def test_all_known(self):
        assert "mcp" in KNOWN_PROTOCOLS
        assert "rest" in KNOWN_PROTOCOLS
        assert "grpc" in KNOWN_PROTOCOLS
        assert "stdio" in KNOWN_PROTOCOLS
        assert "websocket" in KNOWN_PROTOCOLS

    def test_is_frozenset(self):
        assert isinstance(KNOWN_PROTOCOLS, frozenset)


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

    def test_default_protocol(self):
        s = Service("test")
        assert s.protocol == "mcp"
        assert s.protocol_config == {}

    def test_rest_protocol(self):
        s = Service("my-api", protocol="rest", protocol_config={"method": "POST"})
        assert s.protocol == "rest"
        assert s.protocol_config == {"method": "POST"}

    def test_to_dict_includes_protocol(self):
        s = Service("test", protocol="rest", protocol_config={"path": "/api"})
        d = s.to_dict()
        assert d["protocol"] == "rest"
        assert d["protocol_config"] == {"path": "/api"}


class TestServiceRegistry:
    def test_register_and_get(self):
        r = _new_registry()
        r.register(Service("minerva", port=8765))
        r.register(Service("sophia", port=9001))
        assert len(r.list_all()) == 2
        assert r.get("minerva").port == 8765
        assert r.get("nonexistent") is None

    def test_list_healthy(self):
        r = _new_registry()
        r.register(Service("minerva", port=8765))
        r.register(Service("sophia", port=9001))
        assert len(r.list_healthy()) == 2
        r.mark_failure("minerva")
        r.mark_failure("minerva")
        r.mark_failure("minerva")
        assert len(r.list_healthy()) == 1

    def test_mark_success_recovery(self):
        r = _new_registry()
        r.register(Service("test"))
        r.mark_failure("test")
        r.mark_failure("test")
        r.mark_failure("test")
        assert not r.get("test").is_available
        r.mark_success("test")
        r.mark_success("test")
        r.mark_success("test")
        assert r.get("test").is_available  # 3 successes gradually decay to 0

    def test_unregister(self):
        r = _new_registry()
        r.register(Service("test"))
        r.unregister("test")
        assert r.get("test") is None

    def test_to_dict(self):
        r = _new_registry()
        r.register(Service("minerva", mcp_endpoint="http://192.0.2.1:8765"))
        d = r.to_dict()
        assert len(d) == 1
        assert d[0]["name"] == "minerva"
        assert "healthy" in d[0]

    def test_register_valid_protocol(self):
        r = _new_registry()
        r.register(Service("api", protocol="rest", mcp_endpoint="http://192.0.2.1:3000"))
        assert r.get("api").protocol == "rest"

    def test_register_invalid_protocol(self):
        r = _new_registry()
        with pytest.raises(ValueError, match="Unknown protocol"):
            r.register(Service("bad", protocol="invalid_proto"))

    def test_clear_all(self):
        r = _new_registry()
        r.register(Service("a"))
        r.register(Service("b"))
        r.register(Service("c"))
        count = r.clear_all()
        assert count == 3
        assert r.list_all() == []
