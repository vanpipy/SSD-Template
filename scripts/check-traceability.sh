#!/usr/bin/env bash
# check-traceability.sh — 跨文件引用追溯校验
#
# 检查项(编号沿用旧脚本, 便于对照):
#   T1  PRD 场景 → Tech Design 场景映射覆盖 (v4: README.md `## 场景映射`; v3: scenario-mapping.md)
#   T2  Plan 内 V-{n} 引用闭环 (每个 V 在同文件有 `### V-{n}:` 定义)
#   T3  Plan 内 KD-{n} 引用闭环 (每个 KD 在 TD 的 ards.md / decisions.md 有 `## KD-{n}:`)
#   T4  Plan 内 Change #N ↔ V-{n} 双向闭环 (仅当 Plan 含 `## 变更索引`)
#   T6  台账 ID 格式与唯一性 (可选层: 含 `## PRD台账` 段的批次台账)
#   T7  README 关系边表: 关系类型枚举 + 节点标识存在性
#   T8  supersede 边 ↔ Deprecated 状态一致性 (双向)
#   T9  test_cases 元信息上游引用存在性 (test_cases 层存在才校验)
#   T10 README 用例登记表 TEST-ID 唯一性 + 登记路径存在性
#   T11 Plan 元信息「参考 Test Cases」引用存在性
#   T12 跨层级联一致性 (父 PRD/TD Deprecated → 下游应同步降级)
#
# 层容错(契约 M11):
#   - 缺下游层不是违规; 只在**相邻两层都存在**时闭环
#   - 上游层缺失 → 跳过该对, 不报错
#   - 下游层存在而上游层整个缺失 → 违规(有 Plan 却没有 Tech Design)
#   - 只有 PRD 的仓库 → 本脚本必须 exit 0
#
# 可移植性(契约 M9):
#   - 不用 GNU `grep -P` / `grep -oP`; 标识提取用 awk
#   - 不用 `realpath --relative-to`; 相对路径用 cd+pwd 规整 + ROOT 前缀裁剪
#   - 不用 `find -mindepth/-maxdepth`; 全部改为全深度扫描 + 形状判定
#
# 用法:
#   scripts/check-traceability.sh [--json] [--root DIR] [TARGET]
#
# 退出码: 0=通过 1=违规 2=调用错误 / 环境错误

set -uo pipefail

SCRIPT_PATH=$0
SCRIPT_DIR=$(cd -- "$(dirname -- "$SCRIPT_PATH")" >/dev/null 2>&1 && pwd)
DEFAULT_ROOT=$(dirname -- "$SCRIPT_DIR")

JSON=0
ROOT=""
TARGET=""
NO_COLOR=${NO_COLOR:-0}
STAGE_OVERRIDE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    --root)
      [ $# -ge 2 ] || { printf '✗ --root 需要目录参数\n' >&2; exit 2; }
      ROOT="$2"; shift ;;
    --root=*) ROOT="${1#--root=}" ;;
    --stage)
      [ $# -ge 2 ] || { printf '✗ --stage 需要参数\n' >&2; exit 2; }
      STAGE_OVERRIDE=$(printf '%s' "$2" | tr 'A-Z' 'a-z'); shift ;;
    --stage=*) STAGE_OVERRIDE=$(printf '%s' "${1#--stage=}" | tr 'A-Z' 'a-z') ;;
    --help|-h)
      printf '用法: %s [--json] [--root DIR] [--stage STAGE] [TARGET]\n' "$SCRIPT_PATH"; exit 0 ;;
    -*) printf '✗ 未知参数: %s\n' "$1" >&2; exit 2 ;;
    *) [ -z "$TARGET" ] && TARGET="$1" || { printf '✗ 只能指定一个 TARGET\n' >&2; exit 2; } ;;
  esac
  shift
done

if [ -n "$STAGE_OVERRIDE" ]; then
  case "$STAGE_OVERRIDE" in
    draft|deprecated|ready|implemented) : ;;
    *) printf '✗ --stage 取值非法: %s (可用: draft|ready|implemented|deprecated)\n' "$STAGE_OVERRIDE" >&2; exit 2 ;;
  esac
fi

[ -n "$ROOT" ] || ROOT="$DEFAULT_ROOT"
if [ ! -d "$ROOT" ]; then
  printf '✗ --root 目录不存在: %s\n' "$ROOT" >&2
  exit 2
fi
ROOT=$(cd -- "$ROOT" >/dev/null 2>&1 && pwd -P)

# 相对 TARGET 一律按 ROOT 解析(与其余门禁脚本的 CLI 语义一致)
if [ -n "$TARGET" ]; then
  case "$TARGET" in
    /*) ;;
    *) TARGET="$ROOT/$TARGET" ;;
  esac
fi

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

# --- 常量 ---
TOPIC_RE='^[a-z0-9]+(-[a-z0-9]+)*$'
DATE_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
DATETOPIC_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$'
LEDGER_ID_RE='^(PRD|TECH|TEST|PLAN)-[0-9]{8}-[0-9]{2}$'
REL_TYPE_RE='^(supersede|inherit|depend|shared|conflict|relate|split-from|merge-into)$'
NODE_PATH_RE='^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$'

# --- 辅助 ---

# 路径规整(不依赖 GNU realpath --relative-to)
abs_norm() {
  local p="$1" d b
  d=$(dirname -- "$p")
  b=$(basename -- "$p")
  local phys
  if phys=$(cd -- "$d" 2>/dev/null && pwd -P); then
    printf '%s/%s' "$phys" "$b"
  else
    printf '%s' "$p"
  fi
}

# 仓内相对路径(相对 ROOT)
rel_of() {
  local p="$1" root
  root="${ROOT%/}/"
  case "$p" in
    "$root"*) printf '%s' "${p#"$root"}" ;;
    *) printf '%s' "$p" ;;
  esac
}

# 抽取标识(不依赖 grep -P): $1 = 前缀(如 "V-"), $2 = 文件
# 规则: 标识前不得紧邻字母数字(避免 PV-001 之类子串误匹配)
extract_ids() {
  awk -v p="$1" '
    {
      line = $0
      while (match(line, p "[0-9]+")) {
        pre = substr(line, 1, RSTART - 1)
        n = length(pre)
        if (n == 0 || pre !~ /[A-Za-z0-9]/) print substr(line, RSTART, RLENGTH)
        line = substr(line, RSTART + RLENGTH)
      }
    }
  ' "$2" | LC_ALL=C sort -u
}

# 读取 `> **状态**: X` (容忍 `**状态**: X`)
state_of() {
  awk '
    /^[[:space:]]*>?[[:space:]]*\*\*状态\*\*[[:space:]]*[:：]?/ {
      val = $0
      sub(/^[^:：]*[:：][[:space:]]*/, "", val)
      gsub(/^[[:space:]]*[|*`]+[[:space:]]*/, "", val)
      gsub(/[[:space:]]*[|*`]+$/, "", val)
      if (match(val, /(Draft|Ready|Implemented|Deprecated)/)) {
        print substr(val, RSTART, RLENGTH)
        exit
      }
    }
  ' "$1" 2>/dev/null
}

# 段体: `## <prefix>` 段内容
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

# --- 制品发现(全深度扫描 + 形状判定) ---
PRD_ARTIFACTS=""
TD_DIRS=""
PLAN_FILES=""
TC_FILES=""
HAS_PRD_LAYER=0
HAS_TD_LAYER=0
HAS_PLAN_LAYER=0
HAS_TC_LAYER=0

discover() {
  local f d dn bn
  if [ -d "$ROOT/prd" ]; then
    for f in "$ROOT"/prd/*/*.md; do
      [ -f "$f" ] || continue
      d=$(dirname -- "$f"); dn=$(basename -- "$d"); bn=$(basename -- "$f" .md)
      printf '%s' "$dn" | grep -Eq "$DATE_RE" || continue
      printf '%s' "$bn" | grep -Eq "$TOPIC_RE" || continue
      PRD_ARTIFACTS="$PRD_ARTIFACTS$f
"
      HAS_PRD_LAYER=1
    done
  fi
  if [ -d "$ROOT/tech_design" ]; then
    for d in "$ROOT"/tech_design/*/; do
      [ -d "$d" ] || continue
      dn=$(basename -- "$d")
      printf '%s' "$dn" | grep -Eq "$DATETOPIC_RE" || continue
      TD_DIRS="$TD_DIRS$d
"
      HAS_TD_LAYER=1
    done
  fi
  if [ -d "$ROOT/plan" ]; then
    for d in "$ROOT"/plan/*/; do
      [ -d "$d" ] || continue
      dn=$(basename -- "$d")
      printf '%s' "$dn" | grep -Eq "$DATETOPIC_RE" || continue
      for f in "$d"*.md; do
        [ -f "$f" ] || continue
        bn=$(basename -- "$f" .md)
        printf '%s' "$bn" | grep -Eq "$TOPIC_RE" || continue
        PLAN_FILES="$PLAN_FILES$f
"
        HAS_PLAN_LAYER=1
      done
    done
  fi
  if [ -d "$ROOT/test_cases" ]; then
    for f in "$ROOT"/test_cases/*/*.md; do
      [ -f "$f" ] || continue
      d=$(dirname -- "$f"); dn=$(basename -- "$d"); bn=$(basename -- "$f" .md)
      printf '%s' "$dn" | grep -Eq "$DATE_RE" || continue
      case "$bn" in *-key-points) continue ;; esac
      TC_FILES="$TC_FILES$f
"
      HAS_TC_LAYER=1
    done
  fi
}

discover

# --- 层容错(M11) ---
if [ "$HAS_PLAN_LAYER" -eq 1 ] && [ "$HAS_TD_LAYER" -eq 0 ]; then
  err "存在 Plan 制品但 tech_design 层没有任何 Tech Design — 下游层存在而上游层缺失(契约 M11)"
fi
if [ "$HAS_TD_LAYER" -eq 1 ] && [ "$HAS_PRD_LAYER" -eq 0 ]; then
  warn "存在 Tech Design 但 prd 层没有 PRD — 按契约 M11 跳过 PRD↔Tech Design 闭环"
fi
if [ "$HAS_TC_LAYER" -eq 1 ] && [ "$HAS_TD_LAYER" -eq 0 ] && [ "$HAS_PLAN_LAYER" -eq 0 ]; then
  warn "存在 Test Cases 但没有上游 Tech Design/Plan — 按契约 M11 跳过上游闭环"
fi

CHECKED=0
LEDGER_STATES=""   # "ID=STATE" 列表
DEPRECATED_NODES="" # 已 Deprecated 的节点标识(台账 ID 或仓内路径)

# --- 可选层: T6 台账 ---
process_ledger() {
  local lf="$1" body cols id_col st_col row lid lst dup id seen
  body=$(awk '
    /^```/ { fence = !fence; next }
    !fence && /^##[[:space:]]+PRD台账[[:space:]]*$/ { f=1; next }
    !fence && f && /^#{1,6}[[:space:]]/ { exit }
    f { print }
  ' "$lf" 2>/dev/null)
  [ -z "$body" ] && return 0
  printf '%s\n' "$body" | grep -qE '^\|' || return 0
  cols=$(printf '%s\n' "$body" | awk -F'|' '
    { id=0; st=0
      for (i=2; i<=NF-1; i++) {
        c=$i; gsub(/^[ \t]+|[ \t]+$/,"",c)
        if (c=="ID") id=i; else if (c=="状态") st=i
      }
      if (id) { printf "%d %d\n", id, (st?st:7); exit } }
  ')
  if [ -z "$cols" ]; then
    warn "$(rel_of "$lf") — 台账表未找到 \`ID\` 列, 跳过 ID 校验"
    return 0
  fi
  read -r id_col st_col <<< "$cols"
  CHECKED=$((CHECKED + 1))
  seen=" "
  while IFS= read -r row; do
    [ -z "$row" ] && continue
    lid=$(printf '%s\n' "$row" | awk -F'|' -v c="$id_col" '{gsub(/^[ \t]+|[ \t]+$/,"",$c); print $c}')
    case "$lid" in ""|"ID") continue ;; esac
    case "$lid" in *["[]"]*) continue ;; esac
    if ! printf '%s' "$lid" | grep -Eq '^[?:+-]+$'; then
      if ! printf '%s' "$lid" | grep -Eq "$LEDGER_ID_RE"; then
        err "$(rel_of "$lf") — 台账 ID 格式非法: '$lid' (期望 {PRD|TECH|TEST|PLAN}-{YYYYMMDD}-{NN})"
        continue
      fi
      if printf '%s' "$seen" | grep -q " $lid "; then
        err "$(rel_of "$lf") — 台账 ID 重复: $lid"
        continue
      fi
      seen="$seen$lid "
      lst=$(printf '%s\n' "$row" | awk -F'|' -v c="$st_col" '{gsub(/^[ \t]+|[ \t]+$/,"",$c); print $c}')
      LEDGER_STATES="$LEDGER_STATES $lid=$lst"
      if [ "$lst" = "Deprecated" ]; then
        DEPRECATED_NODES="$DEPRECATED_NODES $lid"
      fi
    fi
  done < <(printf '%s\n' "$body" | grep -E '^\|')
}

# 节点状态解析: 台账 ID 优先, 其次仓内路径
node_state() {
  local node="$1" s
  s=$(printf '%s' "$LEDGER_STATES" | tr ' ' '\n' | grep "^${node}=" | head -1 | cut -d= -f2-)
  if [ -n "$s" ]; then printf '%s' "$s"; return 0; fi
  case "$node" in
    *.md)
      if [ -f "$ROOT/$node" ]; then state_of "$ROOT/$node"; return 0; fi
      ;;
  esac
  return 1
}

# --- 可选层: T7/T8 关联矩阵 ---
process_matrix() {
  local readme="$1" edges row a rel_type b seen_ids
  edges=$(awk '
    /^```/ { fence = !fence; next }
    !fence && /^###[[:space:]]+关系边表[[:space:]]*$/ { f=1; next }
    !fence && f && /^#{1,6}[[:space:]]/ { exit }
    f { print }
  ' "$readme" 2>/dev/null)
  [ -z "$edges" ] && return 0
  CHECKED=$((CHECKED + 1))
  EDGE_A=""; EDGE_REL=""; EDGE_B=""
  while IFS= read -r row; do
    [ -z "$row" ] && continue
    printf '%s' "$row" | grep -qE '^\|[[:space:]]*[0-9]+[[:space:]]*\|' || continue
    a=$(printf '%s\n' "$row" | awk -F'|' '{gsub(/^[ \t]+|[ \t]+$/,"",$3); print $3}')
    rel_type=$(printf '%s\n' "$row" | awk -F'|' '{gsub(/^[ \t]+|[ \t]+$/,"",$4); print $4}')
    b=$(printf '%s\n' "$row" | awk -F'|' '{gsub(/^[ \t]+|[ \t]+$/,"",$5); print $5}')
    EDGE_A="$EDGE_A $a"; EDGE_REL="$EDGE_REL $rel_type"; EDGE_B="$EDGE_B $b"
    if ! printf '%s' "$rel_type" | grep -Eq "$REL_TYPE_RE"; then
      err "$(rel_of "$readme") — 关系边类型非法: '$rel_type' (应为 supersede/inherit/depend/shared/conflict/relate/split-from/merge-into)"
    fi
    for node in "$a" "$b"; do
      [ -z "$node" ] && continue
      case "$node" in
        *.md)
          if printf '%s' "$node" | grep -Eq "$NODE_PATH_RE" && [ ! -e "$ROOT/$node" ]; then
            err "$(rel_of "$readme") — 关系边节点路径不存在: $node"
          fi
          ;;
        *)
          if ! printf '%s' "$LEDGER_STATES" | tr ' ' '\n' | grep -q "^${node}="; then
            warn "$(rel_of "$readme") — 关系边节点标识未在台账登记且不是仓内路径, 无法核对: $node"
          fi
          ;;
      esac
    done
    # T8 正向: supersede 的被替代者必须 Deprecated
    if [ "$rel_type" = "supersede" ]; then
      local st
      if st=$(node_state "$b"); then
        if [ "$st" != "Deprecated" ]; then
          err "$(rel_of "$readme") — supersede 边的被替代节点状态不是 Deprecated: $b (当前: $st)"
        fi
      else
        warn "$(rel_of "$readme") — 无法解析被替代节点状态, 跳过 supersede 一致性核对: $b"
      fi
    fi
  done < <(printf '%s\n' "$edges" | grep -E '^\|')

  # T8 反向: 已 Deprecated 的 PRD 必须有 supersede 边指向它
  local node st
  for pf in $PRD_ARTIFACTS; do
    st=$(state_of "$pf")
    [ "$st" = "Deprecated" ] || continue
    node=$(rel_of "$pf")
    if ! printf '%s' "$EDGE_B" | tr ' ' '\n' | grep -qx "$node"; then
      err "$(rel_of "$pf") — 状态为 Deprecated, 但 README 关系边表中没有 supersede 边指向它"
    fi
  done
}

# --- 可选层: T10 用例登记表 ---
process_test_registry() {
  local readme="$1" row tid path seen
  seen=" "
  while IFS= read -r row; do
    [ -z "$row" ] && continue
    tid=$(printf '%s\n' "$row" | grep -oE 'TEST-[0-9]{8}-[0-9]{2}' | head -1)
    [ -z "$tid" ] && continue
    path=$(printf '%s\n' "$row" | grep -oE '`[^`]+\.md`' | tr -d '`' | head -1)
    [ -z "$path" ] && continue
    if printf '%s' "$seen" | grep -q " $tid "; then
      err "$(rel_of "$readme") — 用例登记 ID 重复: $tid"
    else
      seen="$seen$tid "
    fi
    if [ ! -e "$ROOT/$path" ]; then
      err "$(rel_of "$readme") — 用例登记路径不存在: $path"
    fi
  done < <(grep -E '^\|' "$readme" 2>/dev/null)
}

# --- Plan 侧: T3 KD 闭环 / T2 V 闭环 / T4 Change↔V / T11 参考 Test Cases ---
process_plan() {
  local pf="$1" rel dir td_ref td_abs td_rel kd_src v kd chg_no_v defined_vs
  rel=$(rel_of "$pf")
  dir=$(dirname -- "$pf")
  CHECKED=$((CHECKED + 1))

  td_ref=$(grep -oE '\.\./\.\.?/tech_design/[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9_-]+' "$pf" 2>/dev/null | head -1)
  td_rel=""
  if [ -n "$td_ref" ]; then
    td_abs=$(abs_norm "$dir/$td_ref")
    td_rel=$(rel_of "$td_abs")
    [ -d "$ROOT/$td_rel" ] || td_rel=""
  fi
  if [ -z "$td_rel" ]; then
    if [ "$HAS_TD_LAYER" -eq 1 ]; then
      err "$rel — 未引用可解析的 Tech Design(\`../../tech_design/{date}-{topic}/\`); 上游层存在但引用缺失"
    fi
  else
    kd_src=""
    [ -f "$ROOT/$td_rel/ards.md" ] && kd_src="$ROOT/$td_rel/ards.md"
    [ -z "$kd_src" ] && [ -f "$ROOT/$td_rel/decisions.md" ] && kd_src="$ROOT/$td_rel/decisions.md"
    if [ -n "$kd_src" ]; then
      for kd in $(extract_ids "KD-" "$pf"); do
        if ! grep -qE "^##[[:space:]]+${kd}:" "$kd_src"; then
          err "$rel — 引用 ${kd} 但 $(rel_of "$kd_src") 中没有 \`## ${kd}:\` 定义"
        fi
      done
    else
      warn "$rel — Tech Design $td_rel 既无 ards.md 也无 decisions.md, 跳过 KD 闭环"
    fi
  fi

  for v in $(extract_ids "V-" "$pf"); do
    if ! grep -qE "^###[[:space:]]+${v}:" "$pf"; then
      err "$rel — 引用 ${v} 但同文件没有 \`### ${v}:\` 定义"
    fi
  done

  if grep -qE '^##[[:space:]]+变更索引' "$pf"; then
    chg_no_v=$(awk '
      /^### Change #|^#### Change #/ { if (in_chg && !found) print prev; in_chg=1; prev=$0; found=0; next }
      /^##/                          { if (in_chg && !found) print prev; in_chg=0 }
      in_chg && /(^|[^A-Za-z])V-[0-9]+/ { found=1 }
      END                            { if (in_chg && !found) print prev }
    ' "$pf")
    for chg in $chg_no_v; do
      [ -z "$chg" ] && continue
      err "$rel — ${chg} 未引用任何 V-{n}(Change 段应有 \`**验证**: V-{n}\`)"
    done

    defined_vs=$(grep -oE '^###[[:space:]]+V-[0-9]+:' "$pf" | grep -oE 'V-[0-9]+' | LC_ALL=C sort -u)
    for v in $defined_vs; do
      if ! awk -v h="### $v:" 'index($0,h)==1{p=1; next} p && /^### /{p=0} p' "$pf" | grep -qE 'Change #[0-9]+'; then
        err "$rel — ${v} 已定义但无 Change 关联(Change 段 / 变更索引 / 对账行 / V 段自引均未覆盖)"
      fi
    done
  fi

  local refs r
  refs=$(grep -E '^[[:space:]]*>?[[:space:]]*\*\*参考 Test Cases\*\*' "$pf" 2>/dev/null | grep -oE '`[^`]+`' | tr -d '`')
  for r in $refs; do
    case "$r" in
      test_cases/*)
        if [ "$HAS_TC_LAYER" -eq 1 ] && [ ! -e "$ROOT/$r" ]; then
          err "$rel — 参考 Test Cases 引用不存在: $r"
        fi
        ;;
    esac
  done
}

# --- TD 侧: T1 场景覆盖 ---
process_td() {
  local tdd="$1" rel prd_ref prd_abs prd_rel mapping_src prd_count mapping_rows
  rel=$(rel_of "$tdd")
  [ -f "$tdd/README.md" ] || return 0
  CHECKED=$((CHECKED + 1))

  prd_ref=$(grep -oE '\.\./\.\./prd/[A-Za-z0-9._/-]+\.md' "$tdd/README.md" 2>/dev/null | head -1)
  if [ -z "$prd_ref" ]; then
    if [ "$HAS_PRD_LAYER" -eq 1 ]; then
      warn "$rel/README.md — 未引用上游 PRD(\`../../prd/{date}/{topic}.md\`), 跳过 PRD↔Tech Design 闭环"
    fi
    return 0
  fi
  prd_abs=$(abs_norm "$tdd/$prd_ref")
  prd_rel=$(rel_of "$prd_abs")
  if [ ! -f "$ROOT/$prd_rel" ]; then
    if [ "$HAS_PRD_LAYER" -eq 1 ]; then
      err "$rel/README.md — 引用的上游 PRD 不存在: $prd_rel"
    fi
    return 0
  fi

  mapping_src=""
  [ -f "$tdd/scenario-mapping.md" ] && mapping_src="$tdd/scenario-mapping.md"
  [ -z "$mapping_src" ] && [ -f "$tdd/ards.md" ] && mapping_src="$tdd/README.md"
  [ -z "$mapping_src" ] && return 0
  if [ "$mapping_src" = "$tdd/README.md" ]; then
    mapping_rows=$(section_body "$mapping_src" "场景映射" | grep -cE '^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|$')
  else
    mapping_rows=$(grep -cE '^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|$' "$mapping_src")
  fi
  prd_count=$(grep -cE '^###[[:space:]]*场景[:：]' "$ROOT/$prd_rel")
  if [ "$mapping_rows" -lt "$prd_count" ]; then
    err "$(rel_of "$mapping_src") — 场景映射表格行数 ($mapping_rows) 少于 PRD 场景数 ($prd_count)"
  fi
}

# --- T12: Deprecated 级联 ---
process_cascade_plan() {
  local pf="$1" rel prd_ref prd_abs prd_rel self_state td_ref td_rel parent_state
  rel=$(rel_of "$pf")
  self_state=$(state_of "$pf")
  prd_ref=$(grep -oE '\.\./\.\./prd/[A-Za-z0-9._/-]+\.md' "$pf" 2>/dev/null | head -1)
  if [ -n "$prd_ref" ]; then
    prd_abs=$(abs_norm "$(dirname -- "$pf")/$prd_ref")
    prd_rel=$(rel_of "$prd_abs")
    if [ -f "$ROOT/$prd_rel" ]; then
      parent_state=$(state_of "$ROOT/$prd_rel")
      if [ "$parent_state" = "Deprecated" ] && [ "$self_state" != "Deprecated" ]; then
        err "$rel — 父 PRD 已 Deprecated ($prd_rel), Plan 未同步降级 (当前: ${self_state:-未声明})"
      fi
    fi
  fi
  td_ref=$(grep -oE '\.\./\.\.?/tech_design/[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9_-]+' "$pf" 2>/dev/null | head -1)
  if [ -n "$td_ref" ]; then
    td_rel="tech_design/$(basename -- "$td_ref")"
    if [ -f "$ROOT/$td_rel/README.md" ]; then
      parent_state=$(state_of "$ROOT/$td_rel/README.md")
      if [ "$parent_state" = "Deprecated" ] && [ "$self_state" != "Deprecated" ]; then
        err "$rel — 父 Tech Design 已 Deprecated ($td_rel), Plan 未同步降级 (当前: ${self_state:-未声明})"
      fi
    fi
  fi
}

process_cascade_td() {
  local tdd="$1" rel prd_ref prd_abs prd_rel self_state parent_state
  rel=$(rel_of "$tdd")
  [ -f "$tdd/README.md" ] || return 0
  self_state=$(state_of "$tdd/README.md")
  prd_ref=$(grep -oE '\.\./\.\./prd/[A-Za-z0-9._/-]+\.md' "$tdd/README.md" 2>/dev/null | head -1)
  [ -n "$prd_ref" ] || return 0
  prd_abs=$(abs_norm "$tdd/$prd_ref")
  prd_rel=$(rel_of "$prd_abs")
  [ -f "$ROOT/$prd_rel" ] || return 0
  parent_state=$(state_of "$ROOT/$prd_rel")
  if [ "$parent_state" = "Deprecated" ] && [ "$self_state" != "Deprecated" ]; then
    err "$rel/README.md — 父 PRD 已 Deprecated ($prd_rel), Tech Design 未同步降级 (当前: ${self_state:-未声明})"
  fi
}

# --- T9: test_cases 元信息上游引用存在性 ---
process_testcase() {
  local tf="$1" rel refs r
  rel=$(rel_of "$tf")
  CHECKED=$((CHECKED + 1))
  refs=$(awk -F'|' '/^\|/ {
      key=$2; gsub(/^[ \t]+|[ \t]+$/,"",key); gsub(/\*+/,"",key)
      if (key=="来源"||key=="来源 Tech Design"||key=="来源 Plan"||key=="Tech Design"||key=="Plan") print $3
    }' "$tf" | grep -oE '`[^`]+`' | tr -d '`')
  for r in $refs; do
    case "$r" in
      prd/*|material/*|tech_design/*|plan/*)
        if [ ! -e "$ROOT/$r" ]; then
          err "$rel — 元信息上游引用不存在: $r"
        fi
        ;;
    esac
  done
}

# --- 执行 ---
run_all() {
  local pf tdd tf lf
  # M6: 全仓没有任何规格产物 → 门禁无从校验, 退出码 1
  if [ "$HAS_PRD_LAYER" -eq 0 ] && [ "$HAS_TD_LAYER" -eq 0 ] \
     && [ "$HAS_PLAN_LAYER" -eq 0 ] && [ "$HAS_TC_LAYER" -eq 0 ]; then
    err "本仓没有任何规格产物,门禁无从校验"
  fi
  for lf in "$ROOT"/material/*/*.md "$ROOT"/prd/*/*.md "$ROOT/PRDS.md"; do
    [ -f "$lf" ] || continue
    process_ledger "$lf"
  done
  for pf in $PLAN_FILES; do process_plan "$pf"; done
  for tdd in $TD_DIRS; do process_td "$tdd"; done
  for pf in $PLAN_FILES; do process_cascade_plan "$pf"; done
  for tdd in $TD_DIRS; do process_cascade_td "$tdd"; done
  for tf in $TC_FILES; do process_testcase "$tf"; done
  if [ -f "$ROOT/README.md" ]; then
    process_matrix "$ROOT/README.md"
    process_test_registry "$ROOT/README.md"
  fi
}

if [ -n "$TARGET" ]; then
  if [ ! -e "$TARGET" ]; then
    printf '✗ TARGET 不存在: %s\n' "$TARGET" >&2
    exit 2
  fi
  t_abs=$(abs_norm "$TARGET")
  t_rel=$(rel_of "$t_abs")
  case "$t_rel" in
    prd/*)
      for tdd in $TD_DIRS; do
        prd_ref=$(grep -oE '\.\./\.\./prd/[A-Za-z0-9._/-]+\.md' "$tdd/README.md" 2>/dev/null | head -1)
        [ -n "$prd_ref" ] || continue
        prd_abs=$(abs_norm "$tdd/$prd_ref")
        [ "$(rel_of "$prd_abs")" = "$t_rel" ] || continue
        process_td "$tdd"
        process_cascade_td "$tdd"
      done
      ;;
    tech_design/*)
      tdd_dir=$(dirname -- "$t_abs")
      process_td "$tdd_dir"
      process_cascade_td "$tdd_dir"
      ;;
    plan/*)
      for pf in $PLAN_FILES; do
        [ "$(rel_of "$pf")" = "$t_rel" ] || continue
        process_plan "$pf"
        process_cascade_plan "$pf"
      done
      ;;
    test_cases/*)
      for tf in $TC_FILES; do
        [ "$(rel_of "$tf")" = "$t_rel" ] || continue
        process_testcase "$tf"
      done
      ;;
    *)
      printf '✗ TARGET 不在任何规格层内: %s\n' "$t_rel" >&2
      exit 2
      ;;
  esac
else
  run_all
fi

# --- 汇总 ---
ERRC=${#ERRORS[@]}
WARNC=${#WARNINGS[@]}
if [ "$ERRC" -gt 0 ]; then STATUS="violation"; EXIT=1; else STATUS="pass"; EXIT=0; fi

if [ "$JSON" -eq 1 ]; then
  printf '{"script":"check-traceability.sh","root":"%s","status":"%s","exit_code":%d,"error_count":%d,"warning_count":%d,"checked":%d,"stage_override":"%s","errors":%s,"warnings":%s,"notes":%s}\n' \
    "$(printf '%s' "$ROOT" | json_escape)" "$STATUS" "$EXIT" "$ERRC" "$WARNC" "$CHECKED" "$STAGE_OVERRIDE" \
    "$(json_str_array "${ERRORS[@]+"${ERRORS[@]}"}")" \
    "$(json_str_array "${WARNINGS[@]+"${WARNINGS[@]}"}")" \
    "$(json_str_array "${NOTES[@]+"${NOTES[@]}"}")"
else
  if [ "$ERRC" -gt 0 ]; then
    printf '✗ 追溯校验: %d 项违规\n' "$ERRC"
  else
    ok "追溯校验通过 (检查 $CHECKED 个制品)"
  fi
  [ "$WARNC" -gt 0 ] && printf '· %d 项提示\n' "$WARNC"
fi
exit $EXIT
