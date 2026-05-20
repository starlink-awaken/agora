"""Agora Web Dashboard — FastAPI server with embedded UI.

Start: agora web
Access: http://localhost:7430

Features:
- Service status overview (circuit breaker states)
- Quick actions (discover, health check, register)
- Pipeline runner
- JSON API for programmatic access
- WebSocket real-time push (/ws)
"""

from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from prometheus_client import REGISTRY, Gauge, generate_latest

from agora.discovery import DiscoveryEngine
from agora.event_bus import EventBus
from agora.pipeline import Pipeline
from agora.registry import Service, ServiceRegistry, _is_safe_url, _parse_protocol_config, _parse_tags
from agora.router import Router

API_KEY = os.environ.get("AGORA_API_KEY", "")


async def _auth_middleware(request: Request, call_next):
    """Simple API Key auth for write endpoints."""
    if request.method in ("GET", "OPTIONS") or not API_KEY:
        return await call_next(request)
    key = request.headers.get("X-API-Key", "")
    if key != API_KEY:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    yield
    await router.close()


app = FastAPI(title="Agora Dashboard", version="1.4.0", lifespan=_lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7430", "http://127.0.0.1:7430"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.middleware("http")(_auth_middleware)

# Rate limiting — simple sliding window per IP (max 60 req/min)
_rate_limits: dict[str, list[float]] = {}
_RATE_LIMIT_MAX = int(os.environ.get("AGORA_RATE_LIMIT", "60"))
_RATE_LIMIT_WINDOW = 60.0  # seconds
_RATE_LIMIT_CLEANUP_AT = 500  # entries before cleanup


async def _rate_limit_middleware(request: Request, call_next):
    if _RATE_LIMIT_MAX <= 0:
        return await call_next(request)
    client = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _rate_limits.setdefault(client, [])
    window[:] = [t for t in window if now - t < _RATE_LIMIT_WINDOW]
    if len(window) >= _RATE_LIMIT_MAX:
        return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)
    window.append(now)
    # Periodic cleanup
    if len(_rate_limits) > _RATE_LIMIT_CLEANUP_AT:
        for k in list(_rate_limits):
            _rate_limits[k] = [t for t in _rate_limits.get(k, []) if now - t < _RATE_LIMIT_WINDOW]
            if not _rate_limits[k]:
                del _rate_limits[k]
    return await call_next(request)


app.middleware("http")(_rate_limit_middleware)

registry = ServiceRegistry()
_bus = EventBus(registry=registry)
router = Router(registry, event_bus=_bus)
discovery = DiscoveryEngine()
pipeline = Pipeline(registry, router)



def _get_dashboard_html() -> str:
    """Lazy-load dashboard HTML to avoid import-time crash if file missing."""
    html_path = Path(__file__).parent / "dashboard.html"
    if html_path.exists():
        return html_path.read_text()
    return "<html><body><h1>Dashboard not found</h1><p>Run: agora web</p></body></html>"

# Prometheus gauges — created once at module level (not per scrape)
_METRIC_SVC_TOTAL = Gauge("agora_services_total", "Total registered services", registry=REGISTRY)
_METRIC_SVC_HEALTHY = Gauge("agora_services_healthy", "Healthy services", registry=REGISTRY)
_METRIC_SVC_DEGRADED = Gauge("agora_services_degraded", "Degraded/offline services", registry=REGISTRY)


# ── Pages ──────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return _get_dashboard_html()


# ── WebSocket ──────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            svcs = registry.list_all()
            data = {
                "services": [
                    {
                        "name": s.name, "circuit": s.circuit_state, "healthy": s.healthy,
                        "failure_count": s.failure_count, "protocol": s.protocol,
                    }
                    for s in svcs
                ],
                "healthy": len(registry.list_healthy()),
                "total": len(svcs),
            }
            await websocket.send_json(data)
            await asyncio.sleep(2)
    except Exception:
        pass


# ── API ────────────────────────────────────────────────────────

@app.get("/api/services")
async def api_services():
    return [
        {
            "name": s.name, "description": s.description,
            "protocol": s.protocol, "protocol_config": s.protocol_config,
            "mcp_endpoint": s.mcp_endpoint, "health_endpoint": s.health_endpoint,
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
    protocol: str = Form("mcp"),
    protocol_config: str = Form("{}"),
    mcp_endpoint: str = Form(""),
    health_endpoint: str = Form(""),
    port: int = Form(0),
    tags: str = Form(""),
):
    # Parse protocol config JSON
    proto_cfg, err = _parse_protocol_config(protocol_config)
    if err:
        return JSONResponse({"status": "error", "error": f"protocol_config is not valid JSON: {err}"}, status_code=400)

    svc = Service(
        name=name, protocol=protocol, protocol_config=proto_cfg,
        mcp_endpoint=mcp_endpoint, health_endpoint=health_endpoint, port=port,
        tags=_parse_tags(tags),
    )
    registry.register(svc)
    return {"status": "registered", "name": name, "protocol": protocol}


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
    count = registry.clear_all()
    return {"status": "cleared", "removed": count}


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


@app.get("/api/event-log")
async def api_event_log(limit: int = 20):
    """Return recent events from the event bus."""
    return _bus.get_event_log(limit)


@app.post("/api/event-publish")
async def api_event_publish(
    event_type: str = Form(...),
    payload: str = Form("{}"),
    source: str = Form("dashboard"),
):
    """Publish an event via the web dashboard."""
    import json as _json

    try:
        data = _json.loads(payload)
    except _json.JSONDecodeError:
        data = {"raw": payload}
    eid = _bus.publish(event_type, data, source)
    return {"event_id": eid, "status": "published"}


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
