# Agora 基础设施迭代计划

> 定位: API Gateway for AI Agents — 生产级基础设施
> 基于 RedTeam 对抗分析的5个漏洞集群

---

## 修复进度

### Cluster 1: In-Memory Amnesia 🟡

| 项 | 描述 | 状态 |
|---|------|------|
| 1.1 | 断路器状态持久化 (JSON) | ✅ `_load/_save` 已持久化 |
| 1.2 | Event subscription TTL + 心跳 | ⏳ 添加 24h TTL |
| 1.3 | Trace buffer 优雅关闭 | ⏳ atexit flush |
| 1.4 | 进程重启后断路器状态恢复 | ✅ 已从 JSON 加载 |
| 1.5 | Dead subscriber 清理 | ⏳ subscription.last_seen |

### Cluster 2: Silent Failure Propagation 🟡

| 项 | 描述 | 状态 |
|---|------|------|
| 2.1 | 全量 structlog 覆盖 | 🟡 17个点，10个已修 |
| 2.2 | 健康检查失败日志 | ✅ registry.py 已有 |
| 2.3 | 事件投递失败记录 | ✅ event_bus.py 已有 |
| 2.4 | Pipeline 失败上下文 | ✅ pipeline.py 已有 |

### Cluster 3: Interface Proliferation ✅

| 项 | 描述 | 状态 |
|---|------|------|
| 3.1 | JSON Schema 文档 | ✅ CONTRACTS.md |
| 3.2 | CLI `--json` 一致性 | 🟡 部分命令缺失 |
| 3.3 | MCP 工具输入验证 | ✅ FastMCP 内置 |
| 3.4 | REST API 响应格式统一 | ✅ FastAPI 自动 |

### Cluster 4: Localhost Security ✅

| 项 | 描述 | 状态 |
|---|------|------|
| 4.1 | CORS 限制 | ✅ 已限制 localhost:7430 |
| 4.2 | SSRF 防护 (统一) | ✅ registry + webhook + instance |
| 4.3 | Dashboard API Key | ⏳ |
| 4.4 | Market 代码执行沙箱 | ⏳ |

### Cluster 5: Deployment Fiction 🟡

| 项 | 描述 | 状态 |
|---|------|------|
| 5.1 | Dockerfile | ⏳ 待创建 |
| 5.2 | PyPI 发布 | ⏳ CI workflow 已有 |
| 5.3 | docker-compose 可用镜像 | ⏳ 待推送 |
| 5.4 | Health check endpoint | ✅ /api/health |

---

## 迭代路线

### Sprint 1 (本周) — 可靠性

```
目标: 零静默失败 + 优雅关闭
  □ 17个 except 点全量 structlog
  □ atexit flush trace buffer
  □ Dashboard API Key 认证
  □ subscription TTL 24h
```

### Sprint 2 (下周) — 可部署

```
目标: 可被其他人安装使用
  □ Dockerfile (multi-stage, <200MB)
  □ Docker Hub push starlink-awaken/agora:1.2
  □ PyPI publish agora-mcp==1.2.0
  □ CI: test + build + push on tag
```

### Sprint 3 — 可观测

```
目标: 运维可见性
  □ Prometheus alert rules
  □ Grafana dashboard JSON
  □ 断路器状态变更通知 (webhook集成)
  □ P50/P90/P99 历史趋势
```

### Sprint 4 — 生产就绪

```
目标: 企业级可靠性
  □ 断路器状态跨重启持久化 (SQLite)
  □ 事件总线 dead letter queue
  □ Pipeline 执行历史审计日志
  □ API rate limiting per tenant
```

---

## 关键决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 持久化引擎 | JSON (不变) | 开发工具 → 小规模基础设施，SQLite过重 |
| 认证方案 | API Key (X-API-Key header) | 简单，不需要OAuth |
| 部署方式 | Docker + PyPI | 覆盖容器化和pip用户 |
| 监控方案 | Prometheus + Grafana | 行业标准，已有/metrics |
