#!/usr/bin/env python3
"""候选池扫描器 (scan-candidate-pool.py)

**为什么需要**: v2 的验证器只扫了 B (后端) 和 C (PC 前端) 两个仓,
漏掉了工作区里的 **H5 (移动端 React)** 仓, 导致 F-06 被误判为缺口。
本脚本把「扫哪些仓」这件事显式化: 从 spec 真源抽取特征词, 在**全部**代码仓
做双向反查, 列出每个候选在各仓的命中情况, 供人工语义复核。

**用法**:
    python3 scripts/scan-candidate-pool.py                 # 跑内置候选池
    python3 scripts/scan-candidate-pool.py --list          # 列出候选池
    python3 scripts/scan-candidate-pool.py --repo H5       # 只扫某一仓
    python3 scripts/scan-candidate-pool.py --json out.json # 输出 JSON

Stdlib only.
"""
import argparse
import json
import os
import subprocess
import sys

WORKSPACE = "/home/leroy/Project/merchandising-workspace"
REPOS = {
    "B": os.path.join(WORKSPACE, "busyming-merchandising"),
    "C": os.path.join(WORKSPACE, "busyming-merchandising-vue-pc"),
    "H5": os.path.join(WORKSPACE, "busyming-merchandising-h5"),
    "PC-old": os.path.join(WORKSPACE, "busyming-merchandising-pc"),
}

# 候选池: (id, 名称, 规格路径, [各仓的特征词])
# 特征词要**行为特有**, 不能用会在全仓大量命中的泛词
# (例如「失败原因」在后端 71 处, 「漏斗」在无关代码里也有)。
CANDIDATE_POOL = [
    ("F-01", "运营节奏报表 · 三步进度卡片与门店维度转化漏斗",
     "产品真源/功能/运营节奏报表/产品spec.md",
     {"B": ["运营节奏", "rhythmReport", "OperationRhythm"],
      "C": ["运营节奏", "rhythmReport", "OperationRhythm"],
      "H5": ["运营节奏", "rhythmReport"]}),
    ("F-02", "门店执行列表 · 门店展开子任务与图片复核入口",
     "产品真源/功能/货架陈列任务/20261009-门店执行列表与图片复核.md",
     {"B": ["门店执行列表", "StoreExecutionList"],
      "C": ["门店执行列表", "store-execution-list", "StoreExecutionList"],
      "H5": ["门店执行列表", "StoreExecutionList"]}),
    ("F-03", "品类版本批量重算 · 不一致解绑回退待匹配模板",
     "产品真源/实现方案/品类版本批量重算.md",
     {"B": ["recalcUnbind", "RecalcUnbind"], "C": ["recalcUnbind"], "H5": []}),
    ("F-04", "端架/地堆数双源不一致提醒",
     "产品真源/功能/端架地堆数不一致的提醒/端架地堆不一致的提醒.md",
     {"B": ["cadCount", "CadCount"], "C": ["cadCount", "CadCount"],
      "H5": ["cadCount", "CadCount"]}),
    ("F-05", "运营报表 · top300 把货摆对门店明细服务端分页",
     "产品真源/实现方案/运营报表-top300把货摆对-实现方案.md",
     {"B": ["Top300Report", "putGoodsRight", "合格门店率"],
      "C": ["Top300Report", "putGoodsRight", "合格门店率"],
      "H5": []}),
    ("F-06", "移动端货架图 · 品类及货框序号叠加",
     "产品真源/功能/移动端货架图/产品spec.md",
     {"B": ["品类及货框序号"], "C": ["品类及货框序号"],
      "H5": ["品类及货框序号", "CategoryBounds", "showCateBounds",
             "useShelfScatterBounds"]}),
    ("F-07", "新开店数据推送 · 门店商品清单下发要货侧",
     "产品真源/功能/新开店数据推送/产品spec.md",
     {"B": ["StoreSkuDisplayPush", "skuDisplayPush", "pushStoreSkuDisplay"],
      "C": ["StoreSkuDisplayPush", "skuDisplayPush"], "H5": []}),
    ("F-08", "人工导入失败 Excel 下载 + 整店覆盖",
     "产品真源/功能/门店套图管理/specs/门店分类与人工导入.md",
     {"B": ["failExcel", "FailExcel", "整店覆盖"],
      "C": ["failExcel", "FailExcel", "整店覆盖"], "H5": []}),
    ("F-09", "识别结果列表页 Excel 导出 (11 列)",
     "产品真源/实现方案/top300识别统计与AI纠正.md",
     {"B": ["recognitionExport", "RecognitionExport", "识别结果.*导出"],
      "C": ["recognitionExport", "RecognitionExport", "识别结果.*导出"],
      "H5": []}),
    ("F-10", "货架信息反馈版本 2 · 门店-品类维度一次提交多节货架",
     "产品真源/设计中/20260920-货架信息反馈/20260920-货架信息反馈提交.md",
     {"B": ["shelfFeedbackV2", "StoreCategoryFeedback", "FeedbackShelfBatch"],
      "C": ["shelfFeedbackV2", "shelfFeedbackV2"], "H5": []}),
]

# 排除测试文件与注释行 (与 verify-candidates.py 同口径)
RG_GLOBS = [
    "-g", "*.java", "-g", "*.ts", "-g", "*.tsx", "-g", "*.vue",
    "-g", "!*Test.java", "-g", "!*Tests.java",
    "-g", "!*spec.ts", "-g", "!*spec.js", "-g", "!*spec.tsx",
    "-g", "!*test.ts", "-g", "!*test.tsx",
]


def _is_comment_line(s):
    s = s.strip()
    return (s.startswith("//") or s.startswith("*") or s.startswith("/*")
            or s.startswith("<!--") or s.startswith("--"))


def scan(repo, pattern):
    """返回 (非注释命中数, 命中文件列表)。"""
    try:
        p = subprocess.run(
            ["rg", "-n", "--no-messages"] + RG_GLOBS + [pattern, "."],
            cwd=repo, capture_output=True, text=True, timeout=180)
    except Exception:
        return -1, []
    files, n = [], 0
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        path, _, body = line.partition(":")
        if not body:
            continue
        _, _, body = body.partition(":")
        if _is_comment_line(body):
            continue
        n += 1
        if path not in files:
            files.append(path)
    return n, files[:5]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="", help="只扫这一仓 (B/C/H5/PC-old)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    if args.list:
        for cid, name, spec, _ in CANDIDATE_POOL:
            print(f"{cid}  {name}\n      规格: {spec}")
        return 0

    targets = [args.repo] if args.repo else list(REPOS)
    results = []
    for cid, name, spec, probes in CANDIDATE_POOL:
        row = {"id": cid, "name": name, "spec": spec, "hits": {}}
        total = 0
        for label in targets:
            for pat in probes.get(label, []):
                n, files = scan(REPOS[label], pat)
                if n > 0:
                    row["hits"].setdefault(label, []).append(
                        {"pattern": pat, "count": n, "files": files})
                    total += n
        row["total_hits"] = total
        row["verdict"] = "ALREADY_IMPLEMENTED" if total else "GAP_CONFIRMED"
        results.append(row)

        flag = "已实现" if total else "缺口"
        print(f"\n{cid}: [{flag}] {name}")
        for label, hits in row["hits"].items():
            for h in hits:
                print(f"    {label:7s} /{h['pattern']}/ x{h['count']}")
                for f in h["files"][:2]:
                    print(f"             {f}")

    print()
    gaps = [r for r in results if r["verdict"] == "GAP_CONFIRMED"]
    print(f"合计: {len(gaps)} 个缺口成立 / {len(results)} 个候选")
    print("提醒: probe 无命中 ≠ 缺口成立, 仍需人工语义复核。")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        print(f"-> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
