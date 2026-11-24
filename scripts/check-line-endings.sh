#!/usr/bin/env bash
# check-line-endings.sh — M7: 断言受版本控制的文本文件不含 CR 字节(行尾统一 LF)
#
# 背景: 仓内 `.gitattributes` 声明 `* text=auto eol=lf`。若工作区出现 CRLF,
#   POSIX shell 脚本会出现 `bad interpreter` / `syntax error near unexpected token`,
#   CI 在 Linux 上与本地在 Windows 上的结论就会不一致。本脚本把这件事变成机器门禁。
#
# 范围: 受版本控制的文本文件(在非 git 目录下退化为目录下的全部文件)。
#   二进制文件(含 NUL 字节)自动跳过 —— 它们允许 CRLF。
#   本脚本不涉及"层"的概念, 因此不适用 M6 的"本仓没有任何规格产物"规则。
#
# 用法:
#   bash scripts/check-line-endings.sh [--json] [--root DIR] [TARGET]
#     TARGET 可选: 单个文件或目录; 给了就只查它(单文件模式)。
#
# 退出码: 0=通过 1=存在 CR 字节 2=调用/环境错误

set -o pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"

SCRIPT_PATH=$0
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd -P)
DEFAULT_ROOT=$(dirname -- "$SCRIPT_DIR")

JSON=0
ROOT=""
TARGET=""

usage() {
  cat <<EOF
用法: bash scripts/check-line-endings.sh [--json] [--root DIR] [TARGET]

  --json         以 JSON 输出(供 CI 消费)
  --root DIR     仓根目录(默认: 本脚本所在目录的上一级)
  --stage        本门禁与阶段无关:阶段相关必填项由 scripts/check-md-schema.sh 判定。
                 收到 --stage 立即退出 2(不接受,也不回显)。
  TARGET         可选, 单个文件或目录; 给了则只检查它
  --help         显示本帮助

退出码: 0=通过 1=存在 CR 字节 2=调用/环境错误
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    --root)
      shift
      if [ $# -eq 0 ]; then printf '%s: --root 需要参数\n' "$SCRIPT_PATH" >&2; exit 2; fi
      ROOT=$1
      ;;
    --root=*) ROOT=${1#--root=} ;;
    --stage|--stage=*)
      printf '%s: 本门禁与阶段无关;--stage 只对 scripts/check-md-schema.sh 有效\n' "$SCRIPT_PATH" >&2
      exit 2
      ;;
    --help|-h) usage; exit 0 ;;
    --) shift; break ;;
    -*) printf '%s: 未知参数: %s\n' "$SCRIPT_PATH" "$1" >&2; usage >&2; exit 2 ;;
    *)
      if [ -n "$TARGET" ]; then printf '%s: 只接受一个 TARGET\n' "$SCRIPT_PATH" >&2; exit 2; fi
      TARGET=$1
      ;;
  esac
  shift
done

if [ -z "$ROOT" ]; then ROOT=$DEFAULT_ROOT; fi
if [ ! -d "$ROOT" ]; then printf '%s: 根目录不存在: %s\n' "$SCRIPT_PATH" "$ROOT" >&2; exit 2; fi
ROOT=$(CDPATH= cd -- "$ROOT" && pwd -P)

if [ -n "$TARGET" ]; then
  case "$TARGET" in
    /*) : ;;
    *) TARGET="$ROOT/$TARGET" ;;
  esac
  if [ ! -e "$TARGET" ]; then printf '%s: TARGET 不存在: %s\n' "$SCRIPT_PATH" "$TARGET" >&2; exit 2; fi
fi

if [ -n "${NO_COLOR:-}" ] || [ ! -t 1 ]; then
  C_OK=""; C_ERR=""; C_WARN=""; C_DIM=""; C_RESET=""
else
  C_OK=$(printf '\033[32m'); C_ERR=$(printf '\033[31m'); C_WARN=$(printf '\033[33m')
  C_DIM=$(printf '\033[2m'); C_RESET=$(printf '\033[0m')
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

# --- 文本/二进制判定: 含 NUL 字节即视为二进制 ---
is_binary_file() {
  local f=$1 total nul
  total=$(LC_ALL=C wc -c < "$f" 2>/dev/null | tr -d ' \t')
  nul=$(LC_ALL=C tr -d '\000' < "$f" 2>/dev/null | wc -c | tr -d ' \t')
  [ "$total" != "$nul" ]
}

# 文件含 CR 字节 ⇔ 去掉 CR 后与原文件不同
has_cr() {
  ! LC_ALL=C tr -d '\r' < "$1" | cmp -s - "$1"
}

# --- 文件清单 ---
FILE_LIST=""
LIST_MODE="git"
PATH_MODE="rel"   # rel: 清单是相对 ROOT 的路径; abs: 清单是绝对路径(单文件模式)
if [ -n "$TARGET" ]; then
  PATH_MODE="abs"
  if [ -d "$TARGET" ]; then
    FILE_LIST=$(cd "$TARGET" && find . -type f -not -path './.git/*' | sed "s|^\./|$TARGET/|" | LC_ALL=C sort)
  else
    FILE_LIST="$TARGET"
  fi
elif git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  FILE_LIST=$(git -C "$ROOT" ls-files)
else
  LIST_MODE="fs"
  FILE_LIST=$(cd "$ROOT" && find . -type f -not -path './.git/*' | sed 's|^\./||' | LC_ALL=C sort)
fi

if [ "$LIST_MODE" = "fs" ]; then
  note "不在 git 工作树内, 已退化为扫描目录下的全部文件"
fi

if [ -z "$FILE_LIST" ]; then
  ok "没有可检查的文件"
fi

CHECKED=0
SKIPPED_BIN=0

while IFS= read -r rel; do
  [ -z "$rel" ] && continue
  case "$rel" in .git/*) continue ;; esac
  f="$rel"; rel_display="$rel"
  if [ "$PATH_MODE" != "abs" ]; then
    f="$ROOT/$rel"
  else
    rel_display="${rel#$ROOT/}"
  fi
  [ -f "$f" ] || continue
  if is_binary_file "$f"; then
    SKIPPED_BIN=$((SKIPPED_BIN + 1))
    continue
  fi
  CHECKED=$((CHECKED + 1))
  if has_cr "$f"; then
    err "含 CR 字节(行尾不是 LF): $rel_display"
  fi
done <<EOF
$FILE_LIST
EOF

if [ ${#ERRORS[@]} -eq 0 ]; then
  ok "行尾检查通过: $CHECKED 个文本文件均为 LF (跳过二进制 $SKIPPED_BIN 个)"
fi

STATUS="pass"
CODE=0
if [ ${#ERRORS[@]} -gt 0 ]; then STATUS="violation"; CODE=1; fi

if [ "$JSON" -eq 1 ]; then
  printf '{"script":"check-line-endings.sh","root":"%s","status":"%s","exit_code":%d,"error_count":%d,"warning_count":%d,"checked_files":%d,"skipped_binary":%d,"errors":%s,"warnings":%s,"notes":%s}\n' \
    "$(printf '%s' "$ROOT" | json_escape)" "$STATUS" "$CODE" "${#ERRORS[@]}" "${#WARNINGS[@]}" \
    "$CHECKED" "$SKIPPED_BIN" \
    "$(json_str_array "${ERRORS[@]}")" \
    "$(json_str_array "${WARNINGS[@]}")" \
    "$(json_str_array "${NOTES[@]}")"
fi

exit $CODE
