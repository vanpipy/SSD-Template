"""制品发现 + 状态块(§3.1)/复审块(§3.2)读写 + 稳定 ID(§3.3)识别。

契约来源:`docs/contracts/agent-first-implementation.md` §3.1、§3.2、§3.3、§7.2。

设计要点:
- 制品 = 一个「入口文件」(PRD/Plan/TestCase 单文件;Tech Design 目录以 README.md 为入口)。
- 状态块与复审块都是**引用块**(`> **键**: 值`),TestCase 额外允许表格形式(`| **键** | 值 |`)。
- 写入是**幂等替换**:同一段里只保留一份状态块/复审块,其余字段原样保留。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

LAYERS = ("prd", "td", "plan", "test-case")
STATES = ("Draft", "Ready", "Implemented", "Deprecated")

DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
TOPIC_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DIR_STEM_RE = re.compile(r"^(?P<date>[0-9]{4}-[0-9]{2}-[0-9]{2})-(?P<topic>.+)$")

STATUS_FIELDS = ("状态", "状态主体", "状态时间", "状态依据")
REVIEW_FIELDS = ("评审人", "评审日期", "评审结论", "评审方式")
REVIEW_HEADING_KEY = "复审"
LINKS_HEADING_KEY = "链接"

# 状态依据(实施契约 §3.1)的规范形态:
#   criteria:<id>[,<id>…] | external:<ref>
# `criteria:` 之后的逗号分隔项是**同前缀的延续**(省略前缀),所以 `criteria:A,B` 合法。
# 这与 schema/criteria.json 的 `*-STATE-BASIS` 判据正则
# `criteria:[A-Z0-9-]+(,[A-Z0-9-]+)*` 一致 —— 判据与门禁必须说同一件事。
# F9:`decision:` 前缀已删除(控制平面整体删除,不再有决定文件这种授权来源)。
BASIS_PREFIXES = ("criteria", "external")
BASIS_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")

# 复审段里的「已知问题」行(F9 新增,实施契约 §5.2 规则 2):
#   > **已知问题**: <criterion-id> — <说明>
# 机器只看「复审段内是否点名了该判据 id」;形状校验只管 id 形态,不管语义。
KNOWN_ISSUE_KEY = "已知问题"
KNOWN_ISSUE_ID_RE = re.compile(r"^[A-Z0-9-]+$")

_QUOTE_FIELD_RE = re.compile(r"^\s*>\s*\*\*(?P<key>[^*]+)\*\*\s*[:：]\s*(?P<value>.*?)\s*$")
_TABLE_FIELD_RE = re.compile(r"^\s*\|\s*\*\*(?P<key>[^*]+)\*\*\s*\|\s*(?P<value>[^|]*?)\s*\|")
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.*?)\s*$")
_ID_TOKEN_RE = re.compile(r"\b[A-Z]{1,4}-\d+\b")


@dataclass(frozen=True)
class Artifact:
    """一个规格制品。`rel` 是仓库相对路径,`entry` 是状态块所在文件。"""

    layer: str
    topic: str
    date: str
    rel: str
    entry: Path
    files: tuple[Path, ...]

    @property
    def key(self) -> str:
        return f"{self.layer}:{self.rel}"


@dataclass(frozen=True)
class FieldHit:
    """字段的一次命中:值 + 所在文件 + 行号(1 起)。"""

    value: str
    rel: str
    line: int


@dataclass(frozen=True)
class StatusBlock:
    """契约 §3.1 的状态块。Draft 态允许 subject/timestamp/basis 缺省。"""

    state: str | None = None
    subject: str | None = None
    timestamp: str | None = None
    basis: str | None = None
    rel: str = ""
    line: int = 0

    @property
    def present(self) -> bool:
        return self.state is not None


@dataclass(frozen=True)
class ReviewBlock:
    """契约 §3.2 的复审块。

    `known_issues` 是复审段里全部 `> **已知问题**: …` 行的原始值 —— 人工接入
    「在制品里写内容」的那一半:非阻断判据失败时,人把判据 id 点名在这里。
    """

    reviewer: str | None = None
    review_date: str | None = None
    conclusion: str | None = None
    method: str | None = None
    known_issues: tuple[str, ...] = ()
    rel: str = ""
    line: int = 0


# --------------------------------------------------------------------------- 发现


def _iter_layer_dirs(root: Path, layer: str) -> list[Path]:
    base = root / {"prd": "prd", "td": "tech_design", "plan": "plan", "test-case": "test_cases"}[layer]
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir())


def discover_artifacts(root: Path) -> list[Artifact]:
    """按目录约定发现全部制品(契约 §3.2 / §7.2 的目录约定)。

    只认符合命名约定的文件;层根下的 `README.md` / `_index.md` 不算制品。
    """
    found: list[Artifact] = []

    for date_dir in _iter_layer_dirs(root, "prd"):
        if not DATE_RE.match(date_dir.name):
            continue
        for file in sorted(date_dir.glob("*.md")):
            if file.name in ("README.md", "_index.md"):
                continue
            if not TOPIC_RE.match(file.stem):
                continue
            found.append(
                Artifact("prd", file.stem, date_dir.name, _rel(file, root), file, (file,))
            )

    for dir_path in _iter_layer_dirs(root, "td"):
        match = DIR_STEM_RE.match(dir_path.name)
        if not match:
            continue
        topic = match.group("topic")
        if not TOPIC_RE.match(topic):
            continue
        entry = dir_path / "README.md"
        if not entry.is_file():
            continue
        files = tuple(sorted(p for p in dir_path.glob("*.md") if p.is_file()))
        found.append(
            Artifact("td", topic, match.group("date"), _rel(dir_path, root), entry, files)
        )

    for dir_path in _iter_layer_dirs(root, "plan"):
        match = DIR_STEM_RE.match(dir_path.name)
        if not match:
            continue
        topic = match.group("topic")
        if not TOPIC_RE.match(topic):
            continue
        entry = dir_path / f"{topic}.md"
        if not entry.is_file():
            continue
        files = tuple(sorted(p for p in dir_path.glob("*.md") if p.is_file()))
        found.append(
            Artifact("plan", topic, match.group("date"), _rel(entry, root), entry, files)
        )

    for date_dir in _iter_layer_dirs(root, "test-case"):
        if not DATE_RE.match(date_dir.name):
            continue
        for file in sorted(date_dir.glob("*.md")):
            if file.name in ("README.md", "_index.md"):
                continue
            if file.name.endswith("-key-points.md"):
                continue  # 伴生文件,不是独立制品
            stem = re.sub(r"-(smoke|key-points)$", "", file.stem)
            if not TOPIC_RE.match(stem):
                continue
            found.append(
                Artifact("test-case", stem, date_dir.name, _rel(file, root), file, (file,))
            )

    return found


def find_artifact(root: Path, rel: str) -> Artifact | None:
    """按仓库相对路径定位制品。"""
    target = rel.replace("\\", "/").strip()
    for art in discover_artifacts(root):
        if art.rel == target:
            return art
    return None


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:  # pragma: no cover - 仓库外的路径
        return path.as_posix()


# ------------------------------------------------------------------- 文本字段解析


def split_lines(text: str) -> list[str]:
    return text.split("\n")


def section_span(lines: list[str], heading_key: str) -> tuple[int, int] | None:
    """返回 `## <heading_key> ...` 段的正文行区间 `[start, end)`(不含标题行)。

    段落结束于同级或更高级的下一个标题。
    """
    start: int | None = None
    level = 0
    for index, line in enumerate(lines):
        match = _HEADING_RE.match(line)
        if not match:
            continue
        if start is None:
            if heading_key in match.group("title"):
                start = index
                level = len(match.group("hashes"))
            continue
        if len(match.group("hashes")) <= level:
            return (start + 1, index)
    if start is None:
        return None
    return (start + 1, len(lines))


def read_quote_fields(lines: list[str], rel: str = "") -> dict[str, FieldHit]:
    """读取引用块字段(`> **键**: 值`),首次出现为准。"""
    found: dict[str, FieldHit] = {}
    for number, line in enumerate(lines, 1):
        match = _QUOTE_FIELD_RE.match(line)
        if not match:
            continue
        key = match.group("key").strip()
        found.setdefault(key, FieldHit(match.group("value").strip(), rel, number))
    return found


def read_table_fields(lines: list[str], rel: str = "") -> dict[str, FieldHit]:
    """读取表格字段(`| **键** | 值 |`),首次出现为准。"""
    found: dict[str, FieldHit] = {}
    for number, line in enumerate(lines, 1):
        match = _TABLE_FIELD_RE.match(line)
        if not match:
            continue
        key = match.group("key").strip()
        found.setdefault(key, FieldHit(match.group("value").strip(), rel, number))
    return found


def parse_basis(basis: str | None) -> tuple[list[str], list[str]]:
    """把状态依据拆成 (合法项, 非法项)。

    合法项保留原样; 非法项是既没有 `criteria:`/`external:` 前缀、
    又不是 `criteria:` 组延续(省略前缀的裸 id)的片段。

    判定规则与 `scripts/check-md-schema.sh` 的 `check_status_meta` 一致 ——
    判据文件、门禁脚本、CLI 三处必须说同一件事, 否则会出现「advance 写出来的
    依据, verify 自己判非法」这种自相矛盾。
    """
    valid: list[str] = []
    invalid: list[str] = []
    prefix = ""
    for raw in (basis or "").split(","):
        item = raw.strip()
        if not item:
            continue
        head, sep, value = item.partition(":")
        if sep and head in BASIS_PREFIXES and value.strip():
            prefix = head
            valid.append(item)
        elif prefix == "criteria" and BASIS_ID_RE.match(item):
            valid.append(item)
        else:
            invalid.append(item)
    return valid, invalid


def parse_status(text: str, rel: str = "") -> StatusBlock:
    """解析状态块(契约 §3.1)。引用块优先,其次表格块(TestCase)。"""
    lines = split_lines(text)
    quote = read_quote_fields(lines, rel)
    table = read_table_fields(lines, rel)

    def pick(key: str) -> FieldHit | None:
        return quote.get(key) or table.get(key)

    state_hit = pick("状态")
    subject_hit = pick("状态主体")
    timestamp_hit = pick("状态时间")
    basis_hit = pick("状态依据")
    return StatusBlock(
        state=state_hit.value if state_hit else None,
        subject=subject_hit.value if subject_hit else None,
        timestamp=timestamp_hit.value if timestamp_hit else None,
        basis=basis_hit.value if basis_hit else None,
        rel=state_hit.rel if state_hit else rel,
        line=state_hit.line if state_hit else 0,
    )


def parse_review(text: str, rel: str = "") -> ReviewBlock:
    """解析复审块(契约 §3.2):只认 `## 复审 (Review)` 段内的字段。"""
    lines = split_lines(text)
    span = section_span(lines, REVIEW_HEADING_KEY)
    body = lines[span[0] : span[1]] if span else []
    quote = read_quote_fields(body, rel)
    table = read_table_fields(body, rel)

    def pick(key: str) -> FieldHit | None:
        return quote.get(key) or table.get(key)

    def value(key: str) -> str | None:
        hit = pick(key)
        return hit.value if hit else None

    reviewer = pick("评审人")
    return ReviewBlock(
        reviewer=value("评审人"),
        review_date=value("评审日期"),
        conclusion=value("评审结论"),
        method=value("评审方式"),
        known_issues=_read_known_issues(body),
        rel=reviewer.rel if reviewer else rel,
        line=reviewer.line if reviewer else 0,
    )


def _read_known_issues(body: list[str]) -> tuple[str, ...]:
    """复审段内全部 `> **已知问题**: …` 行的值(多行都收)。"""
    values: list[str] = []
    for line in body:
        match = _QUOTE_FIELD_RE.match(line)
        if match and match.group("key").strip() == KNOWN_ISSUE_KEY:
            values.append(match.group("value").strip())
    return tuple(values)


def known_issue_ids(review: ReviewBlock) -> list[str]:
    """复审段内点名的判据 id(去重,保持出现顺序)。

    只认形态合法的 id(大写字母 / 数字 / 连字符);形态非法的行由
    `known_issue_shape_problems` 单独报出来,这里不静默吞掉。
    """
    ids: list[str] = []
    for raw in review.known_issues:
        parts = raw.split()
        if not parts:
            continue
        token = parts[0]
        if KNOWN_ISSUE_ID_RE.match(token) and token not in ids:
            ids.append(token)
    return ids


def known_issue_shape_problems(review: ReviewBlock) -> list[str]:
    """「已知问题」行的**形状**校验(不校验语义)。"""
    problems: list[str] = []
    for raw in review.known_issues:
        parts = raw.split()
        token = parts[0] if parts else ""
        if not token or not KNOWN_ISSUE_ID_RE.match(token):
            problems.append(
                f"`已知问题` 行的判据 id 非法: '{raw}'"
                "(应为形如 PRD-XXX-01 的大写字母/数字/连字符 id,后接说明)"
            )
    return problems


# ------------------------------------------------------------------- 状态块写入


def render_status_block(
    state: str,
    subject: str | None = None,
    timestamp: str | None = None,
    basis: str | None = None,
) -> list[str]:
    """按契约 §3.1 的固定顺序渲染状态块 4 行。"""
    block = [f"> **状态**: {state}"]
    if subject:
        block.append(f"> **状态主体**: {subject}")
    if timestamp:
        block.append(f"> **状态时间**: {timestamp}")
    if basis:
        block.append(f"> **状态依据**: {basis}")
    return block


def apply_status_block(text: str, block: list[str]) -> str:
    """把状态块写进正文:替换既有状态块,没有就插在首个标题之后。"""
    lines = split_lines(text)
    index: int | None = None
    for position, line in enumerate(lines):
        match = _QUOTE_FIELD_RE.match(line)
        if match and match.group("key").strip() == "状态":
            index = position
            break

    if index is None:
        insert_at = 0
        for position, line in enumerate(lines):
            if _HEADING_RE.match(line):
                insert_at = position + 1
                break
        return "\n".join(lines[:insert_at] + block + lines[insert_at:])

    end = index + 1
    while end < len(lines):
        match = _QUOTE_FIELD_RE.match(lines[end])
        if match and match.group("key").strip() in ("状态主体", "状态时间", "状态依据"):
            end += 1
            continue
        break
    return "\n".join(lines[:index] + block + lines[end:])


def render_review_block(
    reviewer: str,
    review_date: str,
    conclusion: str,
    method: str,
) -> list[str]:
    """按契约 §3.2 的固定顺序渲染复审块 4 行。"""
    return [
        f"> **评审人**: {reviewer}",
        f"> **评审日期**: {review_date}",
        f"> **评审结论**: {conclusion}",
        f"> **评审方式**: {method}",
    ]


def apply_review_block(text: str, block: list[str]) -> str:
    """把复审块写进 `## 复审 (Review)` 段;段不存在时抛 ValueError。"""
    lines = split_lines(text)
    span = section_span(lines, REVIEW_HEADING_KEY)
    if span is None:
        raise ValueError("制品缺少 `## 复审 (Review)` 段,无法写入复审块")
    start, end = span

    hits: list[int] = []
    for position in range(start, end):
        match = _QUOTE_FIELD_RE.match(lines[position])
        if match and match.group("key").strip() in REVIEW_FIELDS:
            hits.append(position)

    if not hits:
        return "\n".join(lines[:start] + block + lines[start:])

    drop = set(hits)
    first = hits[0]
    anchor = first - sum(1 for position in hits if position < first)
    kept = [line for position, line in enumerate(lines) if position not in drop]
    return "\n".join(kept[:anchor] + block + kept[anchor:])


# ------------------------------------------------------------------ 稳定 ID 识别


def declared_ids(files: list[tuple[str, list[str]]], prefix: str) -> list[tuple[str, str, int]]:
    """列出**声明位**上的 ID:`(id, rel, line)`。

    声明位 = 列表项开头(`- AC-1 …` / `- [ ] AC-1 …`)或标题行里出现的第一个 ID。
    引用位(例如 `**覆盖**: AC-1`)不算声明,否则同一 ID 会被重复计数。

    `prefix` 为空 ⇒ 返回空列表:空前缀的正则会匹配到 `AC-1` 的尾巴 `-1`,
    那属于「语义未定义」,不能让判据在参数写错时静默通过(契约 §4.1.1)。
    """
    if not prefix:
        return []
    pattern = re.compile(r"\b" + re.escape(prefix) + r"-\d+\b")
    found: list[tuple[str, str, int]] = []
    for rel, lines in files:
        for number, line in enumerate(lines, 1):
            item = re.match(
                r"^\s*[-*+]\s*(?:\[[ xX]\]\s*)?(" + re.escape(prefix) + r"-\d+)\b", line
            )
            if item:
                found.append((item.group(1), rel, number))
                continue
            if _HEADING_RE.match(line):
                token = pattern.search(line)
                if token:
                    found.append((token.group(0), rel, number))
    return found


def referenced_ids(text: str, prefix: str) -> list[str]:
    """取出文本中出现的全部 `<prefix>-n`(去重,保持出现顺序)。"""
    if not prefix:
        return []
    pattern = re.compile(r"\b" + re.escape(prefix) + r"-\d+\b")
    seen: list[str] = []
    for token in pattern.findall(text):
        if token not in seen:
            seen.append(token)
    return seen


def id_pattern_matches(pattern: str, value: str) -> bool:
    """ID 是否满足 pattern。pattern 按正则解释(允许 `^AC-\\d+$` 这种写法)。

    空 pattern 或非法正则 ⇒ **不匹配**(而不是「恒真」):参数写错的判据
    必须表现为失败,不能表现为通过(契约 §4.1.1)。
    """
    if not pattern:
        return False
    try:
        return re.search(pattern, value) is not None
    except re.error:
        return False
