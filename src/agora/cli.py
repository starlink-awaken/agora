"""Agora CLI — command-line interface for the service convergence hub."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agora", description="Agora — Service Convergence Hub")
    sub = p.add_subparsers(dest="command")

    # register
    r = sub.add_parser("register", help="Register a service")
    r.add_argument("name", help="Service name")
    r.add_argument("--mcp", default="", help="MCP endpoint URL")
    r.add_argument("--health", default="", help="Health check URL")
    r.add_argument("--port", type=int, default=0)
    r.add_argument("--tags", default="")

    # list
    sub.add_parser("list", help="List all services")

    # discover
    d = sub.add_parser("discover", help="Auto-discover MCP services in workspace")
    d.add_argument("--register", action="store_true", help="Auto-register discovered services")
    d.add_argument("--json", action="store_true", help="JSON output")
    d.add_argument("--workspace", default="", help="Workspace root path")

    # search
    s = sub.add_parser("search", help="Search services by keyword")
    s.add_argument("keyword", help="Search keyword")
    s.add_argument("--json", action="store_true", help="JSON output")

    # info
    i = sub.add_parser("info", help="Show service details")
    i.add_argument("name", help="Service name")
    i.add_argument("--json", action="store_true", help="JSON output")

    # stats
    sub.add_parser("stats", help="Show service statistics")

    # health
    h = sub.add_parser("health", help="Probe all services")
    h.add_argument("--watch", action="store_true", help="Continuous health monitoring")
    h.add_argument("--interval", type=int, default=30, help="Check interval in seconds (default: 30)")
    h.add_argument("--json", action="store_true", help="JSON output")

    # route
    rt = sub.add_parser("route", help="Add a tool route")
    rt.add_argument("tool", help="Tool name")
    rt.add_argument("service", help="Service name")

    # routes
    sub.add_parser("routes", help="List all routes")

    # mcp
    sub.add_parser("mcp", help="Start MCP server")

    # pipeline
    pl = sub.add_parser("pipeline", help="Run a named pipeline")
    pl.add_argument("name", help="Pipeline name")
    pl.add_argument("--goal", default="", help="Goal for matching/derivation")
    pl.add_argument("--context", default="", help="Context keywords")
    pl.add_argument("--project", default=".", help="Project path for derivation")
    pl.add_argument("--json", action="store_true", help="JSON output")

    # pipelines
    sub.add_parser("pipelines", help="List available pipelines")

    # pipeline-define
    pd = sub.add_parser("pipeline-define", help="Define a custom pipeline from JSON file")
    pd.add_argument("file", help="Pipeline definition JSON file")

    return p


def _cmd_discover(args) -> int:
    """Auto-discover MCP services."""
    from agora.discovery import DiscoveryEngine

    workspace = args.workspace or None
    engine = DiscoveryEngine(workspace)
    services = engine.discover_all()

    if args.register:
        from agora.registry import ServiceRegistry

        registry = ServiceRegistry()
        count = engine.auto_register(registry)
        print(f"🔍 Discovered {len(services)} services, {count} newly registered\n")
    else:
        print(f"🔍 Discovered {len(services)} MCP-capable services:\n")

    if args.json:
        result = [
            {
                "name": s.name,
                "description": s.description,
                "mcp_endpoint": s.mcp_endpoint,
                "health_endpoint": s.health_endpoint,
                "port": s.port,
                "tags": s.tags,
                "source": s.source,
                "confidence": s.confidence,
            }
            for s in services
        ]
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for s in services:
            conf_bar = "█" * int(s.confidence * 10) + "░" * (10 - int(s.confidence * 10))
            print(f"  [{conf_bar}] {s.name}")
            print(f"         {s.description}")
            if s.mcp_endpoint:
                print(f"         endpoint: {s.mcp_endpoint}")
            if s.health_endpoint:
                print(f"         health:   {s.health_endpoint}")
            if s.tags:
                print(f"         tags:     {', '.join(s.tags)}")
            print(f"         source:   {s.source}")
            print()
    return 0


def _cmd_search(args) -> int:
    """Search services by keyword."""
    from agora.registry import ServiceRegistry

    registry = ServiceRegistry()
    keyword = args.keyword.lower()
    matches = [
        s for s in registry.list_all()
        if keyword in s.name.lower()
        or keyword in s.description.lower()
        or any(keyword in t.lower() for t in s.tags)
    ]

    if args.json:
        print(json.dumps([s.__dict__ for s in matches], ensure_ascii=False, indent=2, default=str))
    else:
        print(f"🔍 '{args.keyword}' → {len(matches)} results:\n")
        for s in matches:
            print(f"  📦 {s.name}")
            if s.description:
                print(f"     {s.description}")
            if s.tags:
                print(f"     tags: {', '.join(s.tags)}")
            print(f"     status: {'✓ healthy' if s.is_available else '✗ offline'}")
            print()
    return 0


def _cmd_info(args) -> int:
    """Show detailed service info."""
    from agora.registry import ServiceRegistry

    registry = ServiceRegistry()
    svc = registry.get(args.name)
    if not svc:
        print(f"✗ Service '{args.name}' not found. Use 'agora list' to see all services.")
        return 1

    if args.json:
        info = {
            "name": svc.name,
            "description": svc.description,
            "mcp_endpoint": svc.mcp_endpoint,
            "health_endpoint": svc.health_endpoint,
            "port": svc.port,
            "tags": svc.tags,
            "is_available": svc.is_available,
            "last_health_check": svc.last_health_check,
        }
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        status = "✓ healthy" if svc.is_available else "✗ offline"
        print(f"📦 {svc.name}  [{status}]")
        print(f"   Description:  {svc.description or 'N/A'}")
        print(f"   MCP Endpoint: {svc.mcp_endpoint or 'N/A'}")
        print(f"   Health:       {svc.health_endpoint or 'N/A'}")
        print(f"   Port:         {svc.port or 'N/A'}")
        print(f"   Tags:         {', '.join(svc.tags) if svc.tags else 'N/A'}")
        print(f"   Last Check:   {svc.last_health_check or 'never'}")
        print(f"   Last Status:  {svc.last_health_check or 'N/A'}")
    return 0


def _cmd_stats(args) -> int:
    """Show service statistics."""
    from agora.registry import ServiceRegistry

    registry = ServiceRegistry()
    all_svc = registry.list_all()
    healthy = registry.list_healthy()

    print("📊 Agora Service Statistics\n")
    print(f"   Total services:     {len(all_svc)}")
    print(f"   Healthy:            {len(healthy)}")
    print(f"   Degraded/Offline:   {len(all_svc) - len(healthy)}")
    print(f"   Health check rate:  {len(healthy) / max(len(all_svc), 1) * 100:.1f}%")
    print()

    if all_svc:
        print("   Per-service status:")
        for s in all_svc:
            bar = "█" * 10 if s.is_available else "░" * 10
            print(f"     [{bar}] {s.name:20s} | tags: {', '.join(s.tags) if s.tags else '-'}")
    return 0


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    # Phase 2 commands (no registry needed)
    if args.command == "discover":
        return _cmd_discover(args)

    if args.command == "search":
        return _cmd_search(args)

    if args.command == "info":
        return _cmd_info(args)

    if args.command == "stats":
        return _cmd_stats(args)

    from agora.registry import Service, ServiceRegistry
    from agora.router import Router

    registry = ServiceRegistry()
    router = Router(registry)

    if args.command == "register":
        svc = Service(name=args.name, mcp_endpoint=args.mcp, health_endpoint=args.health,
                      port=args.port, tags=[t.strip() for t in args.tags.split(",") if t.strip()])
        registry.register(svc)
        print(f"Registered: {args.name}")

    elif args.command == "list":
        print(json.dumps(registry.to_dict(), ensure_ascii=False, indent=2))

    elif args.command == "health":
        if args.watch:
            print(f"🫀 Health watch started (interval: {args.interval}s). Ctrl+C to stop.\n")
            try:
                while True:
                    import asyncio
                    asyncio.run(registry.health_check_all())
                    healthy = registry.list_healthy()
                    timestamp = time.strftime("%H:%M:%S")
                    if args.json:
                        status = {
                            "timestamp": timestamp,
                            "healthy": len(healthy),
                            "total": len(registry.list_all()),
                            "services": [
                                {"name": s.name, "status": "up" if s.is_available else "down"}
                                for s in registry.list_all()
                            ],
                        }
                        print(json.dumps(status))
                    else:
                        print(f"[{timestamp}] {'✓' if len(healthy) == len(registry.list_all()) else '⚠'} "
                              f"Healthy: {len(healthy)}/{len(registry.list_all())}")
                        for s in registry.list_all():
                            print(f"  {'✓' if s.is_available else '✗'} {s.name}")
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                print("\nHealth watch stopped.")
        else:
            import asyncio
            asyncio.run(registry.health_check_all())
            healthy = registry.list_healthy()
            print(f"Healthy: {len(healthy)}/{len(registry.list_all())}")
            for s in registry.list_all():
                print(f"  {'✓' if s.is_available else '✗'} {s.name}:{s.port} — {s.mcp_endpoint}")

    elif args.command == "route":
        router.add_route(args.tool, args.service)
        print(f"Route: {args.tool} → {args.service}")

    elif args.command == "routes":
        print(json.dumps(router.list_routes(), ensure_ascii=False, indent=2))

    elif args.command == "mcp":
        from agora.server.mcp import main as mcp_main
        return mcp_main()

    elif args.command == "pipeline":
        import asyncio
        from agora.pipeline import Pipeline
        pl = Pipeline(registry, router)
        variables = {"goal": args.goal, "context": args.context, "project": args.project}
        result = asyncio.run(pl.run(args.name, variables))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"Pipeline: {result['pipeline']}")
            for r in result["results"]:
                status_icon = "✅" if r["status"] == "ok" else "❌"
                print(f"  {status_icon} Step {r['step']}: {r['tool']} — {r['status']}")
                if "error" in r:
                    print(f"     Error: {r['error']}")

    elif args.command == "pipelines":
        from agora.pipeline import Pipeline
        pl = Pipeline(registry, router)
        for name in pl.list_pipelines():
            print(f"  • {name}")
            steps = pl.get_pipeline(name)
            if steps:
                for s in steps:
                    print(f"    → {s['tool']}")

    elif args.command == "pipeline-define":
        from agora.pipeline import Pipeline
        pl = Pipeline(registry, router)
        name = pl.load_definition(args.file)
        print(f"✅ Pipeline loaded: {name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
