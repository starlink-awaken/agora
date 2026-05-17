"""Agora CLI — command-line interface for the service convergence hub."""

from __future__ import annotations

import argparse
import json
import sys


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

    # health
    sub.add_parser("health", help="Probe all services")

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
    pl.add_argument("name", help="Pipeline name (match-derive, derive-check, full-pipeline, or custom)")
    pl.add_argument("--goal", default="", help="Goal for matching/derivation")
    pl.add_argument("--context", default="", help="Context keywords")
    pl.add_argument("--project", default=".", help="Project path for derivation")
    pl.add_argument("--json", action="store_true", help="JSON output")

    # pipeline list
    sub.add_parser("pipelines", help="List available pipelines")

    # pipeline define
    pd = sub.add_parser("pipeline-define", help="Define a custom pipeline from JSON file")
    pd.add_argument("file", help="Pipeline definition JSON file")

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    from agora.registry import ServiceRegistry, Service
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
        from agora.pipeline import Pipeline
        import asyncio

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
