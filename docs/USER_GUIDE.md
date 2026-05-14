# Agora — 用户使用指南

> 面向人类用户：理解服务收敛、搭建服务网格、运维管理

---

## 目录

1. [核心概念](#核心概念)
2. [快速上手](#快速上手)
3. [场景一：连接 Minerva + Sophia](#场景一连接-minerva--sophia)
4. [场景二：多服务健康监控](#场景二多服务健康监控)
5. [场景三：Agent 统一调用入口](#场景三agent-统一调用入口)
6. [常见问题](#常见问题)

---

## 核心概念

### 问题

没有 Agora 时，每个服务需要知道所有其他服务的地址：

```
Minerva ──── Sophia     (1 条边)
Minerva ──── KOS        (1 条边)
Sophia  ──── KOS        (1 条边)
Sophia  ──── Minerva    (1 条边)
...  N 个服务 = N×(N-1) 条边
```

### Agora 方案

```
所有服务 ──── Agora ──── 目标服务
N 个服务 = N 条边（每服务只连 Agora）
```

Agora 是一个**中心化路由表 + 健康检查器 + 服务注册表**，不代理数据流量，只告诉"谁在哪"。

---

## 快速上手

```bash
pip install -e .

# 启动 Agora
agora mcp &
```

---

## 场景一：连接 Minerva + Sophia

**你同时运行着 Minerva 和 Sophia，希望 Agent 能一键调用两个服务。**

### 1. 启动各服务

```bash
# 终端 1: Minerva
minerva web    # http://localhost:8765

# 终端 2: Sophia MCP
sophia mcp

# 终端 3: Agora（中心）
agora mcp
```

### 2. 注册服务到 Agora

```bash
# 注册 Minerva
agora register minerva \
  --mcp http://localhost:8765/mcp \
  --health http://localhost:8765/health \
  --port 8765

# 注册 Sophia
agora register sophia \
  --mcp sophia-mcp \
  --health http://localhost:9001/health \
  --port 9001
```

### 3. 配置路由

```bash
# Minerva 前缀路由 — 所有 minerva.* 工具自动转发
agora route minerva.research_now minerva
agora route minerva.knowledge_search minerva
agora route minerva minerva         # 前缀匹配

# Sophia 工具路由
agora route sophia.compile_paradigm sophia
agora route sophia sophia           # 前缀匹配
```

### 4. 验证

```bash
agora list     # 查看所有已注册服务及健康状态
agora health   # 主动探测所有服务
agora routes   # 查看路由表
```

---

## 场景二：多服务健康监控

**你管理多个服务，需要一个统一的健康面板。**

### 查看状态

```bash
agora list
```

输出：
```
minerva  | port:8765 | healthy | tags: research, search
sophia   | port:9001 | healthy | tags: paradigm, compiler
kos      | port:9002 | unhealthy | tags: knowledge, index
```

### 主动探测

```bash
agora health
```

输出：
```
Total: 3 | Healthy: 2 | Unhealthy: 1
kos: ⚠ offline (3 failures, cooldown 42s remaining)
```

### 断路器机制

当某个服务连续失败 3 次健康检查后，自动进入 60 秒冷却期：
- `is_available` → `False`
- 路由调用直接返回 `"Service temporarily unavailable"`
- 冷却结束后半开探测，成功后恢复

---

## 场景三：Agent 统一调用入口

**你有一个 AI Agent，需要调用多个 MCP 服务。不用配置每个服务的地址，只需连 Agora。**

### Agent 配置

```json
{
  "mcpServers": {
    "agora": {
      "command": "agora-mcp"
    }
  }
}
```

Agent 调用 Agora 的工具：
```
register_service("minerva", mcp_endpoint="http://...")
add_route("minerva.research_now", "minerva")
route_call("minerva.research_now", {"query": "What is RAG?"})
```

Agora 自动将调用转发到 Minerva 并返回结果。Agent 不需要知道 Minerva 的地址或端口。

### 完整流程

```
Agent → Agora.register_service()           # 注册 Minerva
Agent → Agora.add_route()                  # 配置路由
Agent → Agora.route_call("minerva.*", {})  # 发起调用
         │
         └── Agora 查找路由表 → 找到 minerva 服务
              └── POST minerva 的 MCP endpoint
                   └── 返回结果给 Agent
```

---

## 常见问题

**Q: Agora 会增加延迟吗？**
A: 每次路由调用约增加 5-10ms（一次 HTTP 转发）。Agora 不代理大流量，只转发 JSON RPC 调用。

**Q: 一个服务挂了怎么办？**
A: 断路器自动隔离。Agora 连续 3 次探测失败后进入 60 秒冷却，避免级联故障。

**Q: 如何限制可注册的服务？**
A: 最多 50 个服务，健康检查有 10 秒冷却和 10 并发上限。URL 验证阻止注册内网地址。

**Q: Agora 本身挂了怎么办？**
A: Agora 是中心化设计，挂了意味着路由不可用。生产环境建议配合 systemd 做进程守护。未来版本计划支持多 Agora 实例。

**Q: 支持哪些 MCP 传输方式？**
A: Agora 本身使用 stdio MCP。路由转发使用 HTTP POST 到服务端点的 JSON-RPC 格式。
