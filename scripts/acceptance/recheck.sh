#!/usr/bin/env bash
# recheck.sh — 合并 amend 前的全量复跑(gates + ssdctl + 单测 + 验收)
set -u
cd /d/project/SSD-Template || exit 2
fail=0

echo "=== 1. 8 gates ==="
bash scripts/acceptance/run-all-gates.sh || fail=1

echo "=== 2. ssdctl gate ==="
bash scripts/ssdctl.sh gate || fail=1

echo "=== 3. ssdctl scan --check ==="
bash scripts/ssdctl.sh scan --check || fail=1

echo "=== 4. unit tests ==="
PY="$(bash scripts/ssdctl.sh --python)"
"$PY" -m unittest discover -s scripts/tests -t scripts/tests || fail=1

echo "=== 5. acceptance ==="
"$PY" scripts/acceptance/agent-first-acceptance.py || fail=1

echo "=== OVERALL fail=$fail ==="
exit $fail
