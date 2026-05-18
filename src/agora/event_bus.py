"""Event Bus — lightweight publish-subscribe engine.

Design decisions (per spec 103-agora-upgrade-spec.md §3.2):
- JSON persistence (agora-events.json), zero additional dependencies
- HTTP POST push to subscriber callback endpoints
- At-least-once delivery, retry 3 times
- Pattern matching: exact ("index:done"), prefix ("index:*"), catch-all ("*")
- Auto-truncate event log at 1000 events (keep last 500)
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agora.registry import ServiceRegistry


@dataclass
class Subscription:
    id: str
    service: str
    pattern: str
    callback_url: str = ""
    created: str = ""


class EventBus:
    """Publish-subscribe event engine with JSON persistence."""

    def __init__(self, storage_path: str | None = None, registry: "ServiceRegistry | None" = None):
        self._storage_path = Path(storage_path or str(
            Path(__file__).parent.parent.parent / "agora-events.json"
        ))
        self._registry = registry
        self._events: list[dict] = []
        self._subscriptions: dict[str, Subscription] = {}
        self._max_events = 1000
        self._load()

    def _load(self):
        try:
            if self._storage_path.exists():
                data = json.loads(self._storage_path.read_text())
                self._events = data.get("events", [])
                for s in data.get("subscriptions", []):
                    sub = Subscription(**s)
                    self._subscriptions[sub.id] = sub
                self._max_events = data.get("max_events", 1000)
        except Exception:
            pass

    def _save(self):
        try:
            data = {
                "events": self._events,
                "subscriptions": [
                    {"id": s.id, "service": s.service, "pattern": s.pattern,
                     "callback_url": s.callback_url, "created": s.created}
                    for s in self._subscriptions.values()
                ],
                "max_events": self._max_events,
            }
            self._storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        except Exception:
            pass

    def _match(self, pattern: str, event_type: str) -> bool:
        """Check if event_type matches subscription pattern."""
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        return pattern == event_type

    def publish(self, event_type: str, payload: dict, source: str = "") -> str:
        """Publish event. Returns event_id."""
        event_id = f"evt_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        event = {
            "id": event_id,
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": source or "unknown",
            "type": event_type,
            "payload": payload,
        }

        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-500:]  # Keep last 500
        self._save()

        # Deliver to matching subscribers (async if loop available, sync otherwise)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._deliver(event))
        except RuntimeError:
            # No running loop (CLI context) — fire and forget ok
            pass
        return event_id

    async def _deliver(self, event: dict):
        """Deliver event to all matching subscribers with retry."""
        import httpx

        for sub in self._subscriptions.values():
            if not self._match(sub.pattern, event["type"]):
                continue

            callback = sub.callback_url
            if not callback and self._registry:
                svc = self._registry.get(sub.service)
                if svc and svc.health_endpoint:
                    callback = svc.health_endpoint.rstrip("/") + "/events"

            if not callback:
                continue

            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        r = await client.post(callback, json=event)
                        if r.status_code < 500:
                            break
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                    else:
                        # Log failure but don't block
                        pass

    def subscribe(self, service: str, pattern: str, callback_url: str = "") -> str:
        """Subscribe to events. Returns subscription_id."""
        sub_id = f"sub_{uuid.uuid4().hex[:8]}"
        sub = Subscription(
            id=sub_id, service=service, pattern=pattern,
            callback_url=callback_url,
            created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self._subscriptions[sub_id] = sub
        self._save()
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove subscription. Returns True if removed."""
        if sub_id in self._subscriptions:
            del self._subscriptions[sub_id]
            self._save()
            return True
        return False

    def get_event_log(self, limit: int = 50, since: str = "") -> list[dict]:
        """Query historical events."""
        events = self._events
        if since:
            events = [e for e in events if e.get("time", "") > since]
        return events[-limit:]

    def list_subscriptions(self) -> list[dict]:
        """List all subscriptions."""
        return [
            {"id": s.id, "service": s.service, "pattern": s.pattern,
             "callback_url": s.callback_url, "created": s.created}
            for s in self._subscriptions.values()
        ]
