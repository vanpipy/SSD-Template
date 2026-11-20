#!/usr/bin/env bash
# sync-prd.sh — L1 PRD 台账机械登记 + 根 README 统计块再生成（幂等）
#
# 职责:
#   - 扫描 material/{YYYY-MM-DD}/ 素材区，为未登记的素材补「骨架行」到批次台账
#   - 批次台账不存在 → 按 schema/prd-ledger.md 模板创建 (含 `## PRD台账` 段)
#   - 报告哨兵: 待分析 (优先级=待定 或 提出人=[待补]) / 待抓取 (来源=external 且有 URL 但创建时间为空) / 孤儿行
#   - 统计回写: 幂等再生根 README.md 的 `<!-- prd-stats:begin -->` … `<!-- prd-stats:end -->` 块
#
# 边界 (硬约束):
#   - 确定性脚本: 幂等, 无 LLM, **无网络**, 无外部平台依赖
#   - `来源` 枚举只有 3 个: local / external / internal —— 模板**不内置任何抓取器**
#   - 不执行任何 git 写操作
#   - 台账 11 列定义见 schema/prd-ledger.md; 统计块格式见 docs/mechanism-contract.md I-1
#
# 用法 (仓库根目录):
#   ./scripts/sync-prd.sh              # 巡检全部批次
#   ./scripts/sync-prd.sh 2026-08-05   # 只处理指定批次
#
# 退出码:
#   0 = 无待办
#   1 = 存在待分析 / 待抓取 / 孤儿行
#   2 = 调用 / 环境错误

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STORE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$STORE_ROOT" || exit 2

SCHEMA="schema/prd-ledger.md"
LEDGER_NAME="PRDS.md"
BATCH_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
# `来源` 枚举 —— 只有 3 个, 不含任何具体外部平台名
SOURCE_ENUM_RE='^(local|external|internal)$'

BATCH_FILTER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      sed -n '2,23p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*) echo -e "${RED}✗ 未知参数: $1${NC}" >&2; exit 2 ;;
    *) BATCH_FILTER="$1"; shift ;;
  esac
done

# --- 可选层: 无素材区 → 无事可做, 干净跳过 (退出码 0) ---
if [[ ! -d material ]]; then
  echo -e "${YELLOW}○${NC} 未启用素材区 (material/ 不存在), 跳过台账同步"
  echo "---"
  echo -e "${GREEN}✓ PRD台账同步: 无待办${NC}"
  exit 0
fi

total_batches=0
material_total=0
ledger_total=0
added_total=0
pending_analysis_total=0
pending_fetch_total=0
orphan_total=0
errors=0
nonstandard=""

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

# 取台账最大序号 (同前缀同日期)
max_seq() {
  local file="$1" prefix="$2" stamp="$3"
  grep -oE "${prefix}-${stamp}-[0-9]{2}" "$file" 2>/dev/null \
    | sed "s/^${prefix}-${stamp}-//" | sort -n | tail -1
}

# 取文件首个一级标题, 无则用文件名; 表格竖线替换掉以免破坏台账表格
first_title() {
  local t
  t=$(grep -m1 '^# ' "$1" 2>/dev/null | sed 's/^# //' | tr -d '|')
  [[ -n "$t" ]] && printf '%s' "$t" || basename "$1"
}

# 提取 `## PRD台账` 段 (跳过围栏内的同名标题); 无该段时回退全文
ledger_section() {
  local file="$1" body
  body=$(awk '
    /^```/ { fence = !fence; next }
    !fence && /^##[[:space:]]+PRD台账[[:space:]]*$/ { f=1; next }
    !fence && f && /^#{1,6}[[:space:]]/ { exit }
    f { print }
  ' "$file" 2>/dev/null)
  if [[ -z "$body" ]]; then
    cat "$file" 2>/dev/null
    return
  fi
  printf '%s\n' "$body"
}

# 由台账表头推算列号 (awk -F'|' 口径: 首列 '|' 之前是空字段, 故 # = 2, ID = 3)
# 输出: "<no_col> <id_col> <name_col> <prio_col> <state_col> <source_col> <material_col> <create_col> <owner_col>"
ledger_columns() {
  awk -F'|' '
    { no=0; id=0; nm=0; pr=0; st=0; so=0; mt=0; ct=0; ow=0
      for (i=2; i<=NF-1; i++) {
        c=$i; gsub(/^[ \t]+|[ \t]+$/,"",c)
        if (c=="#") no=i
        else if (c=="ID") id=i
        else if (c=="PRD 名称" || c=="名称") nm=i
        else if (c=="优先级") pr=i
        else if (c=="状态") st=i
        else if (c=="来源") so=i
        else if (c=="关联素材") mt=i
        else if (c=="创建时间") ct=i
        else if (c=="提出人") ow=i
      }
      if (id) { printf "%d %d %d %d %d %d %d %d %d\n", (no?no:2), id, (nm?nm:4), (pr?pr:5), (st?st:7), (so?so:8), (mt?mt:9), (ct?ct:10), (ow?ow:12); exit } }
  ' <<< "$1"
}

# 从 schema/prd-ledger.md 取台账表头行 + 分隔行
# 优先取 ```markdown 围栏内的表格; 围栏不存在时回退全文第一个含 ID 列的表头。
schema_ledger_header() {
  local src="$1" body
  body=$(awk '/^```markdown[[:space:]]*$/{f=1;next} /^```[[:space:]]*$/{if(f)exit} f' "$src" 2>/dev/null)
  if ! printf '%s\n' "$body" | grep -qE '\|[[:space:]]*ID[[:space:]]*\|'; then
    body=$(cat "$src" 2>/dev/null)
  fi
  printf '%s\n' "$body" | awk '
    /\|[ \t]*ID[ \t]*\|/ { if (!got) { print; got=1; want=1; next } }
    want && /^\|[ \t]*:?-+/ { print; exit }
  '
}

# 从一行台账记录取第 c 列 (awk 口径, 去空白)
col() {
  local row="$1" c="$2"
  awk -F'|' -v c="$c" '{gsub(/^[ \t]+|[ \t]+$/,"",$c); print $c}' <<< "$row"
}

# --- 在台账表的最后一行之后插入一行 (而不是追加到文件末尾) ---
# 这样台账文件后面即使还有其他小节, 新行仍落在表内。
append_ledger_row() {
  local file="$1" row="$2" last tmp
  last=$(awk '
    /^```/ { fence = !fence; next }
    !fence && /^##[[:space:]]+PRD台账[[:space:]]*$/ { f=1; next }
    !fence && f && /^#{1,6}[[:space:]]/ { exit }
    f && /^\|/ { last=NR }
    END { print last+0 }
  ' "$file")
  if [[ "$last" -le 0 ]]; then
    printf '%s\n' "$row" >> "$file"
    return 0
  fi
  tmp="${file}.row.tmp"
  awk -v last="$last" -v row="$row" 'NR==last { print; print row; next } { print }' "$file" > "$tmp" \
    && mv "$tmp" "$file"
  return 0
}

# --- 按模板创建批次台账文件 ---
create_ledger() {
  local file="$1" bname="$2" yyyymmdd="$3" header
  header=$(schema_ledger_header "$SCHEMA")
  if [[ -z "$header" ]]; then
    return 1
  fi
  {
    echo "# PRDS: $bname"
    echo ""
    echo "> 批次统一入口: 素材 → PRD 台账。字段顺序与列名见 \`schema/prd-ledger.md\`。"
    echo ""
    echo "## PRD台账"
    echo ""
    echo "> 批次素材入口。行状态在收敛后回填, 创建/更新时间由登记事件回填, 其余列不得修改。"
    echo ""
    printf '%s\n' "$header"
  } > "$file"
  return 0
}

for batch in material/*/; do
  [[ -d "$batch" ]] || continue
  bname=$(basename "$batch")

  # 非规范日期目录 → 只点名, 交给 check-naming.sh
  if ! [[ "$bname" =~ $BATCH_RE ]]; then
    nonstandard="$nonstandard $bname"
    continue
  fi

  # 只处理指定批次
  if [[ -n "$BATCH_FILTER" && "$bname" != "$BATCH_FILTER" ]]; then
    continue
  fi

  total_batches=$((total_batches+1))
  req_file="${batch}${LEDGER_NAME}"
  yyyymmdd=${bname//-/}

  # 收集素材文件 (排除台账自身)
  mat_files=()
  while IFS= read -r f; do
    mat_files+=("$f")
  done < <(find "$batch" -maxdepth 1 -type f -name '*.md' ! -name "$LEDGER_NAME" 2>/dev/null | sort)

  material_total=$((material_total + ${#mat_files[@]}))

  # 无素材且无台账 → 无事可做
  if [[ ${#mat_files[@]} -eq 0 && ! -f "$req_file" ]]; then
    continue
  fi

  # 台账不存在 → 按模板创建
  if [[ ! -f "$req_file" ]]; then
    if [[ -f "$SCHEMA" ]]; then
      if create_ledger "$req_file" "$bname" "$yyyymmdd"; then
        echo -e "${YELLOW}○${NC} $bname — 按模板创建 $LEDGER_NAME (含 \`## PRD台账\` 段)"
      else
        echo -e "${RED}✗${NC} $bname — 无法从 $SCHEMA 提取台账表头, 无法创建 $LEDGER_NAME" >&2
        exit 2
      fi
    else
      echo -e "${RED}✗${NC} $bname — 缺少 $SCHEMA, 无法创建 $LEDGER_NAME" >&2
      exit 2
    fi
  fi

  ledger_body=$(ledger_section "$req_file")
  [[ -z "$(grep -E '^\|' <<< "$ledger_body")" ]] && continue

  cols=$(ledger_columns "$ledger_body")
  if [[ -z "$cols" ]]; then
    echo -e "${YELLOW}⚠${NC} $bname — 台账表未找到 \`ID\` 列, 跳过补登记与哨兵检查"
    continue
  fi
  read -r no_col id_col name_col prio_col state_col source_col material_col create_col owner_col <<< "$cols"
  no_col="${no_col:-2}"; id_col="${id_col:-3}"; name_col="${name_col:-4}"; prio_col="${prio_col:-5}"
  state_col="${state_col:-7}"; source_col="${source_col:-8}"; material_col="${material_col:-9}"
  create_col="${create_col:-10}"; owner_col="${owner_col:-12}"

  # --- 逐素材核对登记 (台账只增) ---
  for f in "${mat_files[@]}"; do
    fname=$(basename "$f")
    if grep -qF "$fname" <<< "$ledger_body"; then
      continue
    fi
    seq=$(max_seq "$req_file" "PRD" "$yyyymmdd")
    seq=$(printf '%02d' $(( ${seq:-0} + 1 )))
    title=$(first_title "$f")
    # 骨架行: 来源=local (模板不内置任何抓取器, 外部来源由项目自定义 skill 登记)
    # 列序: # | ID | PRD 名称 | 优先级 | 验收要点 | 状态 | 来源 | 关联素材 | 创建时间 | 更新时间 | 提出人
    skeleton=$(printf '| %s | PRD-%s-%s | %s | 待定 |  | 待分析 | local | %s | %s | %s | [待补] |' \
      "$seq" "$yyyymmdd" "$seq" "$title" "$fname" "$(date +%F)" "$(date +%F)")
    append_ledger_row "$req_file" "$skeleton"
    added_total=$((added_total+1))
    echo -e "${YELLOW}+${NC} $bname — 补登记骨架行 PRD-$yyyymmdd-$seq ← $fname (local)"
    ledger_body=$(ledger_section "$req_file")
  done

  ledger_body=$(ledger_section "$req_file")

  # --- 哨兵检查 ---
  while IFS= read -r row; do
    [[ -z "$row" ]] && continue
    lid=$(col "$row" "$id_col")
    case "$lid" in
      ""|"ID") continue ;;
    esac
    [[ "$lid" =~ ^:?-+:?$ ]] && continue
    [[ "$lid" == *"["* || "$lid" == *"]"* ]] && continue

    lsource=$(col "$row" "$source_col")
    lmaterial=$(col "$row" "$material_col")
    lcreate=$(col "$row" "$create_col")
    lprio=$(col "$row" "$prio_col")
    lowner=$(col "$row" "$owner_col")

    ledger_total=$((ledger_total+1))

    # 来源枚举校验 (只有 local / external / internal)
    if [[ -n "$lsource" && ! "$lsource" =~ $SOURCE_ENUM_RE ]]; then
      echo -e "${RED}✗${NC} $bname — $lid 来源非法: '$lsource' (期望 local / external / internal)"
      errors=$((errors+1))
    fi

    # 哨兵 1: 待分析 (优先级=待定 或 提出人=[待补])
    if [[ "$lprio" == "待定" || "$lowner" == "[待补]" ]]; then
      pending_analysis_total=$((pending_analysis_total+1))
      echo -e "${YELLOW}⚠${NC} $bname — 待分析: $lid (优先级=$lprio, 提出人=$lowner)"
    fi

    # 哨兵 2: 待抓取 (来源=external 且有 URL 但 创建时间为空)
    if [[ "$lsource" == "external" && "$lmaterial" == http* && -z "$lcreate" ]]; then
      pending_fetch_total=$((pending_fetch_total+1))
      echo -e "${YELLOW}⚠${NC} $bname — 待抓取: $lid ($lmaterial)"
    fi

    # 孤儿行: 关联素材指向的仓内 .md 文件不存在 (URL 不查)
    # 解析顺序: 批次目录相对路径 → 仓根相对路径 → 台账文件所在目录相对路径
    ref="${lmaterial##*→}"
    ref="$(trim "$ref")"
    if [[ "$ref" == *.md && "$ref" != http* ]]; then
      if [[ ! -f "${batch}${ref}" && ! -f "$ref" && ! -f "$(dirname "$req_file")/${ref}" ]]; then
        orphan_total=$((orphan_total+1))
        echo -e "${RED}✗${NC} $bname — 孤儿行: $lid 关联素材不存在: $ref"
      fi
    fi
  done < <(grep -E '^\|' <<< "$ledger_body")
done

# --- 根 README 统计块回写 (标记之间幂等再生) ---
update_readme_stats() {
  local readme="README.md"
  [[ -f "$readme" ]] || { echo -e "${YELLOW}⚠ 统计回写跳过: README.md 不存在${NC}"; return 0; }

  local b_marker='<!-- prd-stats:begin -->'
  local e_marker='<!-- prd-stats:end -->'
  local b_line e_line
  b_line=$(grep -nF "$b_marker" "$readme" | head -1 | cut -d: -f1)
  e_line=$(grep -nF "$e_marker" "$readme" | head -1 | cut -d: -f1)
  if [[ -z "${b_line:-}" || -z "${e_line:-}" || "$e_line" -le "$b_line" ]]; then
    echo -e "${YELLOW}⚠ 统计回写跳过: README.md 未找到 prd-stats 标记${NC}"
    return 0
  fi

  # --- 各层计数 ---
  # Layer 1: PRD — prd/{date}/*.md 的 `**状态**` 行
  local prd_total=0 prd_ready=0 prd_impl=0 prd_dep=0 prd_other=0 f st
  for f in prd/*/*.md; do
    [[ -f "$f" ]] || continue
    prd_total=$((prd_total+1))
    st=$(grep -m1 -E '^[[:space:]]*>?[[:space:]]*\*\*状态\*\*' "$f" 2>/dev/null || true)
    if [[ "$st" == *Deprecated* ]]; then prd_dep=$((prd_dep+1))
    elif [[ "$st" == *Implemented* ]]; then prd_impl=$((prd_impl+1))
    elif [[ "$st" == *Ready* ]]; then prd_ready=$((prd_ready+1))
    else prd_other=$((prd_other+1)); fi
  done

  # Layer 2: Tech Design — tech_design/{date}-{topic}/ 内首个 `**状态**` 行
  local td_total=0 td_ready=0 td_impl=0 td_dep=0 td_other=0 d
  for d in tech_design/*/; do
    [[ -d "$d" ]] || continue
    td_total=$((td_total+1))
    st=$(grep -h -m1 -E '^[[:space:]]*>?[[:space:]]*\*\*状态\*\*' "$d"*.md 2>/dev/null | head -1 || true)
    if [[ "$st" == *Deprecated* ]]; then td_dep=$((td_dep+1))
    elif [[ "$st" == *Implemented* ]]; then td_impl=$((td_impl+1))
    elif [[ "$st" == *Ready* ]]; then td_ready=$((td_ready+1))
    else td_other=$((td_other+1)); fi
  done

  # Layer 3: Plan — plan/{date}-{topic}/ 内首个 `**状态**` 行
  local plan_total=0 plan_ready=0 plan_impl=0 plan_dep=0 plan_other=0
  for d in plan/*/; do
    [[ -d "$d" ]] || continue
    plan_total=$((plan_total+1))
    st=$(grep -h -m1 -E '^[[:space:]]*>?[[:space:]]*\*\*状态\*\*' "$d"*.md 2>/dev/null | head -1 || true)
    if [[ "$st" == *Implemented* ]]; then plan_impl=$((plan_impl+1))
    elif [[ "$st" == *Ready* ]]; then plan_ready=$((plan_ready+1))
    elif [[ "$st" == *Deprecated* ]]; then plan_dep=$((plan_dep+1))
    else plan_other=$((plan_other+1)); fi
  done

  # Layer 4: Test — test_cases/{date}/*.md 元信息表「状态」行 (排除 *-key-points.md)
  local test_total=0 test_draft=0 test_ready=0 test_impl=0 test_dep=0 test_other=0 f2 st2
  while IFS= read -r f2; do
    [[ -f "$f2" ]] || continue
    test_total=$((test_total+1))
    st2=$(grep -m1 -E '^\|[[:space:]]*状态[[:space:]]*\|' "$f2" 2>/dev/null || true)
    if [[ "$st2" == *Implemented* ]]; then test_impl=$((test_impl+1))
    elif [[ "$st2" == *Ready* ]]; then test_ready=$((test_ready+1))
    elif [[ "$st2" == *Deprecated* ]]; then test_dep=$((test_dep+1))
    elif [[ "$st2" == *Draft* ]]; then test_draft=$((test_draft+1))
    else test_other=$((test_other+1)); fi
  done < <(find test_cases -mindepth 2 -maxdepth 2 -type f -name '*.md' ! -name '*-key-points.md' 2>/dev/null | sort)

  # 全局: README 关系边表边数 + 演进链条数
  local edges chains
  edges=$(awk '/^### 关系边表/{f=1;next} /^### /{if(f){exit}} f && /^\| [0-9]+ \|/' "$readme" | wc -l)
  chains=$(awk '/^### 演进链索引/{f=1;next} /^### |^## /{if(f){exit}} f && /^\| [A-Za-z]/' "$readme" | wc -l)

  # --- 状态分布文案 (计数为 0 的项整项省略) ---
  local prd_dist="" td_dist="" plan_dist="" test_dist=""
  [[ $prd_ready -gt 0 ]] && prd_dist="Ready $prd_ready"
  [[ $prd_impl  -gt 0 ]] && prd_dist="${prd_dist:+$prd_dist · }Implemented $prd_impl"
  [[ $prd_dep   -gt 0 ]] && prd_dist="${prd_dist:+$prd_dist · }Deprecated $prd_dep"
  [[ $prd_other -gt 0 ]] && prd_dist="${prd_dist:+$prd_dist · }其他 $prd_other"

  [[ $td_ready -gt 0 ]] && td_dist="Ready $td_ready"
  [[ $td_impl  -gt 0 ]] && td_dist="${td_dist:+$td_dist · }Implemented $td_impl"
  [[ $td_dep   -gt 0 ]] && td_dist="${td_dist:+$td_dist · }Deprecated $td_dep"
  [[ $td_other -gt 0 ]] && td_dist="${td_dist:+$td_dist · }其他 $td_other"

  [[ $plan_ready -gt 0 ]] && plan_dist="Ready $plan_ready"
  [[ $plan_impl  -gt 0 ]] && plan_dist="${plan_dist:+$plan_dist · }Implemented $plan_impl"
  [[ $plan_dep   -gt 0 ]] && plan_dist="${plan_dist:+$plan_dist · }Deprecated $plan_dep"
  [[ $plan_other -gt 0 ]] && plan_dist="${plan_dist:+$plan_dist · }其他 $plan_other"

  [[ $test_draft -gt 0 ]] && test_dist="Draft $test_draft"
  [[ $test_ready -gt 0 ]] && test_dist="${test_dist:+$test_dist · }Ready $test_ready"
  [[ $test_impl  -gt 0 ]] && test_dist="${test_dist:+$test_dist · }Implemented $test_impl"
  [[ $test_dep   -gt 0 ]] && test_dist="${test_dist:+$test_dist · }Deprecated $test_dep"
  [[ $test_other -gt 0 ]] && test_dist="${test_dist:+$test_dist · }其他 $test_other"

  # --- 生成新块体 (不含时间戳行) ---
  local body tmp
  body=$(
    echo ""
    echo "| 层 | 制品 | 数量 | 状态分布 |"
    echo "|------|------|:---:|---------|"
    echo "| Layer 1 | PRD | $prd_total | $prd_dist |"
    echo "| Layer 2 | Tech Design | $td_total | $td_dist |"
    echo "| Layer 3 | Plan | $plan_total | $plan_dist |"
    echo "| Layer 4 | Test | $test_total | $test_dist |"
    echo "| 全局 | PRD关联矩阵 | $edges 条边 | 演进链 $chains 条 |"
  )

  # --- 幂等: 去掉旧块的时间戳行后与新块体比对, 相同则不写文件 (保留原时间戳) ---
  local old_body
  old_body=$(sed -n "$((b_line+1)),$((e_line-1))p" "$readme" | grep -v '^> 统计时间: ' || true)
  if [[ "$old_body" == "$body" ]]; then
    echo -e "${GREEN}✓${NC} 统计回写: README.md 规格统计无变化, 保持原时间戳"
    return 0
  fi

  local now
  now=$(date '+%Y-%m-%d %H:%M')
  tmp="${readme}.stats.tmp"
  {
    head -n "$b_line" "$readme"
    echo "> 统计时间: ${now} · 由 \`scripts/sync-prd.sh\` 自动生成"
    echo "$body"
    tail -n +"$e_line" "$readme"
  } > "$tmp" && mv "$tmp" "$readme"

  echo -e "${GREEN}✓${NC} 统计回写: README.md 规格统计已更新 (PRD $prd_total / TD $td_total / Plan $plan_total / Test $test_total)"
  return 0
}

update_readme_stats

# --- 汇总 ---
echo "---"
echo "批次总数: $total_batches"
echo "素材文件: $material_total | 台账行数: $ledger_total | 本次补登记: $added_total"
echo "待分析行: $pending_analysis_total | 待抓取行: $pending_fetch_total | 孤儿行: $orphan_total"
if [[ -n "$nonstandard" ]]; then
  echo -e "${YELLOW}⚠ 非规范目录 (命名问题归 check-naming.sh 管, 此处仅点名):${nonstandard}${NC}"
fi

if [[ $pending_analysis_total -gt 0 || $pending_fetch_total -gt 0 || $orphan_total -gt 0 ]]; then
  echo -e "${YELLOW}○ PRD台账同步: 存在待办 (待分析/待抓取/孤儿行), 退出码 1${NC}"
  exit 1
fi

if [[ $errors -gt 0 ]]; then
  echo -e "${RED}✗ PRD台账同步: $errors 项违规, 退出码 1${NC}"
  exit 1
fi

echo -e "${GREEN}✓ PRD台账同步: 无待办${NC}"
exit 0
