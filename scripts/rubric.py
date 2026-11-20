#!/usr/bin/env python3
"""RUBRIC.md 的 AC 解析与**共享检查表**生成 (rubric.py)

Stdlib only.

## 为什么需要这个模块

`docs/efficacy/RUBRIC.md` 用**表格行**列 AC:

    | # | AC | 可观测判据 |
    |---|-----|-----------|
    | AC-2.1 | 不合格数 = 0 时, 该数字后不渲染 `›` 箭头 | DOM 中该格内不存在箭头 img 元素 |

而旧的 `measure.py` 只认 Markdown 复选框行 (`- [x] ...`), 因此解析出 **0 条 AC**,
`A_spec` 恒为 0, `CE` 恒为 0 —— 整个评分链路是坏的。

本模块把 RUBRIC.md 解析成结构化 AC 列表, 并据此生成**两臂共用**的检查表。

## 共享检查表的语义 (RUBRIC.md §4.1 的机械实现)

两臂的 AC 列表必须**逐字相同**。做法:

1. 从 RUBRIC.md 解析出 (候选 ID, AC ID, AC 文本, 判据) 四元组;
2. 生成一份**空勾选**的检查表 (每条 AC 一行, 复选框未勾选);
3. 两臂各自**独立填**自己的检查表副本 (填 `[x]` + 证据锚点);
4. 评分时校验: 两臂的检查表**除勾选状态与锚点外**, 其余内容必须与模板逐字相同。

模板本身由 `render_template()` 生成, 是**唯一真源**, 两臂都从它派生。
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- RUBRIC.md 结构 --------------------------------------------------------

# 章节标题: "### 3.1 F-02 · H5 移动端 · 「合格/不合格 Top300」格在不合格 = 0 时不渲染箭头"
RE_SECTION = re.compile(
    r"^###\s+(\d+\.\d+)\s+([A-Z][A-Za-z0-9-]*)\s+·\s+(.*)$")

# AC 表格行: "| AC-2.1 | 文本 | 判据 |"
# AC ID 允许连字符 (AC-B01-1 / AC-R01-1), 故字符集含 "-"。
RE_AC_ROW = re.compile(
    r"^\|\s*(AC-[A-Za-z0-9.-]+)\s*\|(.*)\|(.*)\|\s*$")

# 判据列里可能含转义竖线, 拆列时要处理
RE_SPLIT_COLS = re.compile(r"(?<!\\)\|")


def _split_row(line):
    """把表格行拆成单元格列表, 去掉首尾空单元与分隔行。"""
    s = line.strip()
    if not s.startswith("|"):
        return []
    inner = s[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    cells = RE_SPLIT_COLS.split(inner)
    return [c.strip() for c in cells]


def _is_separator(cells):
    return all(re.fullmatch(r":?-{2,}:?", c or "") for c in cells if c != "")


# --- 证据锚点 --------------------------------------------------------------

# 形如 {B}@<sha>:<path>#L<line>
RE_ANCHOR = re.compile(
    r"\{([A-Z][A-Z0-9]{0,7})\}@([0-9a-f]{7,40}):([^\s#]+)#L(\d+)")


def extract_anchor(text):
    """从一行文本里抽取证据锚点, 返回 (标识, sha, path, line) 或 None。"""
    m = RE_ANCHOR.search(text)
    if not m:
        return None
    return (m.group(1), m.group(2), m.group(3), int(m.group(4)))


# --- 解析 ------------------------------------------------------------------

def parse_rubric(path=None):
    """解析 RUBRIC.md, 返回 AC 列表。

    返回的每一项是 dict:
      candidate   候选 ID (如 "F-02")
      section     章节号 (如 "3.1")
      title       章节标题
      ac_id       AC ID (如 "AC-2.1")
      text        AC 描述
      criterion   可观测判据
      line        在 RUBRIC.md 中的行号 (1-based), 供人工核对
    """
    path = path or os.path.join(ROOT, "docs", "efficacy", "RUBRIC.md")
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    acs = []
    cur = None
    for lineno, line in enumerate(lines, start=1):
        m = RE_SECTION.match(line)
        if m:
            cur = {"section": m.group(1), "candidate": m.group(2),
                   "title": m.group(3).strip()}
            continue
        cells = _split_row(line)
        if len(cells) < 3:
            continue
        if _is_separator(cells):
            continue
        am = RE_AC_ROW.match(line.strip())
        if not am:
            continue
        # 跳过表头行 ("| # | AC | 可观测判据 |")
        if cells[0] in ("#", "AC") or cells[0].startswith("---"):
            continue
        ac_id = cells[0]
        if not ac_id.startswith("AC-"):
            continue
        if cur is None:
            raise ValueError(
                f"RUBRIC.md:{lineno}: AC {ac_id} 出现在任何 '### x.y' 章节之前")
        acs.append({
            "candidate": cur["candidate"],
            "section": cur["section"],
            "title": cur["title"],
            "ac_id": ac_id,
            "text": cells[1],
            "criterion": cells[2],
            "line": lineno,
        })
    return acs


def acs_by_candidate(acs):
    """按候选 ID 分组, 保持 RUBRIC.md 里的出现顺序。"""
    out = {}
    for a in acs:
        out.setdefault(a["candidate"], []).append(a)
    return out


def check_uniqueness(acs):
    """返回 (是否通过, 问题列表)。AC ID 必须全局唯一。"""
    problems = []
    seen = {}
    for a in acs:
        if a["ac_id"] in seen:
            problems.append(
                f"AC ID 重复: {a['ac_id']} (第 {seen[a['ac_id']]} 行 与 第 {a['line']} 行)")
        else:
            seen[a["ac_id"]] = a["line"]
    return (not problems), problems


def check_candidate_order(acs):
    """返回 (是否通过, 问题列表)。候选必须恰好 10 个, 且每个候选至少一条 AC。"""
    problems = []
    groups = acs_by_candidate(acs)
    if len(groups) != 10:
        problems.append(f"候选数应为 10, 实为 {len(groups)}: {sorted(groups)}")
    for cand, items in groups.items():
        if not items:
            problems.append(f"候选 {cand} 没有任何 AC")
    return (not problems), problems


# --- 共享检查表 ------------------------------------------------------------

HEADER_NOTE = ""  # 保留占位: 模板头部统一由 TEMPLATE_HEADER 承担


def _template_hash_of(text):
    """从检查表文本里抽出「模板版本」哈希。"""
    m = re.search(r"\*\*模板版本\*\*:\s*`([0-9a-f]{8,64})`", text)
    return m.group(1) if m else None


def _static_lines(text):
    """检查表里**非判定行**的静态内容 (头部 + 表头 + 分隔行)。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if RE_VERDICT_ROW.match(s):
            continue
        if s.startswith("|---") or s.startswith("| # |"):
            continue
        out.append(s)
    return out

TEMPLATE_HEADER = """# {candidate} 验收检查表

> **本表由 `scripts/rubric.py` 从 `docs/efficacy/RUBRIC.md` 自动生成, 请勿手工编辑。**
>
> 规则:
> 1. 每条 AC 一行, 判定为 `交付` 时把 `[ ]` 改成 `[x]`;
> 2. 判定为 `交付` 时, 在该行末尾追加证据锚点, 形如
>    `{{B}}@<sha>:<path>#L<line>`;
> 3. 判定为 `不适用` 时, 追加 `<!-- NA: <理由> -->`;
> 4. **只允许改动复选框状态、锚点与 NA 标记**, 其余内容必须与模板逐字相同
>    (由 `scripts/check-shared-checklist.py` 校验);
> 5. 两臂使用**同一份**检查表模板, 各自填自己的副本。
>
> **模板版本**: `{template_hash}`
"""


def render_template(candidate, acs, template_hash=None):
    """生成某个候选的**空勾选**检查表模板 (两臂共用的唯一真源)。"""
    if template_hash is None:
        template_hash = compute_template_hash()
    body = TEMPLATE_HEADER.format(candidate=candidate, template_hash=template_hash)
    body += "\n| # | AC | 可观测判据 | 判定 | 证据锚点 |\n"
    body += "|---|-----|---------|------|---------|\n"
    for i, a in enumerate(acs, start=1):
        body += (f"| {i} | `{a['ac_id']}` | {a['criterion']} | "
                 f"[ ] {a['ac_id']} |  |\n")
    return body


def render_all_templates(acs=None):
    """生成全部候选的检查表模板, 返回 {候选 ID: 模板文本}。"""
    acs = acs if acs is not None else parse_rubric()
    groups = acs_by_candidate(acs)
    h = compute_template_hash(acs)
    return {cand: render_template(cand, items, h) for cand, items in groups.items()}


def compute_template_hash(acs=None):
    """模板内容的 SHA-256 前 16 位。

    任何 AC 的文本、判据或顺序变化都会改变该哈希, 因此它能作为
    「两臂用的是同一份清单」的机器可验证凭据。
    """
    import hashlib
    acs = acs if acs is not None else parse_rubric()
    h = hashlib.sha256()
    for a in acs:
        h.update(a["ac_id"].encode("utf-8"))
        h.update(b"\x1f")
        h.update(a["text"].encode("utf-8"))
        h.update(b"\x1f")
        h.update(a["criterion"].encode("utf-8"))
        h.update(b"\x1e")
    return h.hexdigest()[:16]


# --- 检查表的解析 (供 measure.py 消费) ------------------------------------

# 判定行: "| 1 | `AC-2.1` | 判据 | [x] AC-2.1 | {B}@sha:path#L12 |"
RE_VERDICT_ROW = re.compile(
    r"^\|\s*\d+\s*\|\s*`?(AC-[A-Za-z0-9.-]+)`?\s*\|(.*)\|\s*\[([ xX])\]\s*"
    r"(AC-[A-Za-z0-9.-]+)\s*\|(.*)\|\s*$")


def parse_verdicts(text):
    """从填好的检查表里解析判定结果。

    返回 [(ac_id, checked_bool, anchor_or_None, na_reason_or_None), ...]
    """
    out = []
    for line in text.splitlines():
        m = RE_VERDICT_ROW.match(line.strip())
        if not m:
            continue
        ac_id = m.group(1)
        checked = m.group(3).lower() == "x"
        anchor_cell = m.group(5) or ""
        na = re.search(r"<!--\s*NA:\s*(.*?)\s*-->", anchor_cell)
        anchor = extract_anchor(anchor_cell)
        out.append((ac_id, checked, anchor, na.group(1) if na else None))
    return out


def checklist_diff(template_text, filled_text):
    """校验填好的检查表相对模板**只改了勾选/锚点/NA**。

    检查三件事:
      1. **模板版本哈希一致** —— 证明两臂用的是同一份 AC 清单;
      2. **AC 条数与集合一致** —— 不能增删 AC;
      3. **判据列逐字一致** —— 不能改判据来放水。

    返回 (是否通过, 问题列表)。
    """
    problems = []
    tpl_hash = _template_hash_of(template_text)
    got_hash = _template_hash_of(filled_text)
    if tpl_hash and got_hash != tpl_hash:
        problems.append(
            f"模板版本哈希不符: 模板 {tpl_hash} vs 填写稿 {got_hash} "
            f"(说明填写稿不是从这份模板派生的)")
    tpl = parse_verdicts(template_text)
    got = parse_verdicts(filled_text)
    if len(tpl) != len(got):
        problems.append(
            f"AC 条数不符: 模板 {len(tpl)} 条, 填写稿 {len(got)} 条")
    tpl_by_id = {a[0]: a for a in tpl}
    got_ids = set()
    for ac_id, checked, anchor, na in got:
        got_ids.add(ac_id)
        if ac_id not in tpl_by_id:
            problems.append(f"填写稿出现模板外的 AC: {ac_id}")
            continue
        # 模板自身的判据列必须与填写稿一致
        t_crit = _row_criterion(template_text, ac_id)
        g_crit = _row_criterion(filled_text, ac_id)
        if t_crit != g_crit:
            problems.append(
                f"{ac_id}: 判据列被改动 (模板「{t_crit}」 vs 填写稿「{g_crit}」)")
    for ac_id in tpl_by_id:
        if ac_id not in got_ids:
            problems.append(f"填写稿缺少模板中的 AC: {ac_id}")
    # 静态内容 (头部说明、表头) 必须逐字一致
    t_static = _static_lines(template_text)
    g_static = _static_lines(filled_text)
    if t_static != g_static:
        only_t = [l for l in t_static if l not in g_static]
        only_g = [l for l in g_static if l not in t_static]
        problems.append(
            "检查表的非判定内容被改动: "
            + ("; 模板独有: " + " | ".join(only_t[:3]) if only_t else "")
            + ("; 填写稿独有: " + " | ".join(only_g[:3]) if only_g else ""))
    return (not problems), problems


def _row_criterion(text, ac_id):
    for line in text.splitlines():
        m = RE_VERDICT_ROW.match(line.strip())
        if m and m.group(1) == ac_id:
            return m.group(2).strip()
    return None
