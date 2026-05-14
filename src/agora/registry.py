"""Service Registry — the single source of truth for all connected services."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal"})
BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"), ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"), ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("100.64.0.0/10"), ipaddress.ip_network("fc00::/7"),
]


def _is_safe_url(url: str) -> bool:
    """Validate URL does not target internal/private network resources."""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        return False
    if hostname.lower() in BLOCKED_HOSTS:
        return False
    try:
        ip = ipaddress.ip_address(hostname)
        return not any(ip in net for net in BLOCKED_NETWORKS)
    except ValueError:
        pass
    try:
        resolved = socket.gethostbyname(hostname)
        ip = ipaddress.ip_address(resolved)
        return not any(ip in net for net in BLOCKED_NETWORKS)
    except Exception:
        return False
    return True


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

    _MAX_SERVICES = 50
    _HEALTH_COOLDOWN = 10.0  # min seconds between full health checks
    _MAX_CONCURRENT_CHECKS = 10

    def __init__(self):
        self._services: dict[str, Service] = {}
        self._last_health_check: float = 0.0

    def register(self, service: Service):
        if len(self._services) >= self._MAX_SERVICES:
            raise ValueError(f"Service limit reached ({self._MAX_SERVICES})")
        # Validate URLs on registration
        if service.health_endpoint and not _is_safe_url(service.health_endpoint):
            raise ValueError(f"Health endpoint URL blocked: {service.health_endpoint}")
        if service.mcp_endpoint and service.mcp_endpoint.startswith("http") and not _is_safe_url(service.mcp_endpoint):
            raise ValueError(f"MCP endpoint URL blocked: {service.mcp_endpoint}")
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
        """Probe all registered services' health endpoints with rate limiting."""
        now = time.monotonic()
        if now - self._last_health_check < self._HEALTH_COOLDOWN:
            return  # rate limit
        self._last_health_check = now

        import httpx
        semaphore = asyncio.Semaphore(self._MAX_CONCURRENT_CHECKS)

        async def _check_one(svc: Service):
            async with semaphore:
                if not svc.health_endpoint:
                    return
                if not _is_safe_url(svc.health_endpoint):
                    svc.healthy = False
                    return
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

        tasks = [_check_one(svc) for svc in self._services.values()]
        await asyncio.gather(*tasks)
