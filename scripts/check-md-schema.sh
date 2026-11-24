#!/usr/bin/env bash
# check-md-schema.sh — M3 / M4 / M5: 规格制品的必填段、状态枚举与阶段感知门禁
#
# 权威规则(契约 §1):
#   M3 状态枚举统一 4 值 Draft | Ready | Implemented | Deprecated
#      PRD / Tech Design(README.md) / Plan 读 `> **状态**: X`;
#      Test Case 读元信息表 `| **状态** | X |`; 值可带说明后缀(前缀匹配);
#      非法值 = 违规; 缺状态行 = 违规(否则阶段无法判定)。
#   M4 阶段感知(Stage-aware):
#      Draft      → 必须有 `## 复审 (Review)` 段; 评审日期/评审人豁免; 写入者 = agent
#      Ready      → 复审段 + 复审日期(YYYY-MM-DD) + 评审人非空; 写入者 = 人类评审者
#      Implemented → 同 Ready; 写入者 = 人类
#      Deprecated → 复审段; 日期/评审人豁免
#      agent 的权限天花板 = Draft。
#   M5 必填段:
#      PRD   → ## 为什么 / ## 目标 / ## 场景 / ## 不在范围内 / ## 复审
#               (## 链接 与 ## 变更记录 属人工维护, 不做机器校验)
#      TD v4 → README.md / ards.md / apis.md / data-model.md,
#               每个子文件必须有 `## 门禁清单` 与 `## 变更记录`
#      TD v3 → README/decisions/data-model/api-contracts/scenario-mapping/quality
#               6 个必填 + interactions.md 条件必填
#      Plan → ## 变更清单 + `### Change #1:`/`#### Change #1:` + `### V-1:`
#              + ## 跨文件引用对账 + ## 复审
#              (v2 单段 Plan 不再是豁免, 一律判违规 —— 决策 D4)
#      TestCase → 元信息 7 必填行 + ## 用例总览 + 状态枚举
#              + Ready/Implemented 时必须有 `{topic}-key-points.md` 伴生
#
# 退出码(M1/M6): 0=通过 1=存在违规 2=调用/环境错误
#   - 单文件模式: 有违规即退出 1(绝不把违规条数当退出码)
#   - 层目录不存在 → 跳过该层
#   - 全仓没有任何规格产物 → 退出 1, 消息「本仓没有任何规格产物,门禁无从校验」

set -o pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"

SCRIPT_PATH=$0
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd -P)
DEFAULT_ROOT=$(dirname -- "$SCRIPT_DIR")

JSON=0
ROOT=""
TARGET=""
STAGE_OVERRIDE=""
EFFECTIVE_STAGE=""

usage() {
  cat <<EOF
用法: bash scripts/check-md-schema.sh [--json] [--root DIR] [--stage STAGE] [TARGET]

  --json         以 JSON 输出(供 CI 消费)
  --root DIR     仓根目录(默认: 本脚本所在目录的上一级)
  --stage STAGE  假定制品处于该阶段(draft|ready|implemented|deprecated)。
                 只允许**收紧**校验: 用比制品自身状态更宽松的阶段取值会报错,
                 不会变成绕过签署校验的开关。
                 不给该参数时按制品自身声明的状态判定(契约 M4 / A5)。
  TARGET         可选, 单个文件或目录(只校验它)
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

# --- 常量 ---
TOPIC_RE='^[a-z0-9]+(-[a-z0-9]+)*$'
DATE_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
DATETOPIC_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$'
PLACEHOLDER_RE='\{[A-Z][A-Z_-]+\}|\{[A-Z_-]+ [A-Z_-]+\}'
PLACEHOLDER_ANY_RE='\{[a-zA-Z_-]+\}|\{[a-zA-Z_-]+ [a-zA-Z_-]+\}'
STATE_RE='^(Draft|Ready|Implemented|Deprecated)'
# 状态块元数据的取值格式(实施契约 §3.1)
#   状态块 = 4 行固定顺序
#     > **状态**: Draft
#     > **状态主体**: agent:sddctl
#     > **状态时间**: 2026-11-22T23:30:00+08:00
#     > **状态依据**: criteria:PRD-READY-01,PRD-READY-02
#   Draft / Deprecated: 后三行可缺省(写了就必须合法)
#   Ready / Implemented: 后三行必填且非空(半写 = 违规)
STATE_SUBJECT_RE='^(agent|human):[A-Za-z0-9._-]+$'
STATE_TIME_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}([+-][0-9]{2}:[0-9]{2}|Z)$'
STATE_BASIS_ITEM_RE='^(criteria|external):[^[:space:],]+$'
# criteria:<id>[,<id>…] 的延续项(省略前缀的裸 id)
STATE_BASIS_ID_RE='^[A-Za-z0-9._-]+$'
# Deprecated 态的状态依据只允许 external:(实施契约 §5.2 —— 不允许 criteria:)
# 注意: 这个常量必须存在。未定义时 `grep -Eq ""` 匹配一切, 规则会静默变成 no-op。
STATE_BASIS_DECISION_RE='^external:[^[:space:],]+$'
# 复审方式的取值(实施契约 §3.2)
REVIEW_METHODS_RE='^(自动判据|人工介入|外部事实)$'
# 复审结论的取值(实施契约 §3.2)
REVIEW_CONCLUSION_RE='^(有条件通过|需返工|通过)$'

# --- 结构解析辅助 ---

# 段体: 取 `## <prefix>` 段的内容(到下一个同级或更高级标题为止)
section_body() {
  awk -v h="$2" '
    /^#+[[:space:]]/ {
      if (insec) {
        match($0, /^#+/); lvl = RLENGTH
        if (lvl <= seclevel) exit
        next
      }
      match($0, /^#+/); lvl = RLENGTH
      line = $0; sub(/^#+[[:space:]]+/, "", line)
      if (lvl == 2 && index(line, h) == 1) { insec = 1; seclevel = 2 }
      next
    }
    { if (insec) print }
  ' "$1"
}

has_section_body() {
  [ -n "$(section_body "$1" "$2")" ]
}

# 文件去掉指定段体(用于占位符扫描: 复审段的占位符由阶段规则单独判定)
file_without_section() {
  awk -v h="$2" '
    /^#+[[:space:]]/ {
      if (insec) {
        match($0, /^#+/); lvl = RLENGTH
        if (lvl <= seclevel) { insec = 0; print; next }
        next
      }
      match($0, /^#+/); lvl = RLENGTH
      line = $0; sub(/^#+[[:space:]]+/, "", line)
      if (lvl == 2 && index(line, h) == 1) { insec = 1; seclevel = 2; next }
      print
      next
    }
    { if (!insec) print }
  ' "$1"
}

# 状态行取值(PRD / TD README / Plan): `> **状态**: X`
read_state() {
  awk '
    /^[[:space:]]*>?[[:space:]]*\*\*状态\*\*[[:space:]]*[:：]/ {
      val = $0
      sub(/^[^:：]*[:：][[:space:]]*/, "", val)
      gsub(/^[[:space:]]*[|*`]+[[:space:]]*/, "", val)
      gsub(/[[:space:]]*[|*`]+$/, "", val)
      print val
      exit
    }
  ' "$1"
}

# 元信息表取值(TestCase): `| **字段** | 值 |`
read_meta() {
  awk -F'|' -v k="$2" '
    /^\|/ {
      key = $2; gsub(/^[ \t]+|[ \t]+$/, "", key); gsub(/\*+/, "", key)
      v = $3;   gsub(/^[ \t]+|[ \t]+$/, "", v)
      if (key == k) { print v; exit }
    }
  ' "$1"
}

# 复审段取值: 精确匹配 `**键名**`(评审人 / 评审日期 / 评审结论)
# 无冒号取值时返回空串(不把整行当成值)
review_value() {
  printf '%s\n' "$2" | awk -v k="$1" '
    {
      if (index($0, "**" k "**") == 0) next
      line = $0
      if (sub(/^[^:：]*[:：][[:space:]]*/, "", line) == 0) next
      gsub(/^[[:space:]]*[|*`]+/, "", line)
      gsub(/[[:space:]]*[|*`]+$/, "", line)
      if (index(line, "**" k "**") > 0) next
      print line
      exit
    }
  '
}

# 状态块元数据取值(状态主体 / 状态时间 / 状态依据): 精确匹配 `**键名**`
status_meta_value() {
  awk -v k="$1" '
    {
      if (index($0, "**" k "**") == 0) next
      line = $0
      if (sub(/^[^:：]*[:：][[:space:]]*/, "", line) == 0) next
      gsub(/^[[:space:]]*[|*`]+/, "", line)
      gsub(/[[:space:]]*[|*`]+$/, "", line)
      if (index(line, "**" k "**") > 0) next
      print line
      exit
    }
  ' "$2"
}

is_placeholder_value() {
  printf '%s' "$1" | grep -Eq '^\{.*\}$'
}








# 状态枚举校验(M3): 结果写入全局 STATE_TOKEN; 非法时返回 1
STATE_TOKEN=""
check_state_value() {
  local rel="$1" raw="$2" tok
  STATE_TOKEN=""
  if [ -z "$raw" ]; then
    err "$rel — 缺少状态行(应写 \`> **状态**: Draft|Ready|Implemented|Deprecated\`)"
    return 1
  fi
  case "$raw" in
    *"|"*)
      err "$rel — 状态值非法(仍是模板枚举, 未填写): $raw"
      return 1
      ;;
  esac
  tok=$(printf '%s' "$raw" | awk '{print $1}')
  if ! printf '%s' "$tok" | grep -Eq "$STATE_RE"; then
    err "$rel — 状态值非法: '$tok' (应为 Draft / Ready / Implemented / Deprecated)"
    return 1
  fi
  STATE_TOKEN="$tok"
  return 0
}


# 状态块元数据校验(契约 §3.1, 实施契约 agent-first §3.1)
#   Draft / Deprecated → 状态主体 / 状态时间 / 状态依据 **可缺省**;
#                      若写了就必须合法(半写的状态块是违规, 不是「没关系」)
#   Ready / Implemented → 三行**必填且非空**:
#      状态主体 = agent:<id> | human:<handle>
#      状态时间 = 带时区的 ISO-8601
#      状态依据 = criteria:<id> / external:<ref>(逗号分隔, 至少一项)
check_status_meta() {
  local rel="$1" file="$2" stage="$3"
  local subject ts basis item
  stage=$(canonical_stage "$stage")
  subject=$(status_meta_value "状态主体" "$file")
  ts=$(status_meta_value "状态时间" "$file")
  basis=$(status_meta_value "状态依据" "$file")

  if [ -n "$subject" ] && ! printf '%s' "$subject" | grep -Eq "$STATE_SUBJECT_RE"; then
    err "$rel — 状态主体非法: '$subject' (应为 agent:<id> 或 human:<handle>)"
  fi
  if [ -n "$ts" ] && ! printf '%s' "$ts" | grep -Eq "$STATE_TIME_RE"; then
    err "$rel — 状态时间不是带时区的 ISO-8601: '$ts'"
  fi
  if [ -n "$basis" ]; then
    local oldifs="$IFS" prev_prefix=""
    IFS=','
    for item in $basis; do
      IFS="$oldifs"
      item=$(printf '%s' "$item" | sed 's/^[[:space:]]*//; s/[[:space:]]*$//')
      IFS=','
      [ -z "$item" ] && continue
      if printf '%s' "$item" | grep -Eq "$STATE_BASIS_ITEM_RE"; then
        prev_prefix=$(printf '%s' "$item" | sed 's/^\([a-z][a-z]*\):.*/\1/')
        if [ "$stage" = "Deprecated" ] && [ "$prev_prefix" = "criteria" ]; then
          err "$rel — 状态为 Deprecated, 状态依据不允许 criteria: ('$item'), 只能用 external:<ref>"
        fi
      elif [ "$prev_prefix" = "criteria" ] && printf '%s' "$item" | grep -Eq "$STATE_BASIS_ID_RE"; then
        : # criteria:<id>[,<id>…] 的延续项 —— 前缀继承上一项(与判据正则一致)
      else
        err "$rel — 状态依据项非法: '$item' (应为 criteria:<id>[,<id>…] / external:<ref>)"
      fi
    done
    IFS="$oldifs"
  fi

  case "$stage" in
    Ready|Implemented)
      if [ -z "$subject" ]; then
        err "$rel — 状态为 $stage, 状态块缺少 \`> **状态主体**: agent:<id>\`"
      fi
      if [ -z "$ts" ]; then
        err "$rel — 状态为 $stage, 状态块缺少 \`> **状态时间**: <ISO-8601 带时区>\`"
      fi
      if [ -z "$basis" ]; then
        err "$rel — 状态为 $stage, 状态块缺少 \`> **状态依据**: criteria:<id>[,external:<ref>]\`"
      fi
      ;;
  esac
  return 0
}

# 阶段感知复审段校验(M4)
#   Draft / Deprecated : 复审段必须存在; 评审日期与评审人豁免; 签署行不应残留模板占位符
#   Ready / Implemented : 复审段 + 评审日期(YYYY-MM-DD) + 评审人非空; 评审结论不得是占位符
#
# --stage 覆盖(只允许收紧):
#   校验强度按「复审段 + 日期 + 评审人」是否必填分两级:
#     level 0 = draft / deprecated   level 1 = ready / implemented
#   --stage 只能把强度往上提(例如对 Draft 制品按 ready 校验 → 报缺评审人);
#   往下调(例如对 Ready 制品按 draft 校验)会被报成违规, 不会变成绕过签署的开关。
stage_level() {
  case "$(printf '%s' "$1" | tr 'A-Z' 'a-z')" in
    draft|deprecated) echo 0 ;;
    ready|implemented) echo 1 ;;
    *) echo -1 ;;
  esac
}

canonical_stage() {
  case "$(printf '%s' "$1" | tr 'A-Z' 'a-z')" in
    draft) printf 'Draft' ;;
    deprecated) printf 'Deprecated' ;;
    ready) printf 'Ready' ;;
    implemented) printf 'Implemented' ;;
    *) printf '' ;;
  esac
}

apply_stage_override() {
  # $1 = rel, $2 = 制品自身声明的状态(可空)
  local rel="$1" declared="$2" dlevel slevel canon
  if [ -z "$STAGE_OVERRIDE" ]; then
    EFFECTIVE_STAGE="$declared"
    return 0
  fi
  canon=$(canonical_stage "$STAGE_OVERRIDE")
  dlevel=$(stage_level "$declared")
  slevel=$(stage_level "$canon")
  if [ "$slevel" -ge 0 ] && [ "$dlevel" -ge 0 ] && [ "$slevel" -lt "$dlevel" ]; then
    err "$rel — 用 --stage $STAGE_OVERRIDE 放宽了已处于 ${declared:-未知} 的制品(只允许收紧, 不允许放宽)"
    EFFECTIVE_STAGE="$declared"
    return 1
  fi
  EFFECTIVE_STAGE="$canon"
  if [ "$canon" != "$declared" ]; then
    note "$rel — 按 --stage $STAGE_OVERRIDE 假定阶段校验(制品自身声明: ${declared:-未知})"
  fi
  return 0
}

# 复审段「已知问题」行取值(全部行, 每行一个): `> **已知问题**: <criterion-id> — <说明>`
# F9:非阻断判据失败时, 复审段必须点名该判据 id 才放行; 这里只校验**形状**, 不校验语义。
review_known_issue_lines() {
  printf '%s\n' "$1" | awk '
    {
      if (index($0, "**已知问题**") == 0) next
      line = $0
      if (sub(/^[^:：]*[:：][[:space:]]*/, "", line) == 0) next
      gsub(/^[[:space:]]*[|*`]+/, "", line)
      gsub(/[[:space:]]*[|*`]+$/, "", line)
      if (index(line, "**已知问题**") > 0) next
      print line
    }
  '
}

# 「已知问题」行形状校验: 首个 token 必须是形如 PRD-XXX-01 的判据 id
check_known_issues() {
  # $1 = rel, $2 = 复审段体
  local rel="$1" body="$2" issues line tok
  local oldifs="$IFS"
  issues=$(review_known_issue_lines "$body")
  [ -z "$issues" ] && return 0
  IFS='
'
  for line in $issues; do
    IFS="$oldifs"
    [ -z "$line" ] && continue
    tok=$(printf '%s' "$line" | awk '{print $1}')
    if ! printf '%s' "$tok" | grep -Eq '^[A-Z0-9-]+$'; then
      err "$rel — \`已知问题\` 行的判据 id 非法: '$line' (应为形如 PRD-XXX-01 的大写字母/数字/连字符 id, 后接说明)"
    fi
    IFS='
'
  done
  IFS="$oldifs"
  return 0
}

check_review_block() {
  # $1 = rel, $2 = 文件, $3 = 状态 token(可空)
  local rel="$1" file="$2" stage="$3"
  local body sign_date sign_reviewer sign_conclusion sign_method alt_date date
  stage=$(canonical_stage "$stage")
  if ! grep -q "^##[[:space:]]\{1,\}复审" "$file" 2>/dev/null; then
    err "$rel — 缺少必填段 \`## 复审 (Review)\`"
    return 1
  fi
  body=$(section_body "$file" "复审")
  sign_date=$(review_value "评审日期" "$body")
  sign_reviewer=$(review_value "评审人" "$body")
  [ -z "$sign_reviewer" ] && sign_reviewer=$(review_value "复审人" "$body")
  sign_conclusion=$(review_value "评审结论" "$body")
  sign_method=$(review_value "评审方式" "$body")

  case "$stage" in
    Ready|Implemented)
      date="$sign_date"
      if [ -z "$date" ]; then
        alt_date=$(review_value "复审日期" "$body")
        if printf '%s' "$alt_date" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
          date="$alt_date"
        fi
      fi
      if [ -z "$date" ]; then
        err "$rel — 状态为 $stage, 复审段缺少评审日期(应写 \`> **评审日期**: YYYY-MM-DD\`)"
      elif ! printf '%s' "$date" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
        err "$rel — 状态为 $stage, 评审日期不是 YYYY-MM-DD: '$date'"
      fi
      if [ -z "$sign_reviewer" ]; then
        err "$rel — 状态为 $stage, 复审段缺少评审人(应写 \`> **评审人**: {github-handle}\`)"
      elif is_placeholder_value "$sign_reviewer"; then
        err "$rel — 状态为 $stage, 评审人仍是占位符: '$sign_reviewer'"
      fi
      if [ -z "$sign_conclusion" ]; then
        err "$rel — 状态为 $stage, 复审段缺少评审结论(应写 通过 / 有条件通过 / 需返工)"
      elif is_placeholder_value "$sign_conclusion"; then
        err "$rel — 状态为 $stage, 评审结论仍是占位符: '$sign_conclusion'"
      elif ! printf '%s' "$sign_conclusion" | grep -Eq "$REVIEW_CONCLUSION_RE"; then
        err "$rel — 状态为 $stage, 评审结论取值非法: '$sign_conclusion' (应为 通过 / 有条件通过 / 需返工)"
      fi
      if [ -z "$sign_method" ]; then
        err "$rel — 状态为 $stage, 复审段缺少评审方式(应写 \`> **评审方式**: 自动判据 | 人工介入 | 外部事实\`)"
      elif is_placeholder_value "$sign_method"; then
        err "$rel — 状态为 $stage, 评审方式仍是占位符: '$sign_method'"
      elif ! printf '%s' "$sign_method" | grep -Eq "$REVIEW_METHODS_RE"; then
        err "$rel — 状态为 $stage, 评审方式取值非法: '$sign_method' (应为 自动判据 / 人工介入 / 外部事实)"
      fi
      # agent 署名不得配「人工介入」(实施契约 §3.2 / INV-3)
      case "$sign_reviewer" in
        agent:*)
          if [ "$sign_method" = "人工介入" ]; then
            err "$rel — 状态为 $stage, 评审人为 agent 署名 ('$sign_reviewer') 时评审方式不得为「人工介入」"
          fi
          ;;
      esac
      ;;
    *)
      # Draft / Deprecated / 状态未知: 复审段存在即可, 日期与评审人豁免
      if is_placeholder_value "$sign_date"; then
        warn "$rel — 阶段 ${stage:-未知} 下复审签署行 \`评审日期\` 仍是模板占位符(应为清空)"
      fi
      if is_placeholder_value "$sign_reviewer"; then
        warn "$rel — 阶段 ${stage:-未知} 下复审签署行 \`评审人\` 仍是模板占位符(应为清空)"
      fi
      if is_placeholder_value "$sign_conclusion"; then
        warn "$rel — 阶段 ${stage:-未知} 下复审签署行 \`评审结论\` 仍是模板占位符(应为清空)"
      fi
      ;;
  esac
  check_known_issues "$rel" "$body"
  return 0
}

# --- 层校验 ---

check_prd() {
  local file="$1" rel="$2"
  local raw stage body
  raw=$(read_state "$file")
  if check_state_value "$rel" "$raw"; then stage="$STATE_TOKEN"; else stage=""; fi
  apply_stage_override "$rel" "$stage" || true
  check_status_meta "$rel" "$file" "$EFFECTIVE_STAGE"

  for sec in 为什么 目标 场景 不在范围内; do
    if ! grep -q "^##[[:space:]]\{1,\}$sec" "$file"; then
      err "$rel — 缺少必填段 \`## $sec\`"
    fi
  done

  body=$(section_body "$file" "目标")
  if [ -n "$body" ] && ! printf '%s\n' "$body" | grep -q '^- \[ \]'; then
    err "$rel — \`## 目标\` 段没有验证标准(\`- [ ]\` 勾选项)"
  fi

  body=$(section_body "$file" "场景")
  if [ -n "$body" ] && ! printf '%s\n' "$body" | grep -q '\*\*Given\*\*'; then
    err "$rel — \`## 场景\` 段没有 Given/When/Then(\`**Given**\`)"
  fi

  # 占位符(复审段除外: 那里的占位符由阶段规则判定)
  local ph
  ph=$(file_without_section "$file" "复审" | grep -nE "$PLACEHOLDER_RE" || true)
  if [ -n "$ph" ]; then
    err "$rel — 仍含模板占位符:"
    printf '%s\n' "$ph" | sed 's/^/    /'
  fi

  check_review_block "$rel" "$file" "$EFFECTIVE_STAGE"
}

check_td_dir() {
  local dir="$1" rel="$2"
  local gen="" sub stage raw
  if [ -f "$dir/ards.md" ] || [ -f "$dir/apis.md" ]; then
    gen="v4"
  elif [ -f "$dir/decisions.md" ] || [ -f "$dir/api-contracts.md" ] \
    || [ -f "$dir/scenario-mapping.md" ] || [ -f "$dir/quality.md" ]; then
    gen="v3"
  else
    err "$rel — 无法判定代际(既无 v4 的 ards.md/apis.md, 也无 v3 的 decisions.md 等)"
    return 1
  fi

  if [ ! -f "$dir/README.md" ]; then
    err "$rel — 缺少必填子文件: README.md"
    return 1
  fi

  raw=$(read_state "$dir/README.md")
  if check_state_value "$rel/README.md" "$raw"; then stage="$STATE_TOKEN"; else stage=""; fi
  apply_stage_override "$rel/README.md" "$stage" || true
  check_status_meta "$rel/README.md" "$dir/README.md" "$EFFECTIVE_STAGE"

  if [ "$gen" = "v4" ]; then
    for sub in README.md ards.md apis.md data-model.md; do
      if [ ! -f "$dir/$sub" ]; then
        err "$rel — v4 缺少必填子文件: $sub"
      fi
    done
  else
    for sub in README.md decisions.md data-model.md api-contracts.md scenario-mapping.md quality.md; do
      if [ ! -f "$dir/$sub" ]; then
        err "$rel — v3 缺少必填子文件: $sub"
      fi
    done
    if [ ! -f "$dir/interactions.md" ]; then
      if ! grep -qE 'interactions\.md.*(跳过|不适用|N/A)' "$dir/README.md" 2>/dev/null; then
        warn "$rel — 缺少 interactions.md 且 README.md 未声明跳过(条件必填)"
      fi
    fi
  fi

  # 每个必填子文件都要有门禁清单与变更记录(M5)
  local required
  if [ "$gen" = "v4" ]; then
    required="README.md ards.md apis.md data-model.md"
  else
    required="README.md decisions.md data-model.md api-contracts.md scenario-mapping.md quality.md"
  fi
  for sub in $required; do
    [ -f "$dir/$sub" ] || continue
    if ! grep -q "^##[[:space:]]\{1,\}门禁清单" "$dir/$sub"; then
      err "$rel/$sub — 缺少 \`## 门禁清单 (Completion Gate)\` 段"
    fi
    if ! grep -q "^##[[:space:]]\{1,\}变更记录" "$dir/$sub"; then
      err "$rel/$sub — 缺少 \`## 变更记录 (Change Log)\` 段"
    fi
  done

  if [ "$gen" = "v4" ]; then
    if ! grep -q "^##[[:space:]]\{1,\}场景映射" "$dir/README.md"; then
      err "$rel/README.md — 缺少 \`## 场景映射\` 段"
    fi
    if [ -f "$dir/data-model.md" ] \
      && ! grep -qE 'erDiagram' "$dir/data-model.md" \
      && ! grep -qE '无数据模型变更|不涉及数据模型' "$dir/data-model.md"; then
      err "$rel/data-model.md — 既无 ER 图(erDiagram)也无「无数据模型变更」声明"
    fi
  fi

  check_review_block "$rel/README.md" "$dir/README.md" "$EFFECTIVE_STAGE"
}

check_plan() {
  local file="$1" rel="$2"
  local raw stage
  raw=$(read_state "$file")
  if check_state_value "$rel" "$raw"; then stage="$STATE_TOKEN"; else stage=""; fi
  apply_stage_override "$rel" "$stage" || true
  check_status_meta "$rel" "$file" "$EFFECTIVE_STAGE"

  if ! grep -q "^##[[:space:]]\{1,\}变更清单" "$file"; then
    err "$rel — 缺少必填段 \`## 变更清单 (Changes)\`"
  fi
  if ! grep -q "^##[[:space:]]\{1,\}跨文件引用对账" "$file"; then
    err "$rel — 缺少必填段 \`## 跨文件引用对账\`"
  fi

  if grep -qE '^### Change #1:|^#### Change #1:' "$file"; then
    :
  elif grep -qE '^### Change #[0-9]+:|^#### Change #[0-9]+:' "$file"; then
    err "$rel — 变更条目必须从 \`### Change #1:\` 开始编号"
  else
    err "$rel — v2 单段 Plan 不再被接受(决策 D4): 缺少 \`### Change #1:\` / \`#### Change #1:\`"
  fi

  if ! grep -qE '^### V-1:' "$file"; then
    err "$rel — 缺少 \`### V-1:\`(验证用例定义)"
  fi

  check_review_block "$rel" "$file" "$EFFECTIVE_STAGE"
}

check_testcase() {
  local file="$1" rel="$2"
  local base topic dir field val st stage tok
  base=$(basename "$file" .md)
  dir=$(dirname "$file")

  if [ "${base%-key-points}" != "$base" ]; then
    for sec in 业务背景 核心测试点; do
      if ! grep -q "^##[[:space:]]\{1,\}$sec" "$file"; then
        err "$rel — 要点文档缺少 \`## $sec\` 段"
      fi
    done
    return 0
  fi

  topic="${base%-smoke}"

  for field in 主题 业务产品 目标平台 来源 生成日期 状态 用例总数; do
    val=$(read_meta "$file" "$field")
    if [ -z "$val" ]; then
      err "$rel — 元信息缺少必填行 \`$field\`"
    elif printf '%s' "$val" | grep -Eq "$PLACEHOLDER_ANY_RE"; then
      err "$rel — 元信息 \`$field\` 仍为占位符: $val"
    fi
  done

  st=$(read_meta "$file" "状态")
  stage=""
  if [ -n "$st" ]; then
    tok=$(printf '%s' "$st" | awk '{print $1}')
    if printf '%s' "$tok" | grep -Eq "$STATE_RE"; then
      stage="$tok"
    else
      err "$rel — 状态非合法枚举前缀: '$tok' (应为 Draft/Ready/Implemented/Deprecated)"
    fi
  fi
  apply_stage_override "$rel" "$stage" || true
  check_status_meta "$rel" "$file" "$EFFECTIVE_STAGE"

  if ! grep -q "^##[[:space:]]\{1,\}用例总览" "$file"; then
    err "$rel — 缺少 \`## 用例总览\` 段"
  fi

  case "$EFFECTIVE_STAGE" in
    Ready|Implemented)
      if [ ! -f "$dir/$topic-key-points.md" ]; then
        err "$rel — 状态为 $EFFECTIVE_STAGE 但缺少伴生要点 \`$topic-key-points.md\`"
      fi
      ;;
  esac

  # 复审段(M4): schema/test_case.md 明确标注该段为机器必填段
  check_review_block "$rel" "$file" "$EFFECTIVE_STAGE"
}

# --- 制品发现 ---

PRD_ARTIFACTS=""
TD_ARTIFACTS=""
PLAN_ARTIFACTS=""
TC_ARTIFACTS=""

discover() {
  local d f dn bn topic
  if [ -d "$ROOT/prd" ]; then
    for d in "$ROOT"/prd/*/; do
      [ -d "$d" ] || continue
      dn=$(basename "$d")
      printf '%s' "$dn" | grep -Eq "$DATE_RE" || continue
      for f in "$d"*.md; do
        [ -f "$f" ] || continue
        bn=$(basename "$f" .md)
        printf '%s' "$bn" | grep -Eq "$TOPIC_RE" || continue
        PRD_ARTIFACTS="$PRD_ARTIFACTS$f
"
      done
    done
  fi
  if [ -d "$ROOT/tech_design" ]; then
    for d in "$ROOT"/tech_design/*/; do
      [ -d "$d" ] || continue
      dn=$(basename "$d")
      printf '%s' "$dn" | grep -Eq "$DATETOPIC_RE" || continue
      TD_ARTIFACTS="$TD_ARTIFACTS$d
"
    done
  fi
  if [ -d "$ROOT/plan" ]; then
    for d in "$ROOT"/plan/*/; do
      [ -d "$d" ] || continue
      dn=$(basename "$d")
      printf '%s' "$dn" | grep -Eq "$DATETOPIC_RE" || continue
      topic=$(printf '%s' "$dn" | cut -d- -f4-)
      f="$d$topic.md"
      [ -f "$f" ] || continue
      PLAN_ARTIFACTS="$PLAN_ARTIFACTS$f
"
    done
  fi
  if [ -d "$ROOT/test_cases" ]; then
    for d in "$ROOT"/test_cases/*/; do
      [ -d "$d" ] || continue
      dn=$(basename "$d")
      printf '%s' "$dn" | grep -Eq "$DATE_RE" || continue
      for f in "$d"*.md; do
        [ -f "$f" ] || continue
        bn=$(basename "$f" .md)
        tstem="$bn"
        case "$tstem" in
          *-key-points) tstem="${tstem%-key-points}" ;;
          *-smoke) tstem="${tstem%-smoke}" ;;
        esac
        printf '%s' "$tstem" | grep -Eq "$TOPIC_RE" || continue
        TC_ARTIFACTS="$TC_ARTIFACTS$f
"
      done
    done
  fi
}

# --- 主流程 ---

CHECKED=0

run_whole_repo() {
  discover
  local f rel

  if [ -n "$PRD_ARTIFACTS" ]; then
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      rel="${f#$ROOT/}"
      check_prd "$f" "$rel"
      CHECKED=$((CHECKED + 1))
    done <<EOF
$PRD_ARTIFACTS
EOF
  else
    note "层未启用或无制品(跳过 PRD 校验): prd/"
  fi

  if [ -n "$TD_ARTIFACTS" ]; then
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      rel="${f#$ROOT/}"
      rel="${rel%/}"
      check_td_dir "$f" "$rel"
      CHECKED=$((CHECKED + 1))
    done <<EOF
$TD_ARTIFACTS
EOF
  else
    note "层未启用或无制品(跳过 Tech Design 校验): tech_design/"
  fi

  if [ -n "$PLAN_ARTIFACTS" ]; then
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      rel="${f#$ROOT/}"
      check_plan "$f" "$rel"
      CHECKED=$((CHECKED + 1))
    done <<EOF
$PLAN_ARTIFACTS
EOF
  else
    note "层未启用或无制品(跳过 Plan 校验): plan/"
  fi

  if [ -n "$TC_ARTIFACTS" ]; then
    while IFS= read -r f; do
      [ -z "$f" ] && continue
      rel="${f#$ROOT/}"
      check_testcase "$f" "$rel"
      CHECKED=$((CHECKED + 1))
    done <<EOF
$TC_ARTIFACTS
EOF
  else
    note "层未启用或无制品(跳过 Test Case 校验): test_cases/"
  fi
}

run_single_target() {
  local t="$1" rel kind
  if [ -d "$t" ]; then
    rel="${t#$ROOT/}"
    rel="${rel%/}"
    case "$rel" in
      tech_design/*)
        check_td_dir "$t" "$rel"
        CHECKED=$((CHECKED + 1))
        ;;
      prd|tech_design|plan|test_cases|material)
        printf '%s: 层根目录不能作为单文件校验目标: %s\n' "$SCRIPT_PATH" "$rel" >&2
        exit 2
        ;;
      *)
        printf '%s: 无法识别的目录目标: %s\n' "$SCRIPT_PATH" "$rel" >&2
        exit 2
        ;;
    esac
    return 0
  fi

  rel="${t#$ROOT/}"
  kind=$(printf '%s' "$rel" | awk -F/ '
    $1=="prd"        && NF==3 { print "prd"; exit }
    $1=="tech_design"&& NF==3 { print "td"; exit }
    $1=="plan"       && NF==3 { print "plan"; exit }
    $1=="test_cases" && NF==3 { print "tc"; exit }
    { print "" }
  ')
  case "$kind" in
    prd) check_prd "$t" "$rel" ;;
    td)
      d=$(dirname "$t")
      check_td_dir "$d" "${rel%/*}"
      ;;
    plan) check_plan "$t" "$rel" ;;
    tc) check_testcase "$t" "$rel" ;;
    *)
      printf '%s: 无法识别的文件类型(只支持 prd/ tech_design/ plan/ test_cases/ 下的制品): %s\n' "$SCRIPT_PATH" "$rel" >&2
      exit 2
      ;;
  esac
  CHECKED=$((CHECKED + 1))
}

if [ -n "$TARGET" ]; then
  run_single_target "$TARGET"
else
  run_whole_repo
  if [ "$CHECKED" -eq 0 ]; then
    err "本仓没有任何规格产物,门禁无从校验"
  fi
fi

if [ ${#ERRORS[@]} -eq 0 ]; then
  ok "字段校验通过 (检查 $CHECKED 个制品)"
fi

STATUS="pass"
CODE=0
if [ ${#ERRORS[@]} -gt 0 ]; then STATUS="violation"; CODE=1; fi

if [ "$JSON" -eq 1 ]; then
  printf '{"script":"check-md-schema.sh","root":"%s","status":"%s","exit_code":%d,"error_count":%d,"warning_count":%d,"checked":%d,"stage_override":"%s","errors":%s,"warnings":%s,"notes":%s}\n' \
    "$(printf '%s' "$ROOT" | json_escape)" "$STATUS" "$CODE" "${#ERRORS[@]}" "${#WARNINGS[@]}" "$CHECKED" "$STAGE_OVERRIDE" \
    "$(json_str_array "${ERRORS[@]}")" \
    "$(json_str_array "${WARNINGS[@]}")" \
    "$(json_str_array "${NOTES[@]}")"
fi

exit $CODE
