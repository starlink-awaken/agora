# AGENTS.md — Agora 项目 AI Agent 入口

> 本文件供 Claude Code / Codex / Cursor 等 AI 编码助手使用。

---

## 项目身份

- **名称**: Agora — MCP Service Convergence Hub
- **版本**: 1.2.0 (Beta)
- **定位**: API Gateway for AI Agents · Hub-Spoke 拓扑
- **Python**: >= 3.11
- **安装**: `pip install -e "."`

---

## 架构规则

1. **模块边界**: 每个 `.py` 单一职责，不超过 300 行
2. **持久化**: 使用 `persistence.json_load/json_save`，不要直接 `json.load`
3. **日志**: 使用 `structlog`，不要 `print()` (CLI除外)
4. **SSRF防护**: 始终调用 `_is_safe_url()` 验证外部URL
5. **导入顺序**: stdlib → 第三方 → 项目内部 (ruff I001)
6. **测试**: 每个新模块必须 `tests/test_<module>.py`

---

## 关键模块

| 文件 | 行数 | 核心类/函数 |
|------|------|-----------|
| `registry.py` | 271 | `Service`, `ServiceRegistry`, `_is_safe_url` |
| `router.py` | 201 | `Router`, `_maybe_publish`, `get_percentiles` |
| `event_bus.py` | 163 | `EventBus`, `Subscription` |
| `pipeline.py` | 256 | `Pipeline`, `run/run_stream/run_parallel` |
| `discovery.py` | 367 | `DiscoveryEngine`, `DiscoveredService` |
| `market.py` | 241 | `Market` |
| `cli.py` | 556 | `main`, 20 子命令 |
| `server/mcp.py` | 162 | 9 MCP 工具 |
| `web/app.py` | 221 | 14 REST 端点 |
| `wizard.py` | 67 | `run_wizard` |

---

## 常用命令

```bash
# 测试
python -m pytest tests/ tests/e2e/ -q

# 代码质量
ruff check src/agora/ --select F,E,I,N,W,UP,B,C4,SIM

# 运行
agora web          # Dashboard
agora mcp          # MCP Server
agora discover     # 服务发现
```

---

## 值传递约定

- **无全局可变状态** (模块级 `_bus`, `registry` 仅在 server/mcp.py)
- **依赖注入**: Router/EventBus/Pipeline 接受构造参数
- **错误处理**: CLI 入口捕获异常显示友好信息

---

## 当前状态

- **测试**: 61 passed, 0 failed
- **ruff**: 0 errors
- **覆盖率**: ~28%
- **文档**: README + QUICKSTART + INSTALL + PRODUCT_PLAN + INFRA_PLAN + API_REFERENCE + USER_GUIDE
