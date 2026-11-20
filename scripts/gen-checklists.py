#!/usr/bin/env python3
"""生成**两臂共用**的验收检查表模板 (gen-checklists.py)

Stdlib only. 从 `docs/efficacy/RUBRIC.md` 解析 AC, 为每个候选生成一份
**空勾选**的检查表模板。两臂各自填自己的副本, 保证 AC 列表逐字相同。

用法:
    # 生成全部模板到 docs/efficacy/checklists/
    python3 scripts/gen-checklists.py

    # 只打印某个候选的模板
    python3 scripts/gen-checklists.py --print F-02

    # 校验已存在的模板与 RUBRIC.md 是否仍然一致
    python3 scripts/gen-checklists.py --check
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rubric as R  # noqa: E402

ROOT = R.ROOT
CHECKLIST_DIR = os.path.join(ROOT, "docs", "efficacy", "checklists")


def main():
    ap = argparse.ArgumentParser(description="生成共享验收检查表模板")
    ap.add_argument("--print", dest="print_cand", default=None,
                    help="打印某个候选的模板到 stdout")
    ap.add_argument("--check", action="store_true",
                    help="校验 docs/efficacy/checklists/ 下的模板是否与 RUBRIC.md 一致")
    ap.add_argument("--out-dir", default=CHECKLIST_DIR)
    args = ap.parse_args()

    acs = R.parse_rubric()

    ok, problems = R.check_uniqueness(acs)
    if not ok:
        print("AC ID 唯一性校验失败:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    ok, problems = R.check_candidate_order(acs)
    if not ok:
        print("候选集合校验失败:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    templates = R.render_all_templates(acs)
    h = R.compute_template_hash(acs)

    if args.print_cand:
        cand = args.print_cand
        if cand not in templates:
            print(f"未知候选: {cand}; 可用: {sorted(templates)}", file=sys.stderr)
            return 1
        print(templates[cand], end="")
        return 0

    if args.check:
        if not os.path.isdir(args.out_dir):
            print(f"[check] 模板目录不存在: {args.out_dir}", file=sys.stderr)
            return 1
        problems = []
        expected_files = set()
        for cand, text in templates.items():
            path = os.path.join(args.out_dir, f"{cand}.checklist.md")
            expected_files.add(os.path.basename(path))
            if not os.path.isfile(path):
                problems.append(f"缺少模板文件: {path}")
                continue
            with open(path, encoding="utf-8") as fh:
                actual = fh.read()
            if actual != text:
                problems.append(f"模板与 RUBRIC.md 不一致: {path}")
        for name in sorted(os.listdir(args.out_dir)):
            if name.endswith(".checklist.md") and name not in expected_files:
                problems.append(f"模板目录存在多余文件: {name}")
        if problems:
            print("[check] 失败:", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            return 1
        print(f"[check] 全部 {len(templates)} 份模板与 RUBRIC.md 一致 (hash={h})")
        return 0

    os.makedirs(args.out_dir, exist_ok=True)
    # 清理已不存在的候选模板
    for name in sorted(os.listdir(args.out_dir)):
        if name.endswith(".checklist.md") and name[:-len(".checklist.md")] not in templates:
            os.remove(os.path.join(args.out_dir, name))
            print(f"[gen] 删除过期模板: {name}")

    for cand, text in sorted(templates.items()):
        path = os.path.join(args.out_dir, f"{cand}.checklist.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        n = len(R.parse_verdicts(text))
        print(f"[gen] {cand}: {n} 条 AC -> {os.path.relpath(path, ROOT)}")

    print(f"[gen] 模板版本 hash={h}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
