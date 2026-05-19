# Agora Installation & Integration Guide

## Quick Install

```bash
# From source
cd ~/Workspace/agora
pip install -e "."

# From PyPI (coming soon)
pip install agora-mcp

# Verify
agora --help
agora discover
```

## Claude Code Integration

Add to `~/.claude/mcp.json`:

```json
{
  "mcpServers": {
    "agora": {
      "command": "agora",
      "args": ["mcp"]
    }
  }
}
```

Restart Claude Code. Now you can use:
- `register_service` — Register MCP services
- `list_services` — Browse all services
- `check_health` — Probe service health
- `route_call` — Proxy calls to target services
- `publish_event` — Emit events to the bus
- `subscribe_event` — Subscribe to event patterns
- `get_event_log` — Query event history

## Web Dashboard

```bash
agora web                          # Start at localhost:7430
open http://localhost:7430         # Service status + pipeline runner + market
```

## Docker

```bash
docker compose up -d               # Start agora + minerva + agentmesh
```

## Endpoints

| Service | URL |
|---------|-----|
| Agora Dashboard | http://localhost:7430 |
| Agora Metrics | http://localhost:7430/metrics |
| Minerva Health | http://localhost:8765/health |
| AgentMesh Health | http://localhost:3000/health |
