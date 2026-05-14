# Agora — 三阶段迭代路线图

---

## Phase 1: 核心收敛 (v0.1.0) ← 当前

**目标**: 服务注册 + 路由收敛 + 健康检查，解决 N² 通信问题。

### 已交付

| 能力 | 模块 | 状态 |
|------|------|------|
| 服务注册表 | `registry.py` | ✅ |
| 请求路由器 | `router.py` | ✅ |
| 健康检查 | `registry.health_check_all()` | ✅ |
| 断路器 (3次失败→60s熔断) | `registry.mark_failure()` | ✅ |
| MCP Server (6 tools) | `server/mcp.py` | ✅ |
| CLI (5 命令) | `cli.py` | ✅ |

### 验证

```bash
agora register minerva --mcp http://localhost:8765 --health http://localhost:8765/health
agora register sophia --mcp sophia-mcp
agora route minerva minerva       # 前缀匹配
agora route minerva.research_now minerva  # 精确匹配
agora health                      # 全部探测
agora list                        # 查看注册表
```

---

## Phase 2: 可观测性 (v0.2.0)

**目标**: 调用链追踪 + 指标面板，回答"谁调了谁、耗时多少、成功了吗"。

### 功能清单

| 功能 | 说明 | 工作量 |
|------|------|--------|
| **调用链日志** | 每次 `route_call` 记录: caller, tool, service, latency, status | 2h |
| **/metrics 端点** | Prometheus 格式: request_total, request_duration, circuit_state | 1h |
| **/dashboard** | 简易 HTML 仪表盘: 服务拓扑图 + 最近调用 + 健康历史 | 2h |
| **延迟分位统计** | P50/P90/P99 延迟 | 1h |
| **断路器状态面板** | 实时显示哪些服务被熔断 | 30min |

### 架构增量

```
Phase 1:                   Phase 2:
registry.py                registry.py
router.py                  router.py  +  trace_log.jsonl
server/mcp.py              server/mcp.py
                           server/metrics.py   ← 新增
                           server/dashboard.py ← 新增
                           tracer.py           ← 新增
```

---

## Phase 3: 治理 (v0.3.0)

**目标**: 速率限制 + 依赖管理 + 自动发现，从"能用"到"可控"。

### 功能清单

| 功能 | 说明 | 工作量 |
|------|------|--------|
| **速率限制** | 每服务/每 tool 的 QPS 上限 | 2h |
| **配额管理** | 按优先级分配调用额度 | 1h |
| **服务依赖图** | 自动推断 A→B→C 调用链，可视化 | 2h |
| **自动发现** | 新服务启动时通过 `/health` 自动注册 | 1h |
| **Web 管理界面** | 注册/路由/监控一站式 | 3h |
| **告警规则** | 连续失败 N 次 → 通知（webhook/log） | 30min |

### 规模估算

| 服务数 | N² 边数 | Agora 收敛后 | 节省 |
|--------|---------|-------------|------|
| 3 | 6 | 3 | 50% |
| 5 | 20 | 5 | 75% |
| 10 | 90 | 10 | 89% |
| 20 | 380 | 20 | 95% |

服务数越多，收敛器价值越大。
