"""基线 flake 隔离清单的**自洽性**校验 (check-flaky-quarantine.py)

Stdlib only.

## 它守的是什么

FORMULA.md §3.4.9 用一份**冻结的隔离清单**把基线自身的间歇性失败
(flake) 从 `D_gate_new` 的分子里剔除。清单里多一个条目, `D` 就少算一个。

所以清单必须可核对。这个检查证明:

1. 清单里的每个标识都有**重复跑证据** (出现在
   `docs/efficacy/evidence/flake-study-result.tsv` 里, 且 `seen_runs <
   total_runs`, 即确实是个 flake 而不是稳定失败);
2. 清单里**没有**稳定失败的标识 (把稳定失败隔离掉 = 抹掉真缺陷,
   方向对 SSD 有利, 禁止);
3. 被隔离的标识**不在**基线快照里 (在快照里就说明它是稳定失败);
4. 原始证据的 sha256 与清单里记的**一致** (证据被换过 = 清单失去依据);
5. 清单里的条数与证据表里的 flake 条数**一致** (不多不少);
6. 每个条目的 `seen_runs` / `total_runs` / `seen_in_run_indices` 与证据表
   **逐字一致** (不能只写个数而不对得上具体是哪几次);
7. `seen_in_run_indices` 与 `study.failure_counts_per_run` **交叉一致**
   (超出稳定失败数的那几轮, 就是这个 flake 出现的轮次, 轮次从 1 数)。

用法:
    python3 scripts/check-flaky-quarantine.py
    python3 scripts/check-flaky-quarantine.py --verbose
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EFF = os.path.join(ROOT, "docs", "efficacy")

LIST_FILE = os.path.join(EFF, "flaky-tests.json")
EVIDENCE_FILE = os.path.join(EFF, "evidence", "flake-study-result.tsv")

STABLE = "STABLE_BASELINE_FAILURE"
FLAKE = "INTERMITTENT_FLAKE"


def read_evidence(path):
    """读证据表, 返回 {test_id: (seen_runs, total_runs, classification)}。"""
    out = {}
    with open(path, encoding="utf-8") as fh:
        header = fh.readline().rstrip("\n").split("\t")
        want = ["test_id", "seen_runs", "total_runs", "classification"]
        if header != want:
            raise ValueError(f"证据表表头不对: {header} (应为 {want})")
        for line in fh:
            line = line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 4:
                raise ValueError(f"证据表行格式不对: {line!r}")
            out[parts[0]] = (int(parts[1]), int(parts[2]), parts[3])
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser(description="基线 flake 隔离清单自洽性校验")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--list", default=LIST_FILE,
                    help=f"隔离清单路径 (默认 {os.path.relpath(LIST_FILE, ROOT)})")
    ap.add_argument("--evidence", default=EVIDENCE_FILE,
                    help=f"原始证据路径 (默认 {os.path.relpath(EVIDENCE_FILE, ROOT)})")
    args = ap.parse_args()

    problems = []
    notes = []

    list_file = args.list
    evidence_file = args.evidence

    if not os.path.isfile(list_file):
        print(f"[FAIL] 隔离清单不存在: {list_file}", file=sys.stderr)
        return 1
    if not os.path.isfile(evidence_file):
        print(f"[FAIL] 原始证据不存在: {evidence_file}", file=sys.stderr)
        return 1

    with open(list_file, encoding="utf-8") as fh:
        data = json.load(fh)

    evidence = read_evidence(evidence_file)
    baseline = json.load(open(os.path.join(EFF, "baseline-gates.json"),
                             encoding="utf-8"))
    baseline_ids = set(baseline.get("failing_test_ids", []))

    quarantined = data.get("quarantined", [])
    study = data.get("study", {})

    # --- 1. 证据哈希 ---
    actual = sha256(evidence_file)
    recorded = study.get("raw_result_sha256")
    if not recorded:
        problems.append("清单里没有 raw_result_sha256, 证据无法核对")
    elif recorded != actual:
        problems.append(
            f"原始证据的 sha256 不匹配: 清单记 {recorded}, 实际 {actual}")

    # --- 2. 证据表里被标成 flake 的集合 ---
    flakes_in_evidence = {tid for tid, (_s, _t, c) in evidence.items()
                          if c == FLAKE}
    stables_in_evidence = {tid for tid, (_s, _t, c) in evidence.items()
                            if c == STABLE}

    # --- 3. 清单条数 == 证据里的 flake 条数 ---
    listed = {item.get("test_id", "") for item in quarantined}
    if listed != flakes_in_evidence:
        only_list = sorted(listed - flakes_in_evidence)
        only_ev = sorted(flakes_in_evidence - listed)
        problems.append(
            "隔离清单与证据表的 flake 集合不一致。"
            f"清单多出: {only_list}; 证据多出: {only_ev}")

    # --- 4. 逐条核对 ---
    for item in quarantined:
        tid = item.get("test_id", "")
        alias = item.get("alias", "B")
        if alias != "B":
            problems.append(f"{tid}: 隔离清单只允许 B 仓, 实为 {alias}")
        if tid not in evidence:
            problems.append(f"{tid}: 没有重复跑证据 (证据表里找不到)")
            continue
        seen, total, cls = evidence[tid]
        if cls != FLAKE:
            problems.append(
                f"{tid}: 证据表把它标成 {cls}, 但清单把它隔离了 "
                "(隔离稳定失败 = 抹掉真缺陷)")
        if not (seen < total):
            problems.append(
                f"{tid}: seen_runs={seen} 不小于 total_runs={total}, "
                "那不是 flake")
        # 条目自报的次数必须与证据一致
        for field, got in (("seen_runs", seen), ("total_runs", total)):
            if item.get(field) != got:
                problems.append(
                    f"{tid}: 条目里的 {field}={item.get(field)} 与证据的 {got} 不一致")
        idx = item.get("seen_in_run_indices")
        if idx is not None and len(idx) != seen:
            problems.append(
                f"{tid}: seen_in_run_indices 有 {len(idx)} 项, 但 seen_runs={seen}")
        # **逐轮失败数交叉核对**。
        #
        # `failure_counts_per_run` 记的是每一轮跑出来的失败总数, 稳定失败是
        # 38 个。某一轮的总数 > 38, 说明那一轮**多**失败了标识, 多出来的
        # 就是这个 flake。所以 `seen_in_run_indices` 必须**逐项等于**
        # 「总数 > 稳定失败数」的那些轮次 (轮次从 1 开始数)。
        #
        # 这是一条**独立**的交叉验证: 证据表的 `seen_runs` 与逐轮计数数组
        # 是采集时分别记下的两份数据, 它们对得上才说明证据本身没记错。
        per_run = study.get("failure_counts_per_run")
        n_stable_ref = study.get("stable_baseline_failures")
        if per_run and n_stable_ref is not None:
            expected = [i + 1 for i, c in enumerate(per_run)
                        if c > n_stable_ref]
            if idx is not None and list(idx) != expected:
                problems.append(
                    f"{tid}: seen_in_run_indices={list(idx)} 与逐轮失败数推出的 "
                    f"{expected} 不一致 (轮次从 1 开始数)")
            # 每一轮超出稳定失败数的**个数**就是 flake 出现的次数
            n_over = len(expected)
            if n_over != seen:
                problems.append(
                    f"{tid}: 逐轮失败数显示它在 {n_over} 轮里出现, "
                    f"证据表说是 {seen} 轮")
        # 隔离项不应在基线快照里 (在就说明它是稳定失败)
        if tid in baseline_ids:
            problems.append(
                f"{tid}: 出现在基线快照里, 那它是稳定失败, 不该隔离")
        notes.append(f"{tid}: {seen}/{total} 次出现, 分类 {cls}")

    # --- 5. 稳定失败不得被隔离 ---
    for tid in sorted(listed & stables_in_evidence):
        problems.append(f"{tid}: 是稳定失败, 不该被隔离")

    # --- 6. 证据表的总数自洽 ---
    n_stable = len(stables_in_evidence)
    n_flake = len(flakes_in_evidence)
    for field, got in (("stable_baseline_failures", n_stable),
                       ("intermittent_flakes", n_flake),
                       ("runs", max((t for _s, t, _c in evidence.values()),
                                    default=0))):
        if field in study and study[field] != got:
            problems.append(
                f"清单里 study.{field}={study[field]}, 证据表算出的是 {got}")

    print(f"[OK] 证据表: {len(evidence)} 条标识 "
          f"({n_stable} 稳定失败 + {n_flake} flake)")
    print(f"[OK] 隔离清单: {len(quarantined)} 条")
    if args.verbose:
        for n in notes:
            print(f"      - {n}")
    print(f"[OK] 证据 sha256: {actual[:16]}...")

    if problems:
        print()
        print(f"[FAIL] {len(problems)} 项不一致:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print("[OK] 隔离清单与重复跑证据自洽")
    return 0


if __name__ == "__main__":
    sys.exit(main())
