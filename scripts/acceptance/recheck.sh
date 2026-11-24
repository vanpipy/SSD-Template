#!/usr/bin/env bash
# recheck.sh — 合并前的全量复跑(门禁 + 扫描一致性 + 单测 + 验收)
#
# 仓根从脚本自身位置推导(不写死机器路径)。
# 门禁只跑**一遍**:run-all-gates.sh 现在消费 `ssdctl gate --json`,已经包含
# 仓内门禁 + 判据引擎 + 制品自洽性 —— 所以不再单独再跑一次 `ssdctl gate`
# (那会把同一批门禁跑两遍)。
#
# 解释器口径唯一:`bash scripts/ssdctl.sh --python`。
set -u
cd "$(dirname "$0")/../.." || exit 2
fail=0

echo "=== 1. gates(仓内门禁 + 判据 + 制品自洽) ==="
bash scripts/acceptance/run-all-gates.sh || fail=1

echo "=== 2. ssdctl scan --check ==="
bash scripts/ssdctl.sh scan --check || fail=1

echo "=== 3. unit tests ==="
PY="$(bash scripts/ssdctl.sh --python)" || exit 2
"$PY" -m unittest discover -s scripts/tests -t scripts/tests || fail=1

echo "=== 4. acceptance ==="
"$PY" scripts/acceptance/agent-first-acceptance.py || fail=1

echo "=== OVERALL fail=$fail ==="
exit $fail
