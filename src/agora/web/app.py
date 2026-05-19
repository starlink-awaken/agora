"""Agora Web Dashboard — FastAPI server with embedded UI.

Start: agora web
Access: http://localhost:7430

Features:
- Service status overview (circuit breaker states)
- Quick actions (discover, health check, register)
- Pipeline runner
- JSON API for programmatic access
"""

from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from agora.discovery import DiscoveryEngine
from agora.pipeline import Pipeline
import os

from fastapi import Request
from fastapi.responses import JSONResponse

from agora.registry import Service, ServiceRegistry, _is_safe_url

API_KEY = os.environ.get("AGORA_API_KEY", "")


async def _auth_middleware(request: Request, call_next):
    """Simple API Key auth for write endpoints."""
    if request.method in ("GET", "OPTIONS") or not API_KEY:
        return await call_next(request)
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)


from agora.router import Router

app = FastAPI(title="Agora Dashboard", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:7430", "http://127.0.0.1:7430"], allow_methods=["GET", "POST"], allow_headers=["*"])
app.middleware("http")(_auth_middleware)

registry = ServiceRegistry()
router = Router(registry)
discovery = DiscoveryEngine()
pipeline = Pipeline(registry, router)

def _get_dashboard_html() -> str:
    """Lazy-load dashboard HTML to avoid import-time crash if file missing."""
    html_path = Path(__file__).parent / "dashboard.html"
    if html_path.exists():
        return html_path.read_text()
    return "<html><body><h1>Dashboard not found</h1><p>Run: agora web</p></body></html>"

# Prometheus gauges — created once at module level (not per scrape)
from prometheus_client import Gauge, generate_latest, REGISTRY
_METRIC_SVC_TOTAL = Gauge("agora_services_total", "Total registered services", registry=REGISTRY)
_METRIC_SVC_HEALTHY = Gauge("agora_services_healthy", "Healthy services", registry=REGISTRY)
_METRIC_SVC_DEGRADED = Gauge("agora_services_degraded", "Degraded/offline services", registry=REGISTRY)


# ── Pages ──────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _get_dashboard_html()


# ── API ────────────────────────────────────────────────────────

@app.get("/api/services")
async def api_services():
    return [
        {
            "name": s.name, "description": s.description,
            "circuit": s.circuit_state, "healthy": s.healthy,
            "failure_count": s.failure_count, "port": s.port,
            "tags": s.tags, "instances": len(s.instances) + 1,
        }
        for s in registry.list_all()
    ]


@app.get("/api/health")
async def api_health():
    await registry.health_check_all()
    healthy = registry.list_healthy()
    return {
        "status": "ok",
        "services": len(registry.list_all()),
        "healthy": len(healthy),
        "circuits": {
            s.name: registry.get_circuit_status(s.name)
            for s in registry.list_all()
        },
    }


@app.get("/api/pipeline/{name}/dag")
async def api_pipeline_dag(name: str):
    """Return pipeline dependency graph as node/edge data."""
    steps = pipeline.get_pipeline(name)
    if not steps:
        return {"error": f"Pipeline not found: {name}"}
    nodes = []
    edges = []
    for i, step in enumerate(steps):
        node_id = f"step_{i}"
        tool = step["tool"]
        label = step.get("output_as", f"Step {i+1}")
        deps = step.get("depends_on", [])
        nodes.append({"id": node_id, "label": label, "tool": tool, "index": i})
        for dep in deps:
            # Find which step produces this dependency
            for j, s in enumerate(steps):
                if s.get("output_as") == dep:
                    edges.append({"source": f"step_{j}", "target": node_id, "label": dep})
                    break
    return {"name": name, "nodes": nodes, "edges": edges}


@app.get("/api/pipelines")
async def api_pipelines():
    """List all available pipeline names."""
    return {"pipelines": pipeline.list_pipelines()}


@app.post("/api/discover")
async def api_discover():
    count = discovery.auto_register(registry)
    return {"discovered": count, "total": len(registry.list_all())}


@app.post("/api/register")
async def api_register(
    name: str = Form(...),
    mcp_endpoint: str = Form(""),
    health_endpoint: str = Form(""),
    port: int = Form(0),
    tags: str = Form(""),
):
    svc = Service(
        name=name, mcp_endpoint=mcp_endpoint,
        health_endpoint=health_endpoint, port=port,
        tags=[t.strip() for t in tags.split(",") if t.strip()],
    )
    registry.register(svc)
    return {"status": "registered", "name": name}


@app.post("/api/pipeline")
async def api_run_pipeline(
    name: str = Form(...),
    goal: str = Form(""),
    context: str = Form(""),
    project: str = Form("."),
    mode: str = Form("sequential"),
):
    variables = {"goal": goal, "context": context, "project": project}

    start = time.monotonic()
    if mode == "parallel":
        result = await pipeline.run_parallel(name, variables)
    else:
        result = await pipeline.run(name, variables)
    elapsed = time.monotonic() - start

    return {"pipeline": name, "mode": mode, "elapsed_s": round(elapsed, 3), **result}


@app.post("/api/clear")
async def api_clear():
    for s in list(registry.list_all()):
        registry.unregister(s.name)
    return {"status": "cleared"}


@app.post("/api/instance")
async def api_add_instance(data: dict):
    """Add a load-balanced instance to a service."""
    svc_name = data.get("service", "")
    mcp_endpoint = data.get("mcp_endpoint", "")
    if not svc_name or not mcp_endpoint:
        return {"status": "error", "error": "service and mcp_endpoint required"}
    # P1: Validate URL against SSRF before adding instance
    if mcp_endpoint.startswith("http") and not _is_safe_url(mcp_endpoint):
        return {"status": "error", "error": "MCP endpoint URL blocked by SSRF policy"}
    router._add_instance(svc_name, mcp_endpoint)
    return {"status": "ok", "service": svc_name, "instance": mcp_endpoint}


@app.get("/api/metrics/history")
async def api_metrics_history():
    """Return P50/P90/P99 latency history for dashboards."""
    pct = router.get_percentiles()
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "latency": pct,
        "services": len(registry.list_all()),
        "healthy": len(registry.list_healthy()),
    }


@app.get("/metrics")
async def api_metrics():
    """Prometheus-compatible metrics endpoint."""
    total = len(registry.list_all())
    healthy = len(registry.list_healthy())

    _METRIC_SVC_TOTAL.set(total)
    _METRIC_SVC_HEALTHY.set(healthy)
    _METRIC_SVC_DEGRADED.set(total - healthy)

    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(content=generate_latest(REGISTRY), media_type="text/plain; version=0.0.4")


# ── CLI entry ──────────────────────────────────────────────────

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7430, log_level="info")


if __name__ == "__main__":
    main()
