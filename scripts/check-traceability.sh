#!/usr/bin/env bash
# check-traceability.sh — 校验跨文件引用追溯完整性
#
# 检查项:
#   T1. PRD 场景 → Tech Design 场景映射覆盖 (每个 Given/When/Then 至少 1 行映射; v3: scenario-mapping.md, v4: README.md `## 场景映射` 段)
#   T2. Plan V-{n} 引用闭环 (每个 V 在"验证用例"段有定义)
#   T3. Plan KD-{n} 引用闭环 (每个 KD 在 TD 中存在: v4 ards.md / 存量 v3 decisions.md)
#   T4. Plan Change #N ↔ V-{n} 双向引用闭环 (v3 Plan 严格: 每个 Change 至少 1 个 V,每个 V 至少 1 处 Change 关联; v2 仅查 Change 标题)
#   T5. 引用类型一致性 (引用类型只有 KD / V / FR / SYS / MOD 5 种, 已简化为 no-op)
#   T6. 台账 ID 唯一性 + ID 格式 (批次台账文件含 `## PRD台账` 段才校验; 见 schema/prd-ledger.md)
#   T7. README 关系边表节点标识存在性 + 关系类型枚举 (8 类, 见 schema/prd-matrix.md)
#   T8. supersede 边 ↔ Deprecated 状态一致性 (双向)
#   T9. test_cases 元信息上游引用存在性 (来源/Tech Design/Plan 行中的仓内路径, test_cases 目录存在才校验)
#   T10. README 用例登记表 TEST-ID 唯一性 + 登记行路径存在性
#   T11. Plan 元信息「参考 Test Cases」引用存在性 (可选行, 填了才校验)
#   T12. 跨层级联一致性 (父 PRD/TD Deprecated → 下游 TD/Plan 应同步降级; 通用项目级 state machine 一致性, 与台账 / README 矩阵无关)
#   T13. 新 PRD 关系边评估提示 (仅信息性, 不计违规)
#
# 条件启用 (可选层, 缺失即跳过, 模板自身零实例 → 零违规):
#   T6  台账文件: material/{date}/*.md 或 prd/{date}/*.md 中含 `## PRD台账` 段的批次台账
#   T7/T8/T13  关联矩阵: 根 README.md 的 `## PRD关联矩阵` → `### 关系边表`
#   T10  用例登记表: 根 README.md 中含 TEST-ID 的表格行
#
# 实现块标记统一置于行首 (`# --- T{n}`), 便于机器扫描「头部承诺 → 实现兑现」的覆盖度。
#
# 用法:
#   ./scripts/check-traceability.sh
#
# 退出码: 0=通过 1=违规 2=调用错误

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

# 允许的引用类型(SC 已被废弃,见 G5 修复)
VALID_REFS='^(KD|V|FR|SYS|MOD)$'

errors=0
checked=0

# --- T5: 引用类型一致性扫描（已简化为 no-op）
# 原 T5: 检测任何 [A-Z]+-[0-9]+ 形式,前缀不在白名单报错
# 问题: 会误报业务值（AES-256 加密算法 / SHA-256 哈希 / EAN-13 条码标准等）
# 修复: 只扫描白名单引用类型（KD/V/FR/SYS/MOD）,不主动扫描非白名单前缀
#       这意味着 T5 变成 no-op（T1-T4 已覆盖引用闭环检查）
# 未来如需扫描,需加上下文判断（如只在 markdown 链接 / 表格 / 引用块中扫描）
# 优化: 移除逐行读取（对 50+ 文件极慢），改为文件计数
file_count=$(find prd tech_design plan -type f -name "*.md" 2>/dev/null | wc -l)

# --- Plan 侧引用闭环 (T3 KD / T2 V / T4 Change↔V) ---
while IFS= read -r plan_dir; do
  # 约定: plan/{date}-{topic}/{topic}.md — 文件名不含日期前缀
  dir_base=$(basename "$plan_dir")
  topic_name="${dir_base#[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-}"
  plan_file="$plan_dir/${topic_name}.md"
  [[ -f "$plan_file" ]] || continue

  checked=$((checked+1))

  # 找到 Plan 引用的 Tech Design (匹配 ../ 或 ../../ 开头的 tech_design 路径)
  td_link=$(grep -oE '\.\./\.\.?/tech_design/[a-zA-Z0-9/_-]+' "$plan_file" | head -1 || true)
  if [[ -z "$td_link" ]]; then
    echo -e "${RED}✗${NC} $plan_file — 未引用 Tech Design (../tech_design/...)"
    errors=$((errors+1))
    continue
  fi

  td_path="$(dirname "$plan_file")/$td_link"
  [[ ! -d "$td_path" ]] && td_path="${td_path%/*}"

# --- T3: KD 闭环 — v4 TD 锚点在 ards.md, 存量 v3 在 decisions.md (按存在性择一) ---
  kd_src=""
  if [[ -f "$td_path/ards.md" ]]; then
    kd_src="$td_path/ards.md"
  elif [[ -f "$td_path/decisions.md" ]]; then
    kd_src="$td_path/decisions.md"
  fi
  if [[ -n "$kd_src" ]]; then
    while IFS= read -r kd; do
      [[ -z "$kd" ]] && continue
      if ! grep -qE "^## ${kd}:" "$kd_src"; then
        echo -e "${RED}✗${NC} $plan_file — 引用 ${kd} 但 $kd_src 中不存在"
        errors=$((errors+1))
      fi
    done < <(grep -oE 'KD-[0-9]+' "$plan_file" | sort -u)
  fi

# --- T2: V 闭环 — Plan 引用的 V-{n} 必须在"验证用例"段定义 ---
  # lookbehind 排除 PV-001 等日志码的子串误匹配 (2026-08-07 pay-voice 演练发现)
  plan_vs=$(grep -oP '(?<![A-Za-z])V-[0-9]+' "$plan_file" | sort -u)
  while IFS= read -r v; do
    [[ -z "$v" ]] && continue
    if ! grep -qE "^### ${v}:" "$plan_file"; then
      echo -e "${RED}✗${NC} $plan_file — 引用 ${v} 但未在 \`## 验证用例\` 段定义"
      errors=$((errors+1))
    fi
  done <<< "$plan_vs"

# --- T4: Change ↔ V 双向引用闭环 — 支持 §1.5 多仓分组 (####) 和单仓 (###) ---
  #     v3 Plan (有 ## 变更索引): 严格双向
  #       正向: 每个 Change #N 段至少引用 1 个 V-{n}
  #       反向: 每个已定义 ### V-n: 至少被 1 处 Change 关联证据覆盖
  #       证据来源: ① Change 段正文 ② 变更索引表(含 V-a..V-b 范围展开)
  #                 ③ 跨文件引用对账行 ④ V 定义段正文自引 Change #N
  #     v2 Plan (无变更索引, V 编号不统一): 仅查 Change 标题存在性
  if grep -qE '^## 变更索引' "$plan_file"; then
    # 正向: 逐 Change 段提取,段内无 V-{n} 即报
    chg_no_v=$(awk '
      /^### Change #|^#### Change #/ { if (in_chg && !found) print prev; in_chg=1; prev=$0; found=0; next }
      /^##/                          { if (in_chg && !found) print prev; in_chg=0 }
      in_chg && /(^|[^A-Za-z])V-[0-9]+/ { found=1 }
      END                            { if (in_chg && !found) print prev }
    ' "$plan_file")
    if [[ -n "$chg_no_v" ]]; then
      while IFS= read -r chg; do
        [[ -z "$chg" ]] && continue
        echo -e "${RED}✗${NC} $plan_file — ${chg} 未引用任何 V-{n} (Change 段应有 \`**验证**: V-{n}\`)"
        errors=$((errors+1))
      done <<< "$chg_no_v"
    fi

    # 反向: 引用池 = ① Change 段正文 + ③ 对账行 + ② 变更索引表
    change_bodies=$(awk '/^### Change #|^#### Change #/{f=1} /^## /{f=0} f' "$plan_file")
    index_rows=$(awk '/^## 变更索引/{f=1; next} /^## /{f=0} f && /^\|/' "$plan_file")
    recon_rows=$(grep -E '^\| *验证用例 *\|' "$plan_file" || true)
    ref_pool=$(printf '%s\n%s\n%s\n' "$change_bodies" "$recon_rows" "$index_rows" | grep -oP '(?<![A-Za-z])V-[0-9]+' | sort -u)
    # 范围记法展开 (V-a..V-b)
    range_pool=$(printf '%s\n%s\n' "$change_bodies" "$index_rows" \
      | grep -oP '(?<![A-Za-z])V-[0-9]+\.\.V-[0-9]+' \
      | while IFS= read -r rng; do
          a="${rng#V-}"; a="${a%%..*}"; b="${rng##*V-}"
          i="$a"
          while [[ "$i" -le "$b" ]]; do echo "V-$i"; i=$((i+1)); done
        done | sort -u)
    defined_vs=$(grep -oE '^### V-[0-9]+:' "$plan_file" | grep -oE 'V-[0-9]+' | sort -u)
    for v in $defined_vs; do
      covered=0
      if printf '%s\n%s\n' "$ref_pool" "$range_pool" | grep -qx "$v"; then
        covered=1
      else
        # 证据④: V 定义段正文自引 Change #N
        if awk -v h="### $v:" 'index($0,h)==1{p=1; next} p && /^### /{p=0} p' "$plan_file" | grep -qE 'Change #[0-9]+'; then
          covered=1
        fi
      fi
      if [[ $covered -eq 0 ]]; then
        echo -e "${RED}✗${NC} $plan_file — ${v} 已定义但无 Change 关联 (Change 段/变更索引/对账行/V 段自引均未覆盖)"
        errors=$((errors+1))
      fi
    done
  else
    plan_changes=$(grep -cE '^#{3,4} Change #[0-9]+:' "$plan_file" || true)
    if [[ $plan_changes -eq 0 ]]; then
      echo -e "${RED}✗${NC} $plan_file — 缺少 \`### Change #\` 或 \`#### Change #\` 段"
      errors=$((errors+1))
    fi
  fi

done < <(find plan -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

# --- T1: PRD 场景覆盖 (存量 v3: scenario-mapping.md; v4: README.md `## 场景映射` 段) ---
while IFS= read -r td_dir; do
  prd_link=$(grep -oE '\.\./\.\./prd/[a-zA-Z0-9/_-]+\.md' "$td_dir/README.md" 2>/dev/null | head -1 || true)
  [[ -z "$prd_link" ]] && continue

  prd_path="$(cd "$td_dir" && cd "$(dirname "$prd_link")" && pwd)/$(basename "$prd_link")"
  [[ -f "$prd_path" ]] || continue

  # 映射表数据源: 存量 scenario-mapping.md 优先; v4 (有 ards.md) 落入 README.md 场景映射段
  mapping_src=""
  if [[ -f "$td_dir/scenario-mapping.md" ]]; then
    mapping_src="$td_dir/scenario-mapping.md"
  elif [[ -f "$td_dir/ards.md" ]]; then
    mapping_src="$td_dir/README.md"
  fi
  [[ -z "$mapping_src" ]] && continue

  checked=$((checked+1))

  # PRD 中每个场景名(以 ### 场景: 开头)
  prd_scenarios=$(grep -oE '### 场景:[^[:space:]]+' "$prd_path" 2>/dev/null | sed 's/### 场景://' || true)

  # 简化检查: 映射表行数至少要 ≥ PRD 场景数 (6 列格式)
  # 注: grep -c 在无匹配返回 "0\n" 且退出码 1,触发 `|| echo 0` 会拼出 "0\n0\n" 让 [[ ]] 报算术错误.
  # 修复: 用 grep ... | wc -l 替代 (始终输出单行数字 + 退出码 0),再用 tr 去换行保证单行变量.
  if [[ "$mapping_src" == */README.md ]]; then
    # v4: 仅统计 `## 场景映射` 段内的 6 列表格行, 避免误数 README 其他表格
    mapping_rows=$(awk '/^## 场景映射/{f=1; next} /^## /{f=0} f' "$mapping_src" \
      | grep -cE '^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|$' 2>/dev/null | tr -d '\n')
    mapping_rows=${mapping_rows:-0}
  else
    mapping_rows=$(grep -cE '^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|$' "$mapping_src" 2>/dev/null | tr -d '\n')
    mapping_rows=${mapping_rows:-0}
  fi
  prd_count=$(grep -cE '^### 场景:' "$prd_path" 2>/dev/null | tr -d '\n')
  prd_count=${prd_count:-0}

  if [[ $mapping_rows -lt $prd_count ]]; then
    echo -e "${YELLOW}⚠${NC} $mapping_src — 场景映射表格行数 ($mapping_rows) 少于 PRD 场景数 ($prd_count)"
    errors=$((errors+1))
  fi
done < <(find tech_design -mindepth 1 -maxdepth 1 -type d 2>/dev/null)


# --- T9: test_cases 元信息上游引用存在性 (test_cases 目录存在才校验) ---
# 仓外来源无 prd/|material/|tech_design/|plan/ 前缀, 不校验, 靠备注说明
if [[ -d test_cases ]]; then
  while IFS= read -r tf; do
    checked=$((checked+1))
    refs=$(awk -F'|' '/^\|/ {key=$2; gsub(/^[ \t]+|[ \t]+$/,"",key); if (key=="来源"||key=="Tech Design"||key=="Plan") print $3}' "$tf" | grep -oE '`[^`]+`' | tr -d '`' || true)
    while IFS= read -r r; do
      [[ -z "$r" ]] && continue
      case "$r" in
        prd/*|material/*|tech_design/*|plan/*)
          if [[ ! -e "$r" ]]; then
            echo -e "${RED}✗${NC} $tf — 元信息上游引用不存在: $r"
            errors=$((errors+1))
          fi ;;
      esac
    done <<< "$refs"
  done < <(find test_cases -mindepth 2 -maxdepth 2 -type f -name '*.md' ! -name '*-key-points.md' 2>/dev/null | sort)
fi


# --- T11: Plan↔test_cases 比照 (test_cases 目录存在才校验, 可选行) ---
# Plan 元信息「参考 Test Cases」行反引号仓内路径必须存在 (可选行, 填了才校验)
while IFS= read -r pf; do
  refs=$(grep -E '^> ?\*\*参考 Test Cases\*\*' "$pf" 2>/dev/null | grep -oE '`[^`]+`' | tr -d '`' || true)
  while IFS= read -r r; do
    [[ -z "$r" ]] && continue
    case "$r" in
      test_cases/*)
        if [[ -d test_cases && ! -f "$r" ]]; then
          echo -e "${RED}✗${NC} $pf — 参考 Test Cases 引用不存在: $r"
          errors=$((errors+1))
        fi ;;
    esac
  done <<< "$refs"
done < <(find plan -mindepth 2 -maxdepth 2 -type f -name '*.md' 2>/dev/null | sort)


# --- T12: 跨层级联一致性 (父 PRD/TD Deprecated → 下游 TD/Plan 应同步降级) ---
# 状态提取: 读文件首 30 行匹配 `> **状态**: Draft|Ready|Implemented|Deprecated` 模式
# 通用项目级校验: 与 PRDS.md 台账 / README 关联矩阵无关, 任何用 state machine 的项目都适用
get_state() {
  local f="$1"
  awk '/^> ?\*\*状态\*\*:?[ \t]*(Draft|Ready|Implemented|Deprecated)/ {
    for (i=1; i<=NF; i++) if ($i ~ /^(Draft|Ready|Implemented|Deprecated)([|[:space:]]|$)/) { print $i; exit }
  }' "$f"
}

# 路径规整: 仓内相对路径 (统一锚点, 避免相对/绝对混用导致 lookup miss)
to_repo_rel() {
  local abs="$1"
  if command -v realpath >/dev/null 2>&1; then
    realpath --relative-to=. "$abs" 2>/dev/null || echo "$abs"
  else
    local pwd_prefix
    pwd_prefix="$(pwd)/"
    if [[ "$abs" == "$pwd_prefix"* ]]; then
      echo "${abs#$pwd_prefix}"
    else
      echo "$abs"
    fi
  fi
}

# 缓存: 路径 → 状态 (避免重复 IO)
declare -A prd_states
declare -A td_states
while IFS= read -r pf; do
  rel="${pf#./}"
  prd_states["$rel"]="$(get_state "$pf")"
done < <(find prd -mindepth 2 -maxdepth 2 -type f -name '*.md' 2>/dev/null | sort)
while IFS= read -r td_dir; do
  rel="${td_dir#./}"
  tf="$td_dir/README.md"
  td_states["$rel"]="$(get_state "$tf" 2>/dev/null)"
done < <(find tech_design -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

# 检查 TD: 父 PRD Deprecated → TD 应同步
while IFS= read -r td_dir; do
  tf="$td_dir/README.md"
  [[ -f "$tf" ]] || continue
  prd_link=$(grep -oE '\.\./\.\./prd/[a-zA-Z0-9/_-]+\.md' "$tf" 2>/dev/null | head -1 || true)
  [[ -z "$prd_link" ]] && continue
  prd_abs="$(cd "$td_dir" && cd "$(dirname "$prd_link")" 2>/dev/null && pwd)/$(basename "$prd_link")" || continue
  prd_rel="$(to_repo_rel "$prd_abs")"
  parent_state="${prd_states[$prd_rel]:-}"
  self_state="$(get_state "$tf")"
  if [[ "$parent_state" == "Deprecated" && "$self_state" != "Deprecated" ]]; then
    echo -e "${YELLOW}⚠${NC} $tf — 父 PRD 已 Deprecated ($prd_rel), TD 未同步降级 (当前: ${self_state:-未声明})"
    errors=$((errors+1))
  fi
done < <(find tech_design -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)

# 检查 Plan: 父 PRD 或父 TD Deprecated → Plan 应同步
while IFS= read -r plan_dir; do
  dir_base=$(basename "$plan_dir")
  topic_name="${dir_base#[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-}"
  pf="$plan_dir/${topic_name}.md"
  [[ -f "$pf" ]] || continue
  self_state="$(get_state "$pf")"

  # 父 PRD
  prd_link=$(grep -oE '\.\./\.\./prd/[a-zA-Z0-9/_-]+\.md' "$pf" 2>/dev/null | head -1 || true)
  if [[ -n "$prd_link" ]]; then
    prd_abs="$(cd "$plan_dir" && cd "$(dirname "$prd_link")" 2>/dev/null && pwd)/$(basename "$prd_link")" || true
    if [[ -n "${prd_abs:-}" ]]; then
      prd_rel="$(to_repo_rel "$prd_abs")"
      parent_state="${prd_states[$prd_rel]:-}"
      if [[ "$parent_state" == "Deprecated" && "$self_state" != "Deprecated" ]]; then
        echo -e "${YELLOW}⚠${NC} $pf — 父 PRD 已 Deprecated ($prd_rel), Plan 未同步降级 (当前: ${self_state:-未声明})"
        errors=$((errors+1))
      fi
    fi
  fi

  # 父 TD
  td_link=$(grep -oE '\.\./\.\.?/tech_design/[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9_-]+' "$pf" 2>/dev/null | head -1 || true)
  if [[ -n "$td_link" ]]; then
    td_dirname=$(basename "$td_link")
    td_path="tech_design/$td_dirname"
    parent_state="${td_states[$td_path]:-}"
    if [[ "$parent_state" == "Deprecated" && "$self_state" != "Deprecated" ]]; then
      echo -e "${YELLOW}⚠${NC} $pf — 父 TD 已 Deprecated ($td_path), Plan 未同步降级 (当前: ${self_state:-未声明})"
      errors=$((errors+1))
    fi
  fi
done < <(find plan -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort)


# --- T6: 台账 ID 唯一性 + ID 格式 (可选层: 批次目录下的台账文件) ---
# 台账列定义 (11 列) 与 ID 前缀约定 (PRD/TECH/TEST/PLAN) 见 schema/prd-ledger.md。
LEDGER_ID_RE='^(PRD|TECH|TEST|PLAN)-[0-9]{8}-[0-9]{2}$'
REL_TYPE_RE='^(supersede|inherit|depend|shared|conflict|relate|split-from|merge-into)$'
# 实体文件节点标识: 仓内相对路径 (如 prd/{YYYY-MM-DD}/{topic}.md), 不含空格与 markdown 链接语法
NODE_PATH_RE='^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*$'

# 台账文件发现: 只认批次目录 (material/{date}/*.md, prd/{date}/*.md) 与根 PRDS.md;
# 层级 README (material/README.md 等) 不是台账, 不纳入。
find_ledger_files() {
  local out
  out=$(find material prd -mindepth 2 -maxdepth 2 -type f -name '*.md' 2>/dev/null | sort)
  if [[ -f PRDS.md ]]; then
    out="${out}"$'\n'"PRDS.md"
  fi
  printf '%s\n' "$out"
}

# 提取 `## PRD台账` 段 (跳过围栏代码块内的同名标题)
ledger_section() {
  awk '
    /^```/ { fence = !fence; next }
    !fence && /^##[[:space:]]+PRD台账[[:space:]]*$/ { f=1; next }
    !fence && f && /^#{1,6}[[:space:]]/ { exit }
    f { print }
  ' "$1" 2>/dev/null
}

# 由台账表头推算列号 (awk -F'|' 口径: 首个 '|' 之前为空字段, 故 # 列 = 2, ID 列 = 3)
ledger_columns() {
  awk -F'|' '
    { id=0; st=0; mat=0
      for (i=2; i<=NF-1; i++) {
        c=$i; gsub(/^[ \t]+|[ \t]+$/,"",c)
        if (c=="ID") id=i; else if (c=="状态") st=i; else if (c=="关联素材") mat=i
      }
      if (id) { printf "%d %d %d\n", id, (st?st:7), (mat?mat:9); exit } }
  ' <<< "$1"
}

# 文档状态提取 (容忍 `> **状态**: X` 与 `**状态**: X` 两种写法)
doc_state() {
  local f="$1"
  awk '/^[[:space:]]*>?[[:space:]]*\*\*状态\*\*/ {
    if (match($0, /(Draft|Ready|Implemented|Deprecated)/)) { print substr($0, RSTART, RLENGTH); exit }
  }' "$f" 2>/dev/null
}

declare -A ledger_id_owner=()    # 台账 ID → 所属台账文件
declare -A ledger_id_state=()     # 台账 ID → 状态
declare -A ledger_id_path=()      # 台账 ID → 关联素材解析出的仓内路径
declare -A test_id_seen=()
ledger_ready_ids=()
ledger_deprecated_ids=()

ledger_files=$(find_ledger_files)
if [[ -n "$ledger_files" ]]; then
  while IFS= read -r lf; do
    [[ -n "$lf" && -f "$lf" ]] || continue
    ledger_body=$(ledger_section "$lf")
    [[ -z "$(grep -E '^\|' <<< "$ledger_body")" ]] && continue

    cols=$(ledger_columns "$ledger_body")
    if [[ -z "$cols" ]]; then
      echo -e "${YELLOW}⚠${NC} $lf — 台账表未找到 \`ID\` 列, 跳过 ID 校验"
      continue
    fi
    read -r id_col st_col mat_col <<< "$cols"
    id_col="${id_col:-3}"; st_col="${st_col:-7}"; mat_col="${mat_col:-9}"
    checked=$((checked+1))

    while IFS= read -r row; do
      [[ -z "$row" ]] && continue
      lid=$(awk -F'|' -v c="$id_col" '{gsub(/^[ \t]+|[ \t]+$/,"",$c); print $c}' <<< "$row")
      case "$lid" in
        ""|"ID") continue ;;
      esac
      [[ "$lid" =~ ^:?-+:?$ ]] && continue
      case "$lid" in *"["*|*"]"*) continue ;; esac

      if [[ ! "$lid" =~ $LEDGER_ID_RE ]]; then
        echo -e "${RED}✗${NC} $lf — 台账 ID 格式非法: '$lid' (期望 {PRD|TECH|TEST|PLAN}-{YYYYMMDD}-{NN})"
        errors=$((errors+1))
        continue
      fi
      if [[ -n "${ledger_id_owner[$lid]:-}" ]]; then
        echo -e "${RED}✗${NC} $lf — 台账 ID 重复: $lid (已见于 ${ledger_id_owner[$lid]})"
        errors=$((errors+1))
        continue
      fi
      ledger_id_owner["$lid"]="$lf"

      lst=$(awk -F'|' -v c="$st_col" '{gsub(/^[ \t]+|[ \t]+$/,"",$c); print $c}' <<< "$row")
      ledger_id_state["$lid"]="$lst"
      case "$lst" in
        Ready) ledger_ready_ids+=("$lid") ;;
        Deprecated) ledger_deprecated_ids+=("$lid") ;;
      esac

      # 关联素材 → 仓内路径 (用于台账 ID 与 PRD 实体文件关联; URL 与非 .md 不解析)
      lmat=$(awk -F'|' -v c="$mat_col" '{gsub(/^[ \t]+|[ \t]+$/,"",$c); print $c}' <<< "$row")
      lmat="${lmat//$'\x60'/}"
      case "$lmat" in
        ""|*://*) ;;
        *.md)
          cand=""
          if [[ -f "$lmat" ]]; then
            cand="$lmat"
          elif [[ -f "$(dirname "$lf")/$lmat" ]]; then
            cand="$(dirname "$lf")/$lmat"
          fi
          [[ -n "$cand" ]] && ledger_id_path["$lid"]="$cand"
          ;;
      esac
    done < <(grep -E '^\|' <<< "$ledger_body")
  done <<< "$ledger_files"
fi

# --- T7 + T8: README 关系边表节点标识存在性 + 关系类型枚举 + supersede ↔ Deprecated 一致性 ---
# 关联矩阵为可选层: 根 README.md 含 `## PRD关联矩阵` → `### 关系边表` 才启用。
# 关系类型 8 类见 schema/prd-matrix.md; 节点标识规范见 schema/prd-ledger.md (I-3)。
matrix_enabled=false
edge_section=""
edge_rows=""
if [[ -f README.md ]] && grep -qE '^##[[:space:]]+PRD关联矩阵' README.md; then
  matrix_enabled=true
  # 只取 `### 关系边表` 小节内容 (遇到下一个 `###`/`##` 标题即结束), 再剔除围栏内示例表。
  edge_section=$(awk '
    /^```/ { fence = !fence; next }
    !fence && /^###[[:space:]]+关系边表[[:space:]]*$/ { e=1; next }
    !fence && e && /^#{1,6}[[:space:]]/ { e=0 }
    !fence && e { print }
  ' README.md)
  edge_rows=$(awk '/^\|/ {print}' <<< "$edge_section")
fi

if [[ "$matrix_enabled" == true && -n "$edge_rows" ]]; then
  checked=$((checked+1))
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[|][[:space:]]*:?-+ ]] && continue
    node_a=$(awk -F'|' '{c=$3; gsub(/^[ \t]+|[ \t]+$/,"",c); gsub(/`/,"",c); print c}' <<< "$line")
    rel=$(awk -F'|' '{c=$4; gsub(/^[ \t]+|[ \t]+$/,"",c); gsub(/`/,"",c); print c}' <<< "$line")
    node_b=$(awk -F'|' '{c=$5; gsub(/^[ \t]+|[ \t]+$/,"",c); gsub(/`/,"",c); print c}' <<< "$line")
    # 表头行与分隔行跳过
    [[ "$node_a" == "节点 A" || "$node_a" == "节点A" ]] && continue
    [[ -z "$node_a" && -z "$node_b" && -z "$rel" ]] && continue

    # T7: 关系类型枚举 (8 类)
    if [[ ! "$rel" =~ $REL_TYPE_RE ]]; then
      echo -e "${RED}✗${NC} README.md 关系边表 — 非法关系类型: '$rel' (允许 8 类, 见 schema/prd-matrix.md)"
      errors=$((errors+1))
    fi

    # T7: 节点标识存在性 (台账 ID 或仓内相对路径; 无法识别的形态只告警)
    for node in "$node_a" "$node_b"; do
      [[ -z "$node" ]] && continue
      if [[ "$node" =~ $LEDGER_ID_RE ]]; then
        if [[ -z "$ledger_files" ]]; then
          echo -e "${YELLOW}⚠${NC} README.md 关系边表 — 台账层未启用 (无台账文件), 无法核对节点标识: $node"
        elif [[ -z "${ledger_id_owner[$node]:-}" ]]; then
          echo -e "${RED}✗${NC} README.md 关系边表 — 节点标识未在台账登记: $node"
          errors=$((errors+1))
        fi
      elif [[ "$node" =~ $NODE_PATH_RE ]]; then
        if [[ ! -e "$node" ]]; then
          echo -e "${RED}✗${NC} README.md 关系边表 — 节点文件不存在: $node"
          errors=$((errors+1))
        fi
      else
        echo -e "${YELLOW}⚠${NC} README.md 关系边表 — 无法识别的节点标识: $node"
      fi
    done

    # T8 正向: supersede A→B, 被替代者 B 必须是 Deprecated
    #   B 可能是实体文件 (仓内路径) 或台账 ID (查台账状态列)
    if [[ "$rel" == "supersede" ]]; then
      if [[ "$node_b" =~ $NODE_PATH_RE && -f "$node_b" ]]; then
        if [[ "$(doc_state "$node_b")" != "Deprecated" ]]; then
          echo -e "${RED}✗${NC} README.md 关系边表 — $node_b 已被 $node_a 替代(supersede)但状态不是 Deprecated"
          errors=$((errors+1))
        fi
      elif [[ "$node_b" =~ $LEDGER_ID_RE && -n "${ledger_id_owner[$node_b]:-}" ]]; then
        if [[ "${ledger_id_state[$node_b]:-}" != "Deprecated" ]]; then
          echo -e "${RED}✗${NC} README.md 关系边表 — $node_b 已被 $node_a 替代(supersede)但台账状态不是 Deprecated"
          errors=$((errors+1))
        fi
      fi
    fi
  done <<< "$edge_rows"

  # T8 反向: 已 Deprecated 的 PRD (实体文件或台账行) 必须有 supersede 边指向它
  while IFS= read -r prd_f; do
    [[ -f "$prd_f" ]] || continue
    [[ "$(doc_state "$prd_f")" == "Deprecated" ]] || continue
    if ! printf '%s\n' "$edge_rows" | awk -F'|' -v n="$prd_f" '
      { gsub(/^[ \t]+|[ \t]+$/,"",$4); gsub(/^[ \t]+|[ \t]+$/,"",$5); gsub(/`/,"",$5)
        if ($4=="supersede" && $5==n) found=1 }
      END { exit found?0:1 }'; then
      echo -e "${RED}✗${NC} $prd_f — 已 Deprecated 但 README 关系边表缺少指向它的 supersede 边"
      errors=$((errors+1))
    fi
  done < <(find prd -mindepth 2 -maxdepth 2 -type f -name '*.md' 2>/dev/null | sort)

  # T8 反向 (台账口径): 台账状态为 Deprecated 的 ID 必须有 supersede 边指向它
  for did in "${ledger_deprecated_ids[@]:-}"; do
    [[ -z "$did" ]] && continue
    if ! printf '%s\n' "$edge_rows" | grep -qF "$did"; then
      echo -e "${RED}✗${NC} README.md 关系边表 — 台账 ${did} 状态为 Deprecated 但无 supersede 边指向它"
      errors=$((errors+1))
    fi
  done
fi

# --- T10: README 用例登记表 TEST-ID 唯一性 + 登记行路径存在性 ---
# 用例登记表为可选层: 根 README.md 中首列 (或任一列) 含 TEST-ID 的表格行;
# ID 格式 TEST-{YYYYMMDD}-{NN}。只扫表格行, 不扫正文散文。
if [[ -f README.md ]]; then
  test_rows=$(awk -F'|' '
    /^```/ { fence = !fence; next }
    !fence && /^\|/ {
      for (i=2; i<=NF; i++) { c=$i; gsub(/^[ \t]+|[ \t]+$/,"",c); gsub(/`/,"",c); if (c ~ /^TEST-[0-9]/) { print; break } }
    }' README.md)
  if [[ -n "$test_rows" ]]; then
    checked=$((checked+1))
    while IFS= read -r row; do
      [[ -z "$row" ]] && continue
      tid=$(awk -F'|' '{for(i=2;i<=NF;i++){c=$i; gsub(/^[ \t]+|[ \t]+$/,"",c); gsub(/`/,"",c); if(c ~ /^TEST-/){print c; exit}}}' <<< "$row")
      [[ -z "$tid" ]] && continue
      if [[ ! "$tid" =~ ^TEST-[0-9]{8}-[0-9]{2}$ ]]; then
        echo -e "${RED}✗${NC} README.md 用例登记表 — TEST-ID 格式非法: '$tid' (期望 TEST-{YYYYMMDD}-{NN})"
        errors=$((errors+1))
        continue
      fi
      if [[ -n "${test_id_seen[$tid]:-}" ]]; then
        echo -e "${RED}✗${NC} README.md 用例登记表 — TEST-ID 重复: $tid"
        errors=$((errors+1))
      else
        test_id_seen["$tid"]=1
      fi
      while IFS= read -r p; do
        [[ -z "$p" ]] && continue
        [[ "$p" == *"://"* ]] && continue
        if [[ ! -e "$p" ]]; then
          echo -e "${RED}✗${NC} README.md 用例登记表 — 登记行路径不存在: $p"
          errors=$((errors+1))
        fi
      done < <(awk -F'|' '{for(i=2;i<=NF;i++){c=$i; gsub(/^[ \t]+|[ \t]+$/,"",c); gsub(/`/,"",c); if (c ~ /^[A-Za-z0-9._-]+(\/[A-Za-z0-9._-]+)*$/ && c ~ /\.md$/) print c}}' <<< "$row")
    done <<< "$test_rows"
  fi
fi

# --- T13: 新 PRD 关系边评估提示 (仅信息性, 不计违规) ---
# Ready 的 PRD 若未出现在关系边表 → 提示评估关系 (独立主题可忽略), 不增加 errors。
# 节点两种形态均覆盖: 实体文件路径 (prd/{date}/{topic}.md) 与台账 ID (PRD-{YYYYMMDD}-{NN})。
if [[ "$matrix_enabled" == true ]]; then
  new_no_edge=""
  while IFS= read -r pf; do
    [[ -f "$pf" ]] || continue
    [[ "$(doc_state "$pf")" == "Ready" ]] || continue
    if ! printf '%s\n' "$edge_rows" | grep -qF "$pf"; then
      new_no_edge="$new_no_edge $pf"
    fi
  done < <(find prd -mindepth 2 -maxdepth 2 -type f -name '*.md' 2>/dev/null | sort)

  # 台账口径: 状态为 Ready 的台账 ID 未出现在边表 → 同样提示
  for rid in "${ledger_ready_ids[@]:-}"; do
    [[ -z "$rid" ]] && continue
    if ! printf '%s\n' "$edge_rows" | grep -qF "$rid"; then
      new_no_edge="$new_no_edge $rid"
    fi
  done

  if [[ -n "$new_no_edge" ]]; then
    echo -e "${YELLOW}○${NC} T13 关系边评估提示 — 以下 Ready PRD 未出现在 README 关系边表 (独立主题可忽略; 如存在关系请登记边):${new_no_edge}"
  fi
fi

# --- 总结 ---
echo "---"
if [[ $errors -eq 0 ]]; then
  echo -e "${GREEN}✓${NC} 追溯校验: $checked 项全部通过"
  exit 0
else
  echo -e "${RED}✗ 追溯校验: $checked 项中发现 $errors 处违规${NC}" >&2
  exit 1
fi