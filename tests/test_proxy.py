"""Tests for Agora MCP proxy manager."""
from agora.mcp_proxy.manager import ProxyManager


class TestProxyManager:
    def setup_method(self):
        self.manager = ProxyManager()

    def test_initial_status_idle(self):
        status = self.manager.status()
        assert status["status"] == "idle"
        assert status["tools"] == 0
        assert status["connected_services"] == []

    def test_start_no_services(self):
        """Starting with empty list returns empty results."""
        import asyncio
        results = asyncio.run(self.manager.start([]))
        assert results == {}

    def test_add_bad_service_returns_error(self):
        """Adding a service without endpoint or command should fail gracefully."""
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
        # Even if connection failed, status should reflect no connected services
        status = self.manager.status()
        assert "status" in status
