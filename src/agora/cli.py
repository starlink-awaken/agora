"""Agora CLI — command-line interface for the service convergence hub."""

from __future__ import annotations

import argparse
import json
import sys
import time


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
    d.add_argument("--watch", action="store_true", help="Watch mode: continuous discovery")
    d.add_argument("--interval", type=int, default=30, help="Watch interval in seconds (default: 30)")
    d.add_argument("--workspace", default="", help="Workspace root path")
    d.add_argument("--probe", action="store_true", help="Enable port probing (async, slow)")

    # instance
    inst = sub.add_parser("instance", help="Load-balanced instance operations")
    inst_sub = inst.add_subparsers(dest="instance_cmd")
    inst_add = inst_sub.add_parser("add", help="Add an instance for load balancing")
    inst_add.add_argument("service", help="Service name")
    inst_add.add_argument("--mcp", required=True, help="MCP endpoint URL")
    inst_add.add_argument("--health", default="", help="Health check URL")
    inst_add.add_argument("--port", type=int, default=0)

    # tenant
    ten = sub.add_parser("tenant", help="Multi-tenant management")
    ten_sub = ten.add_subparsers(dest="tenant_cmd")
    ten_list = ten_sub.add_parser("list", help="List all tenants")
    ten_add = ten_sub.add_parser("add", help="Add a tenant")
    ten_add.add_argument("name", help="Tenant name")
    ten_add.add_argument("--services", default="", help="Comma-separated allowed services")
    ten_add.add_argument("--rate-limit", type=int, default=60, help="Requests per minute")
    ten_rm = ten_sub.add_parser("remove", help="Remove a tenant")
    ten_rm.add_argument("name", help="Tenant name")

    # market
    mkt = sub.add_parser("market", help="MCP tool marketplace")
    mkt_sub = mkt.add_subparsers(dest="market_cmd")
    mkt_list = mkt_sub.add_parser("list", help="List available MCP services")
    mkt_search = mkt_sub.add_parser("search", help="Search MCP services")
    mkt_search.add_argument("keyword", help="Search keyword")
    mkt_install = mkt_sub.add_parser("install", help="Install an MCP service")
    mkt_install.add_argument("name", help="Service name or GitHub repo (e.g. filesystem, starlink-awaken/minerva)")
    mkt_pub = mkt_sub.add_parser("publish", help="Publish a service to the market")
    mkt_pub.add_argument("name", help="Service name")
    mkt_pub.add_argument("--repo", default="", help="GitHub repo (e.g. starlink-awaken/my-service)")
    mkt_pub.add_argument("--description", default="", help="Service description")
    mkt_pub.add_argument("--entry", default="server.py", help="Entry point file")
    mkt_pub.add_argument("--type", default="python", help="Service type (python|node)")

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

    # init
    sub.add_parser("init", help="Guided setup wizard for first-time users")

    # config
    sub.add_parser("config", help="Show config paths and status")

    # web
    sub.add_parser("web", help="Start Web Dashboard (port 7430)")

    # pipeline
    pl = sub.add_parser("pipeline", help="Run a named pipeline")
    pl.add_argument("name", help="Pipeline name")
    pl.add_argument("--goal", default="", help="Goal for matching/derivation")
    pl.add_argument("--context", default="", help="Context keywords")
    pl.add_argument("--project", default=".", help="Project path for derivation")
    pl.add_argument("--json", action="store_true", help="JSON output")
    pl.add_argument("--stream", action="store_true", help="Stream each step as it completes")
    pl.add_argument("--parallel", action="store_true", help="Execute independent steps concurrently")

    # pipelines
    sub.add_parser("pipelines", help="List available pipelines")

    # pipeline-define
    pd = sub.add_parser("pipeline-define", help="Define a custom pipeline from JSON file")
    pd.add_argument("file", help="Pipeline definition JSON file")

    # event
    ev = sub.add_parser("event", help="Event bus operations")
    ev_sub = ev.add_subparsers(dest="event_cmd")
    ev_pub = ev_sub.add_parser("publish", help="Publish an event")
    ev_pub.add_argument("type", help="Event type (e.g. index:done)")
    ev_pub.add_argument("--payload", default="{}", help="JSON payload")
    ev_pub.add_argument("--source", default="cli", help="Source service name")
    ev_log = ev_sub.add_parser("log", help="View event log")
    ev_log.add_argument("--limit", type=int, default=50, help="Max events")
    ev_sub_scribe = ev_sub.add_parser("subscribe", help="Subscribe to events")
    ev_sub_scribe.add_argument("pattern", help="Event pattern (e.g. index:*)")
    ev_sub_scribe.add_argument("--callback", default="", help="Callback URL")
    ev_unsub = ev_sub.add_parser("unsubscribe", help="Unsubscribe")
    ev_unsub.add_argument("id", help="Subscription ID")

    return p


def _cmd_discover(args) -> int:
    """Auto-discover MCP services."""
    from agora.discovery import DiscoveryEngine

    workspace = args.workspace or None
    engine = DiscoveryEngine(workspace)

    if args.watch:
        import asyncio
        from agora.registry import ServiceRegistry
        registry = ServiceRegistry()
        async def _watch():
            async for svc in engine.watch(registry, args.interval):
                pass
        try:
            asyncio.run(_watch())
        except KeyboardInterrupt:
            pass
        return 0

    if args.probe:
        import asyncio
        services = asyncio.run(engine.discover_all_async())
        print(f"🔍 Discovered {len(services)} MCP-capable services (incl. port probe):\n")
    else:
        services = engine.discover_all()
        print(f"🔍 Discovered {len(services)} MCP-capable services (strategies: known + pyproject + compose):\n")

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
            "circuit_state": svc.circuit_state,
            "failure_count": svc.failure_count,
            "last_health_check": svc.last_health_check,
        }
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        status = "✓ healthy" if svc.is_available else "✗ offline"
        circuit = svc.circuit_state
        print(f"📦 {svc.name}  [{status}]  Circuit: {circuit}")
        print(f"   Description:    {svc.description or 'N/A'}")
        print(f"   MCP Endpoint:   {svc.mcp_endpoint or 'N/A'}")
        print(f"   Health:         {svc.health_endpoint or 'N/A'}")
        print(f"   Port:           {svc.port or 'N/A'}")
        print(f"   Tags:           {', '.join(svc.tags) if svc.tags else 'N/A'}")
        print(f"   Failures:       {svc.failure_count}/3")
        print(f"   Last Check:     {svc.last_health_check or 'never'}")
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

    if args.command == "instance":
        from agora.registry import ServiceRegistry
        from agora.router import Router
        registry = ServiceRegistry()
        router = Router(registry)
        if args.instance_cmd == "add":
            router._add_instance(args.service, args.mcp, args.health, args.port)
            print(f"✅ Instance added: {args.service} → {args.mcp}")
        return 0

    if args.command == "tenant":
        from agora.tenant import TenantManager
        tm = TenantManager()
        if args.tenant_cmd == "list":
            print("📋 Tenants:\n")
            for t in tm.list_tenants():
                svcs = ', '.join(t['services']) if t['services'] else '(all)'
                print(f"  👤 {t['name']:20s}  rate: {t['rate_limit']:4d} req/min  services: {svcs}")
        elif args.tenant_cmd == "add":
            services = [s.strip() for s in args.services.split(",") if s.strip()]
            token = tm.add_tenant(args.name, services, args.rate_limit)
            print(f"✅ Tenant '{args.name}' created")
            print(f"   Token: {token}")
        elif args.tenant_cmd == "remove":
            ok = tm.remove_tenant(args.name)
            print(f"{'✅' if ok else '❌'} Tenant '{args.name}' {'removed' if ok else 'not found'}")
        return 0

    if args.command == "market":
        from agora.market import Market
        mkt = Market()
        if args.market_cmd == "list":
            print("📦 MCP Tool Market\n")
            for s in mkt.list_all():
                print(f"  {s['name']:20s}  {s['description'][:60]}")
                print(f"  {'':20s}  repo: {s['repo']:30s}  type: {s['type']}")
                print()
        elif args.market_cmd == "search":
            results = mkt.search(args.keyword)
            print(f"🔍 '{args.keyword}' → {len(results)} results:\n")
            for s in results:
                print(f"  📦 {s['name']:20s}  {s['description']}")
                print(f"  {'':20s}  repo: {s['repo']}  tags: {', '.join(s['tags'])}")
                print()
        elif args.market_cmd == "install":
            print(f"⬇️  Installing {args.name}...")
            result = mkt.install(args.name)
            print(f"✅ {result['name']} installed")
            print(f"   Entry: {result['entry']}")
            print(f"   Type:  {result['type']}")
            if result.get("port"):
                print(f"   Port:  {result['port']}")
        elif args.market_cmd == "publish":
            result = mkt.publish(
                args.name, repo=args.repo, description=args.description,
                entry=args.entry, svc_type=args.type,
            )
            print(f"📤 Published: {result['name']} (repo: {result.get('repo', 'N/A')})")
        return 0

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

    elif args.command == "init":
        from agora.wizard import run_wizard
        return run_wizard()

    elif args.command == "config":
        from agora.registry import ServiceRegistry
        r = ServiceRegistry()
        print(f"Services file:   {r._storage_path}")
        print(f"Registered:      {len(r.list_all())} services")
        print(f"Healthy:         {len(r.list_healthy())}")
        print(f"Events file:     agora-events.json")
        print(f"Trace file:      trace_log.jsonl")
        print(f"Dashboard:       http://localhost:7430")
        print(f"Metrics:         http://localhost:7430/metrics")

    elif args.command == "web":
        from agora.web.app import main as web_main
        print("🏛️  Agora Dashboard → http://localhost:7430")
        return web_main()

    elif args.command == "pipeline":
        import asyncio
        from agora.pipeline import Pipeline
        pl = Pipeline(registry, router)
        variables = {"goal": args.goal, "context": args.context, "project": args.project}

        if args.stream:
            async def _stream():
                async for step in pl.run_stream(args.name, variables):
                    icon = "✅" if step["status"] == "ok" else "❌"
                    print(f"  {icon} Step {step['step']}: {step['tool']} — {step['status']}")
                    if "error" in step:
                        print(f"     Error: {step['error']}")
            asyncio.run(_stream())
        elif args.parallel:
            result = asyncio.run(pl.run_parallel(args.name, variables))
            if args.json:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"Pipeline: {result['pipeline']} (parallel)")
                for r in result["results"]:
                    status_icon = "✅" if r["status"] == "ok" else "❌"
                    print(f"  {status_icon} Step {r['step']}: {r['tool']} — {r['status']}")
                    if "error" in r:
                        print(f"     Error: {r['error']}")
        else:
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

    elif args.command == "event":
        from agora.event_bus import EventBus
        bus = EventBus(registry=registry)

        if args.event_cmd == "publish":
            try:
                payload = json.loads(args.payload) if args.payload else {}
            except json.JSONDecodeError:
                payload = {"raw": args.payload}
            eid = bus.publish(args.type, payload, args.source)
            print(f"📡 Published: {eid} ({args.type})")

        elif args.event_cmd == "log":
            events = bus.get_event_log(args.limit)
            if not events:
                print("(no events)")
            for e in events:
                print(f"  [{e['time']}] {e['source']:15s} → {e['type']:30s} | {json.dumps(e.get('payload', {}), ensure_ascii=False)[:80]}")

        elif args.event_cmd == "subscribe":
            sid = bus.subscribe("cli", args.pattern, args.callback)
            print(f"📬 Subscribed: {sid} → {args.pattern}")

        elif args.event_cmd == "unsubscribe":
            ok = bus.unsubscribe(args.id)
            print(f"📭 {'Unsubscribed' if ok else 'Not found'}: {args.id}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n👋 Interrupted.")
        sys.exit(130)
    except Exception:
        print("❌ An unexpected error occurred.")
        print("   Run 'agora config' to check setup, or 'agora init' to re-run setup.")
        sys.exit(1)
