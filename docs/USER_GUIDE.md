# Agora — 用户使用指南 v1.2.0

> 面向人类用户：理解服务收敛、搭建服务网格、运维管理

---

## 核心概念

**问题**: 3 个服务有 6 条边，7 个服务有 42 条边 —— 不可扩展。

**Agora 方案**: Hub-Spoke 拓扑。所有服务只知道 Agora 地址，Agora 路由到目标。新增服务只需更新 Agora 注册表。

---

## 快速上手 (5分钟)

```bash
# 1. 安装
cd ~/Workspace/agora && pip install -e "."

# 2. 引导设置
agora init
# → 自动发现服务 → 注册 → 健康检查 → 下一步提示

# 3. 查看状态
agora stats

# 4. 运行第一个 Pipeline
agora pipeline full-pipeline --goal "分析新能源汽车市场" --project .

# 5. 启动 Dashboard
agora web
# → 打开 http://localhost:7430
```

---

## 场景 1: 服务发现与注册

```bash
# 自动发现 workspace 中的 MCP 服务
agora discover
agora discover --register    # 发现并自动注册
agora discover --watch       # 持续监控新服务

# 手动注册
agora register my-service --mcp "stdio://my-service" --tags "custom,tool"

# 查看已注册
agora list
agora info minerva           # 详情 + 断路器状态
agora search research        # 按关键词搜索
```

---

## 场景 2: 健康监控与故障恢复

```bash
# 全量健康检查
agora health

# 持续监控 (30s 间隔)
agora health --watch --interval 30

# 断路器状态
agora info minerva
# → Circuit: CLOSED | Failures: 0/3

# 故障模拟 → 自动恢复
bash demos/fault-injection.sh
# → CLOSED → OPEN → HALF_OPEN → CLOSED
```

---

## 场景 3: Pipeline 编排

```bash
# 内置管道
agora pipelines
# match-derive / research-derive / derive-check / full-pipeline

# 顺序执行
agora pipeline full-pipeline --goal "分析市场" --project .

# 流式输出 (逐步骤)
agora pipeline full-pipeline --goal "分析市场" --stream

# 并行执行 (独立步骤并发)
agora pipeline full-pipeline --goal "分析市场" --parallel

# 自定义管道
agora pipeline-define my-pipeline.json
```

---

## 场景 4: 事件总线

```bash
# 发布事件
agora event publish "index:done" --payload '{"docs":8941}' --source "kos"

# 查看历史
agora event log --limit 10

# 订阅事件 (通配符)
agora event subscribe "index:*"
agora event subscribe "*"

# 取消订阅
agora event unsubscribe sub_abc123
```

---

## 场景 5: MCP 工具市场

```bash
# 浏览市场
agora market list

# 搜索
agora market search brave

# 安装 (从 GitHub)
agora market install filesystem

# 发布自己的服务
agora market publish my-service --repo "github.com/me/my-service" --description "My MCP tool"
```

---

## 场景 6: Web Dashboard

```bash
agora web
# → http://localhost:7430

# 功能:
#  - 实时服务状态 (Circuit: CLOSED/OPEN/HALF_OPEN)
#  - Pipeline Runner (顺序/并行/流式)
#  - 一键 Discover / Health Check / Register
#  - DAG 可视化
#  - 5 秒自动刷新
```

---

## 场景 7: MCP 集成 (Claude Code)

```json
// ~/.claude/mcp.json
{"mcpServers": {"agora": {"command": "agora", "args": ["mcp"]}}}
```

Claude Code 现在可以直接调用 9 个 MCP 工具:
`register_service`, `list_services`, `check_health`, `add_route`, `list_routes`, `route_call`, `publish_event`, `subscribe_event`, `get_event_log`

---

## 场景 8: 多租户

```yaml
# ~/.config/agora/tenants.yaml
tenants:
  - name: personal
    token: sk-personal-xxx
    services: [minerva, ontoderive]
    rate_limit: 100
  - name: work
    token: sk-work-xxx
    services: [minerva, kos]
    rate_limit: 300
```

```bash
agora tenant list
agora tenant add team --services "minerva,kos" --rate-limit 200
```

---

## 场景 9: 可观测

```bash
# Prometheus 指标
curl http://localhost:7430/metrics
# → agora_services_total 8
# → agora_route_latency_seconds{quantile="0.99"} 0.015

# 延迟历史
curl http://localhost:7430/api/metrics/history
# → {"latency": {"p50": 0.001, "p90": 0.008, "p99": 0.015}}
```

---

## 场景 10: 告警通知

```bash
# 注册服务时配置 webhook
agora register critical-svc --health "http://localhost:8080/health"

# 断路器打开时自动 POST 告警到 webhook URL
# 查看: bash demos/alert-demo.sh
```

---

## 性能基线

```bash
bash demos/benchmark-demo.sh
# → 5 次运行平均延迟
# → 历史对比 (更快/更慢)
```

---

## CLI 速查表

| 命令 | 功能 |
|------|------|
| `agora init` | 引导式初始化 |
| `agora config` | 查看配置 |
| `agora discover` | 发现服务 |
| `agora list` | 列出服务 |
| `agora info <n>` | 服务详情 |
| `agora search <k>` | 搜索服务 |
| `agora stats` | 统计概览 |
| `agora health` | 健康检查 |
| `agora web` | Dashboard |
| `agora mcp` | MCP 服务器 |
| `agora pipeline <n>` | 运行管道 |
| `agora event publish` | 发布事件 |
| `agora market list` | 浏览市场 |
| `agora tenant list` | 租户管理 |

---

## 故障排查

```bash
agora config                    # 检查配置路径
agora health --watch            # 持续监控
agora discover --register       # 重新发现
agora event log --limit 20      # 查看事件历史
```
