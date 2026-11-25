#!/usr/bin/env bash
# check-repo-baseline.sh — 校验 Tech Design README 的「实现基线」表
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
# 可移植性(契约 M9):
#   - 不依赖 GNU `date -d` / BSD `date -j -f`; 两者都不可用时用 POSIX 历法近似换算,
#     并打印**降级提示**(该换算只影响「基线是否过期」的 ⚠ 判断)
#   - 不用 `find -mindepth/-maxdepth`
#
# 用法:
#   scripts/check-repo-baseline.sh [--json] [--root DIR] [--max-age-days N] [TARGET]
#   (--stage 不适用于本脚本:阶段相关必填项由 scripts/check-md-schema.py 判定;收到即退出 2)
#
# 退出码: 0=通过 1=违规 2=调用错误 / 环境错误

set -uo pipefail

SCRIPT_PATH=$0
SCRIPT_DIR=$(cd -- "$(dirname -- "$SCRIPT_PATH")" >/dev/null 2>&1 && pwd)
DEFAULT_ROOT=$(dirname -- "$SCRIPT_DIR")

JSON=0
ROOT=""
TARGET=""
MAX_AGE_DAYS=7
NO_COLOR=${NO_COLOR:-0}

while [ $# -gt 0 ]; do
  case "$1" in
    --json) JSON=1 ;;
    --root)
      [ $# -ge 2 ] || { printf '✗ --root 需要目录参数\n' >&2; exit 2; }
      ROOT="$2"; shift ;;
    --root=*) ROOT="${1#--root=}" ;;
    --stage|--stage=*)
      printf '%s: 本门禁与阶段无关;--stage 只对 scripts/check-md-schema.py 有效\n' "$SCRIPT_PATH" >&2
      exit 2
      ;;
    --max-age-days)
      [ $# -ge 2 ] || { printf '✗ --max-age-days 需要数字参数\n' >&2; exit 2; }
      MAX_AGE_DAYS="$2"; shift ;;
    --max-age-days=*) MAX_AGE_DAYS="${1#--max-age-days=}" ;;
    --help|-h)
      printf '用法: %s [--json] [--root DIR] [--max-age-days N] [TARGET]\n' "$SCRIPT_PATH"; exit 0 ;;
    -*) printf '✗ 未知参数: %s\n' "$1" >&2; exit 2 ;;
    *) [ -z "$TARGET" ] && TARGET="$1" || { printf '✗ 只能指定一个 TARGET\n' >&2; exit 2; } ;;
  esac
  shift
done

case "$MAX_AGE_DAYS" in
  ''|*[!0-9]*) printf '✗ --max-age-days 必须是整数: %s\n' "$MAX_AGE_DAYS" >&2; exit 2 ;;
esac

[ -n "$ROOT" ] || ROOT="$DEFAULT_ROOT"
if [ ! -d "$ROOT" ]; then
  printf '✗ --root 目录不存在: %s\n' "$ROOT" >&2
  exit 2
fi
ROOT=$(cd -- "$ROOT" >/dev/null 2>&1 && pwd -P)

# 相对 TARGET 一律按 ROOT 解析(与其余门禁脚本的 CLI 语义一致)
if [ -n "$TARGET" ]; then
  case "$TARGET" in
    /*) ;;
    *) TARGET="$ROOT/$TARGET" ;;
  esac
fi
AGENTS_FILE="$ROOT/AGENTS.md"

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

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

# --- 日期换算: 优先 GNU date -d, 其次 BSD date -j -f, 最后 POSIX 历法近似 ---
DATE_MODE=""
day_epoch() {
  local d="$1"
  if [ -z "$DATE_MODE" ]; then
    if date -d "$d" +%s >/dev/null 2>&1; then DATE_MODE="gnu"
    elif date -j -f "%Y-%m-%d" "$d" +%s >/dev/null 2>&1; then DATE_MODE="bsd"
    else DATE_MODE="posix"; fi
    if [ "$DATE_MODE" = "posix" ]; then
      note "当前环境的 date 不支持 -d / -j -f, 已降级为 POSIX 历法换算(仅影响「基线是否过期」的 ⚠ 判断, 误差约 ±1 天)"
    fi
  fi
  case "$DATE_MODE" in
    gnu) date -d "$d" +%s 2>/dev/null ;;
    bsd) date -j -f "%Y-%m-%d" "$d" +%s 2>/dev/null ;;
    posix)
      awk -v d="$d" 'BEGIN{
        split(d, a, "-");
        y=a[1]+0; m=a[2]+0; dd=a[3]+0;
        if (m <= 2) { y -= 1; m += 12 }
        era = int((y >= 0 ? y : y-399) / 400);
        yoe = y - era*400;
        doy = int((153*(m-3)+2)/5) + dd-1;
        doe = yoe*365 + int(yoe/4) - int(yoe/100) + doy;
        print (era*146097 + doe - 719468)*86400;
      }'
      ;;
  esac
}

# --- 解析 AGENTS.md §1.1「仓库清单」表 → 标识 → 本地路径 ---
REPO_PATHS=""
MAP_LOADED=0
parse_repo_map() {
  [ -f "$AGENTS_FILE" ] || return 0
  awk '
    /^#{1,4}[[:space:]]+1\.1[[:space:]]/ { sec=1; next }
    sec && /^#{1,3}[[:space:]]/ { sec=0 }
    !sec { next }
    /^\|/ {
      n=split($0, c, "|")
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

while IFS="$(printf '\t')" read -r kind k v; do
  case "$kind" in
    HDR) MAP_LOADED=1 ;;
    ROW)
      case "$v" in "—"|"-"|"") continue ;; esac
      REPO_PATHS="$REPO_PATHS $k=$v"
      ;;
  esac
done < <(parse_repo_map)

repo_path_of() {
  local key="$1" p
  p=$(printf '%s' "$REPO_PATHS" | tr ' ' '\n' | grep "^${key}=" | head -1 | cut -d= -f2-)
  [ -z "$p" ] && return 0
  case "$p" in
    /*) printf '%s' "$p" ;;
    ./*|../*) printf '%s/%s' "$ROOT" "${p#./}" ;;
    *) printf '%s/%s' "$ROOT" "$p" ;;
  esac
}

repo_registered() {
  case " $REPO_PATHS " in *" $1="*) return 0 ;; esac
  return 1
}

# --- 单个 TD README 校验 ---
CHECKED=0
check_readme() {
  local readme="$1" rel section rows repo branch sha date items status
  rel=${readme#"$ROOT"/}
  section=$(awk '
    /^```/ { fence = !fence; next }
    !fence && /^##[[:space:]]+实现基线/ { f=1; next }
    !fence && f && /^#{1,6}[[:space:]]/ { f=0 }
    f { print }
  ' "$readme" 2>/dev/null)

  if [ -z "$section" ]; then
    err "$rel — 缺少 \`## 实现基线\` 段 (AGENTS.md §1.6 门禁)"
    return 1
  fi

  if ! printf '%s\n' "$section" | grep -qE '^\|'; then
    if printf '%s\n' "$section" | grep -qE '不适用|N/A|无关联代码仓'; then
      note "$rel — 实现基线不适用(已声明), 跳过"
      return 0
    fi
    err "$rel — \`## 实现基线\` 段既无表格行也无「不适用」声明"
    return 1
  fi

  rows=0
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    case "$line" in \|*) ;; *) continue ;; esac
    case "$line" in \|*[:space:]-*) ;; esac
    printf '%s' "$line" | grep -qE '^\|[[:space:]]*:?-+' && continue

    row="${line#|}"
    row="${row%|}"
    IFS='|' read -r repo branch sha date items status <<< "$row"

    repo=$(trim "${repo//\`/}")
    branch=$(trim "${branch//\`/}")
    sha=$(trim "${sha//\`/}")
    date=$(trim "${date//\`/}")
    items=$(trim "${items//\`/}")
    status=$(trim "${status//\`/}")

    case "$repo" in "仓库"|repo|"") continue ;; esac

    rows=$((rows+1))
    CHECKED=$((CHECKED+1))

    if [ -z "$sha" ] || [ -z "$branch" ]; then
      err "$rel — \`$repo\` 缺分支或 SHA"
      continue
    fi
    if [ -z "$items" ]; then
      err "$rel — \`$repo\` 缺「核对项」"
    fi

    local d
    d=$(printf '%s\n' "$date" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
    if [ -z "$d" ]; then
      err "$rel — \`$repo\` 核对日期缺失或格式非 YYYY-MM-DD"
    fi

    case "$status" in
      *待补*|*TODO*|*✗*|*❌*)
        err "$rel — \`$repo\` 状态为 \`$status\`, 基线未完结"
        continue
        ;;
    esac

    # 状态 ○ = 不适用 / 跳过 → 不做仓存在性校验
    [ "$status" = "○" ] && continue

    if ! repo_registered "$repo"; then
      if [ "$MAP_LOADED" -eq 1 ]; then
        warn "$rel — 仓库标识 \`$repo\` 未在 AGENTS.md §1.1 登记, 跳过存在性校验"
      else
        warn "$rel — AGENTS.md §1.1 仓库清单不可解析, 跳过 \`$repo\` 存在性校验"
      fi
      continue
    fi

    local path
    path=$(repo_path_of "$repo")
    if ! git -C "$path" rev-parse --git-dir >/dev/null 2>&1; then
      warn "$rel — 仓库 \`$repo\` 本地未检出 ($path), 跳过存在性校验"
      continue
    fi
    if ! git -C "$path" cat-file -e "${sha}^{commit}" >/dev/null 2>&1; then
      err "$rel — \`$repo@$sha\` 在本地不存在"
      continue
    fi

    local sha_full ref="" head_full
    sha_full=$(git -C "$path" rev-parse "${sha}^{commit}")
    for candidate in "refs/remotes/origin/$branch" "refs/heads/$branch" "$branch"; do
      if git -C "$path" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
        ref="$candidate"; break
      fi
    done
    if [ -n "$ref" ]; then
      head_full=$(git -C "$path" rev-parse "$ref")
      if [ "$sha_full" != "$head_full" ]; then
        local head_short
        head_short=$(git -C "$path" rev-parse --short "$ref")
        warn "$rel — \`$repo\` 基线 \`$sha\` 落后于 \`$branch\` 头 \`$head_short\`(有意钉住请忽略)"
      fi
    fi

    if [ -n "$d" ]; then
      local epoch now age
      epoch=$(day_epoch "$d")
      now=$(date +%s)
      if printf '%s' "$epoch" | grep -Eq '^[0-9]+$' && [ "$epoch" -gt 0 ] 2>/dev/null; then
        age=$(( (now - epoch) / 86400 ))
        if [ "$age" -gt "$MAX_AGE_DAYS" ]; then
          warn "$rel — \`$repo\` 基线已 $age 天未复核(阈值 ${MAX_AGE_DAYS} 天)"
        fi
      fi
    fi
  done <<< "$section"

  if [ "$rows" -eq 0 ]; then
    err "$rel — \`## 实现基线\` 段没有有效表格行"
    return 1
  fi
  ok "$rel — 实现基线 $rows 行"
  return 0
}

# --- 目标解析与执行 ---
TD_READMES=""
has_any_artifact() {
  local f d dn bn
  if [ -d "$ROOT/prd" ]; then
    for f in "$ROOT"/prd/*/*.md; do
      [ -f "$f" ] || continue
      d=$(dirname -- "$f"); dn=$(basename -- "$d"); bn=$(basename -- "$f" .md)
      printf '%s' "$dn" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || continue
      printf '%s' "$bn" | grep -Eq '^[a-z0-9]+(-[a-z0-9]+)*$' || continue
      return 0
    done
  fi
  if [ -d "$ROOT/tech_design" ]; then
    for d in "$ROOT"/tech_design/*/; do
      [ -d "$d" ] || continue
      dn=$(basename -- "$d")
      printf '%s' "$dn" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$' || continue
      return 0
    done
  fi
  if [ -d "$ROOT/plan" ]; then
    for d in "$ROOT"/plan/*/; do
      [ -d "$d" ] || continue
      dn=$(basename -- "$d")
      printf '%s' "$dn" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$' || continue
      return 0
    done
  fi
  if [ -d "$ROOT/test_cases" ]; then
    for f in "$ROOT"/test_cases/*/*.md; do
      [ -f "$f" ] || continue
      d=$(dirname -- "$f"); dn=$(basename -- "$d"); bn=$(basename -- "$f" .md)
      printf '%s' "$dn" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' || continue
      case "$bn" in *-key-points) continue ;; esac
      return 0
    done
  fi
  return 1
}

if [ -n "$TARGET" ]; then
  if [ ! -e "$TARGET" ]; then
    printf '✗ TARGET 不存在: %s\n' "$TARGET" >&2
    exit 2
  fi
  case "$TARGET" in
    */README.md)
      check_readme "$TARGET"
      ;;
    *)
      if [ -d "$TARGET/tech_design" ]; then
        for d in "$TARGET"/tech_design/*/; do
          [ -d "$d" ] || continue
          dn=$(basename -- "$d")
          printf '%s' "$dn" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$' || continue
          d=${d%/}
          [ -f "$d/README.md" ] && check_readme "$d/README.md"
        done
      elif [ -f "$TARGET/README.md" ]; then
        check_readme "$TARGET/README.md"
      else
        note "未找到 tech_design/ 或 TD 目录, 跳过(无可校验的基线段)"
      fi
      ;;
  esac
else
  TD_COUNT=0
  if [ -d "$ROOT/tech_design" ]; then
    for d in "$ROOT"/tech_design/*/; do
      [ -d "$d" ] || continue
      dn=$(basename -- "$d")
      printf '%s' "$dn" | grep -Eq '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$' || continue
      d=${d%/}
      [ -f "$d/README.md" ] || continue
      TD_COUNT=$((TD_COUNT+1))
      check_readme "$d/README.md"
    done
  fi
  if [ "$TD_COUNT" -eq 0 ]; then
    if has_any_artifact; then
      note "tech_design 层没有 Tech Design 制品, 跳过实现基线校验(该层无制品)"
    else
      err "本仓没有任何规格产物,门禁无从校验"
    fi
  fi
fi

ERRC=${#ERRORS[@]}
WARNC=${#WARNINGS[@]}
if [ "$ERRC" -gt 0 ]; then STATUS="violation"; EXIT=1; else STATUS="pass"; EXIT=0; fi

if [ "$JSON" -eq 1 ]; then
  printf '{"script":"check-repo-baseline.sh","root":"%s","status":"%s","exit_code":%d,"error_count":%d,"warning_count":%d,"checked":%d,"errors":%s,"warnings":%s,"notes":%s}\n' \
    "$(printf '%s' "$ROOT" | json_escape)" "$STATUS" "$EXIT" "$ERRC" "$WARNC" "$CHECKED" \
    "$(json_str_array "${ERRORS[@]+"${ERRORS[@]}"}")" \
    "$(json_str_array "${WARNINGS[@]+"${WARNINGS[@]}"}")" \
    "$(json_str_array "${NOTES[@]+"${NOTES[@]}"}")"
else
  if [ "$ERRC" -gt 0 ]; then
    printf '✗ 实现基线校验: %d 项违规, %d 项警告, 共 %d 行\n' "$ERRC" "$WARNC" "$CHECKED"
  else
    ok "实现基线校验: $CHECKED 行全部通过 ($WARNC 项警告)"
  fi
fi
exit $EXIT
