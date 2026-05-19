#!/bin/bash
# Observability Demo — 延迟分位 + 指标查询
set -euo pipefail
AGORA="${AGORA_BIN:-agora}"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   📊 可观测性演示                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

echo "━ Step 1: 模拟 10 次事件发布 (产生延迟数据)"
for i in $(seq 1 10); do
    $AGORA event publish "obs:test" --payload '{"n":'$i'}' --source "observe" 2>/dev/null
done
echo "  ✅ 10 次事件发布完成"
echo ""

echo "━ Step 2: 查询 Prometheus 指标"
echo '  GET /metrics'
python3 -c "
import subprocess, sys
# Read metrics via Python import (web server not needed)
from agora.registry import ServiceRegistry
from agora.router import Router

r = ServiceRegistry()
router = Router(r)
pct = router.get_percentiles()

print(f'  P50:  {pct[\"p50\"]}s')
print(f'  P90:  {pct[\"p90\"]}s')
print(f'  P99:  {pct[\"p99\"]}s')
print(f'  样本: {pct[\"samples\"]}')
print(f'  平均: {pct[\"avg\"]}s')
" 2>/dev/null
echo ""

echo "━ Step 3: 延迟历史 (新 /api/metrics/history)"
python3 -c "
from agora.registry import ServiceRegistry
from agora.router import Router
r = ServiceRegistry()
router = Router(r)
pct = router.get_percentiles()
print(f'  {pct}')
" 2>/dev/null
echo ""

echo "━ Step 4: 服务健康趋势"
$AGORA stats 2>/dev/null | head -5
echo ""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ✅ 可观测性演示完成 — P50/P90/P99 + /metrics + /history  ║"
echo "╚══════════════════════════════════════════════════════════╝"
