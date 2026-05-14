"""Service Registry — the single source of truth for all connected services."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class Service:
    """A registered MCP-capable service."""
    name: str
    description: str = ""
    mcp_endpoint: str = ""       # MCP server address (URL or CLI command)
    health_endpoint: str = ""    # GET /health endpoint
    port: int = 0
    tags: list[str] = field(default_factory=list)
    # Runtime state
    healthy: bool = True
    last_health_check: float = 0.0
    failure_count: int = 0
    cooldown_until: float = 0.0   # Circuit breaker cooldown

    @property
    def is_available(self) -> bool:
        return self.healthy and time.monotonic() >= self.cooldown_until

    def to_dict(self) -> dict:
        return {
            "name": self.name, "description": self.description,
            "healthy": self.is_available, "endpoint": self.mcp_endpoint,
            "port": self.port, "tags": self.tags,
        }


class ServiceRegistry:
    """Central registry for all Agora-connected services.

    Services register themselves (or are configured statically).
    The registry is the only place that knows the full topology.
    """

    def __init__(self):
        self._services: dict[str, Service] = {}

    def register(self, service: Service):
        self._services[service.name] = service

    def unregister(self, name: str):
        self._services.pop(name, None)

    def get(self, name: str) -> Service | None:
        return self._services.get(name)

    def list_all(self) -> list[Service]:
        return list(self._services.values())

    def list_healthy(self) -> list[Service]:
        return [s for s in self._services.values() if s.is_available]

    def mark_failure(self, name: str):
        svc = self._services.get(name)
        if svc:
            svc.failure_count += 1
            if svc.failure_count >= 3:
                svc.cooldown_until = time.monotonic() + 60
                svc.healthy = False

    def mark_success(self, name: str):
        svc = self._services.get(name)
        if svc:
            svc.failure_count = 0
            svc.healthy = True
            svc.cooldown_until = 0.0

    def to_dict(self) -> list[dict]:
        return [s.to_dict() for s in self._services.values()]

    async def health_check_all(self):
        """Probe all registered services' health endpoints."""
        import httpx
        for svc in self._services.values():
            if not svc.health_endpoint:
                continue
            try:
                async with httpx.AsyncClient(timeout=5) as c:
                    r = await c.get(svc.health_endpoint)
                    svc.healthy = r.status_code == 200
                    svc.last_health_check = time.monotonic()
                    if svc.healthy:
                        self.mark_success(svc.name)
                    else:
                        self.mark_failure(svc.name)
            except Exception:
                self.mark_failure(svc.name)
