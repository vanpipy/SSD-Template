#!/usr/bin/env bash
# a17-e2e.sh — A17 端到端验收(驱动 Symphony runner 跑一轮,再拿仓内门禁复核工作区)
#
# 路径与解释器都不再写死:
#   - 本仓根 = 脚本自身位置推导;
#   - runner  = 本仓的**同级目录** symphony-runner(可用 $SYMPHONY_RUNNER 覆盖);
#   - 解释器 = `bash scripts/ssdctl.sh --python`(全仓唯一口径)。
#
# 用法: bash scripts/acceptance/a17-e2e.sh [--dry-run-only]
set -u

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
RUNNER="${SYMPHONY_RUNNER:-$(dirname "$REPO")/symphony-runner}"
WORKFLOW="$REPO/WORKFLOW.md"
DRY_ONLY=0
[ "${1:-}" = "--dry-run-only" ] && DRY_ONLY=1

if [ ! -d "$RUNNER" ]; then
  echo "FAIL: symphony runner not found: $RUNNER (set SYMPHONY_RUNNER=<path>)"
  exit 2
fi

PY="$(bash "$REPO/scripts/ssdctl.sh" --python)" || {
  echo "FAIL: cannot resolve the python interpreter (bash scripts/ssdctl.sh --python)"
  exit 2
}

export PYTHONPATH="$RUNNER/src"
export DSH_PERMISSION_MODE=workspace-write
export PYTHONIOENCODING=utf-8

cd "$RUNNER" || { echo "FAIL: cannot cd to $RUNNER"; exit 2; }

echo "=== 0. 单元测试 ==="
"$PY" -m unittest discover -s tests 2>&1 | tail -4
echo "unittest exit=${PIPESTATUS[0]}"

echo
echo "=== 1. dry-run(不调 DSH) ==="
"$PY" -m symphony_runner.cli \
  --workflow "$WORKFLOW" \
  --issues-file examples/issues.json \
  --tracker memory \
  --dry-run \
  --clone-source "$REPO" \
  --json
echo "dry-run exit=$?"

if [ "$DRY_ONLY" -eq 1 ]; then exit 0; fi

echo
echo "=== 2. 真跑一轮(DSH 跑一个 turn) ==="
"$PY" -m symphony_runner.cli \
  --workflow "$WORKFLOW" \
  --issues-file examples/issues.json \
  --tracker memory \
  --once \
  --clone-source "$REPO" \
  --json
rc=$?
echo "runner exit=$rc"

echo
echo "=== 3. 工作区内容 ==="
ws_root="$HOME/code/symphony-workspaces"
ls -1 "$ws_root" 2>/dev/null || echo "(工作区根目录不存在: $ws_root)"
for ws in "$ws_root"/*/; do
  [ -d "$ws" ] || continue
  echo "--- 工作区: $ws"
  ls -1 "$ws" | head -20
  echo "--- 制品:"
  find "$ws" -path '*/.git' -prune -o -name '*.md' -path '*prd*' -print 2>/dev/null | head -10
  echo "--- 门禁:"
  for s in check-line-endings check-naming check-md-schema check-traceability check-repo-baseline; do
    out="$(cd "$ws" && bash "scripts/$s.sh" 2>&1)"; r=$?
    printf '    %-26s exit=%s\n' "$s" "$r"
    [ "$r" -ne 0 ] && printf '%s\n' "$out" | sed 's/^/        | /' | head -20
  done
  out="$(cd "$ws" && "$PY" scripts/check-doc-links.py 2>&1)"; r=$?
  printf '    %-26s exit=%s\n' "check-doc-links.py" "$r"
  [ "$r" -ne 0 ] && printf '%s\n' "$out" | sed 's/^/        | /' | head -10
done

echo
echo "=== 4. API key 明文扫描 ==="
grep -rInE "sk-[A-Za-z0-9]{16,}|[A-Za-z0-9_-]{32,}" "$ws_root" --include='*.md' --include='*.json' --include='*.yml' 2>/dev/null | head -10
echo "(以上若为空则无明文 key)"

exit "$rc"
