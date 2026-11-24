#!/usr/bin/env bash
# clone-verify.sh — 对已提交的 HEAD 做一次干净克隆验证
#
# 断言 A(F1):克隆内**受版本控制的文件不得引用未跟踪的编排目录路径**
#   (编排目录 = 仓根下的 `.swarm`,被 .gitignore 排除;下文的正则写作 `\.swarm[/]`
#    —— 斜杠放进字符组,而不是直接跟在后面 —— 是为了让本文件自身不含「点+swarm+斜杠」
#    那个字面串,否则本脚本会被自己的断言判为违规。两种写法匹配等价。)
#   白名单(2 条,均为「跳过编排目录」的实现细节,不是对文件的引用):
#     scripts/check-doc-links.py  —— walk_md() 的 skip_dirs
#     scripts/lib/commands.py    —— REPO_TEXT_SKIP_PARTS 的 skip parts
#   判定按**文件路径**做(不是按命中条数):白名单文件里命中多少行都放行;
#   白名单之外的任何受控文件出现编排目录路径即失败,并打印全部越界行。
#
# 断言 B(F1):「实施契约」「决策真源」「判据反证用例」「验收工具链」必须都在克隆内
#   —— 新克隆的仓不缺零件。
#
# 用法: bash scripts/acceptance/clone-verify.sh [clone_src_url] [dest_dir]
#   clone_src_url 默认 file:///D:/project/SSD-Template(即当前仓的已提交 HEAD)
#   dest_dir       默认 /d/project/_verify-merge2
set -u

SRC="${1:-file:///D:/project/SSD-Template}"
DEST="${2:-/d/project/_verify-merge2}"

WHITELIST="scripts/check-doc-links.py scripts/lib/commands.py"

REQUIRED="
docs/contracts/agent-first-implementation.md
docs/contracts/agent-first-direction.md
docs/contracts/phase2-task-flow.md
control/decisions/2026-11-22-agent-primary.md
docs/evidence/a17-run2/example-feature.md
docs/evidence/a17-run2/example-feature.migrated.md
docs/evidence/a17-run2/run-evidence.json
docs/reports/agent-first-direction-lane-a.md
scripts/acceptance/a17-e2e.sh
scripts/acceptance/agent-first-acceptance.py
scripts/acceptance/clone-verify.sh
scripts/acceptance/recheck.sh
scripts/acceptance/run-all-gates.sh
"

rm -rf "$DEST"
git clone --depth 1 "$SRC" "$DEST" >/dev/null 2>&1 || { echo "CLONE FAILED: $SRC"; exit 1; }
cd "$DEST" || exit 1
echo "HEAD: $(git log --oneline -1)"
echo "root md: $(ls *.md | tr '\n' ' ')"
fail=0

# ------------------------------------------------------------ 断言 A
hits=$(git grep -n '\.swarm[/]' -- '*.md' '*.py' '*.sh' '*.yml' 2>/dev/null)
hit_files=$(printf '%s\n' "$hits" | awk -F: 'NF>=3 {print $1}' | sort -u)
offenders=""
for f in $hit_files; do
  case " $WHITELIST " in
    *" $f "*) ;;
    *) offenders="$offenders $f" ;;
  esac
done
if [ -n "$offenders" ]; then
  echo "✗ 断言A 失败: 受控文件引用了未跟踪的编排目录路径:"
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
  echo "✓ 断言A 通过: 白名单外 0 处编排目录引用(白名单内命中文件数=$n_hit, 命中行数=$n_lines)"
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

# ------------------------------------------------------------ 既有门禁
for s in check-line-endings check-naming check-md-schema check-traceability check-repo-baseline; do
  out=$(bash "scripts/$s.sh" 2>&1); rc=$?
  echo "$s rc=$rc bytes=${#out}"
  [ $rc -ne 0 ] && fail=1
done
PY="$(bash scripts/ssdctl.sh --python)"
out=$("$PY" scripts/check-doc-links.py 2>&1); rc=$?
echo "check-doc-links rc=$rc bytes=${#out}"
[ $rc -ne 0 ] && fail=1
bash scripts/ssdctl.sh gate >/dev/null 2>&1 || { echo "ssdctl gate FAILED"; fail=1; }
bash scripts/ssdctl.sh scan --check >/dev/null 2>&1 || { echo "scan --check FAILED"; fail=1; }
bash scripts/sync-prd.sh >/dev/null 2>&1
drift=$(git status --porcelain -- README.md material/)
echo "drift after sync-prd: ${drift:-<none>}"
[ -n "$drift" ] && fail=1
"$PY" -m unittest discover -s scripts/tests -t scripts/tests 2>&1 | tail -3
cd /d/project && rm -rf "$DEST"
echo "CLONE VERIFY fail=$fail"
exit $fail
