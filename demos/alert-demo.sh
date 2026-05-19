#!/bin/bash
# Alert Webhook Demo — 断路器状态变更自动通知
set -euo pipefail
AGORA="${AGORA_BIN:-agora}"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   🔔  告警 Webhook 演示                                    ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Start a simple echo server to receive webhooks
echo "━ Step 1: 启动 echo 服务器 (localhost:19998)"
python3 -c "
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, sys, threading

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode()
        print(f'  📨 Webhook received: {body[:200]}')
        self.send_response(200)
        self.end_headers()
    def log_message(self, *args): pass

server = HTTPServer(('localhost', 19998), Handler)
thread = threading.Thread(target=server.serve_forever, daemon=True)
thread.start()
print('  Echo server running on :19998')
import time; time.sleep(0.5)
" &

# Step 2: Register a service with alert webhook
echo ""
echo "━ Step 2: 注册服务 + 配置告警 webhook"
python3 -c "
from agora.registry import ServiceRegistry
r = ServiceRegistry(alert_webhook='http://localhost:19998/alert')

# Simulate 3 failures to trigger alert
svc = type('Svc', (), {'name': 'demo-alert', 'port': 19999})()
r.register(svc) if 'demo-alert' not in {s.name for s in r.list_all()} else None
for _ in range(3):
    r.mark_failure('demo-alert')
s = r.get('demo-alert')
print(f'  断路器状态: {s.circuit_state}')
print(f'  Webhook 已发送到 http://localhost:19998/alert')
r.unregister('demo-alert')
" 2>/dev/null
echo ""

sleep 1
echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ✅ 告警演示完成 — 断路器 OPEN 时自动通知 webhook         ║"
echo "╚══════════════════════════════════════════════════════════╝"
kill %1 2>/dev/null || true
