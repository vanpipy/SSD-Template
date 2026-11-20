#!/usr/bin/env python3
"""规格-代码 缺口探针器 (spec-gap-probe.py)

**为什么需要这个脚本**: 人工逐条读规格找缺口太慢, 而且极易漏。
本脚本把规格里的**行为签名**提取成可搜索的正则, 到 B / C / H5 / legacy PC 四个代码仓里
反查, 找出**规格要求但代码里完全没有承载点**的能力。

**它不是判决器**: probe 无命中 **不等于** 缺口成立 (可能是命名不同)。
脚本只输出**候选缺口**, 每条都必须人工语义复核后才能进预登记清单。

**判定模型 (anchors / absent / present)**:

每条探针声明三组正则:

- **anchors** (必须命中): 该能力**所在模块确实存在**的证据。
  用来证明「探针确实搜对了地方」。anchor 缺失 → 判定 **INCONCLUSIVE**,
  而不是直接判缺口 —— 否则「仓库路径写错」「模块整体不存在」
  会被静默当成「功能没实现」, 这类假阳性会直接污染实验候选池。
- **absent** (必须不命中): 若命中, 说明**目标能力已经实现** → 排除该候选。
- **present** (必须命中): 代码里**当前偏差确实存在**的证据。
  例如「开关默认关」写成 `useState(false)`; 只有搜到它, 才能说
  「规格要求默认开, 而代码默认关」。

三种判定:

| 判定 | 含义 | 处理 |
|------|------|------|
| GAP | anchors 全命中 + absent 全不命中 + present 全命中 | 候选缺口, 需人工复核后进池 |
| IMPLEMENTED | 任一 absent 命中 | 排除 |
| INCONCLUSIVE | anchor 缺失, 或 present 未命中 (证据不足) | 探针无效, 需修路径或换标识 |

**为什么需要 present**: 只靠 absent 只能证明「没实现」, 无法证明
「当前行为是什么」。两者分开后, 判语可以直接引用代码行,
评审者不必自己再去翻代码。

用法:
    python3 scripts/spec-gap-probe.py                     # 列出所有探针结果
    python3 scripts/spec-gap-probe.py --id F-01           # 只看某条
    python3 scripts/spec-gap-probe.py --json out.json     # 输出 JSON
    python3 scripts/spec-gap-probe.py --list              # 只列探针定义

探针定义格式 (见 PROBES):
    "anchors": [(repo, scope_or_None, [正则...]), ...]   # 必须命中
    "absent":  [(repo, scope_or_None, [正则...]), ...]   # 必须不命中
    "present": [(repo, scope_or_None, [正则...]), ...]   # 必须命中 (当前偏差证据)
    repo 限定 = 子树路径, 命中必须落在该子树内
"""
import argparse
import json
import os
import re
import subprocess
import sys

WORKSPACE = "/home/leroy/Project/merchandising-workspace"
REPO_B = os.path.join(WORKSPACE, "busyming-merchandising")
REPO_C = os.path.join(WORKSPACE, "busyming-merchandising-vue-pc")
REPO_H5 = os.path.join(WORKSPACE, "busyming-merchandising-h5")
# legacy PC (Next.js) —— 真实目录名是 busyming-merchandising-pc, 不是 -vue-pc-old。
# 写错会让该仓静默变成 REPO_MISSING, 探针看起来「零命中」实际是「没查」。
REPO_PC_OLD = os.path.join(WORKSPACE, "busyming-merchandising-pc")

REPOS = {"B": REPO_B, "C": REPO_C, "H5": REPO_H5, "PCOLD": REPO_PC_OLD}

SOURCE_GLOBS = [
    "-g", "*.java", "-g", "*.ts", "-g", "*.tsx", "-g", "*.vue", "-g", "*.js",
    "-g", "!*Test.java", "-g", "!*Tests.java", "-g", "!*Test.kt",
    "-g", "!*spec.ts", "-g", "!*spec.tsx", "-g", "!*spec.js", "-g", "!*test.ts",
    "-g", "!*tests.ts", "-g", "!*__tests__/*",
]


def _rg(repo, pattern, scope=None):
    """在仓库里搜索。返回 (命中行数, 命中文件前 5 个)。"""
    if not os.path.isdir(repo):
        return 0, []
    cmd = ["rg", "-n", "--no-messages"] + SOURCE_GLOBS + [pattern]
    cmd.append(scope if scope else ".")
    try:
        p = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=180)
    except Exception:
        return -1, []
    lines = [l for l in p.stdout.splitlines() if l.strip()]
    files = []
    for l in lines:
        f = l.split(":", 1)[0]
        if f not in files:
            files.append(f)
    return len(lines), files[:5]


def _is_comment(text):
    t = text.strip()
    return (t.startswith("//") or t.startswith("*") or t.startswith("/*")
            or t.startswith("<!--") or t.startswith("--")
            or t.startswith("* @"))


def probe_repo(repo, pattern, scope=None, include_comments=False):
    """返回 (非注释命中数, 命中样例列表)。注释里的字面提及不算实现。

    **scope 必须是唯一路径参数**。同时传 scope 与 "." 会让 rg 同时搜两处,
    scope 就完全失效了 —— 那会让「限定子树」的探针被全仓命中误判为已实现。

    **include_comments**: present 组必须置 True。理由:
    「偏差证据」常常就写在 Javadoc 里 —— 例如
    DisplayTaskImageAiRejudgedHandleService 的类注释明写「不重算门店」,
    这句话本身就是「当前行为与规格相反」的直接证据。
    anchors / absent 组必须保持 False (注释里的提及不算实现)。
    """
    if not os.path.isdir(repo):
        return 0, []
    cmd = ["rg", "-n", "--no-messages"] + SOURCE_GLOBS + [pattern]
    cmd.append(scope if scope else ".")
    try:
        p = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=180)
    except Exception:
        return 0, []
    hits = []
    for line in p.stdout.splitlines():
        if not line.strip():
            continue
        # rg -n 的输出格式取决于搜索目标:
        #   - 搜索目录:  path:lineno:content   (3 段)
        #   - 搜索单文件: lineno:content       (2 段, **没有 path 前缀**)
        # 旧实现只认 3 段, 于是**指向单个文件的 scope 全部返回 0 命中** ——
        # 这会把「文件里明确写了偏差声明」误判成「文件里什么都没写」。
        parts = line.split(":", 2)
        if len(parts) == 3:
            path, lineno, content = parts
        elif len(parts) == 2:
            path, lineno, content = "", parts[0], parts[1]
        else:
            continue
        if not include_comments and _is_comment(content):
            continue
        hits.append(f"{path}:{lineno}" if path else f"(scoped):{lineno}")
    return len(hits), hits[:5]


# ---------------------------------------------------------------------------
# 探针定义
#   anchors: [(repo, scope|None, [正则...])]  必须命中, 否则 INCONCLUSIVE
#   absent:  [(repo, scope|None, [正则...])]  必须不命中, 否则 IMPLEMENTED
#   present: [(repo, scope|None, [正则...])]  必须命中, 否则 INCONCLUSIVE
#   scope=None = 全仓; 否则限定子树
# ---------------------------------------------------------------------------
PROBES = [
    {
        "id": "F-01",
        "name": "运营节奏报表 · 三步进度卡片与门店维度转化漏斗",
        "spec": "产品真源/功能/运营节奏报表/产品spec.md + 设计中/20260908-运营节奏转化漏斗/specs/Web端UI描述.md",
        "anchors": [
            # 漏斗的宿主域: 人工纠正 / 挂图 —— 后端已有, 说明探针搜对了模块
            ("B", None, [r"StoreCheckCorrection", r"ManualCheck"]),
            # 前端宿主域: 识别结果列表页 (C 仓 display-inspection)
            ("C", "src/modules/display-inspection/", [r".*"]),
        ],
        "absent": [
            ("B", None, [r"运营节奏", r"OperationRhythm", r"operationRhythm", r"rhythmReport"]),
            ("C", None, [r"运营节奏", r"OperationRhythm", r"operationRhythm", r"rhythmReport"]),
            ("H5", None, [r"运营节奏", r"OperationRhythm", r"rhythmReport"]),
            # 漏斗的四个专有字段 (spec: specMatched / specRendered / manualMatched / manualRendered)
            # 注: manualMatched 单独用会误伤 —— 后端 StoreCheckCorrectionServiceImpl 的
            # ext_json.manualMatched 是「人工挂接图片」标记, 与漏斗无关。
            # 因此只查 specMatched / specRendered / manualRendered 三个无歧义标识。
            ("B", None, [r"specMatched", r"specRendered", r"manualRendered"]),
            ("C", None, [r"specMatched", r"specRendered", r"manualRendered"]),
            # 漏斗专有口径
            ("B", None, [r"剔除特殊品类"]),
            ("C", None, [r"剔除特殊品类", r"流失\s*\d+\s*家"]),
        ],
    },
    {
        "id": "F-02",
        "name": "门店执行列表 · 门店展开子任务与图片复核入口",
        "spec": "产品真源/功能/货架陈列任务/20261009-门店执行列表与图片复核.md",
        "anchors": [
            # 宿主域: 货架陈列任务模块在 C 仓确实存在
            ("C", "src/modules/display-task-shelf/", [r".*"]),
        ],
        "absent": [
            ("B", None, [r"门店执行列表", r"StoreExecutionList", r"storeExecutionList"]),
            ("C", None, [r"门店执行列表", r"StoreExecutionList", r"store-execution-list",
                         r"storeExecutionList"]),
            ("H5", None, [r"门店执行列表", r"StoreExecutionList"]),
        ],
    },
    {
        "id": "F-11",
        "name": "算法迭代重跑 · 仅重跑不合格图 + 触发合格率重算 + 排除已达标门店",
        "spec": "产品真源/功能/货架陈列任务/top300无图稽查-specs/spec-21-重跑机制.md §2/§6/§7",
        "anchors": [
            # 识别重判链路确实存在 (但只做「SKU 重判」, 不是「算法迭代重跑」)
            ("B", "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/displaytask/service/check/",
             [r"DisplayAiSkuRejudgeService"]),
            # 门店合格率统计确实存在
            ("B", None, [r"StoreCheckReportStatCalculator"]),
        ],
        "absent": [
            # (a) 「算法迭代重跑」作为**独立触发源**的承载点。
            #     现有 DisplayAiSkuRejudgeService 只支持「按 imageIds 重判已保存明细」,
            #     走的是 checkEngine.evaluateImageSkus(...) 本地规则引擎, **不调外部算法**,
            #     也没有「按算法版本挑选不合格图批量重跑」的编排。
            #     实测: rejudgeOne() 读的是 readMapper.selectDetails(imageId) 已保存明细。
            ("B", None, [r"algorithmVersion", r"algoVersion", r"modelVersion",
                         r"recognizeVersion", r"algorithmRerun", r"rerunByAlgorithm"]),
            # (b) 「已达标门店不参与重跑」的范围过滤。
            #     现有 eligibility() 只校验 IMAGE_NOT_FOUND / TASK_OWNER_MISMATCH /
            #     UNSUPPORTED_SCENE / IMAGE_NOT_RECOGNIZED / RECOGNITION_TASK_CODE_EMPTY,
            #     **不检查门店是否 completed**。
            ("B", "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/displaytask/service/check/DisplayAiSkuRejudgeService.java",
             [r"COMPLETED", r"completed", r"storeStatus", r"taskStatus"]),
            # (c) 「重跑后触发合格率结算」—— 现有链路只推图级事件, 不重算门店合格率。
            #     实测: DisplayTaskImageAiRejudgedHandleService 的 Javadoc 明写
            #     「不重算门店」。
            ("B", "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/displaytask/event/DisplayTaskImageAiRejudgedHandleService.java",
             [r"passRate", r"PassRate", r"recalcStore", r"recomputeStore",
              r"settleStore", r"qualifyStore"]),
            # (d) 前端无「算法重跑」入口 (C 仓无 rejudge API 封装)
            ("C", None, [r"rejudge", r"rejudgeSkus", r"rerunRecognition"]),
        ],
        "present": [
            # 偏差证据 1: 现有 handler 明确声明「不重算门店」—— 与规格 §7 相反。
            ("B", "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/displaytask/event/DisplayTaskImageAiRejudgedHandleService.java",
             [r"不重算门店"]),
            # 偏差证据 2: 重判请求体只有 imageIds, 没有算法版本 / 重跑范围参数。
            ("B", "busyming-merchandising-api/src/main/java/io/busyming/product/merchandising/api/request/write/DisplayAiSkuRejudgeRequestVO.java",
             [r"imageIds"]),
        ],
    },
    {
        "id": "F-03",
        "name": "品类版本批量重算 · 不一致解绑回退待匹配模板",
        "spec": "产品真源/实现方案/品类版本批量重算.md (现状 5: 技术尚未实现)",
        "anchors": [
            # 重算链路本身确实存在
            ("B", "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/recalc/",
             [r"CategoryVersionRecalc"]),
        ],
        "absent": [
            # 关键: 解绑在重算链路里是**间接**完成的。
            # CategoryVersionRecalcStoreService:233 调 patternAutoMatchService.matchAndReconcileWithDetail,
            # 而 PatternAutoMatchService.unbind()(:549) 内部调 itemDisplayPlanTxService.unbindPattern。
            # 所以 absent 必须查「重算链路 → 自动匹配 → 解绑」这条**间接链**,
            # 只在 recalc/ 子树里查 unbindPattern 会漏判成缺口 (假阳性)。
            ("B", "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/recalc/",
             [r"unbindPattern", r"matchAndReconcileWithDetail", r"autoMatch"]),
        ],
        "present": [
            # 偏差证据: 重算链路确实走了自动匹配 (所以解绑能力被复用)
            ("B", "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/recalc/",
             [r"patternAutoMatchService\.matchAndReconcileWithDetail",
              r"patternAutoMatchFormationService\.autoMatch"]),
        ],
    },
    {
        "id": "F-04",
        "name": "端架/地堆数双源不一致提醒 (CAD 解析值 vs 门店域值)",
        "spec": "产品真源/功能/端架地堆数不一致的提醒/端架地堆不一致的提醒.md",
        "anchors": [
            # 端架/地堆对比能力确实存在于后端与 legacy PC
            ("B", None, [r"EndcapFloorCompare"]),
        ],
        "absent": [
            # 缺口在 C/H5 侧: 双源不一致提醒的承载点。
            # 人工复核: legacy PC (busyming-merchandising-pc) **已实现**——
            #   src/routes/storeDetail/-components/PreviewLeftPanel/StoreOverviewPanel.tsx:31  cadCount 字段
            #   :49  「CAD 识别为 ${cadCount} 个，与门店域不符合。」
            #   :70  端架: { cadCount: compare.cadEndcapCount, ... }
            #   src/api/types/store.ts:171-174  cadEndcapCount / cadFloorCount / endcapConsistent / floorConsistent
            # 所以缺口不是「有没有 cadCount」, 而是「Vue PC (C 仓) 这条新前端线**没有迁移**该能力」。
            # 注意: 本探针只查 C/H5, 不查 PCOLD —— 因为 legacy PC 已实现, 查它只会让探针恒定判 IMPLEMENTED。
            ("C", None, [r"cadCount", r"CadCount", r"cadEndcapCount", r"cadFloorCount",
                         r"端架.*不一致", r"地堆.*不一致"]),
            ("H5", None, [r"cadCount", r"CadCount", r"cadEndcapCount", r"cadFloorCount",
                          r"端架.*不一致", r"地堆.*不一致"]),
        ],
    },
    {
        "id": "F-05",
        "name": "运营报表 · top300 把货摆对门店明细服务端分页",
        "spec": "产品真源/实现方案/运营报表-top300把货摆对-实现方案.md (风险项 5)",
        "anchors": [
            # 报表的宿主域: 「把货摆对」清单能力在后端确实存在
            ("B", None, [r"把货摆对", r"DisplayGoods"]),
        ],
        "absent": [
            # 「把货摆对」在 B 仓指的是**清单表** (ads_bhbd_display_goods_d_i), 不是报表,
            # 所以不能拿它当报表承载点, 也不能拿它当「无命中」依据。
            # 报表的真正专有标识是「合格门店率」与组织维度四层。
            ("B", None, [r"Top300Report", r"top300Report", r"PutGoodsRight",
                         r"putGoodsRight", r"合格门店率"]),
            ("C", None, [r"Top300Report", r"top300Report", r"PutGoodsRight",
                         r"putGoodsRight", r"合格门店率"]),
            ("H5", None, [r"Top300Report", r"PutGoodsRight", r"合格门店率"]),
            # 四级组织维度 (报表专有, 陈列侧其它功能不会用这四个词组)
            ("B", None, [r"运营大区", r"运营战区"]),
            ("C", None, [r"运营大区", r"运营战区"]),
        ],
    },
    {
        "id": "F-06",
        "name": "移动端货架图 · 定量蓝框 / 开关默认开 / 覆盖定量与混合货架",
        "spec": "产品真源/功能/移动端货架图/产品spec.md R01-R05",
        "anchors": [
            # H5 是真实宿主仓, 且该功能已部分实现 (散称品类框/开关/列徽章都在)
            ("H5", "src/components/ShelfPanel/DisplayInfo/",
             [r"CategoryBounds", r"useShelfScatterBounds", r"showCateBounds"]),
        ],
        "absent": [
            # (a) 定量品类蓝框 —— 整个 DisplayInfo 子树对「定量」0 命中。
            #     实测: rg '定量|Quantitative' src/components/ShelfPanel/DisplayInfo/ -> 0 文件。
            #     实现里只有散称橙框 (CategoryBounds.tsx:66 lineColor='#FF7300')。
            #     规格 R03 要求「蓝框 + 蓝底白字标签」。
            ("H5", "src/components/ShelfPanel/DisplayInfo/", [r"定量", r"Quantitative"]),
            # (b) 开关默认开 —— 规格 R01「默认开、不记忆」。
            #     实测: index.tsx:57 useState(false) —— 默认关。
            #     若将来改成 useState(true), 这个模式就会命中 → 排除该候选。
            ("H5", "src/components/ShelfPanel/DisplayInfo/",
             [r"showCateBounds,\s*setShowCateBounds\]\s*=\s*useState\(true\)"]),
        ],
        "present": [
            # 偏差证据 1: 开关默认关 (规格 R01 要求默认开)
            #     实测: index.tsx:57 const [showCateBounds, setShowCateBounds] = useState(false);
            ("H5", "src/components/ShelfPanel/DisplayInfo/",
             [r"showCateBounds,\s*setShowCateBounds\]\s*=\s*useState\(false\)"]),
            # 偏差证据 2: 开关容器被 isScattered 门控 (规格 F1 要求在货架基础信息卡片标题行右侧, 不分货架类型)
            #     实测: index.tsx:510 {isScattered && (
            #     注: rg 默认按行匹配, 所以只匹配到 `{isScattered && (` 这一行即可。
            ("H5", "src/components/ShelfPanel/DisplayInfo/",
             [r"\{isScattered\s*&&\s*\("]),
            # 偏差证据 3: 渲染参数被 isScattered 门控 (规格 R05 混合货架需各自渲染)
            #     实测: index.tsx:540 showCateBounds={isScattered && showCateBounds}
            ("H5", "src/components/ShelfPanel/DisplayInfo/",
             [r"showCateBounds=\{isScattered\s*&&\s*showCateBounds\}"]),
        ],
    },
    {
        "id": "F-07",
        "name": "新开店数据推送 · 门店商品清单下发要货侧",
        "spec": "产品真源/功能/新开店数据推送/产品spec.md",
        "anchors": [
            # 推送基础设施确实存在 (StoreEventCallbackProducer / ProjectPushAppService)
            ("B", None, [r"StoreEventCallbackProducer|ProjectPushAppService", r"PushRules"]),
        ],
        "absent": [
            # 真正缺的是「商品清单下发要货侧」的推送契约与字段
            ("B", None, [r"totalCategoryCount", r"cadParsedCategoryCount",
                         r"layoutUploadUserCode", r"layoutUploadUserName",
                         r"layoutUploadTime", r"successCategoryCount"]),
            ("C", None, [r"totalCategoryCount", r"cadParsedCategoryCount",
                         r"layoutUploadUserCode", r"successCategoryCount"]),
            ("H5", None, [r"totalCategoryCount", r"cadParsedCategoryCount",
                         r"successCategoryCount"]),
        ],
    },
    {
        "id": "F-08",
        "name": "人工导入失败 Excel 下载 + 整店覆盖",
        "spec": "产品真源/功能/门店套图管理/specs/门店分类与人工导入.md §2.2.4b (v1.8 新增)",
        "anchors": [
            # 导入任务与导入记录配置确实存在
            ("B", None, [r"FileImportTask"]),
            ("C", "src/modules/merchandising-template-manage/store-image-set-manage/components/ImportRecordDrawer/",
             [r".*"]),
        ],
        "absent": [
            # 「失败 Excel 下载」与「整店覆盖」是具体行为, 不能被「失败原因」(泛词) 误判
            ("B", None, [r"failExcel", r"FailExcel", r"failedExcel", r"downloadFailExcel"]),
            ("B", "busyming-merchandising-service/src/main/java/io/busyming/product/merchandising/service/write/",
             [r"整店覆盖"]),
            ("B", "busyming-merchandising-domain/", [r"整店覆盖"]),
            ("C", None, [r"failExcel", r"FailExcel", r"failedExcel", r"下载失败\s*Excel"]),
            ("C", None, [r"整店覆盖"]),
        ],
    },
    {
        "id": "F-09",
        "name": "识别结果列表页 Excel 导出 (11 列)",
        "spec": "产品真源/实现方案/top300识别统计与AI纠正.md §3「本期不做」第 1 条",
        "anchors": [
            # 识别结果列表页在 C 仓确实存在
            ("C", "src/modules/display-inspection/", [r".*"]),
            ("B", None, [r"DisplayAiRecognition"]),
        ],
        "absent": [
            ("B", None, [r"recognition.*[Ee]xport", r"[Ee]xport.*recognition",
                         r"识别结果.*导出", r"导出.*识别结果"]),
            ("C", None, [r"recognition.*[Ee]xport", r"[Ee]xport.*recognition",
                         r"识别结果.*导出", r"导出.*识别结果"]),
            # 前端导出通用能力存在 (其它模块有 image-export), 但**识别结果列表页**没有导出入口
            ("C", "src/modules/display-inspection/", [r"[Ee]xport.*[Ee]xcel",
                                                    r"导出", r"downloadExcel"]),
            ("H5", None, [r"识别结果.*导出"]),
        ],
        "present": [
            # 偏差证据: 规格把该导出明确列入「本期不做」。
            #   产品真源/实现方案/top300识别统计与AI纠正.md:122
            #     「- 导出功能（识别结果列表页 11 列的 Excel 导出）」
            # => 这不是「漏实现」, 而是**规格主动排除**。作为候选会诱导两臂去实现规格说不做的事,
            #    且任何一臂实现了都算「超出规格范围」, 破坏配对公平。
            #    所以本探针用 spec_excluded 标记 (见 evaluate()), 不走 GAP 路径。
        ],
        "spec_excluded": True,
        "spec_exclusion_ref": "产品真源/实现方案/top300识别统计与AI纠正.md:122 「- 导出功能（识别结果列表页 11 列的 Excel 导出）」",
    },
    {
        "id": "F-10",
        "name": "货架信息反馈版本 2 · 门店-品类维度一次提交多节货架",
        "spec": "产品真源/归档/20261011-货架信息反馈-版本2/20260920-货架信息反馈提交.md",
        "anchors": [
            ("B", "busyming-merchandising-api/src/main/java/io/busyming/product/merchandising/api/request/shelffeedback/",
             [r"ShelfFeedback"]),
        ],
        "absent": [
            # v2 签名: 门店-品类维度 + 多节货架 + 新增/删除标记。
            # 人工复核: 这三项**已实现**——
            #   ShelfFeedbackSubmitRequest.java:47  categoryCode (门店-品类维度)
            #   ShelfFeedbackSubmitRequest.java:53  List<Shelf> shelves (多节货架, max 200)
            #   ShelfFeedbackSubmitRequest.java:71  shelfTempKey (新增货架临时标识)
            #   ShelfFeedbackSubmitRequest.java:74  deleted (删除标记)
            # 所以「整段货架一次性提交」不是缺口, 缺口在别处 (见 present)。
            # 保留这些模式作为回归哨兵: 若将来有人把它们删掉, 本探针应重新判定。
            ("B", "busyming-merchandising-api/src/main/java/io/busyming/product/merchandising/api/request/shelffeedback/",
             [r"shelfTempKey", r"List<Shelf>\s+shelves", r"private Boolean deleted"]),
            ("H5", "src/", [r"shelfTempKey"]),
        ],
        "present": [
            # 偏差证据 1: 提交体有货架删除标记, 但规格 R15 要求「删除为**待审核意向**, 门店标记删除不代表总部已确认删除」。
            #   需核实服务端是否把门店的 deleted 标记直接落成真实删除。
            ("B", "busyming-merchandising-api/src/main/java/io/busyming/product/merchandising/api/request/shelffeedback/ShelfFeedbackSubmitRequest.java",
             [r"deleted"]),
        ],
    },
]


def evaluate(probe):
    """对一条探针跑 anchors + absent + present, 返回判定结果。

    判定顺序:
      1. anchors 有未命中            → INCONCLUSIVE (探针没落在对的模块上)
      2. absent 有命中               → IMPLEMENTED (目标能力已实现, 排除)
      3. present 有未命中            → INCONCLUSIVE (证据不足)
      4. 否则                        → GAP (候选缺口)

    **REPO_MISSING 的仓, 不参与命中判定, 但必须显式报出来** ——
    否则「仓不存在」会被当成「代码里没有」, 这是最危险的假阳性来源。
    """
    results = []
    anchors_hit = 0
    anchors_total = 0
    absent_hit = False
    searched_repos = set()
    present_groups = []

    def run(kind, repo_label, scope, patterns):
        repo = REPOS.get(repo_label)
        if repo is None or not os.path.isdir(repo):
            results.append({"kind": kind, "repo": repo_label, "scope": scope,
                            "status": "REPO_MISSING", "hits": [],
                            "note": f"仓库不存在或路径错误: {repo}"})
            return False
        searched_repos.add(repo_label)
        hit = False
        # present 组允许命中注释 (偏差声明常写在 Javadoc 里)
        with_comments = (kind == "present")
        for pattern in patterns:
            count, samples = probe_repo(repo, pattern, scope,
                                        include_comments=with_comments)
            if count > 0:
                hit = True
                results.append({
                    "kind": kind, "repo": repo_label, "scope": scope,
                    "pattern": pattern, "status": "HIT",
                    "count": count, "samples": samples,
                })
        return hit

    for repo_label, scope, patterns in probe.get("anchors", []):
        anchors_total += 1
        if run("anchor", repo_label, scope, patterns):
            anchors_hit += 1

    anchor_ok = anchors_total > 0 and anchors_hit == anchors_total

    for repo_label, scope, patterns in probe.get("absent", []):
        if run("absent", repo_label, scope, patterns):
            absent_hit = True

    for repo_label, scope, patterns in probe.get("present", []):
        present_groups.append(run("present", repo_label, scope, patterns))

    # present 是可选的: 「整块模块缺失」类候选没有偏差行可引,
    # 它的证据就是 absent 不命中。只有「部分实现 + 行为偏差」类候选
    # 才需要 present 来锚定「当前行为是什么」。
    present_ok = all(present_groups)

    missing = sorted({r["repo"] for r in results
                      if r["status"] == "REPO_MISSING"})
    searched = sorted(searched_repos)

    if not anchor_ok:
        verdict = "INCONCLUSIVE"
    elif probe.get("spec_excluded"):
        # 规格主动排除的能力 (列入「本期不做」/ 明确不做) 不是缺口。
        # 把它当候选会诱导两臂实现规格说不做的事, 且任何一臂实现了都算「超出规格范围」,
        # 破坏配对公平。单独标记, 不计入 GAP 也不计入 IMPLEMENTED。
        verdict = "SPEC_EXCLUDED"
    elif absent_hit:
        verdict = "IMPLEMENTED"
    elif present_ok:
        verdict = "GAP"
    else:
        verdict = "INCONCLUSIVE"

    return verdict, results, missing, searched, {
        "anchors_hit": anchors_hit, "anchors_total": anchors_total,
        "absent_hit": absent_hit,
        "present_hit": present_groups.count(True),
        "present_total": len(present_groups),
    }


def main():
    ap = argparse.ArgumentParser(description="规格-代码 缺口探针器")
    ap.add_argument("--id", help="只跑某条探针 (如 F-01)")
    ap.add_argument("--json", help="输出 JSON 到该文件")
    ap.add_argument("--list", action="store_true", help="只列探针定义")
    args = ap.parse_args()

    if args.list:
        for p in PROBES:
            print(f"{p['id']}  {p['name']}")
            print(f"      规格: {p['spec']}")
        return 0

    probes = [p for p in PROBES if not args.id or p["id"] == args.id]
    if not probes:
        print(f"没有 ID 为 {args.id} 的探针", file=sys.stderr)
        return 2

    out = []
    for p in probes:
        verdict, results, missing, searched, stats = evaluate(p)
        label = {"GAP": "候选缺口(需人工复核)",
                 "IMPLEMENTED": "已实现(排除)",
                 "SPEC_EXCLUDED": "规格排除(本期不做)",
                 "INCONCLUSIVE": "探针无效(anchor 未命中)"}[verdict]
        print(f"{p['id']}: {label}  <- {p['name']}")
        print(f"      规格: {p['spec']}")
        if p.get("spec_excluded"):
            print(f"      规格排除依据: {p.get('spec_exclusion_ref', '(未登记)')}")
        print(f"      anchor {stats['anchors_hit']}/{stats['anchors_total']}"
              f"  absent_hit={stats['absent_hit']}"
              f"  present {stats['present_hit']}/{stats['present_total']}")
        for r in results:
            scope = r.get("scope") or "(全仓)"
            tag = r["kind"]
            if r["status"] == "HIT":
                print(f"      [{tag}] {r['repo']} {scope} /{r['pattern']}/ x{r['count']}")
                for s in r["samples"][:3]:
                    print(f"        {s}")
            else:
                print(f"      [{tag}] {r['repo']} {scope} -> {r['status']}"
                      + (f"  ({r['note']})" if r.get("note") else ""))
        if missing:
            print(f"      !! 未实际查询的仓: {', '.join(missing)}"
                  f"  (结论仅覆盖: {', '.join(searched) or '无'})")
        out.append({
            "id": p["id"], "name": p["name"], "spec": p["spec"],
            "verdict": verdict,
            "spec_exclusion_ref": p.get("spec_exclusion_ref"),
            "searched_repos": searched,
            "missing_repos": missing,
            "stats": stats,
            "results": results,
        })

    gaps = sum(1 for o in out if o["verdict"] == "GAP")
    inconclusive = sum(1 for o in out if o["verdict"] == "INCONCLUSIVE")
    excluded = sum(1 for o in out if o["verdict"] == "SPEC_EXCLUDED")
    print(f"\n合计: {gaps} 个候选缺口 / {len(out)} 个探针"
          + (f"  ({inconclusive} 个探针无效)" if inconclusive else "")
          + (f"  ({excluded} 个规格排除)" if excluded else ""))

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"已写入 {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
