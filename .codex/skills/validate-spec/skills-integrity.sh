#!/usr/bin/env bash
#
# skills-integrity.sh: .codex/skills/ 目录的内部一致性自检。
#
# 它只检查 skill 目录本身, 不检查 spec 产物（产物由 scripts/check-*.sh 管）。
#
# 用法: bash .codex/skills/validate-spec/skills-integrity.sh [标签]
#
# 退出码:
#   0  PASS（可能有警告）
#   1  FAIL（有违规）
#
# 依赖: 只有 POSIX 工具（find / grep / sed / awk / sort）。不使用 ripgrep。
#
# Sweeps:
#   A  skill 正文引用的 scripts/*.{sh,py} 必须存在
#   B  §N(.M) 引用必须命中被引用文档的标题号
#   C  每个文件的 § 引用次数（信息项）
#   D  <repo>/path 交叉引用目标必须存在（可选层路径除外）
#   E  Tech Design 代际口径：必须写「默认 v4」，禁「默认 v3」「opt-in v4」
#   F  项目专属业务词零命中（模板不应带某个 fork 的业务名词）
#   G  零 em dash（U+2014）
#   H  每个 SKILL.md 的 front matter 键集合必须恰好是 name + description
#   I  不得残留 Slash Command 标题或 [MODE: ...] 标记
#   J  旧表述零命中（黑名单数据文件 legacy-wording.txt, 不在代码里写字面量）
#      + 占位式回写表述只允许出现在否定句里
#      + ssdctl 子命令名封闭（白名单 scan/criteria/gate/advance/queue/decide/evidence/verify）

set -uo pipefail

LABEL=${1:-}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SKILLS_DIR=$(cd "$SCRIPT_DIR/.." && pwd)
REPO_ROOT=$(cd "$SKILLS_DIR/../.." && pwd)

ERRORS=0
WARNS=0

if [ -t 1 ]; then
    GREEN=$(printf '\033[0;32m')
    YELLOW=$(printf '\033[0;33m')
    RED=$(printf '\033[0;31m')
    RESET=$(printf '\033[0m')
else
    GREEN=''; YELLOW=''; RED=''; RESET=''
fi

ok()    { printf '  %s[ok]%s   %s\n' "$GREEN" "$RESET" "$1"; }
warn()  { printf '  %s[warn]%s %s\n' "$YELLOW" "$RESET" "$1"; WARNS=$((WARNS + 1)); }
bad()   { printf '  %s[fail]%s %s\n' "$RED" "$RESET" "$1"; ERRORS=$((ERRORS + 1)); }
head2() { printf '\n== %s%s ==\n' "$1" "$LABEL"; }

# 被扫描的 skill 文件（排除本脚本自身）
scan_files() {
    find "$SKILLS_DIR" -type f \( -name '*.md' -o -name '*.sh' -o -name '*.py' \) \
        ! -name 'skills-integrity.sh' | sort
}

skill_md_files() {
    find "$SKILLS_DIR" -type f -name 'SKILL.md' | sort
}

heading_numbers() {
    grep -ohE '^#{1,4} [0-9]+(\.[0-9]+)*' "$1" 2>/dev/null \
        | sed -E 's/^#+ //' | sed -E 's/[^0-9.]//g' | sort -u
}

has_num() {
    printf '%s\n' "$1" | grep -qx "$2"
}

# ---------------------------------------------------------------- Sweep A
head2 'Sweep A: 引用的 scripts/* 必须存在'
missing_script=0
for f in $(scan_files); do
    for ref in $(grep -ohE 'scripts/[A-Za-z0-9_.-]+\.(sh|py)' "$f" 2>/dev/null | sort -u); do
        if [ ! -f "$REPO_ROOT/$ref" ]; then
            bad "DANGLING: ${f#$REPO_ROOT/} 引用 $ref, 但 $ref 不存在"
            missing_script=$((missing_script + 1))
        fi
    done
done
[ "$missing_script" -eq 0 ] && ok '所有引用的 scripts/*.{sh,py} 都存在'

# ---------------------------------------------------------------- Sweep B
head2 'Sweep B: §引用必须命中被引用文档的标题号'
AGENTS_NUMS=$(heading_numbers "$REPO_ROOT/AGENTS.md")
WORKFLOW_NUMS=''
[ -f "$REPO_ROOT/WORKFLOW.md" ] && WORKFLOW_NUMS=$(heading_numbers "$REPO_ROOT/WORKFLOW.md")

bad_section=0
for f in $(scan_files); do
    hits=$(grep -nE '§[0-9]+(\.[0-9]+)*' "$f" 2>/dev/null)
    [ -z "$hits" ] && continue
    missing=$(printf '%s\n' "$hits" | while IFS= read -r hit; do
        line=${hit#*:}
        nums="$AGENTS_NUMS"
        case "$line" in *WORKFLOW.md*) nums="$WORKFLOW_NUMS" ;; esac
        for sec in $(printf '%s' "$line" | grep -ohE '§[0-9]+(\.[0-9]+)*' | sed 's/§//' | sort -u); do
            has_num "$nums" "$sec" || printf '%s\n' "$sec"
        done
    done | sort -u)
    for sec in $missing; do
        bad "§$sec 在 ${f#$REPO_ROOT/} 中被引用, 但被引用文档没有对应的标题号"
        bad_section=$((bad_section + 1))
    done
done
[ "$bad_section" -eq 0 ] && ok '所有 §引用都命中被引用文档的标题号'

# ---------------------------------------------------------------- Sweep C
head2 'Sweep C: 每个文件的 §引用次数（信息项）'
for f in $(skill_md_files); do
    n=$(grep -ohE '§[0-9]+(\.[0-9]+)*' "$f" 2>/dev/null | wc -l | tr -d ' ')
    printf '  %s: %s 处\n' "${f#$SKILLS_DIR/}" "$n"
done

# ---------------------------------------------------------------- Sweep D
head2 'Sweep D: <repo>/path 交叉引用目标必须存在'
# 可选层: 目录不存在时该层的校验自动跳过, 因此交叉引用允许悬空
is_optional_path() {
    case "$1" in
        material/*|deep/*|test-business/*|docs/*|test_cases/_index.md) return 0 ;;
    esac
    return 1
}
missing_ref=0
for f in $(scan_files); do
    for ref in $(grep -ohE '<repo>/[A-Za-z0-9._/-]+' "$f" 2>/dev/null | sed 's|^<repo>/||' | sort -u); do
        is_optional_path "$ref" && continue
        if [ ! -e "$REPO_ROOT/$ref" ]; then
            bad "DEAD REF: ${f#$REPO_ROOT/} 引用 <repo>/$ref, 但目标不存在"
            missing_ref=$((missing_ref + 1))
        fi
    done
done
[ "$missing_ref" -eq 0 ] && ok '所有 <repo>/path 交叉引用目标都存在'

# ---------------------------------------------------------------- Sweep E
head2 'Sweep E: Tech Design 代际口径'
gen_bad=0
for f in $(scan_files); do
    if grep -qE '默认 v3|opt-in v4' "$f"; then
        bad "代际口径错误: ${f#$REPO_ROOT/} 出现「默认 v3」或「opt-in v4」"
        gen_bad=$((gen_bad + 1))
    fi
done
[ "$gen_bad" -eq 0 ] && ok '没有「默认 v3」/「opt-in v4」'
if grep -rqE '默认 v4' "$SKILLS_DIR"; then
    ok '存在「默认 v4」表述'
else
    bad '全目录找不到「默认 v4」表述'
fi
v3_top=0
for f in $(scan_files); do
    if grep -qE 'schema/tech_design/(decisions|api-contracts|scenario-mapping|quality|interactions)\.md' "$f"; then
        bad "顶层引用了 v3 模板: ${f#$REPO_ROOT/}（v3 模板在 schema/tech_design/v3/ 下）"
        v3_top=$((v3_top + 1))
    fi
done
[ "$v3_top" -eq 0 ] && ok '没有从 schema/tech_design/ 顶层引用 v3 模板'

# ---------------------------------------------------------------- Sweep F
head2 'Sweep F: 项目专属业务词零命中'
BUSINESS_WORDS='busy"ying|yu"que|store-order-"h5|requirement-"center|神"策|AR"MS|陈列"域|门店"订货|订货"草稿|品牌"切换|门店"切换'
word_hits=0
for f in $(scan_files); do
    if grep -qE "$BUSINESS_WORDS" "$f"; then
        bad "出现项目专属业务词: ${f#$REPO_ROOT/}"
        word_hits=$((word_hits + 1))
    fi
done
[ "$word_hits" -eq 0 ] && ok '没有项目专属业务词'

# ---------------------------------------------------------------- Sweep G
head2 'Sweep G: 零 em dash (U+2014)'
dash_hits=0
for f in $(scan_files); do
    if LC_ALL=C grep -q $'\xe2\x80\x94' "$f" 2>/dev/null; then
        bad "含 em dash (U+2014): ${f#$REPO_ROOT/}"
        dash_hits=$((dash_hits + 1))
    fi
done
[ "$dash_hits" -eq 0 ] && ok '没有 em dash'

# ---------------------------------------------------------------- Sweep H
head2 'Sweep H: front matter 键集合'
fm_bad=0
for f in $(skill_md_files); do
    keys=$(awk '
        NR == 1 && $0 != "---" { exit }
        NR == 1 { infm = 1; next }
        infm && $0 == "---" { exit }
        infm && /^[A-Za-z][A-Za-z0-9_-]*:/ { sub(/:.*/, "", $0); print $0 }
    ' "$f" | sort | tr '\n' ' ')
    expected='description name '
    if [ "$keys" != "$expected" ]; then
        bad "front matter 键集合错误: ${f#$SKILLS_DIR/} = [$keys], 期望 [$expected]"
        fm_bad=$((fm_bad + 1))
    fi

    # description 的值必须能被 YAML 解析: 纯量里出现 ": " 或 " #" 会直接解析失败
    desc_line=$(awk '
        NR == 1 && $0 != "---" { exit }
        NR == 1 { infm = 1; next }
        infm && $0 == "---" { exit }
        infm && /^description:/ { print; exit }
    ' "$f")
    case "$desc_line" in
        'description: >-'*|'description: >'*|'description: |-'*|'description: |'*)
            : # 块标量, 由 YAML 自己折行
            ;;
        '')
            bad "front matter 缺少 description: ${f#$SKILLS_DIR/}"
            fm_bad=$((fm_bad + 1))
            ;;
        *)
            value=${desc_line#description: }
            case "$value" in
                *': '*|*' # '*)
                    bad "description 含 ': ' 或 ' #', 不是合法 YAML 纯量: ${f#$SKILLS_DIR/}"
                    fm_bad=$((fm_bad + 1))
                    ;;
            esac
            ;;
    esac

    # name 必须等于所在目录名
    name_line=$(awk '
        NR == 1 && $0 != "---" { exit }
        NR == 1 { infm = 1; next }
        infm && $0 == "---" { exit }
        infm && /^name:/ { print; exit }
    ' "$f")
    name_val=${name_line#name: }
    dir_val=$(basename "$(dirname "$f")")
    if [ "$name_val" != "$dir_val" ]; then
        bad "front matter 的 name ($name_val) 与目录名 ($dir_val) 不一致: ${f#$SKILLS_DIR/}"
        fm_bad=$((fm_bad + 1))
    fi
done
[ "$fm_bad" -eq 0 ] && ok '每个 SKILL.md 的 front matter 恰好是 name + description'

# ---------------------------------------------------------------- Sweep I
head2 'Sweep I: 不得残留 Slash Command 段 / MODE 标记'
slash_bad=0
for f in $(scan_files); do
    if grep -qE '^#+ *Slash Command' "$f"; then
        bad "残留 Slash Command 标题: ${f#$REPO_ROOT/}"
        slash_bad=$((slash_bad + 1))
    fi
    if grep -qF '[MODE:' "$f"; then
        bad "残留 [MODE: ...] 标记: ${f#$REPO_ROOT/}"
        slash_bad=$((slash_bad + 1))
    fi
done
[ "$slash_bad" -eq 0 ] && ok '没有 Slash Command 标题, 也没有 [MODE: ...] 标记'

# ---------------------------------------------------------------- Sweep J
head2 'Sweep J: 旧表述零命中 + ssdctl 子命令名封闭'

# J1 旧口径: 命中 legacy-wording.txt 里的任意一条即违规.
#            黑名单是数据文件, 不写在代码里, 避免自查自污染.
#            命中行会连同行号一起打印, 便于定位.
WORDING_LIST="$SCRIPT_DIR/legacy-wording.txt"
OLD_PAT=''
if [ -f "$WORDING_LIST" ]; then
    OLD_PAT=$(awk '!/^[[:space:]]*#/ && NF { if (n++) printf "|"; printf "%s", $0 }' "$WORDING_LIST")
else
    bad "缺少旧表述黑名单数据文件: $WORDING_LIST"
fi
if [ -z "$OLD_PAT" ]; then
    bad "旧表述黑名单为空: $WORDING_LIST"
    OLD_PAT='ZZZ_NO_SUCH_WORDING_ZZZ'
fi
old_bad=0
for f in $(scan_files); do
    hits=$(grep -nE "$OLD_PAT" "$f" 2>/dev/null || true)
    [ -z "$hits" ] && continue
    bad "旧表述残留: ${f#$REPO_ROOT/}"
    printf '%s\n' "$hits" | sed 's/^/         /'
    old_bad=$((old_bad + 1))
done
[ "$old_bad" -eq 0 ] && ok '没有旧表述残留'

# J2 占位式「人工回写 / 待人工回写」: 只允许出现在否定句（不得 / 禁止 / 不写 / 不出现）里.
PH_PAT='人工[回]写'
ph_bad=0
for f in $(scan_files); do
    hits=$(grep -nE "$PH_PAT" "$f" 2>/dev/null || true)
    [ -z "$hits" ] && continue
    while IFS= read -r hit; do
        [ -z "$hit" ] && continue
        case "$hit" in
            *不得*|*禁止*|*不写*|*不出现*|*不该*|*勿*|*不能*) : ;;
            *) bad "占位式回写表述: ${f#$REPO_ROOT/}: $hit"; ph_bad=$((ph_bad + 1)) ;;
        esac
    done <<EOF
$hits
EOF
done
[ "$ph_bad" -eq 0 ] && ok '没有未加否定限定的占位式回写表述'

# J3 ssdctl 子命令白名单: 只能出现契约 §5 定义的 8 个子命令.
SSDCTL_CMDS='scan criteria gate advance queue decide evidence verify'
ssd_bad=0
for f in $(scan_files); do
    cmds=$(grep -ohE 'ssdctl(\.py)?[[:space:]]+[a-z][a-z-]*' "$f" 2>/dev/null | sed -E 's/.*[[:space:]]//' | sort -u || true)
    for c in $cmds; do
        case " $SSDCTL_CMDS " in
            *" $c "*) : ;;
            *) bad "未知 ssdctl 子命令 '$c': ${f#$REPO_ROOT/}"; ssd_bad=$((ssd_bad + 1)) ;;
        esac
    done
done
[ "$ssd_bad" -eq 0 ] && ok 'ssdctl 子命令名都在白名单内'

# ---------------------------------------------------------------- 汇总
printf '\n'
if [ "$ERRORS" -eq 0 ]; then
    printf 'RESULT: PASS (%s 项警告)\n' "$WARNS"
    exit 0
fi
printf 'RESULT: FAIL (%s 项违规, %s 项警告)\n' "$ERRORS" "$WARNS"
exit 1
