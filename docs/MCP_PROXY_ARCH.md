# Agora MCP Proxy — 架构设计

> 让 Agora 成为 Hermes 唯一的 MCP 入口，聚合所有下游服务的工具。

---

## 现状

```
Hermes ──→ agora (MCP)     ← 仅注册中心+健康检查
Hermes ──→ kos (MCP)
Hermes ──→ minerva (MCP)
Hermes ──→ sophia (MCP)
Hermes ──→ ontoderive (MCP)
Hermes ──→ bos (MCP)
Hermes ──→ sharedbrain (MCP)
```

**问题：** 所有服务在 Hermes 端直连，Agora 只是旁观者。Router 只支持 HTTP 转发，但本地服务全是 stdio。

---

## 目标

```
Hermes ──→ agora (MCP Proxy)
                ├──→ kos (stdio subprocess)
                ├──→ minerva (stdio subprocess)
                ├──→ sophia (stdio subprocess)
                ├──→ ontoderive (stdio subprocess)
                ├──→ bos/bos-daemon (HTTP client)
                └──→ sharedbrain (HTTP client)
```

- Hermes 只连 Agora 一个 MCP
- Agora 聚合所有下游服务的 tool schemas，作为自己的工具暴露
- 收到工具调用时，按 transport 类型转发到对应服务
- 熔断、负载均衡、事件总线全部打通

---

## 架构

```
┌──────────────────────────────────────────────┐
│                 Agora MCP Server              │
│                                              │
│   ┌─────────────────────────────────────┐    │
│   │        Tool Aggregation Layer        │    │
│   │  - tools/list → return ALL schemas   │    │
│   │  - tools/call → dispatch to client   │    │
│   └──────────┬──────────────────────────┘    │
│              │                                │
│   ┌──────────▼──────────────────────────┐    │
│   │        MCP Client Manager            │    │
│   │                                      │    │
│   │  ┌─────────┐  ┌─────────┐           │    │
│   │  │ stdio   │  │ HTTP    │           │    │
│   │  │ Client  │  │ Client  │           │    │
│   │  └────┬────┘  └────┬────┘           │    │
│   └───────┼────────────┼────────────────┘    │
└───────────┼────────────┼─────────────────────┘
            │            │
   ┌────────▼──┐  ┌─────▼──────┐
   │ kos       │  │ bos        │
   │ minerva   │  │ bos-daemon │
   │ sophia    │  │ sharedbrain│
   │ ontoderive│  │ (HTTP)     │
   │ (stdio)   │  └────────────┘
   └───────────┘
```

---

## 模块设计

### 1. `src/agora/mcp_proxy/`

#### `client.py` — MCP Client 抽象

```python
class MCPClient(ABC):
    """Base MCP client — connects to a downstream service as an MCP client."""

    @abstractmethod
    async def connect(self) -> bool: ...
    @abstractmethod
    async def list_tools(self) -> list[ToolSchema]: ...
    @abstractmethod
    async def call_tool(self, name: str, args: dict) -> Any: ...
    @abstractmethod
    async def disconnect(self): ...

class StdioMCPClient(MCPClient):
    """Stdio-based MCP client — spawns a subprocess, MCP JSON-RPC over stdin/stdout."""
    
    def __init__(self, service_name: str, command: str, args: list[str]):
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}

    async def connect(self):
        # 1. spawn subprocess (command + args)
        # 2. send MCP initialize request
        # 3. start reader loop (parse JSON-RPC responses, resolve futures)

    async def list_tools(self):
        # send {"jsonrpc":"2.0","id":1,"method":"tools/list"}
        # parse response → list of tool schemas

    async def call_tool(self, name, args):
        # send {"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":name,"arguments":args}}

class HttpMCPClient(MCPClient):
    """HTTP/SSE-based MCP client — uses httpx. Already partially implemented in Router."""
    
    def __init__(self, service_name: str, endpoint: str):
        self._client = httpx.AsyncClient(timeout=30)
        self._endpoint = endpoint

    async def list_tools(self):
        resp = await self._client.post(self._endpoint, json={
            "method": "tools/list", "params": {}
        })
        return resp.json().get("result", {}).get("tools", [])

    async def call_tool(self, name, args):
        resp = await self._client.post(self._endpoint, json={
            "method": "tools/call",
            "params": {"name": name, "arguments": args}
        })
        return resp.json()
```

#### `registry.py` — 下游工具注册表

```python
class ProxyRegistry:
    """Maps tool names → downstream service + client."""

    def __init__(self):
        self._entries: dict[str, ProxyEntry] = {}  # tool_name → entry
        self._clients: dict[str, MCPClient] = {}   # service_name → client

    async def register_service(self, name: str, client: MCPClient):
        """Connect to a service, discover its tools, register them."""
        if not await client.connect():
            return False
        tools = await client.list_tools()
        for tool in tools:
            full_name = f"{name}.{tool['name']}"
            self._entries[full_name] = ProxyEntry(
                tool_name=full_name,
                tool_schema=tool,
                service_name=name,
            )
        self._clients[name] = client
        return True

    def resolve(self, tool_name: str) -> ProxyEntry | None:
        # Exact match, then prefix match (e.g. "kos.search" → kos prefix)
        ...

    async def dispatch(self, tool_name: str, args: dict) -> dict:
        entry = self.resolve(tool_name)
        if not entry:
            return {"status": "error", "error": "Tool not found"}
        client = self._clients[entry.service_name]
        result = await client.call_tool(entry.tool_schema["name"], args)
        return result
```

#### `manager.py` — 生命周期管理

```python
class ProxyManager:
    """Manages all downstream MCP client connections."""

    def __init__(self):
        self.registry = ProxyRegistry()
        self._tasks: list[asyncio.Task] = []

    async def start(self, services: list[ServiceConfig]):
        """Connect to all registered services."""
        for svc in services:
            client = self._create_client(svc)
            ok = await self.registry.register_service(svc.name, client)
            if not ok:
                logger.warning("proxy_connect_failed", service=svc.name)

    async def stop(self):
        """Disconnect all clients."""
        ...

    def _create_client(self, svc) -> MCPClient:
        if svc.mcp_endpoint.startswith("http"):
            return HttpMCPClient(svc.name, svc.mcp_endpoint)
        elif svc.mcp_endpoint == "stdio" and svc.command:
            return StdioMCPClient(svc.name, svc.command, svc.args)
        ...
```

### 2. 集成到现有 `server/mcp.py`

```python
# 新增：初始化时启动 ProxyManager
_proxy_manager: ProxyManager | None = None

def init_proxy():
    global _proxy_manager
    _proxy_manager = ProxyManager()
    services = registry.list_all()
    asyncio.create_task(_proxy_manager.start(services))

# 新增：动态工具路由
@mcp.tool()
async def proxy_call(tool_name: str, arguments: str = "{}") -> str:
    """Call a downstream service tool through the proxy."""
    args = json.loads(arguments)
    result = await _proxy_manager.dispatch(tool_name, args)
    return json.dumps(result, ensure_ascii=False)

# 或者更激进：将下游工具直接注册为 Agora 的 tools
# 在 init_proxy() 中调用 mcp.add_tool() 动态注册
```

### 3. 服务配置

需要在 `agora-services.json` 中为每个 stdio 服务补充 `command`/`args`，以便 Agora 能 spawn 子进程。例如：

```json
{
  "name": "kos",
  "mcp_endpoint": "stdio",
  "command": "python3",
  "args": ["/Users/xiamingxing/Workspace/Tools/kos/kos-mcp-server.py"],
  ...
}
```

---

## 执行计划

| Phase | 内容 | 估算 |
|-------|------|------|
| **P1** | 实现 `MCPClient` 基类 + `StdioMCPClient` | 半天 |
| **P2** | 实现 `ProxyRegistry` + `ProxyManager` | 半天 |
| **P3** | 集成到 `server/mcp.py`，动态注册工具 | 半天 |
| **P4** | 补充服务配置（command/args），端到端验证 | 半天 |
| **P5** | 熔断器集成 + 事件总线集成 | 半天 |

总计：**2.5 天**

---

## 注意事项

1. **MCP 协议兼容**：下游服务需实现标准 MCP 协议（`initialize`、`tools/list`、`tools/call`）。当前所有服务（kos/minerva/sophia/ontoderise）都使用 FastMCP，天然兼容。
2. **子进程生命周期**：StdioClient 需要管理子进程退出、重启、超时。
3. **JSON-RPC 请求 ID 去重**：多个并发调用需要唯一 ID + Future 映射。
4. **SSRF 防护**：HTTP client 保留本地地址白名单（开发环境放行 localhost）。
5. **工具名冲突**：不同服务可能有同名工具，用 `服务名.工具名` 命名空间区分。
6. **资源/提示词代理**：可扩展 `resources/list`、`prompts/list` 代理。
