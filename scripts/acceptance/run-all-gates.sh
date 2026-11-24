#!/usr/bin/env bash
# Lead-owned acceptance harness (lives in scripts/acceptance/ and IS version-controlled).
# Runs the 9 canonical gates in M8 order and reports exit code + stdout emptiness per step.
# Usage: bash scripts/acceptance/run-all-gates.sh [repo_root]
set -u

ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT" || { echo "FAIL: cannot cd to $ROOT"; exit 2; }

GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-}"

steps=(
  "scripts/check-line-endings.sh"
  "scripts/check-naming.sh"
  "scripts/check-md-schema.sh"
  "scripts/check-traceability.sh"
  "scripts/check-repo-baseline.sh"
  "scripts/check-doc-links.py"
  "scripts/sync-prd.sh --check"
  "scripts/sync-test-index.sh --check"
)

# interpreter discovery: python3 > python > DSH bundled runtime python
# (this machine has no system python; `python` is the Microsoft Store stub that exits 49)
if [ -z "${PYTHON_BIN:-}" ]; then
  for cand in python3 python "/c/Users/leroy/.dsh/dsh-runtimes/dsh-primary-runtime/dependencies/python/python.exe"; do
    if command -v "$cand" >/dev/null 2>&1; then
      if "$cand" -c 'import sys' >/dev/null 2>&1; then PYTHON_BIN="$cand"; break; fi
    elif [ -x "$cand" ]; then
      if "$cand" -c 'import sys' >/dev/null 2>&1; then PYTHON_BIN="$cand"; break; fi
    fi
  done
fi
PYTHON_BIN="${PYTHON_BIN:-python}"

overall=0
printf '%-34s %-6s %-8s %s\n' "STEP" "EXIT" "STDOUT" "NOTE"
printf -- '----------------------------------------------------------------------\n'

for step in "${steps[@]}"; do
  script="${step%% *}"
  args="${step#* }"
  if [ "$args" = "$script" ]; then args=""; fi

  if [ ! -f "$script" ]; then
    printf '%-34s %-6s %-8s %s\n' "$script" "MISS" "-" "script not found"
    overall=1
    continue
  fi

  out="$(mktemp)"
  case "$script" in
    *.py) "$PYTHON_BIN" "$script" $args >"$out" 2>&1 ;;
    *)    bash "$script" $args >"$out" 2>&1 ;;
  esac
  rc=$?
  bytes=$(wc -c <"$out" | tr -d ' ')
  note=""
  # anti-idle assertion: a passing gate that printed nothing may have silently no-opped
  if [ "$rc" -eq 0 ] && [ "$bytes" -eq 0 ]; then
    note="WARN: exit 0 with empty stdout (possible silent no-op)"
  fi
  printf '%-34s %-6s %-8s %s\n' "$script" "$rc" "$bytes" "$note"
  if [ -n "$out" ] && [ "$rc" -ne 0 ]; then
    sed 's/^/    | /' "$out"
  fi
  [ "$rc" -ne 0 ] && overall=1
  rm -f "$out"
done

printf -- '----------------------------------------------------------------------\n'
if [ "$overall" -eq 0 ]; then
  echo "RESULT: PASS"
else
  echo "RESULT: FAIL"
fi
exit "$overall"
