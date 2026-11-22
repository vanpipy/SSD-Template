#!/usr/bin/env bash
# check-naming.sh — M2: 目录 / 文件命名与层结构(形状)门禁
#
# 权威形状(契约 §1 M2):
#   prd/{YYYY-MM-DD}/{topic}.md
#   tech_design/{YYYY-MM-DD}-{topic}/*.md
#   plan/{YYYY-MM-DD}-{topic}/{topic}.md
#   test_cases/{YYYY-MM-DD}/{topic}.md        (允许 -smoke / -key-points 后缀)
#   material/{YYYY-MM-DD}/*.md                (可选层)
#   层根目录可放 README.md / _index.md, 免于内容校验。
#
# 发现方式(G3 修复): 对每层做**全深度**扫描(find 不带 -mindepth/-maxdepth),
#   再按相对路径的深度与形状判定, 不再依赖固定深度 find —— 旧实现里
#   深度 1 / 深度 3 的垃圾文件**一个都不计入**, 门禁照样全绿。
#
# 判定:
#   prd/ 深度 1 或 ≥3 的 .md         → 违规(形状错误)
#   prd/{date}/ 下非 topic 命名的 .md → 暂存素材(⚠), 跳过 PRD 字段校验
#   其余命名不合规                    → 违规
#
# 退出码(M6): 0=通过 1=存在违规 2=调用/环境错误
#   - 层目录不存在            → 跳过该层(未启用)
#   - 层目录存在但没有制品    → ⚠, 退出码 0
#   - 全仓没有任何规格产物    → 退出码 1, 消息「本仓没有任何规格产物,门禁无从校验」

set -o pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"

SCRIPT_PATH=$0
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd -P)
DEFAULT_ROOT=$(dirname -- "$SCRIPT_DIR")

JSON=0
ROOT=""
TARGET=""
STAGE_OVERRIDE=""

usage() {
  cat <<EOF
用法: bash scripts/check-naming.sh [--json] [--root DIR] [--stage STAGE] [TARGET]

  --json         以 JSON 输出(供 CI 消费)
  --root DIR     仓根目录(默认: 本脚本所在目录的上一级)
  --stage STAGE  与其余门禁保持同一 CLI 契约(draft|ready|implemented|deprecated);
                 本脚本只校验命名/层结构, 没有阶段相关必填项, 因此该参数被接受并回显,
                 但不改变任何判定。阶段相关必填项由 check-md-schema.sh 按 M4 判定。
  TARGET         可选, 只检查这一个文件或目录
  --help         显示本帮助

退出码: 0=通过 1=存在违规 2=调用/环境错误
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
    --stage)
      shift
      if [ $# -eq 0 ]; then printf '%s: --stage 需要参数\n' "$SCRIPT_PATH" >&2; exit 2; fi
      STAGE_OVERRIDE=$(printf '%s' "$1" | tr 'A-Z' 'a-z')
      ;;
    --stage=*) STAGE_OVERRIDE=$(printf '%s' "${1#--stage=}" | tr 'A-Z' 'a-z') ;;
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

if [ -n "$STAGE_OVERRIDE" ]; then
  case "$STAGE_OVERRIDE" in
    draft|deprecated|ready|implemented) : ;;
    *) printf '%s: --stage 取值非法: %s (可用: draft|ready|implemented|deprecated)\n' "$SCRIPT_PATH" "$STAGE_OVERRIDE" >&2; exit 2 ;;
  esac
fi

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

# --- 形状常量 (M2) ---
TOPIC_RE='^[a-z0-9]+(-[a-z0-9]+)*$'
DATE_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
DATETOPIC_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$'

LAYERS="prd tech_design plan test_cases material"

is_root_doc() {
  case "$1" in
    README.md|_index.md) return 0 ;;
    *) return 1 ;;
  esac
}

split_date_topic() {
  # $1 = 目录名; 输出 "date topic"
  printf '%s' "$1" | awk '{
    if (match($0, /^[0-9]{4}-[0-9]{2}-[0-9]{2}-/)) {
      d = substr($0, 1, 10); t = substr($0, 12); print d, t
    }
  }'
}

# --- 逐层扫描 ---
ARTIFACT_TOTAL=0
ARTIFACT_FILES=0

scan_layer() {
  layer=$1
  ldir="$ROOT/$layer"
  if [ ! -d "$ldir" ]; then
    note "层未启用(目录不存在,跳过): $layer/"
    return 0
  fi

  layer_files=$(cd "$ldir" && find . -type f -name '*.md' | sed 's|^\./||' | LC_ALL=C sort)
  if [ -z "$layer_files" ]; then
    warn "层已启用但没有任何制品(仅可能有 README.md / _index.md): $layer/"
    return 0
  fi

  layer_artifacts=0

  while IFS= read -r rel; do
    [ -z "$rel" ] && continue
    slashes=$(printf '%s' "$rel" | tr -cd '/' | wc -c)
    depth=$((slashes + 1))
    base=$(basename "$rel")
    parent=$(dirname "$rel")
    stem="${base%.md}"

    # 深度 1: 层根目录
    if [ "$depth" -eq 1 ]; then
      if is_root_doc "$base"; then
        continue
      fi
      ARTIFACT_FILES=$((ARTIFACT_FILES + 1))
      layer_artifacts=$((layer_artifacts + 1))
      case "$layer" in
        material) warn "素材区根目录出现 .md(建议放 $layer/{YYYY-MM-DD}/): $layer/$base" ;;
        *) err "层根目录不允许放规格文件(只允许 README.md / _index.md): $layer/$base" ;;
      esac
      continue
    fi

    ARTIFACT_FILES=$((ARTIFACT_FILES + 1))
    layer_artifacts=$((layer_artifacts + 1))

    case "$layer" in
      prd)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: prd/ 下只允许 {YYYY-MM-DD}/{topic}.md 两级结构, 实际深度 $depth: prd/$rel"
          continue
        fi
        if ! printf '%s' "$parent" | grep -Eq "$DATE_RE"; then
          err "日期目录格式错误(期望 YYYY-MM-DD): prd/$parent"
          continue
        fi
        if printf '%s' "$stem" | grep -Eq "$TOPIC_RE"; then
          ARTIFACT_TOTAL=$((ARTIFACT_TOTAL + 1))
        else
          warn "疑似 PRD 命名不合规(topic 必须小写连字符), 按暂存素材处理并跳过字段校验: prd/$rel"
        fi
        ;;
      tech_design)
        pdir=$(printf '%s' "$parent" | cut -d/ -f1)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: tech_design/ 下只允许 {YYYY-MM-DD}-{topic}/*.md 两级结构, 实际深度 $depth: tech_design/$rel"
          continue
        fi
        if ! printf '%s' "$pdir" | grep -Eq "$DATETOPIC_RE"; then
          err "Tech Design 目录名必须为 {YYYY-MM-DD}-{topic}: tech_design/$pdir"
          continue
        fi
        ARTIFACT_TOTAL=$((ARTIFACT_TOTAL + 1))
        ;;
      plan)
        pdir=$(printf '%s' "$parent" | cut -d/ -f1)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: plan/ 下只允许 {YYYY-MM-DD}-{topic}/{topic}.md 三级结构, 实际深度 $depth: plan/$rel"
          continue
        fi
        if ! printf '%s' "$pdir" | grep -Eq "$DATETOPIC_RE"; then
          err "Plan 目录名必须为 {YYYY-MM-DD}-{topic}: plan/$pdir"
          continue
        fi
        dt=$(split_date_topic "$pdir")
        ptopic=$(printf '%s' "$dt" | cut -d' ' -f2)
        if [ "$stem" != "$ptopic" ]; then
          err "Plan 文件名必须等于目录 topic(目录 $pdir): plan/$rel"
          continue
        fi
        ARTIFACT_TOTAL=$((ARTIFACT_TOTAL + 1))
        ;;
      test_cases)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: test_cases/ 下只允许 {YYYY-MM-DD}/{topic}.md 两级结构, 实际深度 $depth: test_cases/$rel"
          continue
        fi
        if ! printf '%s' "$parent" | grep -Eq "$DATE_RE"; then
          err "日期目录格式错误(期望 YYYY-MM-DD): test_cases/$parent"
          continue
        fi
        tstem="$stem"
        case "$tstem" in
          *-key-points) tstem="${tstem%-key-points}" ;;
          *-smoke) tstem="${tstem%-smoke}" ;;
        esac
        if ! printf '%s' "$tstem" | grep -Eq "$TOPIC_RE"; then
          err "测试用例文件名不合法(topic 小写连字符, 允许 -smoke / -key-points 后缀): test_cases/$rel"
          continue
        fi
        ARTIFACT_TOTAL=$((ARTIFACT_TOTAL + 1))
        ;;
      material)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: material/ 下只允许 {YYYY-MM-DD}/*.md 两级结构, 实际深度 $depth: material/$rel"
          continue
        fi
        if ! printf '%s' "$parent" | grep -Eq "$DATE_RE"; then
          err "素材批次目录格式错误(期望 YYYY-MM-DD): material/$parent"
          continue
        fi
        ;;
    esac
  done <<EOF
$layer_files
EOF

  if [ "$layer_artifacts" -eq 0 ]; then
    warn "层已启用但没有任何规格制品(只有 README.md / _index.md): $layer/"
  fi
}

if [ -n "$TARGET" ]; then
  if [ -d "$TARGET" ]; then
    trel="${TARGET#$ROOT/}"
    layer=$(printf '%s' "$trel" | cut -d/ -f1)
    case "$layer" in
      prd|tech_design|plan|test_cases|material)
        LAYERS="$layer"
        note "单目录模式: 只检查 $layer/"
        ;;
      *)
        printf '%s: 无法识别的层目录: %s\n' "$SCRIPT_PATH" "$trel" >&2
        exit 2
        ;;
    esac
  else
    trel="${TARGET#$ROOT/}"
    layer=$(printf '%s' "$trel" | cut -d/ -f1)
    case "$layer" in
      prd|tech_design|plan|test_cases|material) ;;
      *)
        printf '%s: 无法识别的层路径: %s\n' "$SCRIPT_PATH" "$trel" >&2
        exit 2
        ;;
    esac
    LAYERS="$layer"
    note "单文件模式: 只检查 $trel"
    # 单文件模式: 只跑这一个文件
    ARTIFACT_FILES=0
    ARTIFACT_TOTAL=0
    rel_in_layer="${trel#$layer/}"
    slashes=$(printf '%s' "$rel_in_layer" | tr -cd '/' | wc -c)
    depth=$((slashes + 1))
    base=$(basename "$rel_in_layer")
    stem="${base%.md}"
    parent=$(dirname "$rel_in_layer")
    case "$layer" in
      prd)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: prd/ 下只允许 {YYYY-MM-DD}/{topic}.md 两级结构: $trel"
        elif ! printf '%s' "$stem" | grep -Eq "$TOPIC_RE"; then
          warn "疑似 PRD 命名不合规, 按暂存素材处理并跳过字段校验: $trel"
        else
          ARTIFACT_TOTAL=1
        fi
        ;;
      tech_design)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: tech_design/ 下只允许 {YYYY-MM-DD}-{topic}/*.md 两级结构: $trel"
        else
          ARTIFACT_TOTAL=1
        fi
        ;;
      plan)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: plan/ 下只允许 {YYYY-MM-DD}-{topic}/{topic}.md 三级结构: $trel"
        else
          ARTIFACT_TOTAL=1
        fi
        ;;
      test_cases)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: test_cases/ 下只允许 {YYYY-MM-DD}/{topic}.md 两级结构: $trel"
        else
          ARTIFACT_TOTAL=1
        fi
        ;;
      material)
        if [ "$depth" -ne 2 ]; then
          err "形状错误: material/ 下只允许 {YYYY-MM-DD}/*.md 两级结构: $trel"
        fi
        ;;
    esac
  fi
else
  for layer in $LAYERS; do
    scan_layer "$layer"
  done
fi

# --- M6: 全仓没有任何规格产物 ---
if [ -z "$TARGET" ] && [ "$ARTIFACT_FILES" -eq 0 ]; then
  err "本仓没有任何规格产物,门禁无从校验"
fi

if [ ${#ERRORS[@]} -eq 0 ]; then
  ok "命名与层结构检查通过 (制品 $ARTIFACT_TOTAL 个)"
fi

STATUS="pass"
CODE=0
if [ ${#ERRORS[@]} -gt 0 ]; then STATUS="violation"; CODE=1; fi

if [ "$JSON" -eq 1 ]; then
  printf '{"script":"check-naming.sh","root":"%s","status":"%s","exit_code":%d,"error_count":%d,"warning_count":%d,"artifacts":%d,"stage_override":"%s","errors":%s,"warnings":%s,"notes":%s}\n' \
    "$(printf '%s' "$ROOT" | json_escape)" "$STATUS" "$CODE" "${#ERRORS[@]}" "${#WARNINGS[@]}" "$ARTIFACT_TOTAL" "$STAGE_OVERRIDE" \
    "$(json_str_array "${ERRORS[@]}")" \
    "$(json_str_array "${WARNINGS[@]}")" \
    "$(json_str_array "${NOTES[@]}")"
fi

exit $CODE
