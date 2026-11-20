#!/usr/bin/env bash
# check-repo-baseline.sh — 校验 Tech Design README 的「实现基线」表
#
# 目的:
#   防止 TD 以过期 commit 或错误分支作为实现结论(把已实现写成「待建」、
#   把无 DDL 写成结论而仓库已有建表脚本)。
#
# 规约 (见 AGENTS.md §1.6):
#   - 每个 tech_design/{date}-{topic}/README.md 必须包含 `## 实现基线` 段
#   - 表头固定 6 列: | 仓库 | 分支 | SHA | 核对日期 | 核对项 | 状态 |
#   - 「仓库」列填 AGENTS.md §1.1 登记的**标识**, 脚本据此解析本地路径
#   - SHA 必须能在本地代码仓解析; 分支头与 SHA 不一致 → ⚠(允许有意钉住)
#   - 核对日期超过 --max-age-days(默认 7 天)→ ⚠
#   - 状态为 待补/TODO/✗/❌ → ✗
#   - 0 代码仓项目写 `> 不适用: ...` 声明 → ○ 跳过, 不报错
#
# 仓库 → 本地路径的映射**从 AGENTS.md §1.1「本地路径」列解析**, 脚本内不硬编码任何仓名。
#
# 用法:
#   ./scripts/check-repo-baseline.sh                 # 检查整个仓库
#   ./scripts/check-repo-baseline.sh path/to/td-dir  # 检查单个 TD 目录
#   ./scripts/check-repo-baseline.sh --max-age-days 30
#
# 退出码:
#   0 = 全部通过(可含 ⚠)
#   1 = 发现 ✗
#   2 = 调用错误

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MAX_AGE_DAYS=7
TARGET=""
STORE_ROOT="$SCRIPT_ROOT"
AGENTS_FILE=""

usage() {
  sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'
}

# --- 定位被检 store 根目录与 AGENTS.md ---
# 被检目标可能是别的仓库(本仓只提供脚本), 因此 AGENTS.md 必须**从目标向上找**,
# 而不是固定用脚本所在仓。找不到时退化为脚本自身仓, 后续仓库解析全部降级为 ⚠。
find_store_root() {
  local start="$1" dir=""
  if [[ -f "$start" ]]; then
    dir="$(cd "$(dirname "$start")" && pwd)"
  else
    dir="$(cd "$start" && pwd 2>/dev/null)" || dir=""
  fi
  [[ -n "$dir" ]] || return 0
  local probe="$dir"
  while [[ -n "$probe" && "$probe" != "/" ]]; do
    if [[ -f "$probe/AGENTS.md" ]]; then
      printf '%s' "$probe"
      return 0
    fi
    probe="$(dirname "$probe")"
  done
  # 目标树内没有 AGENTS.md → 用脚本自身仓
  printf '%s' "$SCRIPT_ROOT"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max-age-days)
      [[ $# -ge 2 ]] || { usage >&2; exit 2; }
      MAX_AGE_DAYS="$2"
      shift 2
      ;;
    -h|--help) usage; exit 0 ;;
    -*) echo -e "${RED}✗ 未知参数: $1${NC}" >&2; usage >&2; exit 2 ;;
    *) TARGET="$1"; shift ;;
  esac
done

TARGET="${TARGET%/}"

# 未指定目标 → 默认检查脚本所在仓 (fork 后本仓即被检 store)
if [[ -z "$TARGET" ]]; then
  TARGET="$SCRIPT_ROOT"
fi

if [[ -e "$TARGET" ]]; then
  STORE_ROOT="$(find_store_root "$TARGET")"
fi
AGENTS_FILE="$STORE_ROOT/AGENTS.md"

errors=0
warnings=0
checked=0

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

day_epoch() {
  local d="$1"
  if date -d "$d" +%s >/dev/null 2>&1; then
    date -d "$d" +%s
  elif date -j -f "%Y-%m-%d" "$d" +%s >/dev/null 2>&1; then
    date -j -f "%Y-%m-%d" "$d" +%s
  else
    printf '0'
  fi
}

# --- 解析 AGENTS.md §1.1「仓库清单」表 → 标识 → 本地路径 ---
# 表格形态: | 标识 | 仓库 | Git URL | 本地路径 | 角色 | ... |
# 标识列可加粗 (**A**); 本地路径列可能是 ./ 或 ../foo/ 形式。
# §1.1 缺失或表头不匹配时返回空, 后续所有仓库解析降级为 ⚠ 跳过。
parse_repo_map() {
  [[ -f "$AGENTS_FILE" ]] || return 0
  awk '
    # 只在 §1.1 小节内取表 (§1.1 的 #### 子标题不算结束)
    /^#{1,4}[[:space:]]+1\.1[[:space:]]/ { sec=1; next }
    sec && /^#{1,3}[[:space:]]/ { sec=0 }
    !sec { next }
    /^\|/ {
      n=split($0, c, "|")
      # 表头探测 (hid/hlp 是本行临时量; id/lp 是确定下来的列号, 后续行复用)
      hid=-1; hlp=-1
      for (i=1; i<=n; i++) {
        v=c[i]; gsub(/^[ \t]+|[ \t]+$/,"",v); gsub(/\*\*/,"",v)
        if (v=="标识" && hid<0) hid=i
        else if (v=="本地路径" && hlp<0) hlp=i
      }
      if (hid>0 && hlp>0) { id=hid; lp=hlp; print "HDR"; next }
      if (id>0 && lp>0) {
        if (n<=id || n<=lp) next
        k=c[id]; v=c[lp]
        gsub(/^[ \t]+|[ \t]+$/,"",k); gsub(/\*\*/,"",k)
        gsub(/^[ \t]+|[ \t]+$/,"",v); gsub(/`/,"",v)
        if (k=="") next
        if (k ~ /^:?-+:?$/) next
        printf "ROW\t%s\t%s\n", k, v
      }
    }
  ' "$AGENTS_FILE"
}

declare -A repo_paths=()
map_loaded=false
while IFS=$'\t' read -r kind k v; do
  case "$kind" in
    HDR) map_loaded=true ;;
    ROW)
      [[ "$v" == "—" || "$v" == "-" || -z "$v" ]] && continue
      repo_paths["$k"]="$v"
      ;;
  esac
done < <(parse_repo_map)

# 标识 → 绝对本地路径 (相对路径按仓根解析; ./ 指本仓自身)
repo_dir() {
  local key="$1"
  local p="${repo_paths[$key]:-}"
  [[ -z "$p" ]] && { printf ''; return 0; }
  case "$p" in
    /*) printf '%s' "$p" ;;
    ./*|../*) printf '%s/%s' "$STORE_ROOT" "${p#./}" ;;
    *)  printf '%s/%s' "$STORE_ROOT" "$p" ;;
  esac
}

check_readme() {
  local readme="$1"
  local td_dir="$2"

  local section
  section=$(awk '
    /^```/ { fence = !fence; next }
    !fence && /^##[[:space:]]+实现基线/ { f=1; next }
    !fence && f && /^#{1,6}[[:space:]]/ { f=0 }
    f { print }
  ' "$readme" 2>/dev/null)

  if [[ -z "$section" ]]; then
    echo -e "${RED}✗${NC} $readme — 缺少 \`## 实现基线\` 段 (AGENTS.md §1.6 门禁)"
    errors=$((errors+1))
    return
  fi

  # 「不适用」声明: 无表格行 + 声明文本 → 按 ○ 跳过 (0 代码仓项目)
  if ! grep -qE '^\|' <<< "$section"; then
    if grep -qE '不适用|N/A|无关联代码仓' <<< "$section"; then
      echo -e "○ $readme — 实现基线不适用（已声明）"
    else
      echo -e "${RED}✗${NC} $readme — \`## 实现基线\` 段既无表格行也无「不适用」声明"
      errors=$((errors+1))
    fi
    return
  fi

  local rows=0
  while IFS= read -r line; do
    [[ "$line" == \|* ]] || continue
    [[ "$line" =~ ^\|[[:space:]]*:?-+ ]] && continue

    local row="${line#|}"
    row="${row%|}"
    local repo branch sha date items status
    IFS='|' read -r repo branch sha date items status <<< "$row"

    repo="$(trim "${repo//\`/}")"
    branch="$(trim "${branch//\`/}")"
    sha="$(trim "${sha//\`/}")"
    date="$(trim "${date//\`/}")"
    items="$(trim "${items//\`/}")"
    status="$(trim "${status//\`/}")"

    [[ "$repo" == "仓库" || "$repo" == "repo" ]] && continue
    [[ -z "$repo" ]] && continue

    rows=$((rows+1))
    checked=$((checked+1))

    if [[ -z "$sha" || -z "$branch" ]]; then
      echo -e "${RED}✗${NC} $readme — \`$repo\` 缺分支或 SHA"
      errors=$((errors+1))
      continue
    fi

    if [[ -z "$items" ]]; then
      echo -e "${RED}✗${NC} $readme — \`$repo\` 缺「核对项」"
      errors=$((errors+1))
    fi

    # 核对日期: 格式必须是 YYYY-MM-DD (与仓库是否检出无关)
    local d
    d="$(grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' <<< "$date" | head -1 || true)"
    if [[ -z "$d" ]]; then
      echo -e "${RED}✗${NC} $readme — \`$repo\` 核对日期缺失或格式非 YYYY-MM-DD"
      errors=$((errors+1))
    fi

    if [[ "$status" =~ 待补|TODO|✗|❌ ]]; then
      echo -e "${RED}✗${NC} $readme — \`$repo\` 状态为 \`$status\`，基线未完结"
      errors=$((errors+1))
    fi

    # 状态 ○ = 不适用 / 跳过 → 不做仓存在性校验
    if [[ "$status" == "○" ]]; then
      continue
    fi

    # 标识未在 AGENTS.md §1.1 登记 → ⚠ 并跳过存在性校验
    if [[ -z "${repo_paths[$repo]:-}" ]]; then
      if [[ "$map_loaded" == true ]]; then
        echo -e "${YELLOW}⚠${NC} $readme — 仓库标识 \`$repo\` 未在 AGENTS.md §1.1 登记，跳过存在性校验"
      else
        echo -e "${YELLOW}⚠${NC} $readme — AGENTS.md §1.1 仓库清单不可解析，跳过 \`$repo\` 存在性校验"
      fi
      warnings=$((warnings+1))
      continue
    fi

    local path
    path="$(repo_dir "$repo")"
    if ! git -C "$path" rev-parse --git-dir >/dev/null 2>&1; then
      echo -e "${YELLOW}⚠${NC} $readme — 仓库 \`$repo\` 本地未检出 ($path)，跳过存在性校验"
      warnings=$((warnings+1))
      continue
    fi

    if ! git -C "$path" cat-file -e "${sha}^{commit}" >/dev/null 2>&1; then
      echo -e "${RED}✗${NC} $readme — \`$repo@$sha\` 在本地不存在"
      errors=$((errors+1))
      continue
    fi

    # 分支头与基线 SHA 不一致 → ⚠ (允许有意钉住)
    local sha_full ref="" head_full
    sha_full="$(git -C "$path" rev-parse "${sha}^{commit}")"
    for candidate in "refs/remotes/origin/$branch" "refs/heads/$branch" "$branch"; do
      if git -C "$path" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
        ref="$candidate"
        break
      fi
    done
    if [[ -n "$ref" ]]; then
      head_full="$(git -C "$path" rev-parse "$ref")"
      if [[ "$sha_full" != "$head_full" ]]; then
        local head_short
        head_short="$(git -C "$path" rev-parse --short "$ref")"
        echo -e "${YELLOW}⚠${NC} $readme — \`$repo\` 基线 \`$sha\` 落后于 \`$branch\` 头 \`$head_short\`（有意钉住请忽略）"
        warnings=$((warnings+1))
      fi
    fi

    # 核对日期新鲜度 (格式已在前面校验过)
    if [[ -n "$d" ]]; then
      local epoch now age
      epoch="$(day_epoch "$d")"
      now="$(date +%s)"
      if [[ "$epoch" =~ ^[0-9]+$ ]] && (( epoch > 0 )); then
        age=$(( (now - epoch) / 86400 ))
        if (( age > MAX_AGE_DAYS )); then
          echo -e "${YELLOW}⚠${NC} $readme — \`$repo\` 基线已 $age 天未复核（阈值 ${MAX_AGE_DAYS} 天）"
          warnings=$((warnings+1))
        fi
      fi
    fi
  done <<< "$section"

  if (( rows == 0 )); then
    echo -e "${RED}✗${NC} $readme — \`## 实现基线\` 段没有有效表格行"
    errors=$((errors+1))
  else
    echo -e "${GREEN}✓${NC} $readme — 实现基线 $rows 行"
  fi
}

if [[ -f "$TARGET" && "$(basename "$TARGET")" == "README.md" ]]; then
  # 显式指定了 README.md 文件 → 当作单个 TD 的 README 校验
  check_readme "$TARGET" "$(dirname "$TARGET")"
elif [[ -d "$TARGET" && -d "$TARGET/tech_design" ]]; then
  # 仓根或含 tech_design/ 的目录 → 扫描全部 TD README
  while IFS= read -r readme; do
    check_readme "$readme" "$(dirname "$readme")"
  done < <(find "$TARGET/tech_design" -mindepth 2 -maxdepth 2 -name README.md -type f 2>/dev/null | sort)
elif [[ -d "$TARGET" && -f "$TARGET/README.md" && "$(basename "$TARGET")" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}- ]]; then
  # 单个 TD 目录 (tech_design/{date}-{topic}/)
  check_readme "$TARGET/README.md" "$TARGET"
elif [[ -d "$TARGET" ]]; then
  echo -e "${YELLOW}○${NC} 未找到 tech_design/ 或 TD 目录，跳过（无可校验的基线段）"
else
  echo -e "${RED}✗ 路径不存在: $TARGET${NC}" >&2
  exit 2
fi

echo "---"
if (( errors > 0 )); then
  echo -e "${RED}✗ 实现基线校验: $errors 项违规, $warnings 项警告, 共 $checked 行${NC}"
  exit 1
fi

echo -e "${GREEN}✓ 实现基线校验: $checked 行全部通过${NC} ($warnings 项警告)"
exit 0
