#!/bin/bash
# Agora Demo Recording Script — simulate user journey for GIF/documentation
AGORA="${AGORA_BIN:-agora}"

echo "╔════════════════════════════════════╗"
echo "║   Agora v1.2 — Demo Walkthrough   ║"
echo "╚════════════════════════════════════╝"
echo ""

echo "1️⃣  Discover services..."
$AGORA discover 2>/dev/null | head -6
echo ""

echo "2️⃣  Check health..."
$AGORA stats 2>/dev/null | head -5
echo ""

echo "3️⃣  Search for research tools..."
$AGORA search research 2>/dev/null
echo ""

echo "4️⃣  View service details..."
$AGORA info minerva 2>/dev/null | head -5
echo ""

echo "5️⃣  Browse MCP market..."
$AGORA market list 2>/dev/null | head -8
echo ""

echo "6️⃣  Publish event..."
$AGORA event publish "demo:walkthrough" --payload '{"ok":true}' --source "demo" 2>/dev/null
echo ""

echo "7️⃣  View event log..."
$AGORA event log --limit 3 2>/dev/null
echo ""

echo "8️⃣  Check config..."
$AGORA config 2>/dev/null
echo ""

echo "✅ Demo complete. Dashboard: http://localhost:7430"
