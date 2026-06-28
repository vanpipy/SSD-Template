#!/usr/bin/env bash
# check-naming.sh — 校验 SSD-Template 目录与文件命名规范
#
# 规范 (见 AGENTS.md §3.2):
#   - prd/{YYYY-MM-DD}-processed/{topic}.md           (Layer 1 PRD)
#   - prd/{YYYY-MM-DD}/*.md                          (素材区,任意文件名)
#   - tech_design/{YYYY-MM-DD}-{topic}/*.md          (Layer 2,7 子文件)
#   - plan/{YYYY-MM-DD}-{topic}/{topic}.md           (Layer 3,文件名=目录 topic)
#
# topic 规则: 小写连字符 (lowercase-with-hyphens),如 login / order-flow
#
# 用法:
#   ./scripts/check-naming.sh                  # 检查整个仓库
#   ./scripts/check-naming.sh path/to/dir       # 检查指定目录
#
# 退出码:
#   0 = 全部通过
#   1 = 发现命名违规
#   2 = 调用错误

set -euo pipefail

DATE_RE='[0-9]{4}-[0-9]{2}-[0-9]{2}'
TOPIC_RE='[a-z][a-z0-9-]*'

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

ROOT="${1:-.}"

if [[ ! -d "$ROOT" ]]; then
  echo -e "${RED}✗ 路径不存在: $ROOT${NC}" >&2
  exit 2
fi

errors=0
checked=0

# --- prd/{date}-processed/{topic}.md ---
while IFS= read -r f; do
  checked=$((checked+1))
  base="$(basename "$f")"
  parent="$(basename "$(dirname "$f")")"
  # 父目录必须是 {DATE}-processed
  if [[ ! "$parent" =~ ^${DATE_RE}-processed$ ]]; then
    echo -e "${RED}✗${NC} $f — 父目录应为 \`{YYYY-MM-DD}-processed/\`,实为 \`$parent/\`"
    errors=$((errors+1))
    continue
  fi
  # 文件名必须是 {topic}.md (topic 用小写连字符)
  if [[ ! "$base" =~ ^${TOPIC_RE}\.md$ ]]; then
    echo -e "${RED}✗${NC} $f — 文件名应为 \`{topic}.md\` (小写连字符),实为 \`$base\`"
    errors=$((errors+1))
    continue
  fi
done < <(find "$ROOT/prd" -mindepth 2 -maxdepth 2 -type f -name "*.md" -path "*-processed/*" 2>/dev/null)

# --- tech_design/{date}-{topic}/ ---
while IFS= read -r d; do
  checked=$((checked+1))
  parent="$(basename "$d")"
  if [[ ! "$parent" =~ ^${DATE_RE}-${TOPIC_RE}$ ]]; then
    echo -e "${RED}✗${NC} $d — 目录名应为 \`{YYYY-MM-DD}-{topic}\`,实为 \`$parent/\`"
    errors=$((errors+1))
    continue
  fi
done < <(find "$ROOT/tech_design" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

# --- plan/{date}-{topic}/{topic}.md ---
while IFS= read -r d; do
  checked=$((checked+1))
  parent="$(basename "$d")"
  if [[ ! "$parent" =~ ^${DATE_RE}-${TOPIC_RE}$ ]]; then
    echo -e "${RED}✗${NC} $d — 目录名应为 \`{YYYY-MM-DD}-{topic}\`,实为 \`$parent/\`"
    errors=$((errors+1))
    continue
  fi
  # 内部文件: 应该是 {topic}.md
  for f in "$d"/*.md; do
    [[ -f "$f" ]] || continue
    checked=$((checked+1))
    base="$(basename "$f")"
    topic="${parent#${DATE_RE}-}"  # 去掉日期前缀
    if [[ "$base" != "${topic}.md" ]]; then
      echo -e "${RED}✗${NC} $f — 文件名应为 \`${topic}.md\`,实为 \`$base\`"
      errors=$((errors+1))
    fi
  done
done < <(find "$ROOT/plan" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

# --- 总结 ---
if [[ $errors -eq 0 ]]; then
  echo -e "${GREEN}✓${NC} 命名规范: $checked 项全部通过"
  exit 0
else
  echo -e "${RED}✗ 命名规范: 发现 $errors 处违规 (检查 $checked 项)${NC}" >&2
  exit 1
fi