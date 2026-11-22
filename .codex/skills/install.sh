#!/usr/bin/env sh
#
# install.sh: 把本目录下的 skill 注册到宿主的 skills 根目录。
#
# 用法:
#   bash .codex/skills/install.sh                  # 注册到 ~/.codex/skills/
#   bash .codex/skills/install.sh --target <dir>   # 注册到指定目录
#   bash .codex/skills/install.sh --unregister     # 注销已注册的 skill
#
# 退出码:
#   0  成功
#   1  未找到任何 skill
#   2  参数错误
#
# 行为约定:
#   - 幂等: 同一目标重复执行, 结果一致
#   - 优先建符号链接; 目标系统不允许建链接时(Windows 无开发者模式)退回复制
#   - 目标已存在但不是本脚本装的 → 跳过并提示, 绝不覆盖用户文件
#   - 目标目录里的 .codex-skills-install-manifest 记录本脚本装了什么,
#     注销时据此清理(只删本脚本装的条目), 不误删用户自己的目录
#   - 注销另外会删掉指向本脚本 skills 目录的符号链接(即使没有 manifest 记录)

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

printf '注册目标: %s\n' "$TARGET"
for name in $SKILLS; do
    src="$SCRIPT_DIR/$name"
    link="$TARGET/$name"

    if [ -L "$link" ]; then
        current=$(readlink "$link")
        if [ "$current" = "$src" ]; then
            manifest_add "$name" symlink
            printf '  %s[ok]%s %s 已指向正确位置\n' "$GREEN" "$RESET" "$name"
            continue
        fi
        rm -f "$link"
        manifest_add "$name" symlink
        printf '  %s[update]%s %s 已重新指向 %s\n' "$GREEN" "$RESET" "$name" "$src"
        continue
    fi

    if [ -e "$link" ]; then
        if manifest_has "$name"; then
            # 本脚本上次装的副本: 刷新内容, 保持与仓内同步
            rm -rf -- "$link"
            mkdir -p "$link"
            cp -R "$src/." "$link/"
            manifest_add "$name" copy
            printf '  %s[update]%s %s 已刷新为最新副本\n' "$GREEN" "$RESET" "$name"
        else
            printf '  %s[skip]%s %s 已存在且不是本脚本安装的, 不覆盖\n' "$YELLOW" "$RESET" "$name"
        fi
        continue
    fi

    if ln -s "$src" "$link" 2>/dev/null; then
        if [ -L "$link" ]; then
            manifest_add "$name" symlink
            printf '  %s[ok]%s %s -> %s\n' "$GREEN" "$RESET" "$name" "$src"
        else
            # 某些 Windows 环境把 ln -s 降级成了复制
            manifest_add "$name" copy
            printf '  %s[ok]%s %s 已复制到 %s（该系统不支持符号链接）\n' "$GREEN" "$RESET" "$name" "$link"
        fi
    else
        mkdir -p "$link"
        cp -R "$src/." "$link/"
        manifest_add "$name" copy
        printf '  %s[ok]%s %s 已复制到 %s（符号链接创建失败）\n' "$GREEN" "$RESET" "$name" "$link"
    fi
done

exit 0
