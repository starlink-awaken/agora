"""Service Registry — the single source of truth for all connected services."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

BLOCKED_HOSTS = frozenset({"0.0.0.0", "metadata.google.internal"})
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
    # Load-balanced instances (Phase 3)
    instances: list[dict] = field(default_factory=list)
    # Runtime state
    healthy: bool = True
    last_health_check: float = 0.0
    failure_count: int = 0
    cooldown_until: float = 0.0    # Circuit breaker cooldown timestamp
    half_open: bool = False        # Half-open: testing if service recovered
    consecutive_successes: int = 0  # Successes in half-open state

    @property
    def is_available(self) -> bool:
        """Service is available if healthy OR cooldown expired (half-open candidate)."""
        if self.healthy:
            return True
        return time.monotonic() >= self.cooldown_until

    @property
    def circuit_state(self) -> str:
        """CLOSED (normal), OPEN (failed, cooling down), HALF_OPEN (testing)."""
        if self.healthy:
            return "CLOSED"
        if self.half_open:
            return "HALF_OPEN"
        return "OPEN"

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
    Supports health alert firing via optional EventBus callback or webhook URL.
    """

    _MAX_SERVICES = 50
    _HEALTH_COOLDOWN = 10.0
    _MAX_CONCURRENT_CHECKS = 10

    def __init__(self, storage_path: str | None = None,
                 cb_max_failures: int = 3, cb_cooldown: float = 60.0,
                 cb_success_threshold: int = 2,
                 alert_callback: Callable | None = None,
                 alert_webhook: str = ""):
        self._services: dict[str, Service] = {}
        self._last_health_check: float = 0.0
        self._cb_max_failures = cb_max_failures
        self._cb_cooldown = cb_cooldown
        self._cb_success_threshold = cb_success_threshold
        self._alert_callback = alert_callback
        self._alert_webhook = alert_webhook
        self._storage_path = storage_path or str(
            Path(__file__).parent.parent.parent / "agora-services.json"
        )
        self._load()

    def _send_webhook_alert(self, name: str, prev: str, new: str, failures: int):
        """Send circuit state change alert via webhook."""
        if not self._alert_webhook:
            return
        # P0: Validate webhook URL against SSRF before sending
        if not _is_safe_url(self._alert_webhook):
            import structlog
            logger = structlog.get_logger(__name__)
            logger.warning("webhook_alert_blocked", service=name, webhook=self._alert_webhook)
            return
        import httpx

        async def _send():
            async with httpx.AsyncClient(timeout=5) as c:
                await c.post(self._alert_webhook, json={
                    "service": name, "prev_state": prev,
                    "new_state": new, "failures": failures,
                })

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send())
        except RuntimeError:
            asyncio.run(_send())
        except Exception:
            pass

    def _load(self):
        """Load persisted services from JSON file."""
        from agora.persistence import json_load
        data = json_load(Path(self._storage_path))
        for s in data.get("services", []):
            svc = Service(**{k: v for k, v in s.items() if k in Service.__dataclass_fields__})
            self._services[svc.name] = svc

    def _save(self):
        """Persist services to JSON file."""
        from agora.persistence import json_save
        json_save(Path(self._storage_path), {"services": [s.__dict__ for s in self._services.values()]})

    def register(self, service: Service):
        if len(self._services) >= self._MAX_SERVICES:
            raise ValueError(f"Service limit reached ({self._MAX_SERVICES})")
        # Validate URLs on registration
        if service.health_endpoint and not _is_safe_url(service.health_endpoint):
            raise ValueError(f"Health endpoint URL blocked: {service.health_endpoint}")
        if service.mcp_endpoint and service.mcp_endpoint.startswith("http") and not _is_safe_url(service.mcp_endpoint):
            raise ValueError(f"MCP endpoint URL blocked: {service.mcp_endpoint}")
        self._services[service.name] = service
        self._save()

    def unregister(self, name: str):
        self._services.pop(name, None)
        self._save()

    def get(self, name: str) -> Service | None:
        return self._services.get(name)

    def list_all(self) -> list[Service]:
        return list(self._services.values())

    def list_healthy(self) -> list[Service]:
        return [s for s in self._services.values() if s.is_available]

    def _try_half_open(self, name: str) -> bool:
        """Attempt a half-open probe. Returns True if probe should proceed."""
        svc = self._services.get(name)
        if svc and not svc.healthy and not svc.half_open and time.monotonic() >= svc.cooldown_until:
            svc.half_open = True
            return True
        return False

    def mark_failure(self, name: str):
        svc = self._services.get(name)
        if svc:
            prev_state = svc.circuit_state
            svc.failure_count += 1
            if svc.half_open:
                svc.healthy = False
                svc.half_open = False
                svc.consecutive_successes = 0
                svc.cooldown_until = time.monotonic() + (self._cb_cooldown * 2)
                if self._alert_callback:
                    self._alert_callback(name, prev_state, "OPEN (HALF_OPEN→OPEN)", svc.failure_count)
                self._send_webhook_alert(name, prev_state, "OPEN", svc.failure_count)
            elif svc.failure_count >= self._cb_max_failures:
                svc.cooldown_until = time.monotonic() + self._cb_cooldown
                svc.healthy = False
                if self._alert_callback and prev_state != "OPEN":
                    self._alert_callback(name, prev_state, "OPEN", svc.failure_count)
                self._send_webhook_alert(name, prev_state, "OPEN", svc.failure_count)

    def mark_success(self, name: str):
        svc = self._services.get(name)
        if svc:
            if svc.half_open:
                svc.consecutive_successes += 1
                if svc.consecutive_successes >= self._cb_success_threshold:
                    svc.failure_count = 0
                    svc.healthy = True
                    svc.half_open = False
                    svc.consecutive_successes = 0
                    svc.cooldown_until = 0.0
            else:
                svc.failure_count = max(0, svc.failure_count - 1)  # Gradual decay
                if svc.failure_count < self._cb_max_failures and not svc.healthy:
                    svc.healthy = True
                    svc.cooldown_until = 0.0

    def get_circuit_status(self, name: str) -> dict:
        """Get detailed circuit breaker status for a service."""
        svc = self._services.get(name)
        if not svc:
            return {}
        return {
            "name": name,
            "state": svc.circuit_state,
            "healthy": svc.healthy,
            "failure_count": svc.failure_count,
            "cooldown_remaining": max(0, svc.cooldown_until - time.monotonic()) if not svc.healthy else 0,
        }

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
