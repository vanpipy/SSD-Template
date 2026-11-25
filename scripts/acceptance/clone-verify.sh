#!/usr/bin/env bash
# clone-verify.sh — 对已提交的 HEAD 做一次干净克隆验证
#
# 断言 A1(脚本自足):克隆内的**脚本**(py/sh/yml)不得引用编排目录内容,也不得引用已迁出的文档目录
#   - 编排目录 = 仓根下的 `.swarm`(被 .gitignore 排除,不入库)
#   - 2026-11-24 起仓内不再保留过程文档目录;过程与契约补充文档在编排目录里
#   正则写作 `\.swarm[/]` 与 `docs[/]`(斜杠放进字符组)—— 是为了让本文件自身不含
#   「点+swarm+斜杠」「docs+斜杠」那两个字面串,否则本脚本会被自己的断言判为违规。
#   两种写法匹配等价。本文件自身再用 pathspec 排除(`:!scripts/acceptance/clone-verify.sh`)。
#   白名单(2 条,均为「跳过编排目录」的实现细节,不是对文件的引用):
#     scripts/check-doc-links.py  —— walk_md() 的 skip_dirs
#     scripts/lib/commands.py    —— REPO_TEXT_SKIP_PARTS 的 skip parts
#   判定按**文件路径**做(不是按命中条数):白名单文件里命中多少行都放行;
#   白名单之外的任何受控脚本出现这两类路径即失败,并打印全部越界行。
#
# 断言 A2(指针可读):仓内 **md** 若提到编排目录,同一行必须带「编排目录」或「不入库」标注
#   —— 读者必须一眼看出那是仓外指针,不是仓内文件。
#
# 断言 B(零件齐全):仓内规范真源与验收工具链必须都在克隆内 —— 新克隆的仓不缺零件。
#
# 断言 C(旧目录已清):克隆内不得再出现已迁出的文档目录。
#
# 用法: bash scripts/acceptance/clone-verify.sh [clone_src] [dest_dir]
#   clone_src  默认**当前仓**(脚本自身位置推导)—— 克隆的是它的**已提交 HEAD**
#   dest_dir   默认当前仓的同级目录 _verify-merge2
# 源仓不再写死一条机器相关的 URL:git 直接吃本地路径,比拼 URL 更不容易在
# Windows / POSIX 之间走形(MSYS 风格的 /d/... 拼成 URL 后不是合法的 Windows 文件 URL)。
set -u

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${1:-$REPO_ROOT}"
DEST="${2:-$(dirname "$REPO_ROOT")/_verify-merge2}"

WHITELIST="scripts/check-doc-links.py scripts/lib/commands.py"

REQUIRED="
WORKFLOW.md
AGENTS.md
README.md
schema/criteria.json
scripts/acceptance/a17-e2e.sh
scripts/acceptance/agent-first-acceptance.py
scripts/acceptance/clone-verify.sh
scripts/acceptance/recheck.sh
scripts/acceptance/run-all-gates.sh
scripts/tests/fixtures/artifacts/uncovered-ac5-prd.md
"

rm -rf "$DEST"
git clone --depth 1 "$SRC" "$DEST" >/dev/null 2>&1 || { echo "CLONE FAILED: $SRC"; exit 1; }
cd "$DEST" || exit 1
echo "HEAD: $(git log --oneline -1)"
echo "root md: $(ls *.md | tr '\n' ' ')"
fail=0

# ------------------------------------------------------------ 断言 A1
hits=$(git grep -n -e '\.swarm[/]' -e 'docs[/]' -- '*.py' '*.sh' '*.yml' ':!scripts/acceptance/clone-verify.sh' 2>/dev/null)
hit_files=$(printf '%s\n' "$hits" | awk -F: 'NF>=3 {print $1}' | sort -u)
offenders=""
for f in $hit_files; do
  case " $WHITELIST " in
    *" $f "*) ;;
    *) offenders="$offenders $f" ;;
  esac
done
if [ -n "$offenders" ]; then
  echo "✗ 断言A1 失败: 受控脚本引用了编排目录路径或已迁出的文档目录:"
  printf '%s\n' "$hits" | awk -F: -v ofs=" $offenders " 'index(ofs, " " $1 " ") {print "    " $0}'
  fail=1
else
  n_hit=0
  n_lines=0
  for f in $hit_files; do
    n_hit=$((n_hit + 1))
    c=$(printf '%s\n' "$hits" | awk -F: -v t="$f" 'NF>=3 && $1 == t' | wc -l)
    n_lines=$((n_lines + c))
  done
  echo "✓ 断言A1 通过: 白名单外 0 处越界引用(白名单内命中文件数=$n_hit, 命中行数=$n_lines)"
fi

# ------------------------------------------------------------ 断言 A2
md_hits=$(git grep -n '\.swarm[/]' -- '*.md' 2>/dev/null)
if [ -n "$md_hits" ]; then
  unlabeled=$(printf '%s\n' "$md_hits" | grep -v -e '编排目录' -e '不入库')
else
  unlabeled=""
fi
if [ -n "$unlabeled" ]; then
  echo "✗ 断言A2 失败: 仓内 md 提到编排目录但同句没有「编排目录」/「不入库」标注:"
  printf '%s\n' "$unlabeled" | sed 's/^/    /'
  fail=1
else
  n_md=0
  [ -n "$md_hits" ] && n_md=$(printf '%s\n' "$md_hits" | wc -l)
  echo "✓ 断言A2 通过: 编排目录指针 $n_md 行,全部带标注"
fi

# ------------------------------------------------------------ 断言 B
missing=""
for p in $REQUIRED; do
  [ -f "$p" ] || missing="$missing $p"
done
if [ -n "$missing" ]; then
  echo "✗ 断言B 失败: 克隆内缺失受控文件:"
  for p in $missing; do echo "    $p"; done
  fail=1
else
  n_req=0
  for p in $REQUIRED; do n_req=$((n_req + 1)); done
  echo "✓ 断言B 通过: $n_req 个受控文件全部存在于克隆内"
fi

# ------------------------------------------------------------ 断言 C
if [ -d docs ]; then
  echo "✗ 断言C 失败: 克隆内仍存在已迁出的文档目录"
  fail=1
else
  echo "✓ 断言C 通过: 克隆内无已迁出的文档目录"
fi

# ------------------------------------------------------------ 既有门禁
# 门禁清单的唯一真源是 scripts/lib/commands.py 的 GATE_SCRIPTS。
# 这里不再自带第二份清单 —— 统一消费 `ssdctl gate --json`。
PY="$(bash scripts/ssdctl.sh --python)"
gate_json="$(mktemp)"
if bash scripts/ssdctl.sh gate --json >"$gate_json" 2>/dev/null; then
  gate_rc=0
else
  gate_rc=$?
fi
if [ -s "$gate_json" ]; then
  "$PY" - "$gate_json" <<'PYEOF'
import json, sys

try:  # 输出显式写 UTF-8 + LF,不用平台默认编码(中文 Windows 的默认编码是 GBK)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="\n")
except AttributeError:  # Python < 3.7 没有 reconfigure
    pass

data = json.load(open(sys.argv[1], encoding="utf-8"))
for g in data["gates"]:
    name = g["script"].replace("scripts/", "").rsplit(".", 1)[0]
    print("%s rc=%s bytes=%s" % (name, g["exit_code"], g["stdout_bytes"]))
PYEOF
else
  echo "(gate --json 没有输出 JSON —— 下面是文本模式的输出)"
  bash scripts/ssdctl.sh gate 2>&1 | sed 's/^/    | /'
fi
rm -f "$gate_json"
echo "ssdctl gate rc=$gate_rc"
[ "$gate_rc" -ne 0 ] && fail=1
bash scripts/ssdctl.sh scan --check >/dev/null 2>&1 || { echo "scan --check FAILED"; fail=1; }
"$PY" scripts/sync-prd.py >/dev/null 2>&1
drift=$(git status --porcelain -- README.md material/)
echo "drift after sync-prd: ${drift:-<none>}"
[ -n "$drift" ] && fail=1
ut_out="$("$PY" -m unittest discover -s scripts/tests -t scripts/tests 2>&1)"
ut_rc=$?
printf '%s\n' "$ut_out" | tail -3
if [ "$ut_rc" -ne 0 ]; then
  echo "✗ 单元测试失败 (rc=$ut_rc)"
  fail=1
fi
cd "$REPO_ROOT" && rm -rf "$DEST"
echo "CLONE VERIFY fail=$fail"
exit $fail
