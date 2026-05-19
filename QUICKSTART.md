# Agora Quickstart — 5 Minutes to a Working MCP Hub

## Prerequisites
- Python 3.11+
- macOS / Linux

## Install
```bash
cd ~/Workspace/agora
pip install -e "."
```

## Guided Setup
```bash
agora init
```
Walks you through: discover services → register → health check → next steps.

## Your First Pipeline
```bash
# 1. Check what's running
agora stats

# 2. Search for research tools
agora search research

# 3. Run a pipeline (match → derive → check)
agora pipeline full-pipeline --goal "分析新能源汽车市场" --project .

# 4. Start the dashboard
agora web
# → open http://localhost:7430
```

## CLI Cheat Sheet
```bash
agora init              Guided setup
agora discover          Find services in workspace
agora list              Show all registered services
agora info <name>       Service details + circuit status
agora search <kw>       Search by keyword
agora health            Health check all services
agora stats             Statistics overview
agora web               Dashboard (port 7430)
agora mcp               MCP server (for Claude Code)
agora config            Show paths and status
agora pipeline <name>   Run a pipeline
agora event log         View event history
agora market list       Browse MCP tool marketplace
```

## Integrate with Claude Code
Add to `~/.claude/mcp.json`:
```json
{"mcpServers": {"agora": {"command": "agora", "args": ["mcp"]}}}
```

## Troubleshooting
```bash
agora config             # Check paths and service count
agora health --watch     # Monitor continuously
agora discover --register  # Rediscover services
```
