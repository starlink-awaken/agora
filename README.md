# Agora — MCP Service Convergence Hub

> 服务通信收敛器：路由、监控、治理。Hub-Spoke 拓扑，收敛 N² 通信为 N 条边。

[English](#english) | [中文](#chinese)

---

## English

### Problem

```
3 services: 6 edges (3×2)    7 services: 42 edges (7×6)    N services: N×(N-1) edges — unscalable
```

### Agora Solution

```
All services only know Agora's address → Agora routes to target → 1 edge per service
New service: only update Agora's registry → other services unaware
```

### Quick Start

```bash
pip install -e .
agora register minerva --mcp http://localhost:8765/mcp --health http://localhost:8765/health --port 8765
agora register sophia --mcp sophia-mcp --port 9001
agora register ontoderive --mcp "python3 engine/mcp-server.py" --port 9002
agora register toolforge --mcp "python3 engine/toolforge/mcp_server.py" --port 9003
agora route minerva.research_now minerva
agora route toolforge.match toolforge
agora route ontoderive.derive ontoderive
agora route kos.search_knowledge kos
agora health          # probe all services
agora mcp             # start MCP server
```

### MCP Tools (9)

| Tool | Function |
|------|----------|
| `register_service` | Register a service with MCP + health endpoints |
| `list_services` | List all services with health status |
| `check_health` | Probe all registered services |
| `add_route` | Add tool→service routing rule |
| `list_routes` | List all registered routes |
| `route_call` | Proxy call routed to target service |

### Architecture

```
                  ┌─────────┐
                  │  Agora  │  ← Hub (registry + router + health)
                  └────┬────┘
          ┌────────┬────┼────────┬────────┐
          │        │    │        │        │
     ┌────┴──┐ ┌───┴──┐ ┌───┴──┐ ┌────┴───┐ ┌────────┐
     │Minerva│ │Sophia│ │OntoDerive│ │ToolForge│ │ KOS │ ← Spokes
     └───────┘ └──────┘ └─────────┘ └────────┘ └────────┘
```

### Roadmap

| Phase | Version | Focus | Timeline |
|-------|---------|-------|----------|
| Phase 1 | v1.2 | Core convergence: registry + router + health + MCP (14 tools) | ✅ Done |
| Phase 2 | v1.3 | Multi-protocol + proxy + REST handler + event bus + dashboard v3 | ✅ Done |
| Phase 3 | v1.4 | gRPC/WS/stdio handlers + connection pool + WebSocket push + topology SVG | ✅ Done |
| Phase 4 | v1.5 | SQLite persistence + SSRF dedup + trace rotation + FastAPI lifespan + debt cleanup | ✅ Current |
| Phase 5 | v2.0 | Governance: API key mgmt + audit log + quotas + dependency graph | 1-2 months |

### Installation

```bash
pip install -e .
```

### CLI Commands

```bash
agora register <name> --mcp <url> --health <url> --port <port>
agora list              # list registered services
agora health            # health check all services
agora route <tool> <service>
agora routes            # list all routes
agora mcp               # start MCP server
```

### Python API

```python
from agora import ServiceRegistry, Router

registry = ServiceRegistry()
registry.register("minerva", mcp_url="http://localhost:8765/mcp",
                  health_url="http://localhost:8765/health", port=8765)
statuses = await registry.health_check_all()

router = Router(registry)
router.add_route("minerva.research_now", "minerva")
result = await router.route("minerva.research_now", {"query": "test"})
```

### Related Projects

- [Minerva](https://github.com/minerva/minerva) — Local-first deep research system
- [Sophia](https://github.com/minerva/sophia) — Symbolic research paradigm engine
- [OntoDerive](https://github.com/your-org/ontoderive) — Fact-driven derivation engine
- [ToolForge](https://github.com/your-org/ontoderive) — Thinking tools matching (in OntoDerive engine/toolforge/)

### License

MIT

---

## 中文

### 问题

```
3 个服务: 6 条边    7 个服务: 42 条边    N 个服务: N×(N-1) 条边 — 不可扩展
```

### Agora 方案

```
所有服务只知道 Agora 地址 → Agora 路由到目标 → 每服务 1 条边
新增服务：只更新 Agora 注册表 → 其他服务无感知
```

### 架构

```
                  ┌─────────┐
                  │  Agora  │  ← Hub（注册表 + 路由器 + 健康检查）
                  └────┬────┘
          ┌────────┬────┼────────┬────────┐
          │        │    │        │        │
     ┌────┴──┐ ┌───┴──┐ ┌───┴──┐ ┌────┴───┐ ┌────────┐
     │Minerva│ │Sophia│ │OntoDerive│ │ToolForge│ │ KOS │ ← Spokes
     └───────┘ └──────┘ └─────────┘ └────────┘ └────────┘
```

### 快速开始

```bash
pip install -e .
agora register minerva --mcp http://localhost:8765/mcp --health http://localhost:8765/health --port 8765
agora register sophia --mcp sophia-mcp --port 9001
agora health          # 探测所有服务健康状态
agora mcp             # 启动 MCP server
```

### 三阶段路线图

| 阶段 | 版本 | 重点 | 时间 |
|------|------|------|------|
| Phase 1 | v1.2 | 核心收敛：注册表 + 路由 + 健康检查 + MCP (14 tools) | ✅ 完成 |
| Phase 2 | v1.3 | 多协议 + Proxy + REST 处理 + 事件总线 + Dashboard v3 | ✅ 完成 |
| Phase 3 | v1.4 | gRPC/WS/stdio handlers + 连接池 + WebSocket 推送 + 拓扑图 | ✅ 完成 |
| Phase 4 | v1.5 | SQLite 持久化 + SSRF 去重 + trace 轮转 + lifespan + 债务清理 | ✅ 当前 |
| Phase 5 | v2.0 | 治理：API Key 管理 + 审计日志 + 配额 + 依赖图 | 1-2 月 |

### 许可证

MIT
