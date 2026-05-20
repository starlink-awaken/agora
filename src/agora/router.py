"""Request Router — routes incoming calls to the correct service.

Phase 3: Load balancing — supports multiple instances per service
with round-robin routing strategy.
"""

from __future__ import annotations

import atexit
import json as _json
import time as _time
from collections import deque
from pathlib import Path as _Path

import httpx
import structlog
from httpx import Limits

from agora.event_bus import EventBus
from agora.registry import ServiceRegistry, _is_safe_url

logger = structlog.get_logger(__name__)

# 连接池单例 — 复用 HTTP 连接，减少开销
_client: httpx.AsyncClient | None = None
# atexit 去重：跟踪所有 Router 实例，确保只注册一次
_routers: list[Router] = []
_atexit_registered = False

def _get_client() -> httpx.AsyncClient:
    """Return the shared httpx AsyncClient singleton."""
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=30, limits=Limits(max_keepalive_connections=20))
    return _client


def _flush_all_routers():
    """Flush trace buffers for all Router instances at exit."""
    import contextlib
    for r in _routers:
        with contextlib.suppress(Exception):
            r._flush_traces()


class Router:
    """Routes tool calls to the appropriate registered service via protocol dispatch.

    Supports:
    - Exact and prefix-based route resolution
    - Circuit breaker awareness (skips OPEN services)
    - Load balancing with round-robin across service instances
    - Multi-protocol dispatch: mcp (implemented), rest/grpc/stdio (reserved)
    - Event bus integration: auto-publishes route:call.succeeded/failed events
    """

    def __init__(self, registry: ServiceRegistry, strategy: str = "round-robin",
                 event_bus: EventBus | None = None,
                 routes_path: str | None = None):
        self.registry = registry
        self._event_bus = event_bus
        self._routes: dict[str, str] = {}  # tool_name → service_name
        self._strategy = strategy
        self._rr_index: dict[str, int] = {}  # service_name → next instance index
        self._latencies: deque[float] = deque(maxlen=1000)  # auto-FIFO truncation
        self._trace_buffer: list[str] = []  # batched disk writes
        self._trace_path = _Path(__file__).parent.parent.parent / "trace_log.jsonl"
        if routes_path:
            self._routes_path = _Path(routes_path)
        else:
            self._routes_path = _Path(registry._storage_path).parent / "agora-routes.json"
        self._load_routes()
        global _routers, _atexit_registered
        _routers.append(self)
        if not _atexit_registered:
            atexit.register(_flush_all_routers)
            _atexit_registered = True

    def _load_routes(self):
        """Load persisted route mappings from JSON file."""
        from agora.persistence import json_load
        data = json_load(self._routes_path, default={})
        self._routes = data.get("routes", {})

    def _save_routes(self):
        """Persist route mappings to JSON file."""
        from agora.persistence import json_save
        json_save(self._routes_path, {"routes": self._routes})

    def add_route(self, tool_name: str, service_name: str):
        """Register a tool → service mapping and persist it."""
        self._routes[tool_name] = service_name
        self._save_routes()

    def resolve(self, tool_name: str) -> str | None:
        """Find which service handles a tool. Supports prefix matching."""
        if tool_name in self._routes:
            return self._routes[tool_name]
        # Prefix match: "minerva.research_now" → try "minerva" prefix
        parts = tool_name.split(".", 1)
        if parts[0] in self._routes:
            return self._routes[parts[0]]
        return None

    def _next_instance(self, service_name: str) -> dict | None:
        """Get the next available instance using current strategy (round-robin).

        Skips services in OPEN circuit state.
        """
        svc = self.registry.get(service_name)
        if not svc:
            return None
        if not svc.is_available:
            return None

        result = {  # single instance mode
            "mcp_endpoint": svc.mcp_endpoint,
            "health_endpoint": svc.health_endpoint,
            "port": svc.port,
            "protocol": svc.protocol,
            "protocol_config": svc.protocol_config,
        }

        # Check if this service has multiple instances
        instances = svc.instances
        if instances:
            idx = self._rr_index.get(service_name, 0)
            instance = instances[idx % len(instances)]
            self._rr_index[service_name] = idx + 1
            result = instance

        return result

    def _add_instance(self, service_name: str, mcp_endpoint: str,
                      health_endpoint: str = "", port: int = 0):
        """Add a load-balanced instance to an existing service."""
        svc = self.registry.get(service_name)
        if not svc:
            return
        if not svc.instances:
            # First instance: promote existing to list
            svc.instances.append({
                "mcp_endpoint": svc.mcp_endpoint,
                "health_endpoint": svc.health_endpoint,
                "port": svc.port,
                "protocol": svc.protocol,
                "protocol_config": svc.protocol_config,
            })
        svc.instances.append({
            "mcp_endpoint": mcp_endpoint,
            "health_endpoint": health_endpoint or "",
            "port": port or 0,
            "protocol": svc.protocol,
            "protocol_config": svc.protocol_config,
        })

    async def _dispatch(self, tool_name: str, arguments: dict,
                         instance: dict) -> dict:
        """Dispatch a tool call via the service's protocol.

        Extension point: add new protocol handlers here.
        Currently only MCP is fully implemented; rest/grpc/websocket are reserved.
        """
        protocol = instance.get("protocol", "mcp")

        if protocol == "mcp":
            return await self._call_mcp(tool_name, arguments, instance["mcp_endpoint"])
        elif protocol == "rest":
            return await self._call_rest(tool_name, arguments, instance)
        elif protocol == "grpc":
            return await self._call_grpc(tool_name, arguments, instance)
        elif protocol == "websocket":
            return await self._call_ws(tool_name, arguments, instance)
        elif protocol == "stdio":
            return {"status": "error", "error": "stdio protocol uses proxy, not router"}
        else:
            return {"status": "error", "error": f"Unknown protocol: {protocol}"}

    async def _call_mcp(self, tool_name: str, arguments: dict, mcp_endpoint: str) -> dict:
        """Execute an MCP tools/call request against the target endpoint."""
        if mcp_endpoint.startswith("http") and not _is_safe_url(mcp_endpoint):
            logger.warning("ssrf_blocked", tool=tool_name, url=mcp_endpoint)
            return {"status": "error", "error": "Service unavailable"}

        client = _get_client()
        resp = await client.post(
            mcp_endpoint,
            json={"method": "tools/call", "params": {"name": tool_name, "arguments": arguments}},
        )
        resp.raise_for_status()
        return resp.json()

    async def _call_rest(self, tool_name: str, arguments: dict, instance: dict) -> dict:
        """Execute a REST API call against the target endpoint.

        Uses protocol_config for method, path, headers. Defaults to GET with
        tool_name-derived path suffix and query params from arguments.
        Supports automatic retry for GET/HEAD methods (max 2 retries by default).
        """
        base_url = instance["mcp_endpoint"].rstrip("/")
        cfg = instance.get("protocol_config", {})

        if base_url.startswith("http") and not _is_safe_url(base_url):
            logger.warning("ssrf_blocked", tool=tool_name, url=base_url)
            return {"status": "error", "error": "Service unavailable"}

        # Resolve path: cfg path > tool_name-derived path
        path = cfg.get("path", "")
        if not path:
            parts = tool_name.split(".", 1)
            path = "/" + (parts[1] if len(parts) > 1 else parts[0])

        method = cfg.get("method", "GET").upper()
        headers = cfg.get("headers", {})
        url = f"{base_url}{path}"

        # 重试配置：仅 GET/HEAD 支持重试，protocol_config 可覆盖 retries
        max_retries = cfg.get("retries", 2) if method in ("GET", "HEAD") else 0

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                client = _get_client()
                if method in ("POST", "PUT", "PATCH"):
                    resp = await client.request(method, url, json=arguments, headers=headers)
                else:  # GET, DELETE, HEAD, etc.
                    resp = await client.request(method, url, params=arguments, headers=headers)

                # Try JSON first, fall back to text
                try:
                    body = resp.json()
                except Exception:
                    body = {"_body": resp.text[:2000]}
                body["_http_status"] = resp.status_code
                resp.raise_for_status()
                return body
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                # 仅对可重试状态码重试
                if attempt < max_retries and status in (408, 429, 500, 502, 503, 504):
                    last_error = e
                    continue
                return {"status": "error", "_http_status": status, "error": str(e)[:200]}
            except Exception as e:
                if attempt < max_retries:
                    last_error = e
                    continue
                return {"status": "error", "error": f"REST call failed: {str(e)[:200]}"}

        return {"status": "error",
                "error": f"REST call failed after {max_retries + 1} attempts: {str(last_error)[:200]}"}

    async def _call_grpc(self, tool_name: str, arguments: dict, instance: dict) -> dict:
        """Execute a gRPC call. Uses protocol_config for proto file and method."""
        proto_file = instance.get("protocol_config", {}).get("proto_file", "")
        grpc_method = instance.get("protocol_config", {}).get("grpc_method", tool_name)
        return {"status": "error",
                "error": f"gRPC call not yet supported (proto={proto_file}, method={grpc_method}). "
                         "Install grpcio and compile proto to enable."}

    async def _call_ws(self, tool_name: str, arguments: dict, instance: dict) -> dict:
        """Execute a WebSocket call. Uses protocol_config for ws:// endpoint."""
        ws_url = instance["mcp_endpoint"]
        if not ws_url.startswith(("ws://", "wss://")):
            return {"status": "error", "error": "Invalid WebSocket URL"}
        return {"status": "error",
                "error": "WebSocket bidirectional streaming not yet supported. "
                         "Use REST or MCP for request-response patterns."}

    async def route(self, tool_name: str, arguments: dict) -> dict:
        """Route a tool call to the target service via protocol dispatch."""
        _start = _time.monotonic()

        service_name = self.resolve(tool_name)
        if not service_name:
            self._trace(tool_name, service_name or "unknown", _start, "error", "not_found")
            logger.warning("route_not_found", tool=tool_name)
            return {"status": "error", "error": "Tool not available"}

        instance = self._next_instance(service_name)
        if not instance:
            self._trace(tool_name, service_name, _start, "error", "no_instance")
            return {"status": "error", "error": "Service temporarily unavailable"}

        try:
            result = await self._dispatch(tool_name, arguments, instance)
            if result.get("status") == "error":
                self._trace(tool_name, service_name, _start, "error", result.get("error", "")[:100])
                logger.warning("route_dispatch_failed", tool=tool_name, service=service_name,
                               error=result.get("error", ""))
                self.registry.mark_failure(service_name)
                self._maybe_publish("route:call.failed", {
                    "tool": tool_name, "service": service_name,
                    "error": result.get("error", "")[:100],
                })
            else:
                self.registry.mark_success(service_name)
                self._trace(tool_name, service_name, _start, "ok")
                self._maybe_publish("route:call.succeeded", {
                    "tool": tool_name, "service": service_name,
                    "duration_s": round(_time.monotonic() - _start, 4),
                })
            return result
        except Exception as e:
            self._trace(tool_name, service_name, _start, "error", str(e)[:100])
            logger.warning("route_failed", tool=tool_name, service=service_name, error=str(e))
            self.registry.mark_failure(service_name)
            self._maybe_publish("route:call.failed", {
                "tool": tool_name, "service": service_name,
                "error": str(e)[:100],
            })
            return {"status": "error", "error": "Routing failed"}

    def _maybe_publish(self, event_type: str, payload: dict):
        """Publish route event if event_bus is configured."""
        if self._event_bus:
            self._event_bus.publish(event_type, payload, "agora-router")

    def _trace(self, tool: str, service: str, start: float, status: str, detail: str = ""):
        """Buffer trace entry; flush to disk every 50 calls."""
        elapsed = round(_time.monotonic() - start, 4)

        if status == "ok":
            self._latencies.append(elapsed)

        entry = _json.dumps({
            "time": _time.time(),
            "tool": tool, "service": service, "status": status,
            "elapsed_s": elapsed, "detail": detail,
        })
        self._trace_buffer.append(entry)
        if len(self._trace_buffer) >= 50:
            self._flush_traces()

    def _flush_traces(self):
        """Write buffered traces to disk."""
        if not self._trace_buffer:
            return
        try:
            with open(self._trace_path, "a") as f:
                f.write("\n".join(self._trace_buffer) + "\n")
            self._trace_buffer.clear()
        except Exception:
            pass

    def get_percentiles(self) -> dict:
        """Calculate P50/P90/P99 from rolling latency window."""
        if not self._latencies:
            return {"p50": 0, "p90": 0, "p99": 0, "samples": 0, "avg": 0}
        sorted_l = sorted(self._latencies)
        n = len(sorted_l)
        return {
            "p50": round(sorted_l[int(n * 0.50)], 4),
            "p90": round(sorted_l[int(n * 0.90)], 4),
            "p99": round(sorted_l[min(int(n * 0.99), n - 1)], 4),
            "samples": n,
            "avg": round(sum(sorted_l) / n, 4),
        }

    def list_routes(self) -> dict[str, str]:
        return dict(self._routes)

    async def close(self):
        """Clean up the shared HTTP client connection pool."""
        global _client
        if _client:
            await _client.aclose()
            _client = None
