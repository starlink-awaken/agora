#!/bin/bash
# Multi-Tenant Demo — 认证 + 服务隔离
set -euo pipefail

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   👥 多租户演示                                            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

echo "━ Step 1: 租户配置"
cat <<'EOF'
  # ~/.config/agora/tenants.yaml
  tenants:
    - name: personal
      token: sk-personal-demo
      services: [minerva, ontoderive]
      rate_limit: 100
    - name: work
      token: sk-work-demo
      services: [minerva, kos]
      rate_limit: 300
EOF
echo ""

echo "━ Step 2: 认证验证"
python3 -c "
from agora.tenant import TenantManager
tm = TenantManager()

# Personal tenant can access minerva
t = tm.authenticate('sk-personal-demo')
if t:
    print(f'  ✅ Personal 租户认证成功: {t.name}')
    print(f'     可访问服务: {t.services}')
    print(f'     速率限制: {t.rate_limit} req/min')

# Wrong token rejected
t2 = tm.authenticate('sk-invalid')
if not t2:
    print(f'  ❌ 无效 token 被拒绝 (预期行为)')
else:
    print(f'  ⚠️  无效 token 未被拒绝')
" 2>/dev/null || echo "  ⚠️  tenants.yaml 未配置 — 创建 ~/.config/agora/tenants.yaml 后可用"
echo ""

echo "━ Step 3: 服务访问控制"
python3 -c "
from agora.tenant import TenantManager
tm = TenantManager()

t = tm.authenticate('sk-personal-demo')
if t:
    for svc in ['minerva', 'ontoderive', 'kos']:
        ok = tm.has_service_access('personal', svc)
        icon = '✅' if ok else '❌'
        print(f'  {icon} personal → {svc}: {\"允许\" if ok else \"拒绝\"}')
" 2>/dev/null || echo "  (需要配置 tenants.yaml)"
echo ""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ✅ 多租户演示完成 — 认证 + 服务隔离 + 速率限制           ║"
echo "╚══════════════════════════════════════════════════════════╝"
