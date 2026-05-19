"""Guided setup wizard — `agora init` for first-time users."""

from __future__ import annotations

import sys
from pathlib import Path


def run_wizard() -> int:
    """Interactive setup wizard for first-time Agora users."""
    print("🏛️  Welcome to Agora — MCP Service Hub\n")
    print("This wizard will help you discover and register services.\n")

    # Step 1: Discover
    print("━ Step 1/4: Discovering MCP services in your workspace...")
    from agora.discovery import DiscoveryEngine
    engine = DiscoveryEngine()
    services = engine.discover_all()
    print(f"   Found {len(services)} MCP-capable services:\n")
    for i, s in enumerate(services, 1):
        conf_bar = "█" * int(s.confidence * 10)
        print(f"   {i}. {s.name:20s} [{conf_bar}] {s.description[:50]}")

    # Step 2: Register
    print(f"\n━ Step 2/4: Register services? [Y/n] ", end="")
    choice = input().strip().lower()
    if choice not in ("n", "no"):
        from agora.registry import ServiceRegistry
        registry = ServiceRegistry()
        count = engine.auto_register(registry)
        print(f"   ✅ Registered {count} new services ({len(registry.list_all())} total)")

    # Step 3: Health check
    print(f"\n━ Step 3/4: Run health check? [Y/n] ", end="")
    choice = input().strip().lower()
    if choice not in ("n", "no"):
        import asyncio
        from agora.registry import ServiceRegistry
        registry = ServiceRegistry()
        asyncio.run(registry.health_check_all())
        healthy = len(registry.list_healthy())
        total = len(registry.list_all())
        status = "✅" if healthy == total else "⚠️"
        print(f"   {status} {healthy}/{total} services healthy")

    # Step 4: Quick start
    print(f"""
━ Step 4/4: You're ready to go!

   Quick commands:
     agora list          List all services
     agora stats         Show statistics
     agora search <kw>   Search services
     agora web           Start dashboard (localhost:7430)
     agora mcp           Start MCP server

   Next steps:
     pip install pallas  (unified CLI entry)
     pallas pipeline --goal 'your goal' --project .
""")

    return 0
