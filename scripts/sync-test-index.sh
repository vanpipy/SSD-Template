#!/usr/bin/env bash
# sync-test-index.sh — 再生成 test_cases/_index.md 索引表（幂等）
#
# 职责边界(契约 M12): 本脚本**只写** `test_cases/_index.md` 一个文件, 不碰任何其他文件。
# 数据唯一真源 = 各用例文档的元信息表。
#
# 退出码(契约 M1): 0=通过/已更新 1=违规(--check 发现差异) 2=调用错误 / 环境错误
#   - `test_cases/` 不存在 → 该层未启用 → 跳过, exit 0(契约 M6/M11: 层缺失=跳过, 不是违规)
#   - `--check` 且索引与文档元信息不一致 → exit 1
#
# 用法:
#   scripts/sync-test-index.sh [--json] [--root DIR] [--check]
#
# 可移植性(契约 M9):
#   - 不用 `find -mindepth/-maxdepth`; 全深度扫描 + 形状判定
#   - 不用 GNU sed 的 -E; P0 数字用 grep -oE 提取

set -uo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"

SCRIPT_PATH=$0
SCRIPT_DIR=$(cd -- "$(dirname -- "$SCRIPT_PATH")" >/dev/null 2>&1 && pwd)
DEFAULT_ROOT=$(dirname -- "$SCRIPT_DIR")

JSON=0
ROOT=""
CHECK_MODE=0
NO_COLOR=${NO_COLOR:-0}

while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    --check) CHECK_MODE=1 ;;
    --root)
      [ $# -ge 2 ] || { printf '✗ --root 需要目录参数\n' >&2; exit 2; }
      ROOT="$2"; shift ;;
    --root=*) ROOT="${1#--root=}" ;;
    --help|-h) printf '用法: %s [--json] [--root DIR] [--check]\n' "$SCRIPT_PATH"; exit 0 ;;
    -*) printf '✗ 未知参数: %s\n' "$1" >&2; exit 2 ;;
    *) printf '✗ 不接受位置参数: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

[ -n "$ROOT" ] || ROOT="$DEFAULT_ROOT"
if [ ! -d "$ROOT" ]; then
  printf '✗ --root 目录不存在: %s\n' "$ROOT" >&2
  exit 2
fi
ROOT=$(cd -- "$ROOT" >/dev/null 2>&1 && pwd -P)

if [ "$NO_COLOR" = "1" ]; then
  C_ERR=''; C_WARN=''; C_OK=''; C_DIM=''; C_RESET=''
else
  C_ERR=$'\033[0;31m'; C_WARN=$'\033[0;33m'; C_OK=$'\033[0;32m'; C_DIM=$'\033[0;36m'; C_RESET=$'\033[0m'
fi

ERRORS=()
WARNINGS=()
NOTES=()
err()  { ERRORS+=("$1"); [ "$JSON" -eq 1 ] || printf '%s✗%s %s\n' "$C_ERR" "$C_RESET" "$1"; }
warn() { WARNINGS+=("$1"); [ "$JSON" -eq 1 ] || printf '%s⚠%s %s\n' "$C_WARN" "$C_RESET" "$1"; }
note() { NOTES+=("$1"); [ "$JSON" -eq 1 ] || printf '%s·%s %s\n' "$C_DIM" "$C_RESET" "$1"; }
ok()   { [ "$JSON" -eq 1 ] || printf '%s✓%s %s\n' "$C_OK" "$C_RESET" "$1"; }

json_escape() {
  awk 'BEGIN{ORS=""} { if (NR>1) printf "\\n"; gsub(/\\/,"\\\\"); gsub(/"/,"\\\""); gsub(/\t/,"\\t"); gsub(/\r/,"\\r"); printf "%s", $0 }'
}
json_str_array() {
  local first=1 item
  printf '['
  for item in "$@"; do
    if [ "$first" -eq 1 ]; then first=0; else printf ','; fi
    printf '"%s"' "$(printf '%s' "$item" | json_escape)"
  done
  printf ']'
}

TOPIC_RE='^[a-z0-9]+(-[a-z0-9]+)*$'
DATE_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}$'

INDEX="$ROOT/test_cases/_index.md"
BEGIN_MARK='<!-- test-index:begin — 由 scripts/sync-test-index.sh 自动生成，勿手改 -->'
END_MARK='<!-- test-index:end -->'

# 层未启用 → 跳过(不是违规)
if [ ! -d "$ROOT/test_cases" ]; then
  note "测试用例层未启用(test_cases/ 不存在), 跳过索引同步"
  if [ "$JSON" -eq 1 ]; then
    printf '{"script":"sync-test-index.sh","root":"%s","status":"pass","exit_code":0,"error_count":0,"warning_count":0,"rows":0,"skipped":true,"errors":[],"warnings":[],"notes":%s}\n' \
      "$(printf '%s' "$ROOT" | json_escape)" "$(json_str_array "${NOTES[@]+"${NOTES[@]}"}")"
  fi
  exit 0
fi

meta_field() {
  awk -F'|' -v k="$2" '/^\|/ {
    key=$2; val=$3;
    gsub(/^[ \t]+|[ \t]+$/, "", key); gsub(/^[ \t]+|[ \t]+$/, "", val);
    gsub(/\*+/, "", key);
    if (key==k) { print val; exit }
  }' "$1" 2>/dev/null
}

keys=()
vals=()

for f in "$ROOT"/test_cases/*/*.md; do
  [ -f "$f" ] || continue
  d=$(dirname -- "$f")
  date_dir=$(basename -- "$d")
  base=$(basename -- "$f" .md)
  case "$base" in *-key-points) continue ;; esac
  printf '%s' "$date_dir" | grep -Eq "$DATE_RE" || continue
  # 主用例 topic 与冒烟 topic 必须符合命名约定
  case "$base" in
    *-smoke) topic="${base%-smoke}" ;;
    *) topic="$base" ;;
  esac
  printf '%s' "$topic" | grep -Eq "$TOPIC_RE" || continue

  rel="${date_dir}/${base}.md"
  subject=$(meta_field "$f" "主题")
  [ -z "$subject" ] && subject="$topic"
  biz=$(meta_field "$f" "业务产品")
  plat=$(meta_field "$f" "目标平台")
  total_line=$(meta_field "$f" "用例总数")
  n=$(printf '%s' "$total_line" | grep -oE '^[0-9]+' || true)
  [ -z "$n" ] && n="?"
  if printf '%s' "$total_line" | grep -q '全部 P0'; then
    p0="$n"
  else
    p0=$(printf '%s' "$total_line" | grep -oE 'P0: *[0-9]+' | head -1 | grep -oE '[0-9]+' || true)
    [ -z "$p0" ] && p0="0"
  fi
  st=$(meta_field "$f" "状态")

  kp_rel="${date_dir}/${topic}-key-points.md"
  if [ -f "$ROOT/test_cases/$kp_rel" ]; then
    kp_link="[key-points](${kp_rel})"
  else
    kp_link="—"
  fi

  case "$base" in
    *-smoke) is_smoke=1 ;;
    *) is_smoke=0 ;;
  esac
  keys+=("${date_dir}/${topic}/${is_smoke}")
  vals+=("| ${date_dir} | ${subject} | ${biz} | ${plat} | ${n} | ${p0} | ${st} | [${base}.md](${rel}) | ${kp_link} |")
done

generate_block() {
  printf '%s\n' "$BEGIN_MARK"
  printf '| 日期 | 主题 | 业务产品 | 平台 | 用例数 | P0 | 状态 | 用例文件 | 要点文件 |\n'
  printf '|------|------|---------|------|--------|----|----|---------|--------|\n'
  if [ "${#keys[@]}" -gt 0 ]; then
    while IFS= read -r k; do
      i=0
      while [ "$i" -lt "${#keys[@]}" ]; do
        if [ "${keys[$i]}" = "$k" ]; then
          printf '%s\n' "${vals[$i]}"
          break
        fi
        i=$((i+1))
      done
    done < <(printf '%s\n' "${keys[@]}" | sort)
  fi
  printf '%s\n' "$END_MARK"
}

generate_file() {
  printf '# 测试用例索引\n'
  printf '\n'
  printf '> 由 `scripts/sync-test-index.sh` 自动生成（标记块内勿手改）。数据源：各用例文档元信息表。\n'
  printf '> 伴生要点文件不单独登记。\n'
  printf '\n'
  generate_block
}

tmp="$ROOT/test_cases/.index.tmp"
generate_file > "$tmp"

if [ "$CHECK_MODE" -eq 1 ]; then
  if [ ! -f "$INDEX" ]; then
    err "test_cases/_index.md 不存在 — 运行 \`scripts/sync-test-index.sh\` 生成"
    rm -f "$tmp"
  elif ! diff -u "$INDEX" "$tmp" >/dev/null 2>&1; then
    err "test_cases/_index.md 与文档元信息不一致 — 运行 \`scripts/sync-test-index.sh\` 再生成"
    if [ "$JSON" -eq 0 ]; then diff -u "$INDEX" "$tmp" | sed 's/^/  /' || true; fi
    rm -f "$tmp"
  else
    rm -f "$tmp"
    ok "test_cases/_index.md 与文档元信息一致 (${#keys[@]} 行)"
  fi
else
  if [ -f "$INDEX" ] && diff -q "$INDEX" "$tmp" >/dev/null 2>&1; then
    rm -f "$tmp"
    ok "test_cases/_index.md 已是最新 (${#keys[@]} 行)"
  else
    mv "$tmp" "$INDEX"
    ok "test_cases/_index.md 已再生成 (${#keys[@]} 行)"
  fi
fi

ERRC=${#ERRORS[@]}
WARNC=${#WARNINGS[@]}
if [ "$ERRC" -gt 0 ]; then STATUS="violation"; EXIT=1; else STATUS="pass"; EXIT=0; fi

if [ "$JSON" -eq 1 ]; then
  printf '{"script":"sync-test-index.sh","root":"%s","status":"%s","exit_code":%d,"error_count":%d,"warning_count":%d,"rows":%d,"errors":%s,"warnings":%s,"notes":%s}\n' \
    "$(printf '%s' "$ROOT" | json_escape)" "$STATUS" "$EXIT" "$ERRC" "$WARNC" "${#keys[@]}" \
    "$(json_str_array "${ERRORS[@]+"${ERRORS[@]}"}")" \
    "$(json_str_array "${WARNINGS[@]+"${WARNINGS[@]}"}")" \
    "$(json_str_array "${NOTES[@]+"${NOTES[@]}"}")"
fi
exit $EXIT
