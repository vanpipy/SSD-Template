#!/usr/bin/env bash
# sync-prd.sh — PRD 台账登记 + 规格统计同步(幂等)
#
# 职责边界(契约 M12):
#   - **不写**仓根的其它顶层文档(AGENTS.md / WORKFLOW.md …)。M12 的禁令
#     只针对「顶层文档」。
#   - **写**两处, 且仅这两处:
#       1) 可选层 `material/{YYYY-MM-DD}/PRDS.md` — 批次台账: 补登骨架行 + 标记待办行
#          (schema/prd-ledger.md 的 11 列格式; 见 material/README.md)
#       2) 根 `README.md` 的 `<!-- prd-stats:begin -->` … `<!-- prd-stats:end -->` 标记块
#          —— 标记块之外的内容永不触碰
#   - 不做任何 git 写操作, 只改工作区文件。
#
# 退出码:
#   0 = 台账与统计块都已同步, 且没有待办行
#   1 = 存在待办行(待分析 / 待抓取 / 孤儿) —— 工作状态信号, 不是规格违规;
#       `--check` 下还表示统计块/台账与实际制品不一致(漂移)
#   2 = 调用/环境错误
#   CI 因此**不**按本脚本的退出码判红(台账有「待分析」是常态),
#   改为「写模式(幂等) + git diff --exit-code -- README.md material/」比对漂移。
#
# 用法:
#   scripts/sync-prd.sh [--json] [--root DIR] [--check]
#
# 可移植性(契约 M9):
#   - 不用 `find -mindepth/-maxdepth`; 全深度扫描 + 形状判定
#   - 不用 GNU 专有 date 选项; 时间戳用 POSIX `date '+%Y-%m-%d %H:%M'`

set -uo pipefail

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
    --help|-h)
      printf '用法: %s [--json] [--root DIR] [--check]\n' "$SCRIPT_PATH"; exit 0 ;;
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
DATETOPIC_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$'

# 读取状态 token: `> **状态**: X`(PRD/TD/Plan) 或 `| **状态** | X |`(TestCase)
read_state() {
  awk '
    /^[[:space:]]*>?[[:space:]]*\*\*状态\*\*[[:space:]]*[:：]?/ {
      val=$0
      sub(/^[^:：]*[:：][[:space:]]*/, "", val)
      gsub(/^[[:space:]]*[|*`]+[[:space:]]*/, "", val)
      gsub(/[[:space:]]*[|*`]+$/, "", val)
      if (match(val, /(Draft|Ready|Implemented|Deprecated)/)) { print substr(val, RSTART, RLENGTH); exit }
    }
  ' "$1" 2>/dev/null
}

read_meta_state() {
  awk -F'|' '
    /^\|/ {
      key=$2; gsub(/^[ \t]+|[ \t]+$/,"",key); gsub(/\*+/,"",key)
      if (key=="状态") {
        v=$3; gsub(/^[ \t]+|[ \t]+$/,"",v)
        if (match(v, /(Draft|Ready|Implemented|Deprecated)/)) { print substr(v, RSTART, RLENGTH); exit }
      }
    }
  ' "$1" 2>/dev/null
}

# --- 各层计数 ---
# 状态分布覆盖契约 D1 的 4 个状态(Draft / Ready / Implemented / Deprecated);
# `其他` 只用于状态值不在枚举内(由 check-md-schema.py 负责报错)。
prd_total=0; prd_draft=0; prd_ready=0; prd_impl=0; prd_dep=0; prd_other=0
td_total=0;  td_draft=0;  td_ready=0;  td_impl=0;  td_dep=0;  td_other=0
plan_total=0; plan_draft=0; plan_ready=0; plan_impl=0; plan_dep=0; plan_other=0
test_total=0; test_draft=0; test_ready=0; test_impl=0; test_dep=0; test_other=0

if [ -d "$ROOT/prd" ]; then
  for f in "$ROOT"/prd/*/*.md; do
    [ -f "$f" ] || continue
    d=$(dirname -- "$f"); dn=$(basename -- "$d"); bn=$(basename -- "$f" .md)
    printf '%s' "$dn" | grep -Eq "$DATE_RE" || continue
    printf '%s' "$bn" | grep -Eq "$TOPIC_RE" || continue
    prd_total=$((prd_total+1))
    st=$(read_state "$f")
    case "$st" in
      Draft) prd_draft=$((prd_draft+1)) ;;
      Deprecated) prd_dep=$((prd_dep+1)) ;;
      Implemented) prd_impl=$((prd_impl+1)) ;;
      Ready) prd_ready=$((prd_ready+1)) ;;
      *) prd_other=$((prd_other+1)) ;;
    esac
  done
fi

if [ -d "$ROOT/tech_design" ]; then
  for d in "$ROOT"/tech_design/*/; do
    [ -d "$d" ] || continue
    dn=$(basename -- "$d")
    printf '%s' "$dn" | grep -Eq "$DATETOPIC_RE" || continue
    [ -f "$d/README.md" ] || continue
    td_total=$((td_total+1))
    st=$(read_state "$d/README.md")
    case "$st" in
      Draft) td_draft=$((td_draft+1)) ;;
      Deprecated) td_dep=$((td_dep+1)) ;;
      Implemented) td_impl=$((td_impl+1)) ;;
      Ready) td_ready=$((td_ready+1)) ;;
      *) td_other=$((td_other+1)) ;;
    esac
  done
fi

if [ -d "$ROOT/plan" ]; then
  for d in "$ROOT"/plan/*/; do
    [ -d "$d" ] || continue
    dn=$(basename -- "$d")
    printf '%s' "$dn" | grep -Eq "$DATETOPIC_RE" || continue
    f="$d${dn#????-??-??-}.md"
    [ -f "$f" ] || continue
    plan_total=$((plan_total+1))
    st=$(read_state "$f")
    case "$st" in
      Draft) plan_draft=$((plan_draft+1)) ;;
      Deprecated) plan_dep=$((plan_dep+1)) ;;
      Implemented) plan_impl=$((plan_impl+1)) ;;
      Ready) plan_ready=$((plan_ready+1)) ;;
      *) plan_other=$((plan_other+1)) ;;
    esac
  done
fi

if [ -d "$ROOT/test_cases" ]; then
  for f in "$ROOT"/test_cases/*/*.md; do
    [ -f "$f" ] || continue
    d=$(dirname -- "$f"); dn=$(basename -- "$d"); bn=$(basename -- "$f" .md)
    printf '%s' "$dn" | grep -Eq "$DATE_RE" || continue
    case "$bn" in *-key-points) continue ;; esac
    printf '%s' "$bn" | grep -Eq "$TOPIC_RE" || continue
    test_total=$((test_total+1))
    st=$(read_meta_state "$f")
    case "$st" in
      Draft) test_draft=$((test_draft+1)) ;;
      Ready) test_ready=$((test_ready+1)) ;;
      Implemented) test_impl=$((test_impl+1)) ;;
      Deprecated) test_dep=$((test_dep+1)) ;;
      *) test_other=$((test_other+1)) ;;
    esac
  done
fi

# --- 状态分布文案(计数为 0 的项整项省略; 顺序固定 Draft → Ready → Implemented → Deprecated → 其他) ---
prd_dist=""; td_dist=""; plan_dist=""; test_dist=""
[ "$prd_draft" -gt 0 ] && prd_dist="Draft $prd_draft"
[ "$prd_ready" -gt 0 ] && prd_dist="${prd_dist:+$prd_dist · }Ready $prd_ready"
[ "$prd_impl"  -gt 0 ] && prd_dist="${prd_dist:+$prd_dist · }Implemented $prd_impl"
[ "$prd_dep"   -gt 0 ] && prd_dist="${prd_dist:+$prd_dist · }Deprecated $prd_dep"
[ "$prd_other" -gt 0 ] && prd_dist="${prd_dist:+$prd_dist · }其他 $prd_other"
[ "$td_draft" -gt 0 ] && td_dist="Draft $td_draft"
[ "$td_ready" -gt 0 ] && td_dist="${td_dist:+$td_dist · }Ready $td_ready"
[ "$td_impl"  -gt 0 ] && td_dist="${td_dist:+$td_dist · }Implemented $td_impl"
[ "$td_dep"   -gt 0 ] && td_dist="${td_dist:+$td_dist · }Deprecated $td_dep"
[ "$td_other" -gt 0 ] && td_dist="${td_dist:+$td_dist · }其他 $td_other"
[ "$plan_draft" -gt 0 ] && plan_dist="Draft $plan_draft"
[ "$plan_ready" -gt 0 ] && plan_dist="${plan_dist:+$plan_dist · }Ready $plan_ready"
[ "$plan_impl"  -gt 0 ] && plan_dist="${plan_dist:+$plan_dist · }Implemented $plan_impl"
[ "$plan_dep"   -gt 0 ] && plan_dist="${plan_dist:+$plan_dist · }Deprecated $plan_dep"
[ "$plan_other" -gt 0 ] && plan_dist="${plan_dist:+$plan_dist · }其他 $plan_other"
[ "$test_draft" -gt 0 ] && test_dist="Draft $test_draft"
[ "$test_ready" -gt 0 ] && test_dist="${test_dist:+$test_dist · }Ready $test_ready"
[ "$test_impl"  -gt 0 ] && test_dist="${test_dist:+$test_dist · }Implemented $test_impl"
[ "$test_dep"   -gt 0 ] && test_dist="${test_dist:+$test_dist · }Deprecated $test_dep"
[ "$test_other" -gt 0 ] && test_dist="${test_dist:+$test_dist · }其他 $test_other"

# --- 台账(可选层: material/{date}/PRDS.md) ---
# M12 的禁令只针对「顶层文档」(AGENTS.md / WORKFLOW.md 等仓根文档);
# material/ 是可选层, 批次台账是本脚本的原始职责: 补登骨架行 + 标记待办行 + 幂等。
#
# 退出码(material/README.md 与 Lead 口径一致):
#   0 = 台账与统计块都已同步, 且没有待办行
#   1 = 存在待办行(待分析 / 待抓取 / 孤儿) —— 工作状态信号, 不是规格违规;
#       `--check` 下还表示统计块/台账与实际制品不一致(漂移)
#   2 = 调用/环境错误
# CI 因此**不**按本脚本的退出码判红(待办是常态), 改为「写模式 + git diff」比对漂移。
PENDING=0

LEDGER_HEADER='| # | ID | PRD 名称 | 优先级 | 验收要点 | 状态 | 来源 | 关联素材 | 创建时间 | 更新时间 | 提出人 |
|---|----|---------|--------|----------|------|------|----------|----------|----------|--------|'

ledger_cols() {
  # 从表头推导列位置: ID / # / 状态 / 关联素材 / 优先级 / 提出人 / 来源 / 创建时间
  awk -F'|' '
    { id=0; num=0; st=0; src=0; tm=0; mat=0; pri=0; own=0
      for (i=2;i<=NF-1;i++) { c=$i; gsub(/^[ \t]+|[ \t]+$/,"",c)
        if (c=="ID") id=i; else if (c=="#") num=i; else if (c=="状态") st=i
        else if (c=="来源") src=i; else if (c=="创建时间") tm=i
        else if (c=="关联素材") mat=i; else if (c=="优先级") pri=i
        else if (c=="提出人") own=i }
      if (id) { printf "%d %d %d %d %d %d %d %d\n", id, (num?num:2), (st?st:7), (mat?mat:9), (pri?pri:5), (own?own:12), (src?src:8), (tm?tm:10); exit } }
  ' "$1" 2>/dev/null
}

cell() {
  # $1 = 行文本, $2 = 列号
  printf '%s\n' "$1" | awk -F'|' -v c="$2" '{gsub(/^[ \t]+|[ \t]+$/,"",$c); print $c}'
}

is_placeholder_cell() {
  case "$1" in
    ""|"["*"]"|"{"*"}"|"待定"|"待补"|"-"*|"—") return 0 ;;
  esac
  return 1
}

ledger_mark_and_count() {
  # $1 = 台账文件, $2 = 批次目录(可空)
  # 检测待办行; 写模式下把「状态列为空/占位符」的行标记为 待分析 / 待抓取
  local lf="$1" bdir="$2"
  local cols id_col num_col st_col mat_col pri_col own_col src_col time_col
  cols=$(ledger_cols "$lf")
  [ -z "$cols" ] && return 0
  read -r id_col num_col st_col mat_col pri_col own_col src_col time_col <<< "$cols"

  local patch="" pending=0 ln row lid lst src ctime mat pri own want
  while IFS= read -r row; do
    ln=${row%%:*}
    row=${row#*:}
    lid=$(cell "$row" "$id_col")
    case "$lid" in ""|"ID") continue ;; esac
    case "$lid" in *["[]"]*) continue ;; esac
    lst=$(cell "$row" "$st_col")
    src=$(cell "$row" "$src_col")
    ctime=$(cell "$row" "$time_col")
    mat=$(cell "$row" "$mat_col")
    pri=$(cell "$row" "$pri_col")
    own=$(cell "$row" "$own_col")
    want=""; reason=""
    case "$mat" in
      *.md)
        if [ ! -e "$ROOT/$mat" ] && { [ -z "$bdir" ] || [ ! -e "$bdir/$mat" ]; }; then
          want=待分析; reason="关联素材不存在(孤儿行): $mat"
        fi
        ;;
    esac
    if [ -z "$want" ]; then
      case "$mat" in
        http://*|https://*)
          if [ "$src" = "external" ] && [ -z "$ctime" ]; then
            want=待抓取; reason="来源 external 但创建时间为空(待抓取)"
          fi
          ;;
      esac
    fi
    if [ -z "$want" ] && { [ "$pri" = "待定" ] || [ "$own" = "[待补]" ]; }; then
      want=待分析; reason="优先级/提出人未落实(待分析): 优先级=$pri 提出人=$own"
    fi
    if [ -n "$want" ]; then
      pending=$((pending+1))
      warn "$(basename -- "$lf") — 台账行 $lid $reason"
    else
      case "$lst" in
        *待分析*|*待抓取*)
          pending=$((pending+1))
          warn "$(basename -- "$lf") — 台账行 $lid 状态为「$lst」(台账哨兵, 待办)"
          ;;
      esac
    fi
    if [ -n "$want" ] && is_placeholder_cell "$lst"; then
      patch="${patch}${ln}:${want},"
    fi
  done < <(grep -n '^|' "$lf" 2>/dev/null)

  if [ -n "$patch" ]; then
    if [ "$CHECK_MODE" -eq 1 ]; then
      err "$(basename -- "$lf") — 台账有未标记的待办行 — 请运行 \`scripts/sync-prd.sh\` 标记"
    else
      local tmp="$lf.tmp" cnt
      cnt=$(printf '%s' "$patch" | tr -cd ',' | wc -c | tr -d ' ')
      awk -F'|' -v OFS='|' -v st="$st_col" -v spec="${patch%,}" '
        BEGIN { n=split(spec, parts, ","); for (i=1;i<=n;i++) { split(parts[i], kv, ":"); map[kv[1]]=kv[2] } }
        { if (NR in map) { $st=" " map[NR] " " } print }
      ' "$lf" > "$tmp" && mv "$tmp" "$lf"
      note "台账标记: $(basename -- "$lf") 标记 ${cnt} 行待办"
    fi
  fi
  PENDING=$((PENDING+pending))
  return 0
}

ledger_register_batch() {
  # $1 = 批次目录, $2 = 批次日期名, $3 = 台账文件
  local bd="$1" bn="$2" lf="$3"
  local mats=() m mbase
  for m in "$bd"*.md; do
    [ -f "$m" ] || continue
    mbase=$(basename -- "$m")
    case "$mbase" in PRDS.md|README.md|_index.md) continue ;; esac
    mats+=("$m")
  done
  if [ ! -f "$lf" ] && [ "${#mats[@]}" -eq 0 ]; then return 0; fi

  if [ ! -f "$lf" ]; then
    if [ "$CHECK_MODE" -eq 1 ]; then
      err "material/$bn/PRDS.md — 批次台账缺失(该批次 ${#mats[@]} 份素材未登记) — 请运行 \`scripts/sync-prd.sh\` 生成"
      return 0
    fi
    {
      printf '# PRD 台账 — material/%s\n\n' "$bn"
      printf '> 由 `scripts/sync-prd.sh` 维护(补登骨架行 / 标记待办行)。字段含义见 `schema/prd-ledger.md`。\n\n'
      printf '## PRD台账\n\n'
      printf '%s\n' "$LEDGER_HEADER"
    } > "$lf" || { err "material/$bn/PRDS.md — 台账写入失败"; return 0; }
    note "台账新建: material/$bn/PRDS.md"
  fi

  if ! grep -qE '^##[[:space:]]+PRD台账[[:space:]]*$' "$lf"; then
    err "material/$bn/PRDS.md — 台账缺少 \`## PRD台账\` 段, 无法登记(请人工补上该段标题)"
    return 0
  fi

  local cols id_col num_col st_col mat_col pri_col own_col src_col time_col
  cols=$(ledger_cols "$lf")
  if [ -z "$cols" ]; then err "material/$bn/PRDS.md — 台账表未找到 \`ID\` 列, 无法登记"; return 0; fi
  read -r id_col num_col st_col mat_col pri_col own_col src_col time_col <<< "$cols"

  local registered seq title new_rows="" nn yyyymmdd cnt last tmp
  registered=$(awk -F'|' -v c="$mat_col" '
    { v=$c; gsub(/^[ \t]+|[ \t]+$/,"",v); gsub(/`/,"",v)
      if (v!="" && v!="关联素材" && v !~ /^-+$/) print v }' "$lf")
  seq=$(awk -F'|' -v c="$num_col" '
    { v=$c; gsub(/^[ \t]+|[ \t]+$/,"",v); if (v ~ /^[0-9]+$/ && v+0>max) max=v+0 } END {print max+0}' "$lf")
  yyyymmdd=$(printf '%s' "$bn" | tr -d '-')

  for m in "${mats[@]+"${mats[@]}"}"; do
    mbase=$(basename -- "$m")
    if printf '%s\n' "$registered" | grep -qF "$mbase"; then continue; fi
    seq=$((seq+1))
    nn=$(printf '%02d' "$seq")
    title=${mbase%.md}
    new_rows="${new_rows}| ${seq} | PRD-${yyyymmdd}-${nn} | ${title} | 待定 |  | 待分析 | local | ${mbase} | ${bn} | ${bn} | [待补] |
"
  done

  if [ -n "$new_rows" ]; then
    cnt=$(printf '%s' "$new_rows" | grep -c '^|')
    if [ "$CHECK_MODE" -eq 1 ]; then
      err "material/$bn/PRDS.md — 台账缺少 ${cnt} 行素材骨架行 — 请运行 \`scripts/sync-prd.sh\` 补登"
    else
      last=$(awk '/^\|/ {n=NR} END {print n+0}' "$lf")
      tmp="$lf.tmp"
      { head -n "$last" "$lf"; printf '%s' "$new_rows"; tail -n +"$((last+1))" "$lf"; } > "$tmp" && mv "$tmp" "$lf"
      note "台账补登: material/$bn/PRDS.md 追加 ${cnt} 行骨架"
    fi
  fi
  return 0
}

if [ -d "$ROOT/material" ]; then
  for bd in "$ROOT"/material/*/; do
    [ -d "$bd" ] || continue
    bn=$(basename -- "$bd")
    printf '%s' "$bn" | grep -Eq "$DATE_RE" || continue
    ledger_register_batch "$bd" "$bn" "$bd/PRDS.md"
  done
  for lf in "$ROOT"/material/*/PRDS.md; do
    [ -f "$lf" ] || continue
    ledger_mark_and_count "$lf" "$(dirname -- "$lf")"
  done
  [ "$PENDING" -eq 0 ] && note "素材区已启用, 台账无待办行"
else
  note "素材层未启用(material/ 不存在), 跳过台账登记与待办检查"
fi
if [ -f "$ROOT/PRDS.md" ]; then ledger_mark_and_count "$ROOT/PRDS.md" ""; fi

# --- 生成统计块 ---
README="$ROOT/README.md"
edges=0; chains=0
if [ -f "$README" ]; then
  edges=$(awk '/^### 关系边表/{f=1;next} /^### /{if(f){exit}} f && /^\| [0-9]+ \|/' "$README" | wc -l)
  chains=$(awk '/^### 演进链索引/{f=1;next} /^### |^## /{if(f){exit}} f && /^\| [A-Za-z]/' "$README" | wc -l)
fi

body=$(
  printf '\n'
  printf '| 层 | 制品 | 数量 | 状态分布 |\n'
  printf '|------|------|:---:|---------|\n'
  printf '| Layer 1 | PRD | %s | %s |\n' "$prd_total" "$prd_dist"
  printf '| Layer 2 | Tech Design | %s | %s |\n' "$td_total" "$td_dist"
  printf '| Layer 3 | Plan | %s | %s |\n' "$plan_total" "$plan_dist"
  printf '| Layer 4 | Test | %s | %s |\n' "$test_total" "$test_dist"
  printf '| 全局 | PRD关联矩阵 | %s 条边 | 演进链 %s 条 |\n' "$edges" "$chains"
)

b_marker='<!-- prd-stats:begin -->'
e_marker='<!-- prd-stats:end -->'
b_line=$(grep -nF "$b_marker" "$README" 2>/dev/null | head -1 | cut -d: -f1)
e_line=$(grep -nF "$e_marker" "$README" 2>/dev/null | head -1 | cut -d: -f1)

if [ -z "$b_line" ] || [ -z "$e_line" ] || [ "$e_line" -le "$b_line" ]; then
  if [ "$CHECK_MODE" -eq 1 ]; then
    err "README.md 缺少 prd-stats 标记块 — 统计块无法核对(违反契约 M12 的唯一写入点约定)"
  else
    warn "统计回写跳过: README.md 未找到 prd-stats 标记"
  fi
else
  old_body=$(sed -n "$((b_line+1)),$((e_line-1))p" "$README" | grep -v '^> 统计时间: ')
  if [ "$old_body" = "$body" ]; then
    ok "规格统计无变化 (PRD $prd_total / TD $td_total / Plan $plan_total / Test $test_total)"
  elif [ "$CHECK_MODE" -eq 1 ]; then
    err "README.md 规格统计块已过期 — 请运行 \`scripts/sync-prd.sh\` 重新生成"
    if [ "$JSON" -eq 0 ]; then
      printf '  --- 当前 ---\n%s\n  --- 期望 ---\n%s\n' "$old_body" "$body" | sed 's/^/  /'
    fi
  else
    now=$(date '+%Y-%m-%d %H:%M')
    tmp="$README.stats.tmp"
    {
      head -n "$b_line" "$README"
      printf '> 统计时间: %s · 由 `scripts/sync-prd.sh` 自动生成\n' "$now"
      printf '%s\n' "$body"
      tail -n +"$e_line" "$README"
    } > "$tmp" && mv "$tmp" "$README"
    ok "统计回写: README.md 规格统计已更新 (PRD $prd_total / TD $td_total / Plan $plan_total / Test $test_total)"
  fi
fi

ERRC=${#ERRORS[@]}
WARNC=${#WARNINGS[@]}
if [ "$ERRC" -gt 0 ]; then
  STATUS="violation"; EXIT=1
elif [ "$PENDING" -gt 0 ]; then
  # 待办行是工作状态, 不是规格违规 —— 但退出码 1 是既定语义(material/README.md)
  STATUS="pending"; EXIT=1
else
  STATUS="pass"; EXIT=0
fi

if [ "$JSON" -eq 1 ]; then
  printf '{"script":"sync-prd.sh","root":"%s","mode":"%s","status":"%s","exit_code":%d,"error_count":%d,"warning_count":%d,"pending_count":%d,"counts":{"prd":%d,"tech_design":%d,"plan":%d,"test":%d,"matrix_edges":%d},"errors":%s,"warnings":%s,"notes":%s}\n' \
    "$(printf '%s' "$ROOT" | json_escape)" \
    "$([ "$CHECK_MODE" -eq 1 ] && echo check || echo write)" \
    "$STATUS" "$EXIT" "$ERRC" "$WARNC" "$PENDING" "$prd_total" "$td_total" "$plan_total" "$test_total" "$edges" \
    "$(json_str_array "${ERRORS[@]+"${ERRORS[@]}"}")" \
    "$(json_str_array "${WARNINGS[@]+"${WARNINGS[@]}"}")" \
    "$(json_str_array "${NOTES[@]+"${NOTES[@]}"}")"
fi
exit $EXIT
