"""Governance — API Key management + Request Quotas for Agora v2.0."""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from agora.persistence_db import _get_db

_DB_PATH = Path(__file__).resolve().parents[3] / "agora.db"

# ── API Key Manager ─────────────────────────────────────────────────

@dataclass
class ApiKey:
    key_id: str
    name: str
    secret_hash: str
    scopes: list[str]
    tenant: str
    created_at: str
    expires_at: str = ""
    last_used: str = ""
    revoked: bool = False


class KeyManager:
    """Create, validate, rotate, and revoke API keys."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or str(_DB_PATH)
        self._ensure_schema()

    def _ensure_schema(self):
        conn = _get_db(self._db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                secret_hash TEXT NOT NULL,
                scopes TEXT NOT NULL DEFAULT '["read"]',
                tenant TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                expires_at TEXT DEFAULT '',
                last_used TEXT DEFAULT '',
                revoked INTEGER DEFAULT 0
            )
        """)
        conn.commit()

    def create_key(self, name: str, scopes: list[str] | None = None,
                   tenant: str = "", expires_days: int = 0) -> tuple[str, str]:
        """Create a new API key. Returns (key_id, raw_secret). Show secret once!"""
        key_id = "ak_" + secrets.token_hex(8)
        raw_secret = "agora_" + secrets.token_hex(24)
        secret_hash = hashlib.sha256(raw_secret.encode()).hexdigest()
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        expires = ""
        if expires_days > 0:
            expires = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                    time.gmtime(time.time() + expires_days * 86400))

        conn = _get_db(self._db_path)
        conn.execute(
            "INSERT INTO api_keys (key_id, name, secret_hash, scopes, tenant, created_at, expires_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (key_id, name, secret_hash,
             _json_dumps(scopes or ["read"]), tenant, ts, expires),
        )
        conn.commit()
        return key_id, raw_secret

    def validate(self, secret: str) -> ApiKey | None:
        """Validate a raw secret. Returns ApiKey if valid, None if invalid/revoked/expired."""
        if not secret or not secret.startswith("agora_"):
            return None
        secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        conn = _get_db(self._db_path)
        row = conn.execute(
            "SELECT * FROM api_keys WHERE secret_hash = ? AND revoked = 0", (secret_hash,)
        ).fetchone()
        if not row:
            return None
        d = _row_to_dict(row, ["key_id", "name", "secret_hash", "scopes",
                                 "tenant", "created_at", "expires_at", "last_used", "revoked"])
        key = ApiKey(
            key_id=d["key_id"], name=d["name"], secret_hash=d["secret_hash"],
            scopes=_json_loads(d["scopes"]), tenant=d["tenant"],
            created_at=d["created_at"], expires_at=d["expires_at"],
            last_used=d["last_used"], revoked=bool(d["revoked"]),
        )
        if key.expires_at and key.expires_at < time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()):
            return None
        # Update last_used
        conn.execute("UPDATE api_keys SET last_used = ? WHERE key_id = ?",
                     (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), key.key_id))
        conn.commit()
        return key

    def rotate(self, key_id: str, expires_days: int = 0) -> tuple[str, str] | None:
        """Rotate a key: revoke old, create new with same name/scopes/tenant. Returns (new_id, new_secret)."""
        conn = _get_db(self._db_path)
        old = conn.execute("SELECT * FROM api_keys WHERE key_id = ?", (key_id,)).fetchone()
        if not old:
            return None
        d = _row_to_dict(old, ["key_id", "name", "secret_hash", "scopes",
                                 "tenant", "created_at", "expires_at", "last_used", "revoked"])
        self.revoke(key_id)
        return self.create_key(d["name"], _json_loads(d["scopes"]), d["tenant"], expires_days)

    def revoke(self, key_id: str) -> bool:
        conn = _get_db(self._db_path)
        conn.execute("UPDATE api_keys SET revoked = 1 WHERE key_id = ?", (key_id,))
        conn.commit()
        return True

    def list_keys(self, tenant: str = "") -> list[dict]:
        conn = _get_db(self._db_path)
        if tenant:
            rows = conn.execute(
                "SELECT key_id, name, scopes, tenant, created_at, last_used, revoked "
                "FROM api_keys WHERE tenant = ?", (tenant,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT key_id, name, scopes, tenant, created_at, last_used, revoked "
                "FROM api_keys"
            ).fetchall()
        result = []
        for r in rows:
            cols = ["key_id", "name", "scopes", "tenant", "created_at",
                    "last_used", "revoked"]
            d = dict(zip(cols, r, strict=True))
            d["scopes"] = _json_loads(d["scopes"])
            d["revoked"] = bool(d["revoked"])
            result.append(d)
        return result

    def check_scope(self, key: ApiKey, required: str) -> bool:
        return required in key.scopes or "admin" in key.scopes


# ── Quota Manager ───────────────────────────────────────────────────

@dataclass
class QuotaConfig:
    requests_per_minute: int = 60
    requests_per_hour: int = 1000


class QuotaManager:
    """Per-tenant / per-service rate limiting with sliding window."""

    def __init__(self):
        self._windows: dict[str, list[float]] = {}  # key → timestamps

    def check(self, key: str, limit_per_minute: int = 60) -> bool:
        """Check if request is within quota. Returns True if allowed."""
        now = time.monotonic()
        window = self._windows.setdefault(key, [])
        window[:] = [t for t in window if now - t < 60]
        if len(window) >= limit_per_minute:
            return False
        window.append(now)
        return True

    def usage(self, key: str) -> dict:
        now = time.monotonic()
        window = self._windows.get(key, [])
        count = len([t for t in window if now - t < 60])
        return {"key": key, "requests_last_minute": count, "limit_per_minute": 60}


# ── Helpers ─────────────────────────────────────────────────────────

def _json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False)


def _json_loads(s: str) -> list | dict:
    return json.loads(s) if s else []


def _row_to_dict(row: tuple, cols: list[str]) -> dict:
    return dict(zip(cols, row, strict=True))
