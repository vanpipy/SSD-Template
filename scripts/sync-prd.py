#!/usr/bin/env python3
"""sync-prd.py —— PRD 台账登记 + 规格统计同步(幂等)(`scripts/sync-prd.sh` 的 Python 端口)。

本文件是 bash 原件 `scripts/sync-prd.sh` 的**逐字节等价**实现:同一 corpus、同一
`--root` 下,stdout / stderr 逐字节相同、退出码相同,落盘的文件树也逐字节相同。
唯一的凭据是仓内 corpus(`scripts/tests/fixtures/sync-prd-corpus.json`)里的 golden ——
golden 由 **bash 原件**采集(原件的 SHA-1 记在 fixture 的 `source_sha1` 里);端口实现
**不得**自己生成 golden(那是同源污染,验收会被推翻)。

端口的硬约束:
  - **单进程**:不 spawn 任何子进程。原件的 `grep -n`、`grep -c`、`sed -n`、`awk`、
    `tr | wc`、`date`、`basename`、`dirname` 全部由 Python 标准库复现。
  - **写模式等价**:只写两处 —— `material/{YYYY-MM-DD}/PRDS.md`(补登骨架行 + 把状态列
    标记为 待分析 / 待抓取)与根 `README.md` 的 `<!-- prd-stats:begin -->` …
    `<!-- prd-stats:end -->` 标记块(标记块之外的内容永不触碰);不做任何 git 写操作。
  - **逐字节**:符号、全角标点、空格、输出顺序、行尾换行全部照抄原件;比对按 bytes。
  - **CLI 契约不变**:`--json` / `--root DIR` / `--check`;退出码
    0=已同步且无待办行 1=存在待办行(或 `--check` 下漂移) 2=调用/环境错误。

用法:
    python scripts/sync-prd.py [--json] [--root DIR] [--check]
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

# --- 退出码(契约 M12) ---
EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2

# --- 形状常量 —— 与 bash 原件逐字一致 ---
TOPIC_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
DATETOPIC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$")

#: 状态枚举(D1 的 4 个值)—— 原件按这个顺序做「最左匹配」。
STATE_TOKENS = ("Draft", "Ready", "Implemented", "Deprecated")

#: `[[:space:]]` 在 C.UTF-8 locale 下 = ASCII 空白集合(不含 \r 之外的其它 Unicode 空白)。
ASCII_WS = " \t\n\r\f\v"

#: 台账表头(原件的 LEDGER_HEADER,11 列)—— 新建台账时逐字写入。
LEDGER_HEADER = (
    "| # | ID | PRD 名称 | 优先级 | 验收要点 | 状态 | 来源 | 关联素材 | 创建时间 | 更新时间 | 提出人 |\n"
    "|---|----|---------|--------|----------|------|------|----------|----------|----------|--------|"
)

#: 台账列的默认位置(原件在表头缺列时用的兜底值)。
DEFAULT_COLS = {
    "id": 3,
    "num": 2,
    "st": 7,
    "mat": 9,
    "pri": 5,
    "own": 12,
    "src": 8,
    "tm": 10,
}


def _configure_stdio() -> None:
    """Windows 控制台默认 GBK,直接打印 ✓/✗/⚠/· 会抛 UnicodeEncodeError。

    `newline="\\n"` 同样关键:Windows 文本模式默认把 `\\n` 翻译成 `\\r\\n`,
    而原件(printf)只写 `\\n` —— 不关掉翻译,stdout 就不是逐字节相同。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
        except (AttributeError, ValueError):
            pass


def json_escape(text: str) -> str:
    """`json_escape()` 的等价实现(原件用 awk 逐行处理)。

    awk 按 `\\n` 拆记录,记录之间输出**字面量** `\\n`(两个字符);每条记录内依次转义
    反斜杠、双引号、制表符、回车。Python 的 `split("\\n")` 比 awk 多出一个尾部空串,
    这里补掉,否则尾部换行会被多编码一次。
    """
    records = text.split("\n")
    if text.endswith("\n") and records:
        records.pop()
    escaped = []
    for record in records:
        record = (
            record.replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("\t", "\\t")
            .replace("\r", "\\r")
        )
        escaped.append(record)
    return "\\n".join(escaped)


def json_str_array(items: list[str]) -> str:
    """`json_str_array()` 的等价实现:方括号包住逐个转义并加双引号的项,逗号分隔。"""
    return "[" + ",".join(f'"{json_escape(item)}"' for item in items) + "]"


def _read_text(path: Path) -> str:
    """按字节读入并用 surrogateescape 解码 —— 非法 UTF-8 字节原样往返。"""
    return path.read_bytes().decode("utf-8", "surrogateescape")


def _write_text(path: Path, text: str) -> None:
    """按字节写回(不做换行翻译)。"""
    path.write_bytes(text.encode("utf-8", "surrogateescape"))


def _split_lines(text: str) -> list[str]:
    """按 `\\n` 拆行、**不含**行尾符;结尾的换行不产生多余的空行(与 awk 记录一致)。"""
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts.pop()
    return parts


def _split_lines_keepends(text: str) -> list[str]:
    """按 `\\n` 拆行、**含**行尾符(等价于 `head` / `tail` 读到的行)。"""
    kept: list[str] = []
    start = 0
    while True:
        index = text.find("\n", start)
        if index < 0:
            break
        kept.append(text[start : index + 1])
        start = index + 1
    if start < len(text):
        kept.append(text[start:])
    return kept


def _trim_cell(value: str) -> str:
    """原件的 `gsub(/^[ \\t]+|[ \\t]+$/,"",v)` —— 只 trim 空格与制表符(不 trim CR)。"""
    return value.strip(" \t")


def _find_state_token(value: str) -> str:
    """复现 awk 的 `match(val, /(Draft|Ready|Implemented|Deprecated)/)`:取**最左**匹配。"""
    best_index = -1
    best_token = ""
    for token in STATE_TOKENS:
        index = value.find(token)
        if index >= 0 and (best_index < 0 or index < best_index):
            best_index = index
            best_token = token
    return best_token


#: 原件 `read_state()` 的行首模式:`^[[:space:]]*>?[[:space:]]*\\*\\*状态\\*\\*[[:space:]]*[:：]?`
STATE_LINE_RE = re.compile(r"^[ \t\n\r\f\v]*>?[ \t\n\r\f\v]*\*\*状态\*\*[ \t\n\r\f\v]*[:：]?")
#: 原件 `sub(/^[^:：]*[:：][[:space:]]*/, "", val)` 的前缀剥离
STATE_VALUE_PREFIX_RE = re.compile(r"^[^:：]*[:：][ \t\n\r\f\v]*")
#: 原件的前后缀剥离:行首/行尾的空格 + `|*` + 反引号
STATE_TRIM_PREFIX_RE = re.compile(r"^[ \t\n\r\f\v]*[|*`]+[ \t\n\r\f\v]*")
STATE_TRIM_SUFFIX_RE = re.compile(r"[ \t\n\r\f\v]*[|*`]+$")


def read_state(path: Path) -> str:
    """读取 `> **状态**: X` 形态的状态 token(原件 `read_state()`)。

    逐行匹配行首模式;对命中的行做前缀/后缀剥离,再在整行里找**最左**的状态 token;
    找到即返回(原件的 `exit`)。没有命中返回空串。
    """
    if not path.is_file():
        return ""
    for line in _split_lines(_read_text(path)):
        if not STATE_LINE_RE.match(line):
            continue
        value = STATE_VALUE_PREFIX_RE.sub("", line, count=1)
        value = STATE_TRIM_PREFIX_RE.sub("", value, count=1)
        value = STATE_TRIM_SUFFIX_RE.sub("", value, count=1)
        token = _find_state_token(value)
        if token:
            return token
    return ""


def read_meta_state(path: Path) -> str:
    """读取 `| **状态** | X |` 形态的状态 token(原件 `read_meta_state()`)。

    只扫以 `|` 开头的行;键 = 第 1 个单元去掉首尾空格制表符再去掉所有 `*`;
    值 = 第 2 个单元去掉首尾空格制表符(不去 `*`)。命中键后找不到 token 就继续下一行。
    """
    if not path.is_file():
        return ""
    for line in _split_lines(_read_text(path)):
        if not line.startswith("|"):
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        key = _trim_cell(parts[1]).replace("*", "")
        if key != "状态":
            continue
        token = _find_state_token(_trim_cell(parts[2]))
        if token:
            return token
    return ""


def _color_codes() -> tuple[str, str, str, str, str]:
    """复现原件的着色判定:**只有** `NO_COLOR` 恰好等于 `1` 才不上色。

    原件没有 isatty 判断 —— 输出被管道接走时仍然带颜色码,端口必须照抄。
    """
    if os.environ.get("NO_COLOR", "0") == "1":
        return ("", "", "", "", "")
    return ("\x1b[0;31m", "\x1b[0;33m", "\x1b[0;32m", "\x1b[0;36m", "\x1b[0m")


class Reporter:
    """结果收集与打印 —— 复现 bash 原件「即时打印 + JSON 模式只收集」的两种行为。"""

    def __init__(self, json_mode: bool) -> None:
        self.json_mode = json_mode
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.color_err, self.color_warn, self.color_ok, self.color_dim, self.color_reset = (
            _color_codes()
        )

    def err(self, message: str) -> None:
        self.errors.append(message)
        if not self.json_mode:
            sys.stdout.write(f"{self.color_err}✗{self.color_reset} {message}\n")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        if not self.json_mode:
            sys.stdout.write(f"{self.color_warn}⚠{self.color_reset} {message}\n")

    def note(self, message: str) -> None:
        self.notes.append(message)
        if not self.json_mode:
            sys.stdout.write(f"{self.color_dim}·{self.color_reset} {message}\n")

    def ok(self, message: str) -> None:
        if not self.json_mode:
            sys.stdout.write(f"{self.color_ok}✓{self.color_reset} {message}\n")


# ---------------------------------------------------------------------------
# 各层计数(与原件的四个扫描循环同构)
# ---------------------------------------------------------------------------


def _codepoint_key(path: Path) -> str:
    """排序键 = 路径字符串(码点序)。

    bash 的 glob 用 `LC_COLLATE=C.UTF-8`(码点序)展开;而 Windows 上 `Path` 的比较
    是**大小写不敏感**的 —— 直接 `sorted(glob(...))` 会把 `B.md` 排到 `a.md` 之后,
    与原件不一致(台账补登的序号会错)。故统一用字符串键。
    """
    return path.as_posix()


def _count_layer(
    root: Path,
    layer: str,
    reporter: Reporter,
) -> dict[str, int]:
    """扫描一层并统计各状态的数量 —— 返回 `total/draft/ready/impl/dep/other`。"""
    counts = {"total": 0, "draft": 0, "ready": 0, "impl": 0, "dep": 0, "other": 0}
    layer_dir = root / layer
    if not layer_dir.is_dir():
        return counts

    if layer == "prd":
        for path in sorted(layer_dir.glob("*/*.md"), key=_codepoint_key):
            if not path.is_file():
                continue
            date_dir = path.parent.name
            topic = path.name[:-3] if path.name.endswith(".md") else path.name
            if not DATE_RE.fullmatch(date_dir):
                continue
            if not TOPIC_RE.fullmatch(topic):
                continue
            counts["total"] += 1
            _bump(counts, read_state(path))
    elif layer == "tech_design":
        for path in sorted(layer_dir.glob("*/"), key=_codepoint_key):
            if not path.is_dir():
                continue
            name = path.name
            if not DATETOPIC_RE.fullmatch(name):
                continue
            readme = path / "README.md"
            if not readme.is_file():
                continue
            counts["total"] += 1
            _bump(counts, read_state(readme))
    elif layer == "plan":
        for path in sorted(layer_dir.glob("*/"), key=_codepoint_key):
            if not path.is_dir():
                continue
            name = path.name
            if not DATETOPIC_RE.fullmatch(name):
                continue
            plan_file = path / (name[11:] + ".md")
            if not plan_file.is_file():
                continue
            counts["total"] += 1
            _bump(counts, read_state(plan_file))
    elif layer == "test_cases":
        for path in sorted(layer_dir.glob("*/*.md"), key=_codepoint_key):
            if not path.is_file():
                continue
            date_dir = path.parent.name
            topic = path.name[:-3] if path.name.endswith(".md") else path.name
            if not DATE_RE.fullmatch(date_dir):
                continue
            if topic.endswith("-key-points"):
                continue
            if not TOPIC_RE.fullmatch(topic):
                continue
            counts["total"] += 1
            _bump(counts, read_meta_state(path))

    return counts


def _bump(counts: dict[str, int], state: str) -> None:
    """按状态 token 累加计数(空串 / 未知值都归「其他」)。"""
    if state == "Draft":
        counts["draft"] += 1
    elif state == "Ready":
        counts["ready"] += 1
    elif state == "Implemented":
        counts["impl"] += 1
    elif state == "Deprecated":
        counts["dep"] += 1
    else:
        counts["other"] += 1


def _distribution(counts: dict[str, int]) -> str:
    """状态分布文案 —— 顺序固定 Draft → Ready → Implemented → Deprecated → 其他,
    计数为 0 的项整项省略(原件的 `[ "$x" -gt 0 ] && ...` 连写)。"""
    parts: list[str] = []
    for key, label in (
        ("draft", "Draft"),
        ("ready", "Ready"),
        ("impl", "Implemented"),
        ("dep", "Deprecated"),
        ("other", "其他"),
    ):
        if counts[key] > 0:
            parts.append(f"{label} {counts[key]}")
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# 台账(可选层 material/{date}/PRDS.md)
# ---------------------------------------------------------------------------


def _ledger_cols(lines: list[str]) -> tuple[int, int, int, int, int, int, int, int] | None:
    """从表头推导列位置(原件 `ledger_cols()`)。

    逐行按 `|` 切分,取第 2..NF-1 个单元;命中 `ID` 的**第一行**胜出;
    缺的列用原件的兜底值。返回 None = 没找到 ID 列。
    """
    for line in lines:
        parts = line.split("|")
        last = len(parts) - 1  # awk 的 NF
        found = {"id": 0, "num": 0, "st": 0, "src": 0, "tm": 0, "mat": 0, "pri": 0, "own": 0}
        for index in range(1, last):
            cell = _trim_cell(parts[index])
            if cell == "ID":
                found["id"] = index + 1
            elif cell == "#":
                found["num"] = index + 1
            elif cell == "状态":
                found["st"] = index + 1
            elif cell == "来源":
                found["src"] = index + 1
            elif cell == "创建时间":
                found["tm"] = index + 1
            elif cell == "关联素材":
                found["mat"] = index + 1
            elif cell == "优先级":
                found["pri"] = index + 1
            elif cell == "提出人":
                found["own"] = index + 1
        if found["id"]:
            return (
                found["id"],
                found["num"] or DEFAULT_COLS["num"],
                found["st"] or DEFAULT_COLS["st"],
                found["mat"] or DEFAULT_COLS["mat"],
                found["pri"] or DEFAULT_COLS["pri"],
                found["own"] or DEFAULT_COLS["own"],
                found["src"] or DEFAULT_COLS["src"],
                found["tm"] or DEFAULT_COLS["tm"],
            )
    return None


def _cell(row: str, column: int) -> str:
    """取一行里第 `column` 个(`|` 切分后的)单元并去掉首尾空格制表符。"""
    parts = row.split("|")
    if column - 1 < 0 or column - 1 >= len(parts):
        return ""
    return _trim_cell(parts[column - 1])


def _is_placeholder_cell(value: str) -> bool:
    """原件 `is_placeholder_cell()`:空 / `[...]` / `{...}` / 待定 / 待补 / 以 `-` 开头 / `—`。"""
    if value == "":
        return True
    if value.startswith("[") and value.endswith("]"):
        return True
    if value.startswith("{") and value.endswith("}"):
        return True
    if value in ("待定", "待补", "—"):
        return True
    return value.startswith("-")


class Ledger:
    """台账处理状态 —— 原件用全局变量传递,这里用实例字段保持同样的可见性。"""

    def __init__(self, root: Path, check_mode: bool, reporter: Reporter) -> None:
        self.root = root
        self.check_mode = check_mode
        self.reporter = reporter
        self.pending = 0


def _ledger_mark_and_count(ledger: Ledger, ledger_file: Path, batch_dir: Path | None) -> None:
    """检测待办行;写模式下把「状态列为空/占位符」的行标记为 待分析 / 待抓取。

    原件 `ledger_mark_and_count()` 的逐条对应:列位置从表头推导、孤儿行判定、
    「来源 external 但创建时间为空」判定、「优先级/提出人未落实」判定、
    台账哨兵(状态列已含 待分析/待抓取)判定,以及状态列的占位符改写。
    """
    reporter = ledger.reporter
    if not ledger_file.is_file():
        return
    text = _read_text(ledger_file)
    lines = _split_lines(text)
    cols = _ledger_cols(lines)
    if cols is None:
        return
    id_col, _num_col, st_col, mat_col, pri_col, own_col, src_col, time_col = cols

    patch: dict[int, str] = {}
    pending = 0
    base = ledger_file.name
    batch_prefix = str(batch_dir) + "/" if batch_dir is not None else ""

    for line_number, row in enumerate(lines, start=1):
        if not row.startswith("|"):
            continue
        ledger_id = _cell(row, id_col)
        if ledger_id in ("", "ID"):
            continue
        if "[" in ledger_id or "]" in ledger_id:
            continue
        state = _cell(row, st_col)
        source = _cell(row, src_col)
        created = _cell(row, time_col)
        material = _cell(row, mat_col)
        priority = _cell(row, pri_col)
        owner = _cell(row, own_col)

        want = ""
        reason = ""
        if material.endswith(".md"):
            root_target = ledger.root / material
            batch_target = (batch_dir / material) if batch_dir is not None else None
            missing_at_root = not root_target.exists()
            missing_at_batch = True if batch_target is None else not batch_target.exists()
            if missing_at_root and missing_at_batch:
                want = "待分析"
                reason = f"关联素材不存在(孤儿行): {material}"
        if not want:
            if material.startswith("http://") or material.startswith("https://"):
                if source == "external" and created == "":
                    want = "待抓取"
                    reason = "来源 external 但创建时间为空(待抓取)"
        if not want and (priority == "待定" or owner == "[待补]"):
            want = "待分析"
            reason = f"优先级/提出人未落实(待分析): 优先级={priority} 提出人={owner}"

        if want:
            pending += 1
            reporter.warn(f"{base} — 台账行 {ledger_id} {reason}")
        elif "待分析" in state or "待抓取" in state:
            pending += 1
            reporter.warn(f"{base} — 台账行 {ledger_id} 状态为「{state}」(台账哨兵, 待办)")

        if want and _is_placeholder_cell(state):
            patch[line_number] = want

    if patch:
        if ledger.check_mode:
            reporter.err(f"{base} — 台账有未标记的待办行 — 请运行 `scripts/sync-prd.py` 标记")
        else:
            out_lines = []
            for line_number, row in enumerate(lines, start=1):
                if line_number in patch:
                    parts = row.split("|")
                    index = st_col - 1
                    if 0 <= index < len(parts):
                        parts[index] = " " + patch[line_number] + " "
                        row = "|".join(parts)
                out_lines.append(row + "\n")
            _write_text(ledger_file, "".join(out_lines))
            reporter.note(f"台账标记: {base} 标记 {len(patch)} 行待办")

    ledger.pending += pending


def _ledger_register_batch(
    ledger: Ledger, batch_dir: Path, batch_name: str, ledger_file: Path
) -> None:
    """批次台账登记(原件 `ledger_register_batch()`):新建台账 + 补登骨架行。"""
    reporter = ledger.reporter

    materials: list[Path] = []
    for path in sorted(batch_dir.glob("*.md"), key=_codepoint_key):
        if not path.is_file():
            continue
        if path.name in ("PRDS.md", "README.md", "_index.md"):
            continue
        materials.append(path)

    if not ledger_file.is_file() and not materials:
        return

    if not ledger_file.is_file():
        if ledger.check_mode:
            reporter.err(
                f"material/{batch_name}/PRDS.md — 批次台账缺失(该批次 {len(materials)} 份素材未登记) "
                "— 请运行 `scripts/sync-prd.py` 生成"
            )
            return
        content = (
            f"# PRD 台账 — material/{batch_name}\n"
            "\n"
            "> 由 `scripts/sync-prd.py` 维护(补登骨架行 / 标记待办行)。字段含义见 "
            "`schema/prd-ledger.md`。\n"
            "\n"
            "## PRD台账\n"
            "\n"
            f"{LEDGER_HEADER}\n"
        )
        try:
            _write_text(ledger_file, content)
        except OSError:
            reporter.err(f"material/{batch_name}/PRDS.md — 台账写入失败")
            return
        reporter.note(f"台账新建: material/{batch_name}/PRDS.md")

    text = _read_text(ledger_file)
    lines = _split_lines(text)
    if not any(
        re.fullmatch(r"##[ \t\n\r\f\v]+PRD台账[ \t\n\r\f\v]*", line) for line in lines
    ):
        reporter.err(
            f"material/{batch_name}/PRDS.md — 台账缺少 `## PRD台账` 段, "
            "无法登记(请人工补上该段标题)"
        )
        return

    cols = _ledger_cols(lines)
    if cols is None:
        reporter.err(f"material/{batch_name}/PRDS.md — 台账表未找到 `ID` 列, 无法登记")
        return
    _id_col, num_col, _st_col, mat_col, _pri_col, _own_col, _src_col, _time_col = cols

    registered: list[str] = []
    for row in lines:
        value = _cell(row, mat_col).replace("`", "")
        if value and value != "关联素材" and not re.fullmatch(r"-+", value):
            registered.append(value)

    seq = 0
    for row in lines:
        value = _cell(row, num_col)
        if re.fullmatch(r"[0-9]+", value):
            seq = max(seq, int(value))

    yyyymmdd = batch_name.replace("-", "")
    new_rows = ""
    for material in materials:
        if any(material.name in item for item in registered):
            continue
        seq += 1
        title = material.name[:-3] if material.name.endswith(".md") else material.name
        new_rows += (
            f"| {seq} | PRD-{yyyymmdd}-{seq:02d} | {title} | 待定 |  | 待分析 | local | "
            f"{material.name} | {batch_name} | {batch_name} | [待补] |\n"
        )

    if new_rows:
        count = sum(1 for line in new_rows.split("\n") if line.startswith("|"))
        if ledger.check_mode:
            reporter.err(
                f"material/{batch_name}/PRDS.md — 台账缺少 {count} 行素材骨架行 "
                "— 请运行 `scripts/sync-prd.py` 补登"
            )
        else:
            kept = _split_lines_keepends(text)
            last = 0
            for index, line in enumerate(kept, start=1):
                if line.startswith("|"):
                    last = index
            merged = "".join(kept[:last]) + new_rows + "".join(kept[last:])
            _write_text(ledger_file, merged)
            reporter.note(f"台账补登: material/{batch_name}/PRDS.md 追加 {count} 行骨架")


# ---------------------------------------------------------------------------
# 统计块
# ---------------------------------------------------------------------------


def _count_matrix_edges(lines: list[str]) -> tuple[int, int]:
    """统计 README 里的「关系边表」边数与「演进链索引」链数(原件的两段 awk)。

    原件用 `awk … | wc -l` 计数,awk 每条记录都带换行 ⇒ `wc -l` 等于命中行数。
    """
    edges = 0
    chains = 0
    in_edges = False
    in_chains = False
    for line in lines:
        if not in_edges and line.startswith("### 关系边表"):
            in_edges = True
            continue
        if in_edges and line.startswith("### "):
            in_edges = False
        if in_edges and re.match(r"^\| [0-9]+ \|", line):
            edges += 1
        if not in_chains and line.startswith("### 演进链索引"):
            in_chains = True
            continue
        if in_chains and (line.startswith("### ") or line.startswith("## ")):
            in_chains = False
        if in_chains and re.match(r"^\| [A-Za-z]", line):
            chains += 1
    return edges, chains


def _stats_body(
    prd: dict[str, int],
    td: dict[str, int],
    plan: dict[str, int],
    test: dict[str, int],
    edges: int,
    chains: int,
) -> str:
    """统计块正文(原件 `body=$( … )` 的内容)。

    命令替换会去掉**尾部**换行、保留**首部**换行 ⇒ body 以 `\\n` 开头、不以 `\\n` 结尾。
    """
    return (
        "\n"
        "| 层 | 制品 | 数量 | 状态分布 |\n"
        "|------|------|:---:|---------|\n"
        f"| Layer 1 | PRD | {prd['total']} | {_distribution(prd)} |\n"
        f"| Layer 2 | Tech Design | {td['total']} | {_distribution(td)} |\n"
        f"| Layer 3 | Plan | {plan['total']} | {_distribution(plan)} |\n"
        f"| Layer 4 | Test | {test['total']} | {_distribution(test)} |\n"
        f"| 全局 | PRD关联矩阵 | {edges} 条边 | 演进链 {chains} 条 |"
    )


def _prefix_lines(text: str) -> str:
    """`sed 's/^/  /'` 的等价实现:每一行(含空行)前面加两个空格。"""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    return "".join("  " + line + "\n" for line in lines)


def main(argv: list[str]) -> int:
    _configure_stdio()
    script_path = sys.argv[0] if sys.argv else "sync-prd.py"

    json_mode = False
    check_mode = False
    root_arg = ""

    # --- 参数解析(逐条复现原件的 while/case 循环) ---
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--json":
            json_mode = True
        elif arg == "--check":
            check_mode = True
        elif arg == "--root":
            index += 1
            if index >= len(argv):
                sys.stderr.write("✗ --root 需要目录参数\n")
                return EXIT_USAGE
            root_arg = argv[index]
        elif arg.startswith("--root="):
            root_arg = arg[len("--root=") :]
        elif arg in ("--help", "-h"):
            sys.stdout.write(f"用法: {script_path} [--json] [--root DIR] [--check]\n")
            return EXIT_OK
        elif arg.startswith("-"):
            sys.stderr.write(f"✗ 未知参数: {arg}\n")
            return EXIT_USAGE
        else:
            sys.stderr.write(f"✗ 不接受位置参数: {arg}\n")
            return EXIT_USAGE
        index += 1

    # --- 根目录解析(原件: 空则用默认,不存在则退 2,存在则取物理路径) ---
    default_root = Path(__file__).resolve().parent.parent
    root_display = root_arg if root_arg else str(default_root)
    if not Path(root_display).is_dir():
        sys.stderr.write(f"✗ --root 目录不存在: {root_display}\n")
        return EXIT_USAGE
    root = Path(os.path.realpath(root_display))

    reporter = Reporter(json_mode)
    ledger = Ledger(root, check_mode, reporter)

    # --- 各层计数 ---
    prd = _count_layer(root, "prd", reporter)
    td = _count_layer(root, "tech_design", reporter)
    plan = _count_layer(root, "plan", reporter)
    test = _count_layer(root, "test_cases", reporter)

    # --- 台账(可选层) ---
    material_dir = root / "material"
    if material_dir.is_dir():
        for batch in sorted(material_dir.glob("*/"), key=_codepoint_key):
            if not batch.is_dir():
                continue
            batch_name = batch.name
            if not DATE_RE.fullmatch(batch_name):
                continue
            _ledger_register_batch(ledger, batch, batch_name, batch / "PRDS.md")
        for ledger_file in sorted(material_dir.glob("*/PRDS.md"), key=_codepoint_key):
            if not ledger_file.is_file():
                continue
            _ledger_mark_and_count(ledger, ledger_file, ledger_file.parent)
        if ledger.pending == 0:
            reporter.note("素材区已启用, 台账无待办行")
    else:
        reporter.note("素材层未启用(material/ 不存在), 跳过台账登记与待办检查")

    root_ledger = root / "PRDS.md"
    if root_ledger.is_file():
        _ledger_mark_and_count(ledger, root_ledger, None)

    # --- 生成统计块 ---
    readme = root / "README.md"
    edges = 0
    chains = 0
    readme_text = ""
    readme_lines: list[str] = []
    if readme.is_file():
        readme_text = _read_text(readme)
        readme_lines = _split_lines(readme_text)
        edges, chains = _count_matrix_edges(readme_lines)

    body = _stats_body(prd, td, plan, test, edges, chains)

    begin_marker = "<!-- prd-stats:begin -->"
    end_marker = "<!-- prd-stats:end -->"
    begin_line = 0
    end_line = 0
    for number, line in enumerate(readme_lines, start=1):
        if not begin_line and begin_marker in line:
            begin_line = number
        if not end_line and end_marker in line:
            end_line = number

    if not begin_line or not end_line or end_line <= begin_line:
        if check_mode:
            reporter.err(
                "README.md 缺少 prd-stats 标记块 — 统计块无法核对(违反契约 M12 的唯一写入点约定)"
            )
        else:
            reporter.warn("统计回写跳过: README.md 未找到 prd-stats 标记")
    else:
        between = readme_lines[begin_line : end_line - 1]
        old_body = "\n".join(
            line for line in between if not line.startswith("> 统计时间: ")
        ).rstrip("\n")
        if old_body == body:
            reporter.ok(
                f"规格统计无变化 (PRD {prd['total']} / TD {td['total']} / "
                f"Plan {plan['total']} / Test {test['total']})"
            )
        elif check_mode:
            reporter.err("README.md 规格统计块已过期 — 请运行 `scripts/sync-prd.py` 重新生成")
            if not json_mode:
                sys.stdout.write(
                    _prefix_lines(
                        f"  --- 当前 ---\n{old_body}\n  --- 期望 ---\n{body}\n"
                    )
                )
        else:
            now = time.strftime("%Y-%m-%d %H:%M")
            kept = _split_lines_keepends(readme_text)
            merged = (
                "".join(kept[:begin_line])
                + f"> 统计时间: {now} · 由 `scripts/sync-prd.py` 自动生成\n"
                + body
                + "\n"
                + "".join(kept[end_line - 1 :])
            )
            _write_text(readme, merged)
            reporter.ok(
                f"统计回写: README.md 规格统计已更新 (PRD {prd['total']} / TD {td['total']} / "
                f"Plan {plan['total']} / Test {test['total']})"
            )

    error_count = len(reporter.errors)
    warning_count = len(reporter.warnings)
    if error_count > 0:
        status = "violation"
        exit_code = EXIT_VIOLATION
    elif ledger.pending > 0:
        status = "pending"
        exit_code = EXIT_VIOLATION
    else:
        status = "pass"
        exit_code = EXIT_OK

    if json_mode:
        payload = (
            '{"script":"sync-prd.py",'
            f'"root":"{json_escape(str(root))}",'
            f'"mode":"{"check" if check_mode else "write"}",'
            f'"status":"{status}",'
            f'"exit_code":{exit_code},'
            f'"error_count":{error_count},'
            f'"warning_count":{warning_count},'
            f'"pending_count":{ledger.pending},'
            f'"counts":{{"prd":{prd["total"]},"tech_design":{td["total"]},'
            f'"plan":{plan["total"]},"test":{test["total"]},"matrix_edges":{edges}}},'
            f'"errors":{json_str_array(reporter.errors)},'
            f'"warnings":{json_str_array(reporter.warnings)},'
            f'"notes":{json_str_array(reporter.notes)}'
            "}"
        )
        sys.stdout.write(payload + "\n")

    sys.stdout.flush()
    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
