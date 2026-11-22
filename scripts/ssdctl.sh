#!/usr/bin/env bash
# ssdctl.sh — `scripts/ssdctl.py` 的解释器解析包装器(仓内状态/调度的唯一入口)
#
# 背景(实施契约 §5 / §8):
#   仓内唯一的状态与调度入口是 `scripts/ssdctl.py`(只用 Python 3 标准库)。但不同机器上
#   `python` 未必可用 —— Windows 的 Microsoft Store 占位符会命中 `exit 9009`
#   (命令存在但不是解释器), 而 `python3` 只在 POSIX 机器上有。若文档直接写
#   `python scripts/ssdctl.py ...`, agent 在本机跑第一条命令就会失败, 然后退回去
#   手改状态行 —— 那正是本轮要禁止的行为(INV-4 / 硬禁止「不得手改状态行」)。
#   本包装器负责挑一个**真能跑**的 Python 3, 让文档与 skill 只有一种调用形态:
#   `bash scripts/ssdctl.sh <子命令> ...`
#
# 解析顺序(第一个通过 `-c 'import sys'` 自检的胜出):
#   1. $SSDCTL_PYTHON                        显式覆盖(绝对路径或可执行名)
#   2. python3                               POSIX
#   3. python                                需自检(排除 Store 占位符)
#   4. py -3                                 Windows Python Launcher
#   5. ~/.dsh/dsh-runtimes/*/dependencies/python/python.exe
#                                            DeepSeek Harness 运行时自带解释器
#
# 退出码: 透传 ssdctl.py 的 0=通过 / 1=不通过 / 2=用法或环境错误(INV-7);
#         找不到任何可用解释器时 exit 2(环境错误), 不静默继续。
#
# 用法:
#   bash scripts/ssdctl.sh scan [--json] [--layer L] [--check]
#   bash scripts/ssdctl.sh criteria <artifact>
#   bash scripts/ssdctl.sh gate
#   bash scripts/ssdctl.sh advance <artifact> --to Ready [--dry-run]
#   bash scripts/ssdctl.sh queue <artifact>
#   bash scripts/ssdctl.sh decide --artifact <path> --action approve --actor <name> --reason <text>
#   bash scripts/ssdctl.sh evidence [--artifact <path>]
#   bash scripts/ssdctl.sh verify <artifact>

set -uo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"

SCRIPT_PATH=$0
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$SCRIPT_PATH")" && pwd -P)
TARGET="$SCRIPT_DIR/ssdctl.py"

if [ ! -f "$TARGET" ]; then
  echo "✗ 找不到 ssdctl.py: $TARGET" >&2
  exit 2
fi

# 自检: 候选解释器必须真的能 import sys(排除 Store 占位符这类空壳命令)
probe() {
  "$@" -c 'import sys' >/dev/null 2>&1
}

PY_CMD=()

if [ -n "${SSDCTL_PYTHON:-}" ]; then
  if probe "$SSDCTL_PYTHON"; then
    PY_CMD=("$SSDCTL_PYTHON")
  else
    echo "✗ SSDCTL_PYTHON 指向的解释器不可用: $SSDCTL_PYTHON" >&2
    exit 2
  fi
fi

if [ ${#PY_CMD[@]} -eq 0 ] && command -v python3 >/dev/null 2>&1 && probe python3; then
  PY_CMD=(python3)
fi

if [ ${#PY_CMD[@]} -eq 0 ] && command -v python >/dev/null 2>&1 && probe python; then
  PY_CMD=(python)
fi

if [ ${#PY_CMD[@]} -eq 0 ] && command -v py >/dev/null 2>&1 && probe py -3; then
  PY_CMD=(py -3)
fi

if [ ${#PY_CMD[@]} -eq 0 ]; then
  for cand in \
    "$HOME"/.dsh/dsh-runtimes/*/dependencies/python/python.exe \
    "$HOME"/.dsh/dsh-runtimes/*/dependencies/python/python3 \
    "$HOME"/.dsh/dsh-runtimes/*/dependencies/python/bin/python3
  do
    [ -f "$cand" ] || continue
    if probe "$cand"; then
      PY_CMD=("$cand")
      break
    fi
  done
fi

if [ ${#PY_CMD[@]} -eq 0 ]; then
  echo "✗ 找不到可用的 Python 3 解释器 —— ssdctl 无法运行" >&2
  echo "  依次尝试过: \$SSDCTL_PYTHON / python3 / python / py -3 / ~/.dsh/dsh-runtimes/*/dependencies/python/python.exe" >&2
  echo "  显式指定: SSDCTL_PYTHON=/path/to/python bash scripts/ssdctl.sh <子命令>" >&2
  exit 2
fi

exec "${PY_CMD[@]}" "$TARGET" "$@"
