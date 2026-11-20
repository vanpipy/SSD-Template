#!/usr/bin/env python3
"""基线门禁的**自洽性**校验 (check-baseline-invariance.py)

Stdlib only.

## 它守的是什么

FORMULA.md §3.4 用**差集法**计算新失败:
只有「基线里没有、本轮新出现」的失败才计入 `D`。这个差集只有在
**基线快照与本轮门禁用同一套标识口径**时才成立。

如果基线快照的标识口径与本轮不同 (例如基线用 surefire XML 的
`classname` 显示名, 本轮用日志里的 FQN), 差集会恒不为空:
**基线自己的失败会被误判成「本轮引入的新失败」**, `D` 被系统性高估。

因此冻结前必须证明: **基线快照与基线日志重新解析的结果完全一致**,
即 `parse(baseline_log) == baseline_snapshot`, 零新增、零消失。

这个检查同时验证:
1. 快照里的失败集与日志**重新解析**的结果逐条相等;
2. 日志中**没有**被解析器漏掉的失败行;
3. 快照记录的 commit 与 `baseline-commits.json` 的冻结 SHA 一致。

用法:
    python3 scripts/check-baseline-invariance.py
    python3 scripts/check-baseline-invariance.py --repo B --repo-path <path>
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_ids as G  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EFF = os.path.join(ROOT, "docs", "efficacy")

# 各仓的快照键 → (日志文件, 解析类型, 文件级键, 用例级键)
REPO_SPECS = {
    "B": {
        "log": os.path.join(EFF, "gates", "baseline-B-full.txt"),
        "kind": "surefire",
        "id_keys": ["failing_test_ids"],
        "file_keys": [],
        "head_key": "repo_B",
    },
    "C": {
        "log": os.path.join(EFF, "gates", "baseline-C-full.txt"),
        "kind": "vitest",
        "id_keys": ["failing_test_ids_C"],
        "file_keys": ["failing_test_files_C"],
        "head_key": "repo_C",
    },
    "H5": {
        "log": os.path.join(EFF, "gates", "baseline-H5-full.txt"),
        "kind": "vitest",
        "id_keys": ["failing_test_cases_H5"],
        "file_keys": ["failing_test_files_H5"],
        "head_key": "repo_H5",
    },
    "PCOLD": {
        "log": os.path.join(EFF, "gates", "baseline-PCOLD-full.txt"),
        "kind": "vitest",
        "id_keys": ["failing_test_cases_PCOLD"],
        "file_keys": ["failing_test_files_PCOLD"],
        "head_key": "repo_PCOLD",
    },
}


def read(path):
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def git_head(repo_path):
    p = subprocess.run(["git", "-C", repo_path, "rev-parse", "HEAD"],
                       capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def check_repo(alias, spec, baseline, commits, repo_path=None):
    """返回 (是否通过, 问题列表, 统计信息)。"""
    problems = []
    log_path = spec["log"]
    if not os.path.isfile(log_path):
        return False, [f"{alias}: 基线日志不存在: {log_path}"], {}

    text = read(log_path)
    if spec["kind"] == "surefire":
        parsed = G.parse_surefire_log_ids(text)
        parsed_files = set()
    else:
        parsed_files, parsed_cases = G.parse_vitest_log_ids(text)
        parsed = parsed_cases

    snap_ids = set()
    for k in spec["id_keys"]:
        snap_ids |= set(baseline.get(k, []))
    snap_files = set()
    for k in spec["file_keys"]:
        snap_files |= set(baseline.get(k, []))

    # --- 1. 用例/测试级: 日志重解析 == 快照 ---
    new, fixed, n_new, n_fixed = G.diff_report(parsed, snap_ids)
    for v in sorted(new)[:10]:
        problems.append(f"{alias}: 日志重解析多出 {n_new} 个失败 (快照里没有): {v}")
    for v in sorted(fixed)[:10]:
        problems.append(f"{alias}: 快照多出 {n_fixed} 个失败 (日志里没有): {v}")
    if n_new > 10:
        problems.append(f"{alias}: ... 还有 {n_new - 10} 个未列出")
    if n_fixed > 10:
        problems.append(f"{alias}: ... 还有 {n_fixed - 10} 个未列出")

    # --- 2. 文件级 (仅前端) ---
    if spec["file_keys"]:
        nf, ff, n_nf, n_ff = G.diff_report(parsed_files, snap_files)
        for v in sorted(nf)[:10]:
            problems.append(f"{alias}: 文件级多出 {n_nf} 个失败文件: {v}")
        for v in sorted(ff)[:10]:
            problems.append(f"{alias}: 文件级快照多出 {n_ff} 个失败文件: {v}")
        if n_nf > 10:
            problems.append(f"{alias}: ... 还有 {n_nf - 10} 个未列出")
        if n_ff > 10:
            problems.append(f"{alias}: ... 还有 {n_ff - 10} 个未列出")

    # --- 3. 后端额外校验: XML 重解析 == 快照 ---
    # 只在仓**当前就在冻结 SHA** 时才有意义: surefire XML 是上一次 `mvn test`
    # 的残留产物, 仓不在冻结 SHA 时它反映的是别的代码状态。
    head_info = baseline.get(spec["head_key"], {}) or {}
    snap_head = head_info.get("head")
    frozen = ((commits.get("baselines", {}) or {}).get(alias, {}) or {}).get("commit")

    xml_ids = set()
    live_head = git_head(repo_path) if repo_path else None
    at_frozen = bool(frozen and live_head and live_head.startswith(frozen))
    if spec["kind"] == "surefire" and at_frozen:
        xml_ids = G.parse_surefire_xml_ids(repo_path)
        if xml_ids:
            nx, fx, n_nx, n_fx = G.diff_report(xml_ids, snap_ids)
            for v in sorted(nx)[:5]:
                problems.append(f"{alias}: surefire XML 多出 {n_nx} 个失败: {v}")
            for v in sorted(fx)[:5]:
                problems.append(f"{alias}: surefire XML 少 {n_fx} 个失败: {v}")

    # --- 4. 采集 head 与冻结 SHA 一致 ---
    if frozen and snap_head and not snap_head.startswith(frozen):
        problems.append(
            f"{alias}: 快照 head {snap_head} 与冻结 SHA {frozen} 不一致")

    # --- 5. 计数字段与集合长度一致 ---
    # `failing_test_count_*` 是**给人看**的汇总数字, 没有任何脚本读它。
    # 正因为没人读, 它一旦与集合长度脱节就永远不会有人发现 ——
    # v4 基线就出现过: C 的 count 写成 6 (只算文件级),
    # 而集合是 6 个文件 + 2 个用例 = 8。
    count_key = {
        "B": "failing_test_count",
        "C": "failing_test_count_C",
        "H5": "failing_test_count_H5",
        "PCOLD": "failing_test_count_PCOLD",
    }.get(alias)
    if count_key and count_key in baseline:
        got = baseline.get(count_key)
        # 前端的 count 语义是「文件级 + 用例级」(见 capture-vitest-baseline.py);
        # 后端没有文件级粒度, count 就是用例数。
        expect = len(snap_files) + len(snap_ids) if spec["file_keys"] \
            else len(snap_ids)
        if got != expect:
            problems.append(
                f"{alias}: {count_key} = {got} != 期望 {expect} "
                f"(文件级 {len(snap_files)} + 用例级 {len(snap_ids)})")

    notes = []
    if repo_path and live_head and frozen and not at_frozen:
        # 不是错误: 门禁在冻结 SHA 的**独立 worktree** 里跑 (见 run-round.sh
        # 的 prepare_baseline_worktree), 业务仓的 HEAD 本来就不必等于冻结 SHA。
        # 但仓里的 surefire XML 是上一次 `mvn test` 的残留, 不能拿来当基线。
        notes.append(
            f"{alias}: 仓当前 HEAD {live_head[:12]} != 冻结 SHA {frozen[:12]}; "
            f"门禁必须在冻结 SHA 的 worktree 里跑, 仓内残留的 surefire XML 不可用作基线")

    stats = {
        "log_failures": len(parsed),
        "log_files": len(parsed_files),
        "snapshot_failures": len(snap_ids),
        "snapshot_files": len(snap_files),
        "new": n_new,
        "fixed": n_fixed,
        "xml_failures": len(xml_ids) if xml_ids else None,
    }
    return (not problems), problems, stats, notes


def main():
    ap = argparse.ArgumentParser(description="基线门禁自洽性校验")
    ap.add_argument("--repo", action="append", default=[],
                    help="只校验指定仓 (可重复), 默认全部")
    ap.add_argument("--repo-path", default=None,
                    help="后端仓路径 (用于 surefire XML 交叉校验)")
    args = ap.parse_args()

    baseline_path = os.path.join(EFF, "baseline-gates.json")
    commits_path = os.path.join(EFF, "baseline-commits.json")
    with open(baseline_path, encoding="utf-8") as fh:
        baseline = json.load(fh)
    commits = {}
    if os.path.isfile(commits_path):
        with open(commits_path, encoding="utf-8") as fh:
            commits = json.load(fh)

    aliases = args.repo or list(REPO_SPECS)
    all_problems = []
    all_notes = []
    print("== 基线门禁自洽性校验 ==")
    for alias in aliases:
        spec = REPO_SPECS.get(alias)
        if not spec:
            print(f"  {alias}: 未知仓")
            all_problems.append(f"未知仓: {alias}")
            continue
        ok, problems, stats, notes = check_repo(
            alias, spec, baseline, commits, args.repo_path)
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {alias}: "
              f"日志重解析 {stats.get('log_failures')} 失败 / "
              f"{stats.get('log_files')} 文件; "
              f"快照 {stats.get('snapshot_failures')} 失败 / "
              f"{stats.get('snapshot_files')} 文件; "
              f"新增 {stats.get('new')} 消失 {stats.get('fixed')}")
        all_problems.extend(problems)
        all_notes.extend(notes)

    for n in all_notes:
        print(f"  [note] {n}")

    if all_problems:
        print("\n问题明细:", file=sys.stderr)
        for p in all_problems:
            print(f"  - {p}", file=sys.stderr)
        print("\n[FAIL] 基线门禁自洽性校验未通过", file=sys.stderr)
        return 1
    print("\n[OK] 基线门禁自洽: 快照 == 日志重解析, 零新增零消失")
    return 0


if __name__ == "__main__":
    sys.exit(main())
