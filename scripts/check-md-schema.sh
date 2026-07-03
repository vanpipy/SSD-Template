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
#   Tech Design 6 子文件 (schema/tech_design/):
#     - README.md (索引)
#     - decisions.md (KD-{n} + 5 段)
#     - data-model.md
#     - api-contracts.md
#     - scenario-mapping.md
#     - quality.md
#     - interactions.md (条件必填,见 README.md 中"何时需要"段)
#
#   Plan (schema/plan.md):
#     - 变更清单
#     - 验证用例 V-{n}
#     - 跨文件引用对账表 (KD/SYS/MOD/FR/V)
#
# 用法:
#   ./scripts/check-md-schema.sh                  # 检查整个仓库
#   ./scripts/check-md-schema.sh prd/2026-06-22-processed/login.md  # 检查单文件
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

  # v2 Plan (无 ## 变更索引) 完全跳过 v3 必需段检查
  # 因为 v2 Plan 的 V 编号格式不统一 (V1/V01/V11/V-1 都存在)
  if ! grep -qE '^## 变更索引' "$f" 2>/dev/null; then
    echo -e "${YELLOW}○${NC} $f — v2 格式 Plan,跳过 v3 校验 (变更索引 / V-N 命名 / 跨文件引用对账)"
    return 0
  fi

  # v3 Plan: 严格校验
  # 1. ## 变更清单 (Changes)
  if ! grep -qE '^### Change #1:' "$f"; then
    echo -e "${RED}✗${NC} $f — 缺少 \`### Change #1:\`(变更清单)"
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

# 检查 Tech Design (整体) - 双模式: v3 多子文件目录 vs v2 单文件目录
check_tech_design() {
  local d="$1"
  local errors=0

  # 双模式识别: v2 形态 = 只有 *.md 单文件,无 README.md → skip
  if [[ ! -f "$d/README.md" ]]; then
    echo -e "${YELLOW}○${NC} $d — v2 格式单文件目录,跳过 v3 7 子文件校验"
    return 0
  fi

  # v3 形态: 完整校验
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
      if ! grep -qE "^## ${kd}:" "$d/decisions.md"; then
        echo -e "${RED}✗${NC} $d/README.md — 引用 ${kd} 但 decisions.md 中不存在"
        errors=$((errors+1))
      fi
    done
  fi

  return $errors
}

# 主逻辑
target="${1:-.}"

if [[ -f "$target" ]]; then
  # 单文件检查
  case "$target" in
    */prd/*-processed/*.md) check_prd "$target" ;;
    */plan/*/*.md)          check_plan "$target" ;;
    *)                      echo "未知文件类型: $target"; exit 2 ;;
  esac
  exit $?
fi

# 整库检查
total_errors=0
total_files=0

# PRD
while IFS= read -r f; do
  total_files=$((total_files+1))
  if check_prd "$f"; then
    echo -e "${GREEN}✓${NC} $f"
  else
    total_errors=$((total_errors+$?))
  fi
done < <(find "$target/prd" -mindepth 2 -maxdepth 2 -type f -name "*.md" -path "*-processed/*" 2>/dev/null)

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

echo "---"
if [[ $total_errors -eq 0 ]]; then
  echo -e "${GREEN}✓${NC} 字段校验: $total_files 项全部通过"
  exit 0
else
  echo -e "${RED}✗ 字段校验: $total_files 项中发现 $total_errors 处违规${NC}" >&2
  exit 1
fi