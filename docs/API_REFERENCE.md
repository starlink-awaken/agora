# Agora — CLI, MCP & Python API Reference

> 面向机器（AI Agent / MCP Client / 开发者）：完整参考

---

## CLI Reference

```bash
agora register <name>                    # 注册服务
  --protocol mcp|rest|grpc|stdio|websocket  # 服务协议 (默认: mcp)
  --protocol-config '{"key":"val"}'       # 协议配置 JSON
  --mcp <url>                             # 端点地址
  --health <url>                          # 健康检查地址
  --port <port>                           # 服务端口
  --tags "tag1,tag2"                      # 标签
  --proto <path>                          # gRPC proto 文件路径
  --rest-method GET|POST|PUT|DELETE|PATCH # REST 请求方法

agora list                               # 列出所有服务及健康状态
agora health                             # 主动探测所有服务健康
agora discover                           # 自动发现 workspace MCP 服务
agora search <keyword>                   # 搜索注册服务
agora info <name>                        # 服务详情 (含断路器)
agora stats                              # 调用统计 (P50/P90/P99)

agora route <tool_name> <service_name>   # 添加工具→服务路由
agora routes                             # 列出所有路由

agora pipeline <name>                    # 运行 Pipeline
  --stream                               # 流式输出
  --parallel                             # 并行执行
agora pipeline-define <file>             # 自定义 Pipeline

agora market list|search|install|publish # 服务市场
agora tenant list|add|remove             # 多租户管理
agora instance add <svc> --mcp <url>      # 多实例负载均衡

agora mcp                                # 启动 MCP Server
agora web                                # 启动 Web Dashboard (:7430)
agora init                               # 引导向导
agora completion                         # Shell 补全
agora event publish|log|subscribe        # 事件总线
```

---

## MCP Server

### 启动

```bash
agora mcp                       # 启动 MCP server (stdio)
agora-mcp                       # 直接调用
```

### 工具列表

#### 1. register_service

注册一个服务到 Agora。

```
Tool: register_service
Params:
  name            (string, required)  — 唯一服务名
  description     (string, optional)  — 描述
  protocol        (string, optional)  — 协议: mcp|rest|grpc|stdio|websocket (默认: mcp)
  protocol_config (string, optional)  — 协议配置 JSON (默认: "{}")
  mcp_endpoint    (string, optional)  — 端点 URL (MCP/REST 通用)
  health_endpoint (string, optional)  — Health URL
  port            (number, optional)  — 端口 (0-65535)
  tags            (string, optional)  — 逗号分隔标签
  command         (string, optional)  — stdio/proxy 命令 (e.g. "python3")
  mcp_args        (string, optional)  — 命令参数 (空格分隔)

Security:
  - health_endpoint/mcp_endpoint SSRF 防护由 registry.register() 统一校验
  - 协议校验: 仅允许已知协议 (mcp/rest/grpc/stdio/websocket)
  - 端口范围 0-65535
  - 最多 50 个注册服务
```

```json
// Request
{"method":"tools/call","params":{"name":"register_service","arguments":{
  "name": "minerva",
  "description": "Deep Research Engine",
  "mcp_endpoint": "http://192.0.2.1:8765/mcp",
  "health_endpoint": "http://192.0.2.1:8765/health",
  "port": 8765,
  "tags": "research,search"
}}}

// Response
{"status": "registered", "name": "minerva"}
```

---

#### 2. list_services

```
Params:  none
Returns: JSON array — [{name, description, healthy, endpoint, port, tags}, ...]
```

```json
[
  {"name": "minerva", "description": "Deep Research", "healthy": true, "endpoint": "http://...", "port": 8765, "tags": ["research"]},
  {"name": "sophia", "description": "Paradigm Engine", "healthy": true, "endpoint": "sophia-mcp", "port": 9001, "tags": ["paradigm"]}
]
```

---

#### 3. check_health

```
Params:  none
Returns: JSON object — {total, healthy, services: [...]}

Rate limit: 10s cooldown between full checks
Concurrency: max 10 simultaneous probes
```

```json
{
  "total": 3,
  "healthy": 2,
  "services": [
    {"name": "minerva", "healthy": true, ...},
    {"name": "sophia", "healthy": true, ...},
    {"name": "kos", "healthy": false, ...}
  ]
}
```

---

#### 4. add_route

```
Tool: add_route
Params:
  tool_name    (string, required)  — 工具名 (e.g. "minerva.research_now" 或 "minerva")
  service_name (string, required)  — 目标服务名

Routing:
  - 精确匹配: "minerva.research_now" → service for "minerva.research_now"
  - 前缀匹配: "minerva.knowledge_search" → service for "minerva" (当无精确匹配时)
```

```json
// Request
{"method":"tools/call","params":{"name":"add_route","arguments":{
  "tool_name": "minerva",
  "service_name": "minerva"
}}}

// Response
{"status": "routed", "tool": "minerva", "service": "minerva"}
```

---

#### 5. list_routes

```
Params:  none
Returns: JSON object — {tool_name: service_name, ...}
```

```json
{"minerva": "minerva", "sophia.compile_paradigm": "sophia", "sophia": "sophia"}
```

---

#### 6. route_call

```
Tool: route_call
Params:
  tool_name  (string, required)  — 目标工具名
  arguments  (string, optional)  — JSON 参数字符串 (default: "{}")

Internally:
  1. 解析 tool_name → service_name (via router.resolve)
  2. 检查 service 可用性 (circuit breaker)
  3. SSRF 验证 (如果是 HTTP endpoint)
  4. POST 到 service.mcp_endpoint
  5. 返回结果
```

```json
// Request
{"method":"tools/call","params":{"name":"route_call","arguments":{
  "tool_name": "minerva.research_now",
  "arguments": "{\"query\": \"What is RAG?\", \"level\": \"L0\"}"
}}}

// Response (from target service)
{
  "task_id": "a1b2c3d4",
  "status": "completed",
  "summary": "...",
  ...
}
```

---

#### 7. publish_event / subscribe_event / get_event_log

事件总线 — 发布/订阅/查询事件。

```
Tool: publish_event
Params: event_type (required), payload (required, JSON string), source (optional)

Tool: subscribe_event
Params: pattern (required), callback_url (optional)

Tool: get_event_log
Params: limit (optional, default=50), since (optional, ISO timestamp)
```

---

#### 8. proxy_connect / proxy_call / proxy_status / proxy_add_service / proxy_remove_service

MCP Proxy — 管理下游 MCP 服务透传连接。

```
Tool: proxy_connect     — 连接所有配置的下游服务
Tool: proxy_call        — 透传调用下游服务工具
  Params: tool_name (required), arguments (optional, JSON)
Tool: proxy_status      — 查看连接状态
Tool: proxy_add_service — 动态添加下游服务
  Params: name (required), mcp_endpoint/command/args (optional)
Tool: proxy_remove_service — 移除下游服务
  Params: name (required)
```

---

### 协议扩展

```python
# 注册 REST API 服务
register_service(name="my-api", protocol="rest",
                 protocol_config='{"method":"GET","headers":{"X-Key":"xxx"}}',
                 mcp_endpoint="http://localhost:3000/api")

# 注册 stdio 命令行服务
register_service(name="my-tool", protocol="stdio",
                 protocol_config='{"command":"python3","args":["-m","my_tool"]}')
```

---

### 错误响应

```json
// 工具不可用（无路由）
{"status": "error", "error": "Tool not available"}

// 服务不可用（down/cooldown）
{"status": "error", "error": "Service temporarily unavailable"}

// 路由失败
{"status": "error", "error": "Routing failed"}

// 注册被拒（安全）
{"status": "error", "error": "Health endpoint URL targets internal network"}
{"status": "error", "error": "Port must be 0-65535"}
```

---

### 断路器状态机

```
         ┌──────────┐
         │  HEALTHY  │──── 3 consecutive failures ────┐
         └──────────┘                                 │
              │                                       ▼
              │                               ┌──────────────┐
              │                               │  COOLDOWN    │
              │                               │  (60s timer) │
              │                               └──────┬───────┘
              │                                      │
              └──── mark_success() ◀──── 探测成功 ────┘ (half-open)
```

---

## Python API

### 服务注册

```python
from agora.registry import ServiceRegistry, Service
from agora.router import Router

# 创建注册表和路由器
registry = ServiceRegistry()
router = Router(registry)

# 注册服务
minerva = Service(
    name="minerva",
    description="Deep Research Engine",
    mcp_endpoint="http://192.0.2.1:8765/mcp",
    health_endpoint="http://192.0.2.1:8765/health",
    port=8765,
    tags=["research", "search"],
)
registry.register(minerva)

# 注册 CLI 模式的服务（不涉及 HTTP）
sophia = Service(
    name="sophia",
    mcp_endpoint="sophia-mcp",  # CLI 命令，非 URL
    port=9001,
)
registry.register(sophia)
```

### 路由配置

```python
# 精确匹配
router.add_route("minerva.research_now", "minerva")
router.add_route("sophia.compile_paradigm", "sophia")

# 前缀匹配（捕获所有 minerva.*）
router.add_route("minerva", "minerva")
router.add_route("sophia", "sophia")

# 查看路由
print(router.list_routes())
# → {"minerva.research_now": "minerva", "minerva": "minerva", ...}
```

### 路由调用

```python
# 转发到 Minerva
result = await router.route("minerva.research_now", {
    "query": "What is quantum computing?",
    "level": "L1",
})
print(result)  # → Minerva 的 JSON 响应

# 转发到 Sophia
result = await router.route("sophia.compile_paradigm", {
    "query": "Compare Rust vs Go",
})
print(result)  # → Sophia 的范式 JSON
```

### 健康检查

```python
# 全量健康检查
await registry.health_check_all()

# 查看状态
for svc in registry.list_all():
    print(f"{svc.name}: {'healthy' if svc.is_available else 'unhealthy'}")

# 断路器触发后
registry.mark_failure("minerva")
registry.mark_failure("minerva")
registry.mark_failure("minerva")  # 第 3 次 → 冷却 60s
print(registry.get("minerva").is_available)  # → False
```
