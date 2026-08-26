#!/usr/bin/env bash
# check-traceability.sh — 校验跨文件引用追溯完整性
#
# 检查项:
#   T1. PRD 场景 → Tech Design 场景映射覆盖 (每个 Given/When/Then 至少 1 行映射; v3: scenario-mapping.md, v4: README.md `## 场景映射` 段)
#   T2. Plan V-{n} 引用闭环 (每个 V 在"验证用例"段有定义)
#   T3. Plan KD-{n} 引用闭环 (每个 KD 在 TD 中存在: v4 ards.md / 存量 v3 decisions.md)
#   T4. Plan Change #N ↔ V-{n} 双向引用闭环 (v3 Plan 严格: 每个 Change 至少 1 个 V,每个 V 至少 1 处 Change 关联; v2 仅查 Change 标题)
#   T5. 引用类型一致性 (引用类型只有 KD / V / FR / SYS / MOD 5 种, 已简化为 no-op)
#   T9. test_cases 元信息上游引用存在性 (来源/Tech Design/Plan 行中的仓内路径, test_cases 目录存在才校验)
#   T11. Plan 元信息「参考 Test Cases」引用存在性 (可选行, 填了才校验)
#
# POS 专属检查 (与 PRDS.md 台账 / README 关联矩阵 / 跨层级联 相关) 不适用于 SSD-Template 通用模板, 不引入:
#   T6. PRDS.md 台账段 PRD-ID 唯一性
#   T7. README 关联矩阵关系边表节点标识存在性 + 关系类型枚举
#   T8. supersede 边 ↔ Deprecated 状态一致性
#   T10. README TEST-ID 唯一性 + 登记行路径存在性
#   T12. 跨层级联一致性 (上游 PRD/TD Deprecated, 下游应级联降级)
#   T13. 新 PRD 关系边评估提示
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

# --- T1 + T3: PRD 场景覆盖 + Plan KD 闭环 ---
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

  # T3: KD 闭环 — v4 TD 锚点在 ards.md, 存量 v3 在 decisions.md (按存在性择一)
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

  # T2: V 闭环 — Plan 引用的 V-{n} 必须在"验证用例"段定义
  # lookbehind 排除 PV-001 等日志码的子串误匹配 (2026-08-07 pay-voice 演练发现)
  plan_vs=$(grep -oP '(?<![A-Za-z])V-[0-9]+' "$plan_file" | sort -u)
  while IFS= read -r v; do
    [[ -z "$v" ]] && continue
    if ! grep -qE "^### ${v}:" "$plan_file"; then
      echo -e "${RED}✗${NC} $plan_file — 引用 ${v} 但未在 \`## 验证用例\` 段定义"
      errors=$((errors+1))
    fi
  done <<< "$plan_vs"

  # T4: Change ↔ V 双向引用闭环 — 支持 §1.5 多仓分组 (####) 和单仓 (###)
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


# --- 总结 ---
echo "---"
if [[ $errors -eq 0 ]]; then
  echo -e "${GREEN}✓${NC} 追溯校验: $checked 项全部通过"
  exit 0
else
  echo -e "${RED}✗ 追溯校验: $checked 项中发现 $errors 处违规${NC}" >&2
  exit 1
fi