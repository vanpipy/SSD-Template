#!/usr/bin/env bash
# 门禁验收渲染层 —— 门禁清单的**唯一真源**是 scripts/lib/commands.py 的 GATE_SCRIPTS。
# 本脚本不再自带清单,只消费 `bash scripts/ssdctl.sh gate --json` 的结果并渲染成表格。
#
# 跑的是什么(全部在 `ssdctl gate` 里面,这里只做呈现):
#   - 仓内脚本门禁:GATE_SCRIPTS 里的那些(check-* / sync-* / check-doc-links.py);
#   - 判据引擎(schema/criteria.json 的 blocking 判据,含跨层与仓库层);
#   - 制品自洽性(状态块 + 复审块)。
# 解释器口径也是唯一的:`bash scripts/ssdctl.sh --python`(不再自带候选探测)。
# 只用 bash 内建 + Python 标准库(json);不用 jq。
# bash 3.2 兼容:不用 mapfile / 关联数组 / ${var^^}。
#
# 失败明细:判据失败(逐条 failure)与制品自洽问题(逐条 problem)打印在表格**之前** ——
# CI 日志要能一眼看出「哪条判据 / 哪个制品挂了」,而不是只看到一行 RESULT: FAIL。
# 全绿时不打印明细段(保持紧凑表)。
#
# 用法:bash scripts/acceptance/run-all-gates.sh [repo_root]
set -u

ROOT="${1:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT" || { echo "FAIL: cannot cd to $ROOT"; exit 2; }

PY="$(bash scripts/ssdctl.sh --python)" || {
  echo "FAIL: cannot resolve the python interpreter (bash scripts/ssdctl.sh --python)"
  exit 2
}

GITHUB_STEP_SUMMARY="${GITHUB_STEP_SUMMARY:-}"

json_file="$(mktemp)"
json_err="$(mktemp)"
trap 'rm -f "$json_file" "$json_err"' EXIT

bash scripts/ssdctl.sh gate --json >"$json_file" 2>"$json_err"
gate_rc=$?

if [ -s "$json_err" ]; then
  sed 's/^/    | /' "$json_err"
fi

"$PY" - "$json_file" "$gate_rc" <<'PY'
import json
import sys

try:  # 渲染层自己写 UTF-8 + LF,不用平台默认编码(中文 Windows 的默认编码是 GBK,会让 CI 日志变乱码)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", newline="\n")
except AttributeError:  # Python < 3.7 没有 reconfigure
    pass

path, gate_rc = sys.argv[1], int(sys.argv[2])
try:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
except (OSError, ValueError) as exc:
    # gate --json 自己失败时(stdout 为空,退出码 2 = 判据文件缺失/非法)——
    # 这里必须原样透传那个退出码,不能让 json 异常把它降级成 1。
    sys.stderr.write("gate --json 没有输出可解析的 JSON: %s\n" % exc)
    sys.exit(gate_rc if gate_rc else 1)

overall = 0 if data.get("ok") else 1
if gate_rc == 2:
    overall = 2

gates = data.get("gates", [])
criteria = data.get("criteria", [])
artifacts = data.get("artifacts", [])


def violation_text(item):
    """一条判据违规 → 一行可读文本(判据 id + 消息 + 位置)。"""
    if isinstance(item, dict):
        vid = item.get("id", "?")
        msg = item.get("message", "")
        rel = item.get("file") or ""
        line = item.get("line")
        where = ""
        if rel:
            where = " (%s%s)" % (rel, ":" + str(line) if line else "")
        return "%s: %s%s" % (vid, msg, where)
    return str(item)


# ---- 失败明细(先于表格:CI 日志要能直接看出哪条判据 / 哪个制品挂了)----
failed_criteria = [row for row in criteria if not row.get("passed")]
failed_artifacts = [row for row in artifacts if row.get("problems")]

if failed_criteria or failed_artifacts:
    print("— 失败明细 —")
    for row in failed_criteria:
        print("✗ [判据] %s" % row.get("target", ""))
        for item in row.get("failures", []):
            print("    · %s" % violation_text(item))
    for row in failed_artifacts:
        print("✗ [制品自洽] %s" % row.get("artifact", ""))
        for problem in row.get("problems", []):
            print("    · %s" % problem)
    print("-" * 70)

print(
    "本次跑的集合:%d 个既有门禁 + 判据引擎(判据 %d 条)+ 制品自洽性(制品 %d 个)"
    % (len(gates), len(criteria), len(artifacts))
)

print("%-34s %-6s %-8s %s" % ("STEP", "EXIT", "STDOUT", "NOTE"))
print("-" * 70)

for gate in gates:
    script = gate["script"]
    args = " ".join(gate.get("args", []))
    label = "%s %s" % (script, args) if args else script
    rc = gate["exit_code"]
    stdout_bytes = gate["stdout_bytes"]
    stdout_text = gate.get("output", "") or ""
    stderr_text = gate.get("stderr", "") or ""

    note = ""
    if rc == 0 and not stdout_text.strip() and not stderr_text.strip():
        note = "WARN: exit 0 with empty stdout (possible silent no-op)"
    elif rc == 0 and not stdout_text.strip():
        note = "note: stdout empty, the gate printed on stderr"

    print("%-34s %-6s %-8s %s" % (label[:34], rc, stdout_bytes, note))

    if rc != 0:
        failed = (stdout_text + stderr_text).strip()
        for line in failed.splitlines():
            print("    | %s" % line)

print("-" * 70)
if overall == 0:
    print("RESULT: PASS")
else:
    print("RESULT: FAIL")
sys.exit(overall)
PY
exit $?
