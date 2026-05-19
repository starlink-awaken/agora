# Graph Report - src  (2026-05-19)

## Corpus Check
- Corpus is ~10,679 words - fits in a single context window. You may not need a graph.

## Summary
- 252 nodes · 332 edges · 17 communities (11 shown, 6 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 38 edges (avg confidence: 0.74)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Module 0|Module 0]]
- [[_COMMUNITY_Module 1|Module 1]]
- [[_COMMUNITY_Module 2|Module 2]]
- [[_COMMUNITY_Module 3|Module 3]]
- [[_COMMUNITY_Module 4|Module 4]]
- [[_COMMUNITY_Module 5|Module 5]]
- [[_COMMUNITY_Module 6|Module 6]]
- [[_COMMUNITY_Module 7|Module 7]]
- [[_COMMUNITY_Module 8|Module 8]]
- [[_COMMUNITY_Module 9|Module 9]]
- [[_COMMUNITY_Module 10|Module 10]]
- [[_COMMUNITY_Module 11|Module 11]]
- [[_COMMUNITY_Module 12|Module 12]]
- [[_COMMUNITY_Module 13|Module 13]]
- [[_COMMUNITY_Module 14|Module 14]]
- [[_COMMUNITY_Module 15|Module 15]]
- [[_COMMUNITY_Module 16|Module 16]]

## God Nodes (most connected - your core abstractions)
1. `ServiceRegistry` - 28 edges
2. `EventBus` - 18 edges
3. `DiscoveryEngine` - 17 edges
4. `Router` - 16 edges
5. `main()` - 14 edges
6. `Pipeline` - 14 edges
7. `TenantManager` - 12 edges
8. `Service` - 10 edges
9. `Market` - 9 edges
10. `DiscoveredService` - 7 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `TenantManager`  [INFERRED]
  cli.py → tenant.py
- `DiscoveredService` --uses--> `ServiceRegistry`  [INFERRED]
  discovery.py → registry.py
- `DiscoveredService` --uses--> `Service`  [INFERRED]
  discovery.py → registry.py
- `DiscoveryEngine` --uses--> `ServiceRegistry`  [INFERRED]
  discovery.py → registry.py
- `DiscoveryEngine` --uses--> `Service`  [INFERRED]
  discovery.py → registry.py

## Communities (17 total, 6 thin omitted)

### Community 0 - "Module 0"
Cohesion: 0.1
Nodes (18): build_parser(), _cmd_discover(), _cmd_info(), _cmd_search(), _cmd_stats(), main(), Agora CLI — command-line interface for the service convergence hub., Auto-discover MCP services. (+10 more)

### Community 1 - "Module 1"
Cohesion: 0.11
Nodes (15): DiscoveredService, DiscoveryEngine, _find_workspace(), Auto-discovery engine — scan workspace for MCP-capable services.  Phase 2 strate, Scan for known projects with .venv confirmation., Scan pyproject.toml for MCP-related project.scripts entries., Scan docker-compose.yml files for MCP-capable services., Check if a port is open. (+7 more)

### Community 2 - "Module 2"
Cohesion: 0.09
Nodes (13): Pipeline, Pipeline Orchestrator — chain multiple MCP tool calls into a workflow.  Usage:, Register a custom pipeline definition., List available pipeline names., Get pipeline definition by name., Execute a named pipeline sequentially., Execute pipeline and yield each step as it completes (streaming)., Execute independent pipeline steps in parallel.          Groups steps by depende (+5 more)

### Community 3 - "Module 3"
Cohesion: 0.08
Nodes (18): api_event_log(), api_event_publish(), api_metrics(), api_metrics_history(), api_pipeline_dag(), api_pipelines(), _auth_middleware(), dashboard() (+10 more)

### Community 4 - "Module 4"
Cohesion: 0.12
Nodes (12): EventBus, Event Bus — lightweight publish-subscribe engine.  Design decisions (per spec 10, Deliver event to all matching subscribers with retry., Subscribe to events. Returns subscription_id., Remove subscriptions older than TTL (dead subscriber cleanup)., Remove subscription. Returns True if removed., Query historical events., List all subscriptions. (+4 more)

### Community 5 - "Module 5"
Cohesion: 0.1
Nodes (12): Request Router — routes incoming calls to the correct service.  Phase 3: Load ba, Route a tool call to the target service and return the result., Publish route event if event_bus is configured., Buffer trace entry; flush to disk every 50 calls., Write buffered traces to disk., Calculate P50/P90/P99 from rolling latency window., Routes MCP tool calls to the appropriate registered service.      Supports:, Register a tool → service mapping. (+4 more)

### Community 6 - "Module 6"
Cohesion: 0.1
Nodes (15): Market, MCP Tool Market — discover, install, and register third-party MCP services.  Usa, MCP tool marketplace — discover, install, and register services., Search the built-in market by keyword., List all available MCP services in the market., Install an MCP service from the built-in market or GitHub URL.          Returns, Fetch repo metadata from GitHub API., Publish an MCP service to the market.          Returns metadata for registration (+7 more)

### Community 7 - "Module 7"
Cohesion: 0.12
Nodes (11): Multi-tenant access control — tenant.yaml + API Token + rate limiting.  Structur, Authenticate a token and return the tenant, or None if invalid., Check if tenant has exceeded rate limit.          Returns True if request is all, Check if tenant has access to a specific service.         Empty services list =, List all tenants (without exposing tokens)., Add a new tenant. Returns the generated token., Persist tenants to YAML config., Multi-tenant access control with token auth + rate limiting.      Tenants are co (+3 more)

### Community 8 - "Module 8"
Cohesion: 0.11
Nodes (17): add_route(), check_health(), get_event_log(), list_routes(), list_services(), publish_event(), Agora MCP Server — unified entry point for all services., Publish an event to the bus. payload is a JSON string.      Args:         event_ (+9 more)

### Community 9 - "Module 9"
Cohesion: 0.12
Nodes (11): _is_safe_url(), Service Registry — the single source of truth for all connected services., Persist services to JSON file. Only stores static config, not runtime state., Validate URL does not target internal/private network resources., A registered MCP-capable service., Service, Register a service with the Agora hub.      Args:         name: Unique service n, register_service() (+3 more)

### Community 10 - "Module 10"
Cohesion: 0.4
Nodes (5): _confirm(), Guided setup wizard — `agora init` for first-time users., Interactive setup wizard for first-time Agora users., Ask Y/n confirmation. Returns True unless user says n/no., run_wizard()

## Knowledge Gaps
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.