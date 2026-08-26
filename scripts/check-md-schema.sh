#!/usr/bin/env bash
# check-md-schema.sh — 校验 PRD / Tech Design / Plan 的必填字段非空
#
# 规范 (对应 schema/* 模板的"门禁清单"):
#   PRD 5 项 (schema/prd.md):
#     1. ## 为什么 (Why)
#     2. ## 目标 (Goal)            — 至少 1 个非占位符验证标准
#     3. ## 场景 (Scenarios)       — 至少 1 个 Given/When/Then
#     4. ## 不在范围内 (Out of Scope)
#     5. ## 复审 (Review)          — 复审日期非占位符
#
#   Tech Design — 双形态 (2026-08-07 起):
#   v4 (新约定, schema/tech_design/ 4 模板, 按 ards.md/apis.md 存在识别):
#     - README.md (综合描述: 摘要 + Context + 场景映射 + 质量保证 + 关联验证用例)
#     - ards.md (架构决策 + 方案对比: Solution Space + KD-{n} + OQ/Spikes/Pivot + Gap + 风险)
#     - apis.md (接口契约全响应变体 + 时序交互 SYS/MOD)
#     - data-model.md (ER 图 erDiagram + 数据结构明细; 无变更须显式声明)
#   v3 (存量 39 目录, 6 子文件必填 + interactions.md 条件必填):
#     - README.md / decisions.md / data-model.md / api-contracts.md /
#       scenario-mapping.md / quality.md (+ interactions.md 条件必填)
#
#   Plan (schema/plan.md):
#     - 变更清单
#     - 验证用例 V-{n}
#     - 跨文件引用对账表 (KD/SYS/MOD/FR/V)
#
#   Test Case (schema/test_case.md, 目录存在才校验, 2026-08-06 机制建设):
#     - 主/冒烟: 元信息 7 必填行 + 状态枚举前缀 + 用例总览段 + Ready/Implemented 时要点伴生
#     - 要点伴生 (*-key-points.md): 业务背景 + 核心测试点 段
#
# 用法:
#   ./scripts/check-md-schema.sh                  # 检查整个仓库
#   ./scripts/check-md-schema.sh prd/2026-06-22/login.md  # 检查单文件 (根相对/./相对/绝对路径均可)
#   ./scripts/check-md-schema.sh tech_design/2026-08-07-receipt-footer  # 检查单个 TD 目录
#
# 退出码: 0=通过 1=违规 2=调用错误

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

# 占位符检测: 形如 {topic} / {YYYY-MM-DD} / {field} 等模板占位符
placeholder_re='\{[a-zA-Z_-]+\}|\{[a-zA-Z_-]+ [a-zA-Z_-]+\}'

# 检查 PRD
check_prd() {
  local f="$1"
  local errors=0

  # 1. ## 为什么 (Why)
  if ! grep -qE '^## 为什么 \(Why\)' "$f"; then
    echo -e "${RED}✗${NC} $f — 缺少 \`## 为什么 (Why)\` 段"
    errors=$((errors+1))
  fi

  # 2. ## 目标 (Goal) — 至少 1 个非占位符 checkbox
  local goal_section
  goal_section=$(awk '/^## 目标 \(Goal\)/,/^## /' "$f" | sed '/^## /!b;/^## 目标 /!d;')
  if [[ -z "$goal_section" ]]; then
    # 退化: 检查有 Goal 段且至少 1 个 [ ] 项
    if ! awk '/^## 目标 \(Goal\)/{p=1; next} /^## /{p=0} p && /^- \[ \]/{found=1; exit} END{exit !found}' "$f"; then
      echo -e "${RED}✗${NC} $f — \`## 目标 (Goal)\` 段无验证标准 ([ ])"
      errors=$((errors+1))
    fi
  fi
  # 占位符检测 - 避免误报业务动态值 (如 {env} / #{token} / {userId})
  # 业务动态值与模板占位符难以区分,改为靠人工 review
  # 仅检测明显是模板的占位符: 全大写或包含连字符的多词组合
  if grep -qE '\{[A-Z][A-Z_-]+\}|\{[A-Z_-]+ [A-Z_-]+\}' "$f"; then
    echo -e "${RED}✗${NC} $f — 仍含模板占位符 (如 {TOPIC} / {FIELD_NAME}):"
    grep -nE '\{[A-Z][A-Z_-]+\}|\{[A-Z_-]+ [A-Z_-]+\}' "$f" | sed 's/^/    /'
    errors=$((errors+1))
  fi

  # 3. ## 场景 (Scenarios) — 至少 1 个 Given
  if ! awk '/^## 场景 \(Scenarios\)/{p=1; next} /^## /{p=0} p && /\*\*Given\*\*/{found=1; exit} END{exit !found}' "$f"; then
    echo -e "${RED}✗${NC} $f — \`## 场景 (Scenarios)\` 段无 Given/When/Then"
    errors=$((errors+1))
  fi

  # 4. ## 不在范围内 (Out of Scope)
  if ! grep -qE '^## 不在范围内 \(Out of Scope\)' "$f"; then
    echo -e "${RED}✗${NC} $f — 缺少 \`## 不在范围内 (Out of Scope)\` 段"
    errors=$((errors+1))
  fi

  # 5. ## 复审 (Review) — 复审日期非占位符
  if ! awk '/^## 复审 \(Review\)/{p=1; next} /^## /{p=0} p && /复审日期.*[0-9]{4}-[0-9]{2}-[0-9]{2}/{found=1; exit} END{exit !found}' "$f"; then
    echo -e "${RED}✗${NC} $f — \`## 复审 (Review)\` 段无有效复审日期"
    errors=$((errors+1))
  fi

  return $errors
}

# 检查 Plan - 双模式: v3 多段结构 vs v2 单段结构
check_plan() {
  local f="$1"
  local errors=0

  # v2 Plan (无 ### Change #1: 或 #### Change #1:) 完全跳过 v3 必需段检查
  # 因为 v2 Plan 的 V 编号格式不统一 (V1/V01/V11/V-1 都存在)
  # 注: `## 变更索引` 与 `## 变更清单` 在 schema 中是两个不同段 (索引 = 目录, 清单 = 详细),
  #     不能用 `## 变更索引` 作为 v3 判定 (有的 v3 Plan 只有清单段, 没有索引段)
  # 多仓分组 (`### 前端变更` 之下用 `#### Change #1:` h4) 也是 v3, 需要兼容
  if ! grep -qE '^### Change #1:|^#### Change #1:' "$f" 2>/dev/null; then
    echo -e "${YELLOW}○${NC} $f — v2 格式 Plan,跳过 v3 校验 (变更清单 / V-N 命名 / 跨文件引用对账)"
    return 0
  fi

  # v3 Plan: 严格校验
  # 1. ## 变更清单 (Changes) — 支持单仓 `### Change #N:` (h3) 与多仓 `#### Change #N:` (h4, 在 `### 前端/后端变更` 之下)
  if ! grep -qE '^### Change #1:|^#### Change #1:' "$f"; then
    echo -e "${RED}✗${NC} $f — 缺少 \`### Change #1:\` 或 \`#### Change #1:\`(变更清单, 多仓分组时用 h4)"
    errors=$((errors+1))
  fi

  # 2. ## 验证用例 (Verification) — V-1
  if ! grep -qE '^### V-1:' "$f"; then
    echo -e "${RED}✗${NC} $f — 缺少 \`### V-1:\`(验证用例)"
    errors=$((errors+1))
  fi

  # 3. ## 跨文件引用对账表
  if ! grep -qE '^## 跨文件引用对账' "$f"; then
    echo -e "${RED}✗${NC} $f — 缺少 \`## 跨文件引用对账\` 段"
    errors=$((errors+1))
  fi

  return $errors
}

# 检查 Tech Design (整体) - 三形态: v4 4 子文件 (新约定) / v3 6 子文件 (存量) / v2 单文件
check_tech_design() {
  local d="$1"
  local errors=0

  # v2 形态 = 只有 *.md 单文件,无 README.md → skip
  if [[ ! -f "$d/README.md" ]]; then
    echo -e "${YELLOW}○${NC} $d — v2 格式单文件目录,跳过子文件校验"
    return 0
  fi

  # v4 形态识别: ards.md 或 apis.md 存在 → 4 子文件严格校验
  if [[ -f "$d/ards.md" || -f "$d/apis.md" ]]; then
    local required_v4=("README.md" "ards.md" "apis.md" "data-model.md")
    for sub in "${required_v4[@]}"; do
      if [[ ! -f "$d/$sub" ]]; then
        echo -e "${RED}✗${NC} $d — v4 缺少必填子文件: $sub"
        errors=$((errors+1))
      fi
    done

    # README 必含场景映射段 (T1 场景覆盖校验的数据源)
    if ! grep -qE '^## 场景映射' "$d/README.md" 2>/dev/null; then
      echo -e "${RED}✗${NC} $d/README.md — 缺少 \`## 场景映射\` 段 (v4 综合描述必含)"
      errors=$((errors+1))
    fi

    # 跨引用对账 (KD): 每个 KD-{n} 引用应存在于 ards.md (锚点 `## KD-{n}:`)
    local refs kd
    refs=$(grep -oE 'KD-[0-9]+' "$d/README.md" 2>/dev/null | sort -u || true)
    for kd in $refs; do
      if ! grep -qE "^## ${kd}:" "$d/ards.md" 2>/dev/null; then
        echo -e "${RED}✗${NC} $d/README.md — 引用 ${kd} 但 ards.md 中不存在 (\`## ${kd}: ...\`)"
        errors=$((errors+1))
      fi
    done

    # data-model.md: ER 图 (erDiagram) 或显式「无数据模型变更」声明
    if [[ -f "$d/data-model.md" ]]; then
      if ! grep -qE 'erDiagram' "$d/data-model.md" \
         && ! grep -qE '无数据模型变更|不涉及数据模型' "$d/data-model.md"; then
        echo -e "${RED}✗${NC} $d/data-model.md — 既无 ER 图 (erDiagram) 也无「无数据模型变更」声明"
        errors=$((errors+1))
      fi
    fi

    return $errors
  fi

  # v3 形态 (存量): 完整校验 (6 子文件必填 + interactions.md 条件必填)
  local required=("README.md" "decisions.md" "data-model.md" "api-contracts.md" "scenario-mapping.md" "quality.md")

  for sub in "${required[@]}"; do
    if [[ ! -f "$d/$sub" ]]; then
      echo -e "${RED}✗${NC} $d — 缺少必填子文件: $sub"
      errors=$((errors+1))
    fi
  done

  # interactions.md: 检查 README.md 是否标注"已跳过"
  if [[ ! -f "$d/interactions.md" ]]; then
    if ! grep -qE 'interactions\.md.*(跳过|不适用|N/A)' "$d/README.md" 2>/dev/null; then
      echo -e "${YELLOW}⚠${NC} $d — 缺少 interactions.md 且 README.md 未声明跳过(默认应创建)"
      errors=$((errors+1))
    fi
  fi

  # 跨引用对账 (KD): 每个 KD-{n} 引用应存在于 decisions.md
  if [[ -f "$d/decisions.md" ]]; then
    # README 的"跨文件引用对账"段,如果有
    local refs
    refs=$(grep -oE 'KD-[0-9]+' "$d/README.md" 2>/dev/null | sort -u || true)
    for kd in $refs; do
      if ! grep -qE "^## ${kd}:" "$d/decisions.md" 2>/dev/null; then
        echo -e "${RED}✗${NC} $d/README.md — 引用 ${kd} 但 decisions.md 中不存在"
        errors=$((errors+1))
      fi
    done
  fi

  return $errors
}

# 检查 Test Case (Layer 4, schema/test_case.md, 目录存在才校验, 2026-08-06 机制建设)
check_test_case() {
  local f="$1"
  local errors=0
  local base dir topic
  base="$(basename "$f" .md)"
  dir="$(dirname "$f")"

  # 要点伴生文档: 轻校验 2 个必备段
  if [[ "$base" == *-key-points ]]; then
    local sec
    for sec in "## 业务背景" "## 核心测试点"; do
      if ! grep -qE "^${sec}" "$f"; then
        echo -e "${RED}✗${NC} $f — 要点文档缺少 \`${sec}\` 段"
        errors=$((errors+1))
      fi
    done
    return $errors
  fi

  topic="${base%-smoke}"

  # 1. 元信息 7 必填行 (字段名唯一口径, 见 schema/test_case.md)
  # 兼容 schema 用 `**主题**` (markdown 加粗) 与裸 `主题` 两种写法 — strip 后比较
  local field val
  for field in 主题 业务产品 目标平台 来源 生成日期 状态 用例总数; do
    val=$(awk -F'|' -v k="$field" '/^\|/ {key=$2; gsub(/^[ \t]+|[ \t]+$/,"",key); gsub(/\*+/,"",key); v=$3; gsub(/^[ \t]+|[ \t]+$/,"",v); if (key==k) {print v; exit}}' "$f")
    if [[ -z "$val" ]]; then
      echo -e "${RED}✗${NC} $f — 元信息缺少必填行 \`$field\`"
      errors=$((errors+1))
    elif [[ "$val" =~ $placeholder_re ]]; then
      echo -e "${RED}✗${NC} $f — 元信息 \`$field\` 仍为占位符: $val"
      errors=$((errors+1))
    fi
  done

  # 2. 状态枚举前缀 (Draft/Ready/Implemented/Deprecated, 可带说明后缀)
  local st
  st=$(awk -F'|' '/^\|/ {key=$2; gsub(/^[ \t]+|[ \t]+$/,"",key); gsub(/\*+/,"",key); v=$3; gsub(/^[ \t]+|[ \t]+$/,"",v); if (key=="状态") {print v; exit}}' "$f")
  if [[ -n "$st" && ! "$st" =~ ^(Draft|Ready|Implemented|Deprecated) ]]; then
    echo -e "${RED}✗${NC} $f — 状态非合法枚举前缀: '$st' (应为 Draft/Ready/Implemented/Deprecated)"
    errors=$((errors+1))
  fi

  # 3. 用例总览段
  if ! grep -qE '^## 用例总览' "$f"; then
    echo -e "${RED}✗${NC} $f — 缺少 \`## 用例总览\` 段"
    errors=$((errors+1))
  fi

  # 4. Ready/Implemented 时要点伴生必须存在 (Draft 豁免)
  if [[ "$st" =~ ^(Ready|Implemented) && ! -f "$dir/$topic-key-points.md" ]]; then
    echo -e "${RED}✗${NC} $f — 状态为 ${st%% *} 但缺少伴生要点 \`$topic-key-points.md\`"
    errors=$((errors+1))
  fi

  return $errors
}

# 主逻辑
target="${1:-.}"

# 规范化: 仓库根相对路径 (prd/... / tech_design/...) 补 ./ 前缀,保证文件与目录 case 模式命中 (F1 修复,2026-08-07; 目录分支补强 2026-08-07)
if [[ "$target" != "." && "$target" != /* && "$target" != ./* ]]; then
  target="./$target"
fi

if [[ -f "$target" ]]; then
  # 单文件检查
  case "$target" in
    */prd/*/*.md)           check_prd "$target" ;;
    */plan/*/*.md)          check_plan "$target" ;;
    */test_cases/*/*.md)    check_test_case "$target" ;;
    *)                      echo "未知文件类型: $target"; exit 2 ;;
  esac
  exit $?
fi

# 单目录检查: Tech Design 目录 (v4 4 子文件 / v3 6 子文件 双模式); 其他目录 (含默认 ".") 落入整库检查
if [[ -d "$target" ]]; then
  case "$target" in
    */tech_design/*) check_tech_design "$target"; exit $? ;;
  esac
fi

# 整库检查
total_errors=0
total_files=0

# PRD (SSD-Template 新约定: prd/{date}/{topic}.md, 无 -processed 后缀)
while IFS= read -r f; do
  total_files=$((total_files+1))
  if check_prd "$f"; then
    echo -e "${GREEN}✓${NC} $f"
  else
    total_errors=$((total_errors+$?))
  fi
done < <(find "$target/prd" -mindepth 2 -maxdepth 2 -type f -name "*.md" 2>/dev/null)

# Tech Design
while IFS= read -r d; do
  total_files=$((total_files+1))
  if check_tech_design "$d"; then
    echo -e "${GREEN}✓${NC} $d"
  else
    total_errors=$((total_errors+$?))
  fi
done < <(find "$target/tech_design" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

# Plan
while IFS= read -r d; do
  for f in "$d"/*.md; do
    [[ -f "$f" ]] || continue
    total_files=$((total_files+1))
    if check_plan "$f"; then
      echo -e "${GREEN}✓${NC} $f"
    else
      total_errors=$((total_errors+$?))
    fi
  done
done < <(find "$target/plan" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

# Test Cases (Layer 4, 目录存在才校验)
if [[ -d "$target/test_cases" ]]; then
  while IFS= read -r f; do
    total_files=$((total_files+1))
    if check_test_case "$f"; then
      echo -e "${GREEN}✓${NC} $f"
    else
      total_errors=$((total_errors+$?))
    fi
  done < <(find "$target/test_cases" -mindepth 2 -maxdepth 2 -type f -name "*.md" 2>/dev/null | sort)
fi

echo "---"
if [[ $total_errors -eq 0 ]]; then
  echo -e "${GREEN}✓${NC} 字段校验: $total_files 项全部通过"
  exit 0
else
  echo -e "${RED}✗ 字段校验: $total_files 项中发现 $total_errors 处违规${NC}" >&2
  exit 1
fi