#!/bin/bash
# Fault Injection Demo — 断路器完整生命周期演示
# 场景: 注册一个测试服务 → 模拟3次失败 → 断路器OPEN → 冷却恢复 → CLOSED
set -euo pipefail

AGORA="${AGORA_BIN:-agora}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   🛡️  断路器生命周期演示                                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Register a test service pointing to a non-existent port
echo "━ Step 1: 注册测试服务 (端口 19999, 不存在的服务)"
$AGORA register "demo-fault" --port 19999 --health "http://localhost:19999/health" 2>/dev/null || true
$AGORA info demo-fault 2>/dev/null || echo "  (服务已存在, 继续)"
echo ""

# Step 2: Inject 3 failures via health check probe
echo "━ Step 2: 触发 3 次健康检查失败 (模拟服务宕机)"
PYTHON=$(dirname $AGORA)/python
for i in 1 2 3; do
    echo "  尝试 $i..."
    $PYTHON -c "
from agora.registry import ServiceRegistry
r = ServiceRegistry()
r.mark_failure('demo-fault')
s = r.get('demo-fault')
print(f'    failure_count={s.failure_count}, circuit={s.circuit_state}, healthy={s.healthy}')
"
done
echo ""

# Step 3: Verify circuit is OPEN
echo "━ Step 3: 检查断路器状态 (应为 OPEN)"
/Users/xiamingxing/Workspace/agora/.venv/bin/python -c "
from agora.registry import ServiceRegistry
r = ServiceRegistry()
s = r.get('demo-fault')
print(f'  状态: {s.circuit_state}')
print(f'  失败次数: {s.failure_count}')
print(f'  可用: {s.is_available}')
assert s.circuit_state == 'OPEN', f'Expected OPEN, got {s.circuit_state}'
print('  ✅ 断路器已打开, 服务被隔离')
" 2>/dev/null
echo ""

# Step 4: Recover — mark successes to gradually close circuit
echo "━ Step 4: 服务恢复, 逐步关闭断路器"
for i in 1 2 3 4; do
    /Users/xiamingxing/Workspace/agora/.venv/bin/python -c "
from agora.registry import ServiceRegistry
r = ServiceRegistry()
r.mark_success('demo-fault')
s = r.get('demo-fault')
print(f'    success $i: failure_count={s.failure_count}, circuit={s.circuit_state}, healthy={s.healthy}')
" 2>/dev/null
done
echo ""

# Step 5: Verify circuit is CLOSED
echo "━ Step 5: 验证断路器已恢复"
/Users/xiamingxing/Workspace/agora/.venv/bin/python -c "
from agora.registry import ServiceRegistry
r = ServiceRegistry()
s = r.get('demo-fault')
assert s.circuit_state == 'CLOSED', f'Expected CLOSED, got {s.circuit_state}'
print(f'  ✅ 断路器已关闭, 服务恢复可用')
" 2>/dev/null
echo ""

# Cleanup
$AGORA unregister demo-fault 2>/dev/null || true
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ✅ 故障恢复演示完成: OPEN → HALF_OPEN → CLOSED          ║"
echo "╚══════════════════════════════════════════════════════════╝"
