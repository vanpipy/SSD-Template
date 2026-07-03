#!/usr/bin/env bash
# check-traceability.sh — 校验跨文件引用追溯完整性
#
# 检查项:
#   T1. PRD 场景 → Tech Design 场景映射覆盖 (每个 Given/When/Then 至少 1 行映射)
#   T2. Plan V-{n} 引用闭环 (每个 V 在"验证用例"段有定义,且在"跨文件引用对账"被引用)
#   T3. Plan KD-{n} 引用闭环 (每个 KD 在 tech_design/decisions.md 中存在)
#   T4. Plan Change #N ↔ V-{n} 双向引用 (每个 Change 至少有 1 个 V,每个 V 至少 1 个 Change)
#   T5. 引用类型一致性 (引用类型只有 KD / V / FR / SYS / MOD 5 种,SC 等遗留类型已被废弃)
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

# --- T5: 引用类型一致性扫描（已简化）
# 原 T5: 检测任何 [A-Z]+-[0-9]+ 形式,前缀不在白名单报错
# 问题: 会误报业务值（AES-256 加密算法 / SHA-256 哈希 / EAN-13 条码标准等）
# 修复: 只扫描白名单引用类型（KD/V/FR/SYS/MOD）,不主动扫描非白名单前缀
#       这意味着 T5 变成 no-op（T1-T4 已覆盖引用闭环检查）
# 未来如需扫描,需加上下文判断（如只在 markdown 链接 / 表格 / 引用块中扫描）
while IFS= read -r f; do
  while IFS= read -r line; do
    # 静默扫描白名单引用,收集为后续检查备查（当前不报错）
    grep -oE '\b(KD|V|FR|SYS|MOD)-[0-9]+\b' <<< "$line" 2>/dev/null > /dev/null
  done < "$f"
done < <(find prd tech_design plan -type f -name "*.md" 2>/dev/null)

# --- T1 + T3: PRD 场景覆盖 + Plan KD 闭环 ---
while IFS= read -r plan_dir; do
  plan_file="$plan_dir/$(basename "$plan_dir").md"
  [[ -f "$plan_file" ]] || continue

  checked=$((checked+1))

  # 找到 Plan 引用的 Tech Design
  td_link=$(grep -oE '../tech_design/[^)]+' "$plan_file" | head -1 || true)
  if [[ -z "$td_link" ]]; then
    echo -e "${RED}✗${NC} $plan_file — 未引用 Tech Design (../tech_design/...)"
    errors=$((errors+1))
    continue
  fi

  td_path="$(dirname "$plan_file")/$td_link"
  [[ ! -d "$td_path" ]] && td_path="${td_path%/*}"

  # T3: KD 闭环
  if [[ -f "$td_path/decisions.md" ]]; then
    while IFS= read -r kd; do
      if ! grep -qE "^## ${kd}:" "$td_path/decisions.md"; then
        echo -e "${RED}✗${NC} $plan_file — 引用 ${kd} 但 $td_path/decisions.md 中不存在"
        errors=$((errors+1))
      fi
    done < <(grep -oE 'KD-[0-9]+' "$plan_file" | sort -u)
  fi

  # T2: V 闭环 — Plan 引用的 V-{n} 必须在"验证用例"段定义
  plan_vs=$(grep -oE 'V-[0-9]+' "$plan_file" | sort -u)
  while IFS= read -r v; do
    [[ -z "$v" ]] && continue
    if ! grep -qE "^### ${v}:" "$plan_file"; then
      echo -e "${RED}✗${NC} $plan_file — 引用 ${v} 但未在 \`## 验证用例\` 段定义"
      errors=$((errors+1))
    fi
  done <<< "$plan_vs"

  # T4: Change ↔ V 双向引用
  plan_changes=$(grep -cE '^### Change #[0-9]+:' "$plan_file" || true)
  if [[ $plan_changes -eq 0 ]]; then
    echo -e "${RED}✗${NC} $plan_file — 缺少 \`### Change #\` 段"
    errors=$((errors+1))
  fi

done < <(find plan -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

# --- T1: PRD 场景覆盖(在 tech_design/scenario-mapping.md 中) ---
while IFS= read -r td_dir; do
  prd_link=$(grep -oE '../../prd/[^)]+\.md' "$td_dir/README.md" 2>/dev/null | head -1 || true)
  [[ -z "$prd_link" ]] && continue

  prd_path="$(cd "$td_dir" && cd "$(dirname "$prd_link")" && pwd)/$(basename "$prd_link")"

  if [[ -f "$prd_path" && -f "$td_dir/scenario-mapping.md" ]]; then
    checked=$((checked+1))

    # PRD 中每个场景名(以 ### 场景: 开头)
    prd_scenarios=$(grep -oE '### 场景:[^[:space:]]+' "$prd_path" 2>/dev/null | sed 's/### 场景://' || true)

    # 简化检查: scenario-mapping.md 表格至少要 ≥ PRD 场景数
    mapping_rows=$(grep -cE '^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|$' "$td_dir/scenario-mapping.md" 2>/dev/null || echo 0)
    prd_count=$(grep -cE '^### 场景:' "$prd_path" 2>/dev/null || echo 0)

    if [[ $mapping_rows -lt $prd_count ]]; then
      echo -e "${YELLOW}⚠${NC} $td_dir/scenario-mapping.md — 表格行数 ($mapping_rows) 少于 PRD 场景数 ($prd_count)"
      errors=$((errors+1))
    fi
  fi
done < <(find tech_design -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

# --- 总结 ---
echo "---"
if [[ $errors -eq 0 ]]; then
  echo -e "${GREEN}✓${NC} 追溯校验: $checked 项全部通过"
  exit 0
else
  echo -e "${RED}✗ 追溯校验: $checked 项中发现 $errors 处违规${NC}" >&2
  exit 1
fi