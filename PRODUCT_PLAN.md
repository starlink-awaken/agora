# Agora — MCP 服务注册中心 · 产品规划

> v1.3 定位：API Gateway for AI Agents · 多协议 MCP 服务市场
> 核心理念：Hub-Spoke 收敛 N²→N，零代码级耦合

---

## 产品愿景

**"一个地址，发现所有能力。"**

Agora 是 Workspace 智能体生态的中央枢纽。任何 MCP 服务注册后，所有 Agent 自动可用。无需记忆端口号、无需硬编码 URL、无需代码 import。

---

## 当前架构 (v1.3.0)

```
                    ┌──────────────────────────┐
                    │     Agora Hub (:7420)     │
                    │  ┌────────────────────┐   │
                    │  │  Service Registry   │   │
                    │  │  ┌──────┬────────┐  │   │
                    │  │  │minerva│ ontode│  │   │
                    │  │  │sophia │ agentm│  │   │
                    │  │  └──────┴────────┘  │   │
                    │  └────────────────────┘   │
                    │  ┌────────────────────┐   │
                    │  │   Pipeline Engine   │   │
                    │  │  match→derive→check │   │
                    │  └────────────────────┘   │
                    └──────────────────────────┘
                              ↑ MCP Protocol
          ┌───────────────────┼───────────────────┐
          ↓                   ↓                   ↓
    [Claude Code]       [Codex CLI]         [Cursor IDE]
```

### 已实现
- ✅ 4 服务注册 (minerva/ontoderive/sophia/agentmesh)
- ✅ 4 条预设 pipeline
- ✅ CLI 管理工具 (register/list/health/route)
- ✅ MCP Server (FastMCP, 9 tools)
- ✅ SSRF 防护, URL 校验
- ✅ 零代码级耦合 (纯协议通信)
- ✅ 智能发现: 4 策略 (已知项目 / pyproject / docker-compose / 端口探测)
- ✅ 健康告警: 熔断器状态变更 → EventBus 通知
- ✅ 负载均衡: 多实例 round-robin
- ✅ Pipeline DAG 可视化 (Dashboard SVG)
- ✅ Hermes MCP 集成 (9 tools, 已注册到 Hermes)
- ✅ 多租户: tenant.yaml + API Token + 速率限制
- ✅ MCP 工具市场: 18 个内置服务 + GitHub 安装

---

## Phase 2 — 智能发现 (v1.1)

### 2.1 工作区自动扫描
```
agora discover                    # 扫描 workspace 发现所有 MCP 服务
agora discover --watch            # 持续监控新服务上线
```

**发现策略：**
- 扫描 `.venv/bin/` 下的 CLI 工具 → 检查是否有 `--mcp` 子命令
- 扫描 `pyproject.toml` 的 `[project.scripts]` → 匹配 MCP 入口
- 扫描 `docker-compose.yml` → 提取端口映射
- 端口探测：扫 localhost:7420-7430 范围 → HTTP `/.well-known/mcp` 端点

### 2.2 健康检查升级
```
agora health --watch --interval 30s   # 30s 心跳监控
agora health --alert webhook://...    # 下线告警
```
- 心跳超时自动标记 `degraded`
- 连续 3 次失败 → `offline` + 通知
- 恢复后自动 `online` + 重新注册 MCP tools

### 2.3 服务市场 CLI
```
agora search "研究"                  # 按关键词搜索服务
agora info minerva                   # 查看服务详情 (tools/version/health)
agora stats                          # 使用统计 (调用次数/延迟/错误率)
```

---

## Phase 3 — 智能路由 (v1.2)

### 3.1 熔断器 ✅ (2026-05-18)
- ✅ CLOSED/OPEN/HALF_OPEN 三态熔断
- ✅ 可配置阈值: `--cb-max-failures N --cb-cooldown S --cb-success-threshold N`
- ✅ 半开探测: 冷却后自动尝试一次 → 连续成功则恢复
- ✅ CLI 展示: `agora info <name>` 显示 Circuit 状态 + 失败计数

### 3.2 流式管道 ✅ (2026-05-18)
- ✅ `run_stream()`: async generator 逐步骤输出
- ✅ `run_parallel()`: asyncio.gather 并发执行独立步骤
- ✅ CLI: `--stream` / `--parallel` 标志
- ✅ 自动依赖分组: 同层级无依赖步骤并行

### 3.3 负载均衡 (planned)
```yaml
services:
  - name: minerva
    instances:
      - mcp_url: "http://localhost:7421/sse"
      - mcp_url: "http://node2:7421/sse"
    strategy: round-robin
```

---

## Phase 4 — 平台化 (v2.0)

### 4.1 Web Dashboard ✅ (2026-05-18)
- ✅ `agora web` 启动 FastAPI Dashboard (localhost:7430)
- ✅ 实时服务状态 (circuit breaker states)
- ✅ Pipeline Runner (sequential/parallel/stream)
- ✅ 一键 Discover / Health Check / Register / Clear
- ✅ JSON API 全覆盖 (/api/services, /api/health, /api/pipeline, etc.)
- ✅ 自动刷新 (5s interval)
- ✅ Pipeline DAG 可视化 (Dashboard SVG)
- ✅ 调用追踪 (trace_log.jsonl + router._trace)
- ✅ Prometheus /metrics 端点

### 4.2 多租户 + 访问控制
```yaml
# agora/tenants.yaml
tenants:
  - name: personal
    services: [minerva, ontoderive, sophia]
    token: sk-personal-xxx
  - name: team
    services: [minerva, agentmesh, kos]
    token: sk-team-xxx
    rate_limit: 100 req/min
```

### 4.3 MCP 工具市场
```bash
agora market install starlink-awaken/minerva-research  # 从 GitHub 安装
agora market publish                                     # 发布到市场
agora market search "知识图谱"                           # 搜索市场
```

---

## 产品指标

| 指标 | v1.2 | v1.3 (当前) | v2.0 |
|------|------|-------------|------|
| 注册服务数 | 4 | ∞ (auto + multi-protocol) | ∞ |
| 服务发现方式 | 手动 CLI + 4策略自动 | ✅ 自动扫描 + 识别协议 | 市场安装 |
| Pipeline 类型 | 4 条预定义 | ✅ 自定义 + DAG 可视化 | 拖拽编排 |
| 高可用 | 心跳监控 | ✅ 熔断器(三态) + webhook告警 | 多实例LB |
| 管理界面 | CLI only | ✅ Web Dashboard (glassmorphism) | 拖拽编排 |
| 多协议 | MCP only | ✅ MCP + REST (完整) + gRPC/WS (预留) | 全协议完善 |
| 多租户 | 无 | ✅ API Token + 速率限制 | 团队协作 |
| 工具市场 | 无 | ✅ 18个内置 + GitHub安装 | 社区贡献 |
| MCP Tools | 9 | ✅ 14 (5 proxy + 3 registry + 3 route + 3 event) | 20+ |
| 测试 | 61 | ✅ 84 | 100+ |

---

## MVP 技术路线

```
Week 1-2:  Phase 2 核心
  - [ ] agora discover (扫描 workspace)
  - [ ] Health watch + alert
  - [ ] Service search/stats CLI

Week 3-4:  Phase 3 核心
  - [ ] 多实例注册
  - [ ] 熔断器 (circuit breaker)
  - [ ] 流式 pipeline

Week 5-8:  Phase 4 核心
  - [ ] Web Dashboard (FastAPI + htmx)
  - [ ] Pipeline DAG 编辑器
  - [ ] 多租户 + API Token
```

---

## 差异化定位

| 维度 | 竞品 (Kong/Traefik) | Agora |
|------|---------------------|-------|
| 目标用户 | DevOps/SRE | AI Agent 开发者 |
| 协议 | HTTP/REST/gRPC | **MCP (Model Context Protocol)** |
| 服务粒 | 微服务 | **AI Tool 级别** |
| 编排模型 | 声明式 YAML | 声明式 YAML + 自然语言 pipeline |
| 耦合方式 | SDK import | **零代码，纯协议** |
| 生态 | 通用 API | **Workspace 知识工程 + Agent 编排** |

---

## 一句话总结

**Agora = API Gateway for AI Agents.** 不是给微服务用的，是给 LLM Agent 发现和调用工具的。
