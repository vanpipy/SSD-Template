#!/usr/bin/env python3
"""sync-test-index.py —— 再生成 `test_cases/_index.md` 索引表(幂等)门禁
(`scripts/sync-test-index.sh` 的 Python 端口)。

本文件是 bash 原件的**逐字节等价**实现:同一 corpus、同一 `--root` 下,
stdout / stderr 归一化后逐字节相同、退出码相同;写模式落盘的结果树
(只写 `test_cases/_index.md` 一个文件)也逐字节相同。

与原件的唯一差异是**脚本身份**:本实现自称 `scripts/sync-test-index.py`
(JSON 载荷的 `script` 字段、生成物里的标记文案、提示信息里的脚本名)。

契约要点(与原件一致):
  - 退出码:0=通过/已更新 1=`--check` 发现漂移 2=调用错误 / 环境错误;
  - `test_cases/` 不存在 ⇒ 该层未启用 ⇒ note + 退出 0(JSON 带 `"skipped":true`);
  - 只写 `test_cases/_index.md` 一个文件,不碰任何其他文件;
  - 数据唯一真源 = 各用例文档的元信息表。

用法:
    scripts/sync-test-index.py [--json] [--root DIR] [--check]
"""

from __future__ import annotations

import difflib
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# --- 退出码(与原件一致) ---
EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2

# --- 形状与解析用的正则(与原件逐字一致) ---
TOPIC_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
LEADING_DIGITS_RE = re.compile(r"^[0-9]+")
P0_COUNT_RE = re.compile(r"P0: *[0-9]+")
DIGITS_RE = re.compile(r"[0-9]+")

# --- 固定文本(与原件逐字一致;只有脚本名用新身份) ---
INDEX_REL = "test_cases/_index.md"
TMP_REL = "test_cases/.index.tmp"
BEGIN_MARK = "<!-- test-index:begin — 由 scripts/sync-test-index.py 自动生成，勿手改 -->"
END_MARK = "<!-- test-index:end -->"
TABLE_HEADER = "| 日期 | 主题 | 业务产品 | 平台 | 用例数 | P0 | 状态 | 用例文件 | 要点文件 |"
TABLE_RULE = "|------|------|---------|------|--------|----|----|---------|--------|"
NO_KEY_POINTS = "—"  # em dash:原件在要点文件缺失时写这个
FILE_TITLE = "# 测试用例索引"
FILE_NOTE_1 = (
    "> 由 `scripts/sync-test-index.py` 自动生成（标记块内勿手改）。数据源：各用例文档元信息表。"
)
FILE_NOTE_2 = "> 伴生要点文件不单独登记。"
NOTE_LAYER_OFF = "测试用例层未启用(test_cases/ 不存在), 跳过索引同步"


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


def _color_codes() -> tuple[str, str, str, str, str]:
    """复现原件的着色判定:**只有** `NO_COLOR` 恰好等于 `1` 才不上色。"""
    if os.environ.get("NO_COLOR", "0") == "1":
        return ("", "", "", "", "")
    return ("\x1b[0;31m", "\x1b[0;33m", "\x1b[0;32m", "\x1b[0;36m", "\x1b[0m")


class Reporter:
    """结果收集与打印 —— 复现原件「即时打印 + JSON 模式只收集」的两种行为。"""

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
            _emit(f"{self.color_err}✗{self.color_reset} {message}\n")

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        if not self.json_mode:
            _emit(f"{self.color_warn}⚠{self.color_reset} {message}\n")

    def note(self, message: str) -> None:
        self.notes.append(message)
        if not self.json_mode:
            _emit(f"{self.color_dim}·{self.color_reset} {message}\n")

    def ok(self, message: str) -> None:
        if not self.json_mode:
            _emit(f"{self.color_ok}✓{self.color_reset} {message}\n")


def _emit(text: str) -> None:
    sys.stdout.write(text)


def meta_field(path: Path, key: str) -> str:
    """`meta_field()` 的等价实现:读元信息表,取「字段」列下一格的值。

    原件用 `awk -F'|'`:只处理 `^\\|` 开头的行;第 2 格是字段名、第 3 格是值;
    字段名先去掉首尾空格/制表符,再去掉所有 `*`;**值**不做去星号处理。
    首个命中即返回(原件 `exit`)。
    """
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    text = raw.decode("utf-8", "replace")
    for line in text.split("\n"):
        if not line.startswith("|"):
            continue
        parts = line.split("|")
        if len(parts) < 3:
            continue
        field = parts[1].strip(" \t").replace("*", "")
        value = parts[2].strip(" \t")
        if field == key:
            return value
    return ""


def scan_rows(root: Path) -> list[tuple[str, str]]:
    """扫描 `test_cases/*/*.md`,返回 (排序键, 表格行) 列表。

    - glob 语义:bash 的 `*` 不匹配点开头的名字(隐藏目录 / 隐藏文件都跳过);
    - 跳过 `*-key-points.md`;日期目录必须匹配 `DATE_RE`;topic 必须匹配 `TOPIC_RE`;
    - 冒烟文件(`*-smoke.md`)的 topic 去掉 `-smoke` 后缀再判定;
    - 排序键 = `${date_dir}/${topic}/${is_smoke}`(同键内冒烟排后)。
    """
    rows: list[tuple[str, str]] = []
    layer = root / "test_cases"
    if not layer.is_dir():
        return rows
    date_dirs = sorted(
        entry.name
        for entry in layer.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )
    for date_dir in date_dirs:
        day_dir = layer / date_dir
        for file_name in sorted(
            entry.name
            for entry in day_dir.iterdir()
            if entry.is_file()
            and entry.name.endswith(".md")
            and not entry.name.startswith(".")
        ):
            base = file_name[: -len(".md")]
            if base.endswith("-key-points"):
                continue
            if not DATE_RE.fullmatch(date_dir):
                continue
            if base.endswith("-smoke"):
                topic = base[: -len("-smoke")]
            else:
                topic = base
            if not TOPIC_RE.fullmatch(topic):
                continue
            path = day_dir / file_name
            rel = f"{date_dir}/{file_name}"
            subject = meta_field(path, "主题")
            if not subject:
                subject = topic
            biz = meta_field(path, "业务产品")
            plat = meta_field(path, "目标平台")
            total_line = meta_field(path, "用例总数")
            digits = LEADING_DIGITS_RE.match(total_line)
            count = digits.group(0) if digits else "?"
            if "全部 P0" in total_line:
                p0 = count
            else:
                match = P0_COUNT_RE.search(total_line)
                p0 = "0"
                if match:
                    p0_digits = DIGITS_RE.findall(match.group(0))
                    if p0_digits:
                        # 原件管道 grep -oE '[0-9]+' 会把 "P0" 里的 0 也算进来
                        p0 = "\n".join(p0_digits)
            state = meta_field(path, "状态")
            key_points_rel = f"{date_dir}/{topic}-key-points.md"
            if (layer / key_points_rel).is_file():
                key_points = f"[key-points]({key_points_rel})"
            else:
                key_points = NO_KEY_POINTS
            is_smoke = 1 if base.endswith("-smoke") else 0
            key = f"{date_dir}/{topic}/{is_smoke}"
            row = (
                f"| {date_dir} | {subject} | {biz} | {plat} | {count} | {p0} | {state} "
                f"| [{file_name}]({rel}) | {key_points} |"
            )
            rows.append((key, row))
    return rows


def generate_content(rows: list[tuple[str, str]]) -> str:
    """`generate_file()` 的等价实现:标题段 + 标记块 + 表格。

    排序:原件把 key 列表交给 `sort`(LC_ALL=C.UTF-8,码点序),再按 key 回查**第一条**
    匹配的行;重复 key 会因此重复输出同一行(此处的循环照搬该行为)。
    """
    keys = [key for key, _ in rows]
    values = [value for _, value in rows]
    lines: list[str] = [BEGIN_MARK, TABLE_HEADER, TABLE_RULE]
    for key in sorted(keys):
        for index, candidate in enumerate(keys):
            if candidate == key:
                lines.append(values[index])
                break
    lines.append(END_MARK)
    header = "\n".join([FILE_TITLE, "", FILE_NOTE_1, FILE_NOTE_2, ""]) + "\n"
    return header + "\n".join(lines) + "\n"


def _split_lines(text: str) -> tuple[list[str], bool]:
    """按 `\\n` 拆行(保留最后一行是否带换行的信息)。"""
    if text == "":
        return [], True
    parts = text.split("\n")
    ends_with_newline = parts[-1] == ""
    if ends_with_newline:
        parts = parts[:-1]
    return parts, ends_with_newline


def _format_range(start: int, stop: int) -> str:
    """hunk 头的行号范围 —— 与 GNU diff / difflib 的写法一致(长度为 1 时省略计数)。"""
    beginning = start + 1
    length = stop - start
    if length == 1:
        return f"{beginning}"
    if not length:
        beginning -= 1
    return f"{beginning},{length}"


def _mtime_text(path: Path) -> str:
    """diff 头里的时间戳(GNU diff 的格式);值本身会被归一化器剥掉。"""
    try:
        stamp = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    except OSError:
        stamp = datetime.fromtimestamp(0).astimezone()
    return stamp.strftime("%Y-%m-%d %H:%M:%S.%f %z")


def unified_diff(
    old_text: str,
    new_text: str,
    old_label: str,
    new_label: str,
    old_stamp: str,
    new_stamp: str,
) -> str:
    """`diff -u` 的等价实现。

    路径与原件一致,用**绝对路径**(仓根 + `/` + 相对路径):归一化器把根路径换成
    `{ROOT}` 之后,两侧落在同一形态上。
    hunk 头与正文按 GNU diff 的写法:3 行上下文、` ` / `-` / `+` 前缀、
    末行缺换行时补 `\\ No newline at end of file`。
    """
    old_lines, old_has_newline = _split_lines(old_text)
    new_lines, new_has_newline = _split_lines(new_text)
    out: list[str] = [f"--- {old_label}\t{old_stamp}", f"+++ {new_label}\t{new_stamp}"]
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    for group in matcher.get_grouped_opcodes(3):
        out.append(
            "@@ -{} +{} @@".format(
                _format_range(group[0][1], group[-1][2]),
                _format_range(group[0][3], group[-1][4]),
            )
        )
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for offset, line in enumerate(old_lines[i1:i2]):
                    index = i1 + offset
                    out.append(" " + line)
                    if index == len(old_lines) - 1 and not old_has_newline:
                        out.append("\\ No newline at end of file")
                    if index == len(new_lines) - 1 and not new_has_newline:
                        out.append("\\ No newline at end of file")
            elif tag == "replace":
                for offset, line in enumerate(old_lines[i1:i2]):
                    out.append("-" + line)
                    if i1 + offset == len(old_lines) - 1 and not old_has_newline:
                        out.append("\\ No newline at end of file")
                for offset, line in enumerate(new_lines[j1:j2]):
                    out.append("+" + line)
                    if j1 + offset == len(new_lines) - 1 and not new_has_newline:
                        out.append("\\ No newline at end of file")
            elif tag == "delete":
                for offset, line in enumerate(old_lines[i1:i2]):
                    out.append("-" + line)
                    if i1 + offset == len(old_lines) - 1 and not old_has_newline:
                        out.append("\\ No newline at end of file")
            elif tag == "insert":
                for offset, line in enumerate(new_lines[j1:j2]):
                    out.append("+" + line)
                    if j1 + offset == len(new_lines) - 1 and not new_has_newline:
                        out.append("\\ No newline at end of file")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    _configure_stdio()
    script_path = sys.argv[0] if sys.argv else "sync-test-index.py"

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

    # --- 根目录解析(原件: 空则用脚本目录的上一级,不存在则退 2,存在则取物理路径) ---
    if not root_arg:
        root_arg = str(Path(script_path).resolve().parent.parent)
    root_input = Path(root_arg)
    if not root_input.is_dir():
        sys.stderr.write(f"✗ --root 目录不存在: {root_arg}\n")
        return EXIT_USAGE
    root = Path(os.path.realpath(str(root_input)))

    reporter = Reporter(json_mode)

    # --- 层未启用 → 跳过(不是违规) ---
    if not (root / "test_cases").is_dir():
        reporter.note(NOTE_LAYER_OFF)
        if json_mode:
            payload = (
                '{"script":"sync-test-index.py",'
                f'"root":"{json_escape(str(root))}",'
                '"status":"pass",'
                '"exit_code":0,'
                '"error_count":0,'
                '"warning_count":0,'
                '"rows":0,'
                '"skipped":true,'
                '"errors":[],'
                '"warnings":[],'
                f'"notes":{json_str_array(reporter.notes)}'
                "}"
            )
            _emit(payload + "\n")
        sys.stdout.flush()
        return EXIT_OK

    rows = scan_rows(root)
    content = generate_content(rows)
    content_bytes = content.encode("utf-8")

    index_path = root / INDEX_REL
    tmp_path = root / TMP_REL
    tmp_path.write_bytes(content_bytes)

    if check_mode:
        if not index_path.is_file():
            reporter.err("test_cases/_index.md 不存在 — 运行 `scripts/sync-test-index.py` 生成")
            tmp_path.unlink(missing_ok=True)
        elif index_path.read_bytes() == content_bytes:
            tmp_path.unlink(missing_ok=True)
            reporter.ok(f"test_cases/_index.md 与文档元信息一致 ({len(rows)} 行)")
        else:
            reporter.err(
                "test_cases/_index.md 与文档元信息不一致 — 运行 `scripts/sync-test-index.py` 再生成"
            )
            if not json_mode:
                diff_text = unified_diff(
                    index_path.read_bytes().decode("utf-8", "replace"),
                    content,
                    f"{root}/{INDEX_REL}",
                    f"{root}/{TMP_REL}",
                    _mtime_text(index_path),
                    _mtime_text(tmp_path),
                )
                for line in diff_text.split("\n")[:-1]:
                    _emit("  " + line + "\n")
            tmp_path.unlink(missing_ok=True)
    else:
        if index_path.is_file() and index_path.read_bytes() == content_bytes:
            tmp_path.unlink(missing_ok=True)
            reporter.ok(f"test_cases/_index.md 已是最新 ({len(rows)} 行)")
        else:
            os.replace(str(tmp_path), str(index_path))
            reporter.ok(f"test_cases/_index.md 已再生成 ({len(rows)} 行)")

    status = "violation" if reporter.errors else "pass"
    code = EXIT_VIOLATION if reporter.errors else EXIT_OK

    if json_mode:
        payload = (
            '{"script":"sync-test-index.py",'
            f'"root":"{json_escape(str(root))}",'
            f'"status":"{status}",'
            f'"exit_code":{code},'
            f'"error_count":{len(reporter.errors)},'
            f'"warning_count":{len(reporter.warnings)},'
            f'"rows":{len(rows)},'
            f'"errors":{json_str_array(reporter.errors)},'
            f'"warnings":{json_str_array(reporter.warnings)},'
            f'"notes":{json_str_array(reporter.notes)}'
            "}"
        )
        _emit(payload + "\n")

    sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
