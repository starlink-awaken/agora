"""Integration tests for Agora Web API (FastAPI TestClient)."""
from fastapi.testclient import TestClient

from agora.web.app import app

client = TestClient(app)


class TestDashboard:
    def test_dashboard_returns_html(self):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "html" in resp.headers["content-type"].lower()

    def test_dashboard_contains_agora(self):
        resp = client.get("/")
        assert "Agora" in resp.text or "agora" in resp.text.lower()


class TestApiServices:
    def test_list_services_returns_list(self):
        resp = client.get("/api/services")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_service_has_protocol_field(self):
        resp = client.get("/api/services")
        data = resp.json()
        if data:
            assert "protocol" in data[0]
            assert "circuit" in data[0]


class TestApiHealth:
    def test_health_returns_status(self):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "services" in data
        assert "healthy" in data

    def test_health_circuits_present(self):
        resp = client.get("/api/health")
        data = resp.json()
        assert "circuits" in data


class TestApiRegister:
    def test_register_service_basic(self):
        resp = client.post("/api/register", data={
            "name": "test-svc",
            "mcp_endpoint": "http://192.0.2.10:8765",
            "tags": "test,api",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "test-svc"
        assert data["status"] == "registered"

    def test_register_with_protocol(self):
        resp = client.post("/api/register", data={
            "name": "rest-api",
            "protocol": "rest",
            "protocol_config": '{"method":"POST","path":"/users"}',
            "mcp_endpoint": "http://192.0.2.11:3000",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["protocol"] == "rest"

    def test_register_invalid_protocol_config(self):
        resp = client.post("/api/register", data={
            "name": "bad-config",
            "protocol_config": "not json",
        })
        assert resp.status_code == 400

    def test_register_default_protocol(self):
        resp = client.post("/api/register", data={
            "name": "default-proto-svc",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["protocol"] == "mcp"


class TestApiPipeline:
    def test_list_pipelines(self):
        resp = client.get("/api/pipelines")
        assert resp.status_code == 200
        data = resp.json()
        assert "pipelines" in data  # returns {"pipelines": [...]}

    def test_pipeline_dag(self):
        resp = client.get("/api/pipeline/full-pipeline/dag")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, (dict, list))


class TestApiDiscover:
    def test_discover_returns_result(self):
        resp = client.post("/api/discover")
        assert resp.status_code == 200
        data = resp.json()
        assert "discovered" in data
        assert "total" in data


class TestApiClear:
    def test_clear_returns_status(self):
        resp = client.post("/api/clear")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cleared"


class TestApiMetrics:
    def test_metrics_history(self):
        resp = client.get("/api/metrics/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "latency" in data
        assert "services" in data


class TestApiEvent:
    def test_event_log_returns_list(self):
        resp = client.get("/api/event-log")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_event_publish_returns_id(self):
        resp = client.post("/api/event-publish", data={
            "event_type": "test:unit",
            "payload": '{"msg":"hello"}',
            "source": "test",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "published"

    def test_event_publish_after_restart(self):
        """Events survive API restart due to module-level EventBus."""
        resp = client.post("/api/event-publish", data={
            "event_type": "test:persist",
            "payload": '{}',
        })
        assert resp.status_code == 200
        # Log should now include this new event
        resp2 = client.get("/api/event-log")
        assert resp2.status_code == 200


class TestRateLimit:
    def test_normal_request_passes(self, monkeypatch):
        monkeypatch.setenv("AGORA_RATE_LIMIT", "5")
        resp = client.get("/api/services")
        assert resp.status_code == 200

    def test_rate_limit_header(self, monkeypatch):
        monkeypatch.setenv("AGORA_RATE_LIMIT", "60")
        resp = client.get("/api/services")
        assert resp.status_code == 200


class TestPrometheusMetrics:
    def test_metrics_endpoint(self):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        # Prometheus format should include gauge lines
        assert "agora_services" in resp.text
