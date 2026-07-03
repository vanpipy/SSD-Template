#!/bin/bash
# setup.sh — 注册 pos-wiki skills 到各种 agent 的 skills 目录
#
# 默认注册到:
#   ~/.claude/skills/    (Claude Code)
#   ~/.qoder/skills/     (Qoder)
#   ~/.pi/agent/skills/  (pi/agent)
#   ~/.cursor/skills/    (Cursor, 如存在)
#
# 用法:
#   bash pos-wiki/skills/setup.sh                    # 注册到默认目录
#   bash pos-wiki/skills/setup.sh --unregister       # 注销已注册 symlink
#   bash pos-wiki/skills/setup.sh --target <dir>     # 注册到指定目录

set -euo pipefail

# 颜色
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 默认目标目录(按优先级排列)
DEFAULT_TARGETS=(
  "$HOME/.claude/skills"
  "$HOME/.qoder/skills"
  "$HOME/.pi/agent/skills"
  "$HOME/.cursor/skills"
)

# 解析参数
unregister=false
custom_targets=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --unregister|-u)
      unregister=true
      shift
      ;;
    --target|-t)
      custom_targets+=("$2")
      shift 2
      ;;
    *)
      echo -e "${RED}✗ 未知参数: $1${NC}" >&2
      echo "用法: $0 [--unregister] [--target <dir>]" >&2
      exit 2
      ;;
  esac
done

# 收集 skill 目录(直接子目录中含 SKILL.md 的)
SKILLS=()
for entry in "$SCRIPT_DIR"/*; do
  [[ -d "$entry" ]] || continue
  [[ -f "$entry/SKILL.md" ]] || continue
  SKILLS+=("$(basename "$entry")")
done

if [[ ${#SKILLS[@]} -eq 0 ]]; then
  echo -e "${RED}✗ 在 $SCRIPT_DIR 下未找到任何 SKILL.md${NC}" >&2
  exit 1
fi

echo "📦 找到 ${#SKILLS[@]} 个 skills: ${SKILLS[*]}"
echo ""

# 决定目标目录
if [[ ${#custom_targets[@]} -gt 0 ]]; then
  TARGETS=("${custom_targets[@]}")
else
  TARGETS=("${DEFAULT_TARGETS[@]}")
fi

# 注册/注销
if [[ "$unregister" == true ]]; then
  echo "🗑️  注销模式"
  echo ""
  for skill in "${SKILLS[@]}"; do
    for target_dir in "${TARGETS[@]}"; do
      target="$target_dir/$skill"
      if [[ -L "$target" ]]; then
        rm "$target"
        echo -e "  ${YELLOW}[removed]${NC} $target"
      elif [[ -e "$target" ]]; then
        echo -e "  ${RED}[skip]${NC} $target 不是 symlink,跳过(避免误删)"
      else
        echo -e "  ${YELLOW}[skip]${NC} $target 不存在"
      fi
    done
  done
else
  echo "📍 注册到: ${TARGETS[*]}"
  echo ""

  for skill in "${SKILLS[@]}"; do
    src="$SCRIPT_DIR/$skill"
    for target_dir in "${TARGETS[@]}"; do
      target="$target_dir/$skill"

      # 创建目标目录(若不存在)
      mkdir -p "$target_dir"

      # 已存在处理
      if [[ -L "$target" ]]; then
        # 已是 symlink,检查指向
        current_src=$(readlink "$target")
        if [[ "$current_src" == "$src" ]]; then
          echo -e "  ${GREEN}[ok]${NC} $target -> $src (已存在,指向正确)"
        else
          echo -e "  ${YELLOW}[update]${NC} $target 当前指向 $current_src,更新为 $src"
          rm "$target"
          ln -s "$src" "$target"
        fi
      elif [[ -e "$target" ]]; then
        echo -e "  ${YELLOW}[skip]${NC} $target 已存在但不是 symlink,跳过(避免覆盖)"
      else
        # 创建新 symlink
        ln -s "$src" "$target"
        echo -e "  ${GREEN}[done]${NC} $target -> $src"
      fi
    done
  done
fi

echo ""
echo -e "${GREEN}✅ 完成${NC}"