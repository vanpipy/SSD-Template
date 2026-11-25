#!/usr/bin/env sh
#
# install.sh: 把本目录下的 skill 注册到宿主的 skills 根目录。
#
# 用法:
#   bash .agents/skills/install.sh                  # 注册到 ~/.codex/skills/
#   bash .agents/skills/install.sh --target <dir>   # 注册到指定目录
#   bash .agents/skills/install.sh --unregister     # 注销已注册的 skill
#
# 退出码:
#   0  成功（全部 skill 都已安装）
#   1  未找到任何 skill
#   2  参数错误
#   3  安装未完成: 有 skill 因目标冲突未安装, 或有 skill 安装失败
#      （冲突 = 目标已存在且不是本脚本装的; 详见末尾汇总里逐个列出的名字）
#
# 行为约定:
#   - 幂等: 同一目标重复执行, 结果一致
#   - 优先建符号链接; 目标系统不允许建链接时(Windows 无开发者模式)退回复制
#   - 目标已存在但不是本脚本装的 → 绝不覆盖用户文件; 该 skill 记为「未安装」,
#     在当场逐行显式点名, 并在末尾汇总里再列一次, 退出码为 3; 不做静默跳过
#   - 注册/刷新路径一律不删除目标目录里的任何东西: 刷新只做拷贝覆盖,
#     目标里源仓没有的文件(用户自己放的)会保留, 并在输出里说明「已保留」。
#     代价: 源仓里已经删掉的文件会残留在目标目录(不再被清掉); 用户文件优先。
#     唯一的删除动作在 --unregister 分支, 且只删本脚本装的条目。
#   - 目标目录里的 .codex-skills-install-manifest 记录本脚本装了什么,
#     注销时据此清理(只删本脚本装的条目), 不误删用户自己的目录
#   - 注销另外会删掉指向本脚本 skills 目录的符号链接(即使没有 manifest 记录)
#   - 每次注册结束都会打印一份汇总: 已安装 / 未安装 / 失败;
#     未安装与失败的 skill 逐行列名, 已安装的在一行列出

set -eu

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
DEFAULT_TARGET="$HOME/.codex/skills"
MANIFEST_NAME=".codex-skills-install-manifest"

GREEN=''
YELLOW=''
RED=''
RESET=''
if [ -t 1 ]; then
    GREEN=$(printf '\033[0;32m')
    YELLOW=$(printf '\033[0;33m')
    RED=$(printf '\033[0;31m')
    RESET=$(printf '\033[0m')
fi

usage() {
    printf '用法: %s [--target <dir>] [--unregister]\n' "$(basename "$0")" >&2
    printf '  --target <dir>   注册目标目录（默认 %s）\n' "$DEFAULT_TARGET" >&2
    printf '  --unregister     注销已注册的 skill\n' >&2
}

MODE='install'
TARGET="$DEFAULT_TARGET"

while [ $# -gt 0 ]; do
    case "$1" in
        --target|-t)
            if [ $# -lt 2 ]; then
                printf '%s错误: --target 需要一个目录参数\n' "$RED" >&2
                usage
                exit 2
            fi
            TARGET="$2"
            shift 2
            ;;
        --target=*)
            TARGET="${1#--target=}"
            shift
            ;;
        --unregister|-u)
            MODE='unregister'
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf '%s错误: 未知参数 %s\n' "$RED" "$1" >&2
            usage
            exit 2
            ;;
    esac
done

# 发现 skill: 本目录的直接子目录且含 SKILL.md
SKILLS=''
for dir in "$SCRIPT_DIR"/*/; do
    [ -d "$dir" ] || continue
    name=$(basename "$dir")
    [ -f "$dir/SKILL.md" ] || continue
    SKILLS="$SKILLS $name"
done

if [ -z "$(printf '%s' "$SKILLS" | tr -d ' ')" ]; then
    printf '%s未找到任何 skill（期望 %s/<name>/SKILL.md）\n' "$RED" "$SCRIPT_DIR" >&2
    exit 1
fi

MANIFEST="$TARGET/$MANIFEST_NAME"

manifest_mode() {
    # 输出某个 skill 在 manifest 里记录的安装方式（symlink / copy），没有则空
    [ -f "$MANIFEST" ] || return 0
    awk -v n="$1" '$1 == n { print $2 }' "$MANIFEST"
}

manifest_has() {
    [ -f "$MANIFEST" ] || return 1
    awk -v n="$1" '$1 == n { found = 1 } END { exit found ? 0 : 1 }' "$MANIFEST"
}

manifest_add() {
    # 追加或更新一条记录
    tmp="$MANIFEST.tmp.$$"
    if [ -f "$MANIFEST" ]; then
        awk -v n="$1" -v m="$2" '$1 != n' "$MANIFEST" > "$tmp"
    else
        : > "$tmp"
    fi
    printf '%s %s\n' "$1" "$2" >> "$tmp"
    mv "$tmp" "$MANIFEST"
}

manifest_remove() {
    [ -f "$MANIFEST" ] || return 0
    tmp="$MANIFEST.tmp.$$"
    awk -v n="$1" '$1 != n' "$MANIFEST" > "$tmp"
    mv "$tmp" "$MANIFEST"
}

safe_name() {
    case "$1" in
        ''|.|..) return 1 ;;
        */*|*\\*) return 1 ;;
    esac
    return 0
}

has_items() {
    # 列表变量里是否至少有一项
    [ -n "$(printf '%s' "$1" | tr -d ' ')" ]
}

count_items() {
    # 列表变量里的项数
    n=0
    for item in $1; do
        n=$((n + 1))
    done
    printf '%s' "$n"
}

if [ "$MODE" = 'unregister' ]; then
    printf '注销目标: %s\n' "$TARGET"
    for name in $SKILLS; do
        link="$TARGET/$name"
        safe_name "$name" || { printf '  %s[skip]%s 非法名称 %s\n' "$YELLOW" "$RESET" "$name"; continue; }

        mode=$(manifest_mode "$name")
        if [ -L "$link" ]; then
            rm -f "$link"
            manifest_remove "$name"
            printf '  %s[ok]%s 已注销符号链接 %s\n' "$GREEN" "$RESET" "$name"
            continue
        fi
        if [ "$mode" = 'copy' ] && [ -d "$link" ]; then
            rm -rf -- "$link"
            manifest_remove "$name"
            printf '  %s[ok]%s 已注销复制目录 %s\n' "$GREEN" "$RESET" "$name"
            continue
        fi
        if [ ! -e "$link" ]; then
            manifest_remove "$name"
            printf '  %s[skip]%s %s 不存在\n' "$YELLOW" "$RESET" "$name"
            continue
        fi
        printf '  %s[skip]%s %s 不是本脚本安装的, 不删除\n' "$YELLOW" "$RESET" "$name"
    done
    if [ -f "$MANIFEST" ] && [ ! -s "$MANIFEST" ]; then
        rm -f "$MANIFEST"
    fi
    exit 0
fi

mkdir -p "$TARGET"

# 注册结果分三类: 已安装 / 未安装(目标冲突) / 失败
INSTALLED=''
NOT_INSTALLED=''
FAILED=''

printf '注册目标: %s\n' "$TARGET"
for name in $SKILLS; do
    src="$SCRIPT_DIR/$name"
    link="$TARGET/$name"

    if [ -L "$link" ]; then
        current=$(readlink "$link")
        if [ "$current" = "$src" ]; then
            manifest_add "$name" symlink
            INSTALLED="$INSTALLED $name"
            printf '  %s[ok]%s %s 已指向正确位置\n' "$GREEN" "$RESET" "$name"
            continue
        fi
        rm -f "$link"
        manifest_add "$name" symlink
        INSTALLED="$INSTALLED $name"
        printf '  %s[update]%s %s 已重新指向 %s\n' "$GREEN" "$RESET" "$name" "$src"
        continue
    fi

    if [ -e "$link" ]; then
        if manifest_has "$name"; then
            # 本脚本上次装的副本: 刷新内容, 保持与仓内同步。
            # 只做拷贝覆盖, 不预先删除目标目录; 目标里源仓没有的文件(用户自己放的)
            # 必须保留。删除动作只允许出现在 unregister 分支。
            if mkdir -p "$link" && cp -R "$src/." "$link/"; then
                manifest_add "$name" copy
                INSTALLED="$INSTALLED $name"
                printf '  %s[update]%s %s 已刷新为最新副本(目标里源仓没有的文件已保留)\n' "$GREEN" "$RESET" "$name"
            else
                FAILED="$FAILED $name"
                printf '  %s[失败]%s %s 刷新副本失败, 未安装\n' "$RED" "$RESET" "$name"
            fi
        else
            # 冲突: 目标已存在且不是本脚本装的。绝不覆盖用户文件, 但必须显式点名,
            # 否则使用者会以为装好了。参见文件头「行为约定」。
            NOT_INSTALLED="$NOT_INSTALLED $name"
            printf '  %s[未安装]%s %s 目标已存在且不是本脚本安装的, 已跳过、未覆盖、未安装\n' "$RED" "$RESET" "$name"
            printf '        原因: %s 已存在, 且不在 %s 里(不是本脚本装的), 为保护用户文件不覆盖\n' "$link" "$MANIFEST_NAME"
            printf '        处理: 手动处理该目录(改名或删除)后重跑, 或用 --target <其它目录> 换一个目标\n'
        fi
        continue
    fi

    if ln -s "$src" "$link" 2>/dev/null; then
        if [ -L "$link" ]; then
            manifest_add "$name" symlink
            INSTALLED="$INSTALLED $name"
            printf '  %s[ok]%s %s -> %s\n' "$GREEN" "$RESET" "$name" "$src"
        else
            # 某些 Windows 环境把 ln -s 降级成了复制
            manifest_add "$name" copy
            INSTALLED="$INSTALLED $name"
            printf '  %s[ok]%s %s 已复制到 %s（该系统不支持符号链接）\n' "$GREEN" "$RESET" "$name" "$link"
        fi
    else
        if mkdir -p "$link" && cp -R "$src/." "$link/"; then
            manifest_add "$name" copy
            INSTALLED="$INSTALLED $name"
            printf '  %s[ok]%s %s 已复制到 %s（符号链接创建失败）\n' "$GREEN" "$RESET" "$name" "$link"
        else
            FAILED="$FAILED $name"
            printf '  %s[失败]%s %s 复制失败, 未安装\n' "$RED" "$RESET" "$name"
        fi
    fi
done

printf '\n'
printf '===== 安装汇总 =====\n'
printf '目标: %s\n' "$TARGET"
printf '已安装 (%s):' "$(count_items "$INSTALLED")"
if has_items "$INSTALLED"; then
    for name in $INSTALLED; do
        printf ' %s' "$name"
    done
fi
printf '\n'
if has_items "$NOT_INSTALLED"; then
    printf '%s未安装 (%s):%s\n' "$RED" "$(count_items "$NOT_INSTALLED")" "$RESET"
    for name in $NOT_INSTALLED; do
        printf '    - %s (目标已存在且不是本脚本安装的, 未覆盖)\n' "$name"
    done
else
    printf '未安装 (0): 无\n'
fi
if has_items "$FAILED"; then
    printf '%s失败 (%s):%s\n' "$RED" "$(count_items "$FAILED")" "$RESET"
    for name in $FAILED; do
        printf '    - %s (安装失败, 见上方该 skill 的输出)\n' "$name"
    done
else
    printf '失败 (0): 无\n'
fi
printf '===================\n'

if has_items "$NOT_INSTALLED" || has_items "$FAILED"; then
    exit 3
fi
exit 0
