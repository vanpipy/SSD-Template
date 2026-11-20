#!/usr/bin/env python3
"""校验共享检查表**模板**与 RUBRIC.md 是否同步 (check-shared-checklist.py)

Stdlib only.

这个脚本是「两臂用同一份 AC 清单」的**机械保证**:

- `RUBRIC.md` 是 AC 的唯一真源;
- `docs/efficacy/checklists/<候选>.checklist.md` 是从它派生的空勾选模板;
- 两臂各自填自己的副本, **只允许**改复选框状态、证据锚点、NA 标记;
- 模板与 RUBRIC.md 任何一处漂移, 本脚本立即失败。

用法:
    # 校验模板与 RUBRIC.md 一致 (冻结前必跑)
    python3 scripts/check-shared-checklist.py

    # 校验某一份填写稿是否只改了允许的部分
    python3 scripts/check-shared-checklist.py --filled F-02=docs/efficacy/rounds/F-02-ssd.checklist.md

    # 校验两臂填写稿用的是同一份模板
    python3 scripts/check-shared-checklist.py --pair F-02=ssd:path1,control:path2

退出码: 0 = 全部通过, 1 = 有问题。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rubric as R  # noqa: E402

ROOT = R.ROOT
CHECKLIST_DIR = os.path.join(ROOT, "docs", "efficacy", "checklists")


def parse_kv_list(spec):
    """解析 `F-02=path1,F-03=path2` 形式的列表。"""
    out = {}
    for chunk in (spec or "").split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        k, v = chunk.split("=", 1)
        k, v = k.strip(), v.strip()
        if k and v:
            out[k] = v
    return out


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        print(f"[FAIL] 无法读取: {path} ({exc})", file=sys.stderr)
        return None


def check_templates(templates, problems):
    """模板目录与 RUBRIC.md 必须逐字一致。"""
    if not os.path.isdir(CHECKLIST_DIR):
        problems.append(f"模板目录不存在: {CHECKLIST_DIR}")
        return
    expected = set()
    for cand, text in templates.items():
        path = os.path.join(CHECKLIST_DIR, f"{cand}.checklist.md")
        expected.add(os.path.basename(path))
        if not os.path.isfile(path):
            problems.append(f"缺少模板: {os.path.relpath(path, ROOT)}")
            continue
        actual = read(path)
        if actual is None:
            continue
        if actual != text:
            problems.append(
                f"模板与 RUBRIC.md 不一致: {os.path.relpath(path, ROOT)}")
    for name in sorted(os.listdir(CHECKLIST_DIR)):
        if name.endswith(".checklist.md") and name not in expected:
            problems.append(f"模板目录存在多余文件: {name}")


def main():
    ap = argparse.ArgumentParser(description="校验共享检查表模板与填写稿")
    ap.add_argument("--filled", default="",
                    help="校验填写稿, 形如 F-02=path,F-03=path")
    ap.add_argument("--pair", default="",
                    help="校验两臂填写稿, 形如 F-02=ssd:path1,control:path2")
    args = ap.parse_args()

    acs = R.parse_rubric()
    problems = []

    ok, probs = R.check_uniqueness(acs)
    problems += probs
    ok, probs = R.check_candidate_order(acs)
    problems += probs

    templates = R.render_all_templates(acs)
    check_templates(templates, problems)

    # --- 填写稿校验 ---
    for cand, path in parse_kv_list(args.filled).items():
        if cand not in templates:
            problems.append(f"未知候选: {cand}")
            continue
        filled = read(path)
        if filled is None:
            continue
        ok, probs = R.checklist_diff(templates[cand], filled)
        if not ok:
            problems.append(f"{cand} ({path}) 与模板不一致:")
            problems += [f"    - {p}" for p in probs]

    # --- 两臂配对校验 ---
    for cand, spec in parse_kv_list(args.pair).items():
        if cand not in templates:
            problems.append(f"未知候选: {cand}")
            continue
        arms = {}
        for chunk in spec.split("|"):
            chunk = chunk.strip()
            if ":" not in chunk:
                continue
            arm, path = chunk.split(":", 1)
            arms[arm.strip()] = path.strip()
        if len(arms) < 2:
            problems.append(f"{cand}: --pair 需要至少两臂, 形如 ssd:path,control:path")
            continue
        texts = {}
        for arm, path in arms.items():
            t = read(path)
            if t is None:
                break
            texts[arm] = t
        if len(texts) != len(arms):
            continue
        # 两臂的**模板版本哈希**必须一致
        hashes = {arm: R._template_hash_of(t) for arm, t in texts.items()}
        if len(set(hashes.values())) != 1:
            problems.append(f"{cand}: 两臂模板版本哈希不一致: {hashes}")
        # 两臂的**判据列**必须逐字一致
        for arm, t in texts.items():
            ok, probs = R.checklist_diff(templates[cand], t)
            if not ok:
                problems.append(f"{cand} ({arm} 臂, {arms[arm]}) 与模板不一致:")
                problems += [f"    - {p}" for p in probs]
        # 判据列互相之间也要一致 (防模板与填写稿同源但 AC 集合被换掉)
        crit_sets = {}
        for arm, t in texts.items():
            crit_sets[arm] = {
                R._row_criterion(t, ac_id)
                for ac_id, _c, _a, _na in R.parse_verdicts(t)
            }
        if len({frozenset(v) for v in crit_sets.values()}) != 1:
            problems.append(f"{cand}: 两臂判据集合不一致")

    if problems:
        print("[FAIL] 共享检查表校验失败:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    h = R.compute_template_hash(acs)
    print(f"[OK] 共享检查表一致: {len(templates)} 份模板, "
          f"{len(acs)} 条 AC, hash={h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
