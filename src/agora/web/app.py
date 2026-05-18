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

import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from agora.discovery import DiscoveryEngine
from agora.pipeline import Pipeline
from agora.registry import Service, ServiceRegistry
from agora.router import Router

app = FastAPI(title="Agora Dashboard", version="1.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

registry = ServiceRegistry()
router = Router(registry)
discovery = DiscoveryEngine()

_DASHBOARD_HTML = (Path(__file__).parent / "dashboard.html").read_text()


# ── Pages ──────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return _DASHBOARD_HTML


# ── API ────────────────────────────────────────────────────────

@app.get("/api/services")
async def api_services():
    return [
        {
            "name": s.name, "description": s.description,
            "circuit": s.circuit_state, "healthy": s.healthy,
            "failure_count": s.failure_count, "port": s.port,
            "tags": s.tags,
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


@app.get("/api/pipelines")
async def api_pipelines():
    pl = Pipeline(registry, router)
    return {"pipelines": pl.list_pipelines()}


@app.post("/api/pipeline")
async def api_run_pipeline(
    name: str = Form(...),
    goal: str = Form(""),
    context: str = Form(""),
    project: str = Form("."),
    mode: str = Form("sequential"),
):
    pl = Pipeline(registry, router)
    variables = {"goal": goal, "context": context, "project": project}

    start = time.monotonic()
    if mode == "parallel":
        result = await pl.run_parallel(name, variables)
    else:
        result = await pl.run(name, variables)
    elapsed = time.monotonic() - start

    return {"pipeline": name, "mode": mode, "elapsed_s": round(elapsed, 3), **result}


@app.post("/api/clear")
async def api_clear():
    for s in list(registry.list_all()):
        registry.unregister(s.name)
    return {"status": "cleared"}


# ── CLI entry ──────────────────────────────────────────────────

def main():
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7430, log_level="info")


if __name__ == "__main__":
    main()
