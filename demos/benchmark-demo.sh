#!/bin/bash
# Performance Baseline Demo — pipeline 延迟 + 历史对比
set -euo pipefail
AGORA="${AGORA_BIN:-agora}"

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ⚡ 性能基线演示                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

echo "━ Step 1: 运行 5 次事件发布, 测量延迟"
RESULTS="/tmp/agora-bench-$(date +%Y%m%d).json"
python3 -c "
import json, time, subprocess, sys
agora = sys.argv[1] if len(sys.argv) &gt; 1 else 'agora'

measurements = []
for i in range(5):
    start = time.monotonic()
    subprocess.run([agora, 'event', 'publish', f'bench:{i}', '--payload', '{}', '--source', 'benchmark'],
                   capture_output=True, timeout=10)
    elapsed = round(time.monotonic() - start, 4)
    measurements.append({'run': i, 'elapsed_s': elapsed})
    print(f'  run {i}: {elapsed}s')

avg = sum(m['elapsed_s'] for m in measurements) / len(measurements)
print(f'\n  平均延迟: {avg:.4f}s')
print(f'  最快: {min(m[\"elapsed_s\"] for m in measurements):.4f}s')
print(f'  最慢: {max(m[\"elapsed_s\"] for m in measurements):.4f}s')

# Compare with previous baseline if exists
import os
baseline_path = '/tmp/agora-bench-baseline.json'
if os.path.exists(baseline_path):
    prev = json.load(open(baseline_path))
    prev_avg = sum(m['elapsed_s'] for m in prev) / len(prev)
    delta = avg - prev_avg
    direction = '↑ SLOWER' if delta &gt; 0 else '↓ FASTER'
    print(f'\n  上次平均: {prev_avg:.4f}s')
    print(f'  变化: {abs(delta):.4f}s {direction}')

# Save as new baseline
json.dump(measurements, open(baseline_path, 'w'))
print(f'\n  基线已保存: {baseline_path}')
" "$AGORA"
echo ""

echo "╔══════════════════════════════════════════════════════════╗"
echo "║   ✅ 性能基线演示完成                                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
