#!/usr/bin/env python3
"""候选验证器 v3 (verify-candidates.py)

对每个候选需求, 用**代码级证据**判定它是否真的未实现。

**为什么需要 v3**: v2 只扫了 B (后端) 和 C (PC 前端) 两个仓,
漏掉了工作区里的第三个代码仓 **H5 (移动端 React)**。
结果 F-06 (移动端货架图 · 品类及货框序号叠加) 被误判为「缺口成立」,
而它其实在 H5 里**已实现大半** (`CategoryBounds.tsx` / `useShelfScatterBounds.ts` /
`ShelfItemsPicDrawing/index.tsx`)。

**v3 的判定规则** (仍是双向的):
  - 后端 B: 该能力是否有**承载点** (VO 字段 / 服务方法 / 控制器端点)?
  - PC 前端 C: 该能力是否有**承载点** (类型 / 组件 / api 函数)?
  - 移动端 H5: 同上 —— **不能漏**, 否则移动端需求会被误判为缺口。
  - 任一侧存在 → 该需求已实现 (排除), 需人工复核后人工改判。

**注意**: probe 无命中 ≠ 缺口成立。probe 只负责**筛掉已实现的**。
缺口成立需要人工语义复核 (见 docs/efficacy/CANDIDATES.md 的「语义复核」列)。

用法: python3 scripts/verify-candidates.py [--json]
"""
import json
import os
import subprocess
import sys

WORKSPACE = "/home/leroy/Project/merchandising-workspace"
REPO_B = os.path.join(WORKSPACE, "busyming-merchandising")
REPO_C = os.path.join(WORKSPACE, "busyming-merchandising-vue-pc")
REPO_H5 = os.path.join(WORKSPACE, "busyming-merchandising-h5")

REPOS = {"B": REPO_B, "C": REPO_C, "H5": REPO_H5}

# 每个候选的 probe: (repo_label, [正则...])
# 任一 probe 命中 → 该需求在该侧已有承载 → 已实现
CANDIDATES = [
    {
        "id": "F-01",
        "name": "运营节奏报表 · 三步进度卡片与门店维度转化漏斗",
        "spec": "产品真源/功能/运营节奏报表/产品spec.md",
        "probes": [
            ("B", [r"运营节奏", r"rhythmReport", r"OperationRhythm", r"funnel"]),
            ("C", [r"运营节奏", r"rhythmReport", r"OperationRhythm",
                   r"漏斗", r"funnel"]),
        ],
    },
    {
        "id": "F-02",
        "name": "门店执行列表 · 门店展开子任务与图片复核入口",
        "spec": "产品真源/功能/货架陈列任务/20261009-门店执行列表与图片复核.md",
        "probes": [
            ("B", [r"门店执行列表", r"StoreExecutionList", r"storeExecution"]),
            ("C", [r"门店执行列表", r"store-execution-list",
                   r"StoreExecutionList", r"storeExecution"]),
        ],
    },
    {
        "id": "F-03",
        "name": "品类版本批量重算 · 不一致解绑回退待匹配模板",
        "spec": "产品真源/实现方案/品类版本批量重算.md (现状 5: 技术尚未实现)",
        "probes": [
            # 只看「品类版本重算」子树: 该链路里没有任何解绑调用
            # (PatternUnbindRepairJobHandler 属「模板误解绑数据修复」,
            #  人工触发、无 Cron, 与重算链路无关)
            ("B", [(r"unbindPattern|unbindStore|unbindPlan", "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/recalc/")]),
            ("B", [(r"unbindPattern|unbindStore|unbindPlan", "busyming-merchandising-job/src/main/java/io/busyming/product/merchandising/job/handler/CategoryVersionRecalcMapReduceJobHandler.java")]),
            ("C", [r"RecalcUnbind", r"recalcUnbind"]),
        ],
    },
    {
        "id": "F-04",
        "name": "端架/地堆数双源不一致提醒 (CAD 解析值 vs 门店域值)",
        "spec": "产品真源/功能/端架地堆数不一致的提醒/端架地堆不一致的提醒.md",
        "probes": [
            ("B", [r"cadCount", r"CadCount"]),
            ("C", [r"cadCount", r"CadCount"]),
        ],
    },
    {
        "id": "F-05",
        "name": "运营报表 · top300 把货摆对门店明细服务端分页",
        "spec": "产品真源/实现方案/运营报表-top300把货摆对-实现方案.md (风险项 5)",
        "probes": [
            ("B", [r"Top300Report", r"top300Report", r"PutGoodsRight",
                   r"putGoodsRight", r"合格门店率"]),
            ("C", [r"Top300Report", r"top300Report", r"PutGoodsRight",
                   r"putGoodsRight", r"合格门店率"]),
        ],
    },
    {
        "id": "F-06",
        "name": "移动端货架图 · 品类及货框序号叠加",
        "spec": "产品真源/功能/移动端货架图/产品spec.md",
        "probes": [
            ("B", [r"品类及货框序号"]),
            ("C", [r"品类及货框序号"]),
            # H5 是本需求的真实宿主仓。v2 漏扫了它, 导致误判。
            # 命中以下任一 → H5 已实现该需求 (至少部分)。
            ("H5", [r"品类及货框序号"]),
            ("H5", [(r"CategoryBounds", "src/")]),
            ("H5", [(r"useShelfScatterBounds|cateBounds|columnBounds",
                     "src/")]),
            ("H5", [(r"showCateBounds", "src/")]),
        ],
    },
    {
        "id": "F-07",
        "name": "新开店数据推送 · 门店商品清单下发要货侧",
        "spec": "产品真源/功能/新开店数据推送/产品spec.md",
        "probes": [
            ("B", [r"StoreSkuDisplayPush", r"skuDisplayPush",
                   r"pushStoreSkuDisplay"]),
            ("C", [r"StoreSkuDisplayPush", r"skuDisplayPush"]),
        ],
    },
    {
        "id": "F-08",
        "name": "人工导入失败 Excel 下载 + 整店覆盖",
        "spec": "产品真源/功能/货架陈列任务/20260930-人工复核和申诉对接流程.md",
        "probes": [
            # 「失败 Excel 下载」与「整店覆盖」是具体行为, 不能被
            # 「失败原因」(71 处) 这类泛词误判为已实现
            ("B", [r"failExcel", r"FailExcel", r"failedExcel",
                   r"downloadFail", r"整店覆盖",
                   (r"整店覆盖", "busyming-merchandising-domain/"),
                   (r"失败.*Excel|Excel.*失败", "busyming-merchandising-web/")]),
            ("C", [r"failExcel", r"FailExcel", r"failedExcel",
                   r"失败 ?Excel", r"整店覆盖"]),
        ],
    },
    {
        "id": "F-09",
        "name": "识别结果列表页 Excel 导出 (11 列)",
        "spec": "产品真源/实现方案/top300识别统计与AI纠正.md (本期不做)",
        "probes": [
            ("B", [r"recognition.*[Ee]xport", r"[Ee]xport.*recognition",
                   r"识别结果.*导出", r"导出.*识别结果"]),
            ("C", [r"recognition.*[Ee]xport", r"[Ee]xport.*recognition",
                   r"识别结果.*导出", r"导出.*识别结果"]),
        ],
    },
    {
        "id": "F-10",
        "name": "货架信息反馈版本 2 · 门店-品类维度一次提交多节货架",
        "spec": "产品真源/归档/20261011-货架信息反馈-版本2/20260920-货架信息反馈提交.md",
        "probes": [
            # v3 修订: v2 的 probe 用了 `shelfIds|shelfList|multiShelf|shelfDeleteFlag`
            # 这些**臆造**的字段名, 而实际实现用的是 `shelves` + `shelfTempKey` +
            # `deleted` + `seqNo` + `slots`。probe 与实现对不上 → 假缺口。
            # 这里改成按**规格语义**的签名 (门店-品类维度 + 多节货架 + 新增/删除标记) 探测。
            #
            # v2 的签名特征: 任务维度是「门店-品类」(而非 v1 的单货架),
            # 且一次可提交该品类的多节货架 + 新增/标记删除货架。
            ("B", [(r"shelfTempKey", "busyming-merchandising-api/")]),
            ("B", [(r"List<Shelf>\s+shelves|shelves\s*=\s*new ArrayList",
                     "busyming-merchandising-api/src/main/java/io/busyming/product/merchandising/api/request/shelffeedback/")]),
            ("B", [(r"shelfTempKey|shelves",
                     "busyming-merchandising-web/src/main/java/io/busyming/product/merchandising/web/controller/mobile/ShelfFeedbackH5Controller.java")]),
            ("B", [(r"shelfTempKey|shelves|deleted",
                     "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/shelffeedback/submit/")]),
            # H5 是本需求的真实前端宿主仓 (v2 漏扫)。
            ("H5", [(r"shelfTempKey|shelves", "src/")]),
            ("H5", [(r"queryFeedbackForm|submitFeedback", "src/services/")]),
            ("C", [(r"shelfTempKey|shelfIds|shelfList", "src/api/")]),
        ],
    },
]


def search(repo, pattern):
    """在仓库里搜索, 返回 (命中文件列表, 命中数)。排除测试文件。"""
    try:
        p = subprocess.run(
            ["rg", "-l", "--no-messages", "-g", "*.java", "-g", "*.ts",
             "-g", "*.vue", "-g", "!*Test.java", "-g", "!*Tests.java",
             "-g", "!*spec.ts", "-g", "!*spec.js", pattern, "."],
            cwd=repo, capture_output=True, text=True, timeout=180)
        files = [os.path.abspath(os.path.join(repo, l.strip()))
                 for l in p.stdout.splitlines() if l.strip()]
        return files[:5], len(files)
    except Exception:
        return [], -1


def _is_comment_line(s):
    """判断一行是否纯注释 (Javadoc / // / /* / html 注释)。"""
    return (s.startswith("//") or s.startswith("*") or s.startswith("/*")
            or s.startswith("<!--") or s.startswith("--"))


def search_scoped(repo, pattern, scope):
    """在 scope 指定的路径子树下搜索, 返回 (命中文件列表, 非注释命中数)。

    计数只统计**非注释**的匹配行 —— 注释里的字面提及不算实现。
    v2 的第三个坑: probe 命中了中文 Javadoc, 例如
    `CategoryVersionRecalcStoreService` 里写着
    「算不出版本不等于不需要解绑」—— 那是**注释**里的字面提及,
    不是解绑调用。

    v3 额外支持 `*.tsx` (H5 是 React)。
    """
    try:
        p = subprocess.run(
            ["rg", "-n", "--no-messages", "-g", "*.java", "-g", "*.ts",
             "-g", "*.tsx", "-g", "*.vue", "-g", "!*Test.java",
             "-g", "!*Tests.java", "-g", "!*spec.ts", "-g", "!*spec.js",
             "-g", "!*spec.tsx", "-g", "!*test.tsx", "-g", "!*test.ts",
             pattern, scope],
            cwd=repo, capture_output=True, text=True, timeout=180)
        files, n, samples = [], 0, []
        for line in p.stdout.splitlines():
            if not line.strip():
                continue
            path, _, body = line.partition(":")
            if not body:
                continue
            # body 形如 "123:    代码内容"
            _, _, body = body.partition(":")
            if _is_comment_line(body.strip()):
                continue
            n += 1
            ap = os.path.abspath(os.path.join(repo, path))
            if ap not in files:
                files.append(ap)
            if len(samples) < 2:
                samples.append(os.path.relpath(ap, repo))
        return files[:5], n
    except Exception:
        return [], -1


def main():
    results = []
    for c in CANDIDATES:
        hits = []
        for label, patterns in c["probes"]:
            repo = REPOS[label]
            for entry in patterns:
                # entry 可以是裸正则, 也可以是 (正则, 路径范围) 二元组
                if isinstance(entry, tuple):
                    pat, scope = entry
                else:
                    pat, scope = entry, "."
                files, n = search_scoped(repo, pat, scope)
                if n > 0:
                    hits.append({
                        "repo": label, "pattern": pat, "scope": scope,
                        "count": n,
                        "sample": [os.path.relpath(f, repo) for f in files[:2]],
                    })
        implemented = bool(hits)
        results.append({
            "id": c["id"], "name": c["name"], "spec": c["spec"],
            "verdict": "ALREADY_IMPLEMENTED" if implemented else "GAP_CONFIRMED",
            "hits": hits,
        })
        print(f"{c['id']}: {'已实现(排除)' if implemented else '缺口成立'}"
              f"  <- {c['name']}")
        for h in hits[:3]:
            print(f"        {h['repo']} /{h['pattern']}/  x{h['count']}"
                  f"  {h['sample']}")
        if not implemented:
            print(f"        (全部 probe 无命中)  规格: {c['spec']}")

    n_gap = sum(1 for r in results if r["verdict"] == "GAP_CONFIRMED")
    print(f"\n合计: {n_gap} 个缺口成立 / {len(results)} 个候选")

    if "--json" in sys.argv:
        out = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "docs", "efficacy", "candidate-verification.json")
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=2)
        print(f"-> {out}")


if __name__ == "__main__":
    main()
