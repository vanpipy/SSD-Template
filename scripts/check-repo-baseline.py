#!/usr/bin/env python3
"""check-repo-baseline.py — 校验 Tech Design README 的「实现基线」表

这是 bash 原件 scripts/check-repo-baseline.sh 的逐字节等价实现: 同一 CLI、
同一退出码、同一输出文案; 归一化(脚本身份串 / 临时根路径形态)后 stdout 与
stderr 逐字节相同。

规约 (见 AGENTS.md §1.6):
  - 每个 tech_design/{date}-{topic}/README.md 必须包含 `## 实现基线` 段
  - 表头固定 6 列: | 仓库 | 分分支 | SHA | 核对日期 | 核对项 | 状态 |
  - 「仓库」列填 AGENTS.md §1.1 登记的**标识**, 脚本据此解析本地路径
  - SHA 必须能在本地代码仓解析; 分支头与 SHA 不一致 → ⚠(允许有意钉住)
  - 核对日期超过 --max-age-days(默认 7 天)→ ⚠
  - 状态为 待补/TODO/✗/❌ → ✗
  - 0 代码仓项目写 `> 不适用: ...` 声明 → ○ 跳过, 不报错

仓库 → 本地路径的映射**从 AGENTS.md §1.1「本地路径」列解析**, 脚本内不硬编码任何仓名。

可移植性:
  - 不依赖 GNU `date -d` / BSD `date -j -f`; 两者都不可用时用 POSIX 历法近似换算,
    并打印**降级提示**(该换算只影响「基线是否过期」的 ⚠ 判断)
  - 不用 `find -mindepth/-maxdepth`
  - 除 git 外不 fork 任何子进程(git 用于解析分支头与校验 SHA 存在性)

用法:
  scripts/check-repo-baseline.py [--json] [--root DIR] [--max-age-days N] [TARGET]
  (--stage 不适用于本脚本:阶段相关必填项由 scripts/check-md-schema.py 判定;收到即退出 2)

退出码: 0=通过 1=违规 2=调用错误 / 环境错误
"""
from __future__ import annotations

import datetime as _dt
import os
import re
import subprocess
import sys
import time

EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2

SCRIPT_PATH = sys.argv[0]

_ASCII_WS = " \t\n\r\v\f"

# 表格行分隔行: bash `grep -qE '^\\|[[:space:]]*:?-+'`
_SEPARATOR_ROW_RE = re.compile(r"^\|[ \t\n\r\v\f]*:?-+")
# 首列为表头时跳过 (bash: case "$repo" in "仓库"|repo|"") continue)
_HEADER_CELLS = ("仓库", "repo", "")
# 核对日期抽取 (bash: grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)
_DATE_IN_CELL_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
# 未完结的状态标记 (bash: *待补*|*TODO*|*✗*|*❌*)
_INCOMPLETE_MARKERS = ("待补", "TODO", "✗", "❌")

# §1.1 段落的起止 (bash: /^#{1,4}[[:space:]]+1\.1[[:space:]]/ 与 /^#{1,3}[[:space:]]/)
_SECTION_START_RE = re.compile(r"^#{1,4}[ \t\n\r\v\f]+1\.1[ \t\n\r\v\f]")
_SECTION_END_RE = re.compile(r"^#{1,3}[ \t\n\r\v\f]")
# `## 实现基线` 标题 (bash: /^##[[:space:]]+实现基线/)
_BASELINE_HEAD_RE = re.compile(r"^##[ \t\n\r\v\f]+实现基线")
# 段内任意标题结束该段 (bash: /^#{1,6}[[:space:]]/)
_ANY_HEADING_RE = re.compile(r"^#{1,6}[ \t\n\r\v\f]")
# 代码围栏 (bash: /^```/)
_FENCE_RE = re.compile(r"^```")

# 目录/文件命名 (bash 内联的 grep -Eq)
_DATE_DIR_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_TOPIC_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_DATETOPIC_DIR_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$")
_DATE_CELL_RE = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$")


def _configure_stdio() -> None:
    """Windows 文本模式会把 \\n 翻译成 \\r\\n; 这里强制只写 \\n。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace", newline="\n")
        except (AttributeError, ValueError):  # pragma: no cover - 老解释器兜底
            pass


def _trim(text: str) -> str:
    """bash trim(): 去首尾 [[:space:]]。"""
    return text.strip(_ASCII_WS)


def _trim_tab(text: str) -> str:
    """awk gsub(/^[ \\t]+|[ \\t]+$/): 只去首尾空格与制表符。"""
    return text.strip(" \t")


def json_escape(text: str) -> str:
    """复刻 bash json_escape() 的 awk 实现: 记录间写字面量 \\n, 逐记录转义。"""
    records = text.split("\n")
    if records and records[-1] == "":
        records.pop()
    out = []
    for rec in records:
        rec = rec.replace("\\", "\\\\").replace('"', '\\"')
        rec = rec.replace("\t", "\\t").replace("\r", "\\r")
        out.append(rec)
    return "\\n".join(out)


def json_str_array(items) -> str:
    """复刻 bash json_str_array()。"""
    return "[" + ",".join('"%s"' % json_escape(item) for item in items) + "]"


class Reporter:
    """复刻 bash 的 err/warn/note/ok + ERRORS/WARNINGS/NOTES 收集。"""

    def __init__(self, json_mode: bool) -> None:
        self.json_mode = json_mode
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        if os.environ.get("NO_COLOR", "0") == "1":
            self.c_err = self.c_warn = self.c_ok = self.c_dim = self.c_reset = ""
        else:
            self.c_err = "\033[0;31m"
            self.c_warn = "\033[0;33m"
            self.c_ok = "\033[0;32m"
            self.c_dim = "\033[0;36m"
            self.c_reset = "\033[0m"

    def err(self, message: str) -> None:
        self.errors.append(message)
        if not self.json_mode:
            print("%s✗%s %s" % (self.c_err, self.c_reset, message))

    def warn(self, message: str) -> None:
        self.warnings.append(message)
        if not self.json_mode:
            print("%s⚠%s %s" % (self.c_warn, self.c_reset, message))

    def note(self, message: str) -> None:
        self.notes.append(message)
        if not self.json_mode:
            print("%s·%s %s" % (self.c_dim, self.c_reset, message))

    def note_captured(self, message: str) -> str:
        """复刻 bash 里 note() 的 stdout 被 `$(day_epoch)` 命令替换吞掉的那一段。

        bash 的 note() 做两件事: 记进 NOTES(会进 JSON 载荷), 并在文本模式下打印到 stdout。
        而 day_epoch 的唯一调用点是 `epoch=$(day_epoch "$d")` ⇒ 命令替换在**子 shell** 里
        执行 ⇒ 两件事都留在子 shell 里: 打印被捕获(不进门禁 stdout), NOTES 的追加也没有
        回到父进程(所以 JSON 载荷的 notes 数组里看不到这条 note)。
        返回值 = 「被捕获的那段输出」; JSON 模式下 bash 不打印 ⇒ 返回空串。
        """
        if self.json_mode:
            return ""
        return "%s·%s %s\n" % (self.c_dim, self.c_reset, message)

    def ok(self, message: str) -> None:
        if not self.json_mode:
            print("%s✓%s %s" % (self.c_ok, self.c_reset, message))


class DateEngine:
    """复刻 bash day_epoch() 的三模式判定。

    bash 顺序: 首次调用时先试 `date -d`(gnu), 再试 `date -j -f`(bsd), 都不行
    就落到 posix 近似换算并**额外打印一条降级 note**; 模式一旦定下不再改变。

    可观察差异只有两处:
      * posix 模式的降级 note 被命令替换吞掉(不进 stdout), 但仍进 JSON 载荷的 notes;
      * gnu/bsd 用「本地午夜」epoch, posix 用 POSIX 历法(UTC 午夜)近似值。
    GNU 与 BSD date 对合法日期给出同一个 epoch, 因此端口只需区分
    「本地午夜(合法日历日)」与「POSIX 近似(非法日历日 / 本机无 -d / -j -f)」。
    文本模式下 posix 的降级 note 还会污染**首次** day_epoch 的返回值(与 bash 的
    `epoch=$(day_epoch "$d")` 同构), 使过期判断随原件一起被跳过。
    """

    POSIX_NOTE = (
        "当前环境的 date 不支持 -d / -j -f, 已降级为 POSIX 历法换算"
        "(仅影响「基线是否过期」的 ⚠ 判断, 误差约 ±1 天)"
    )

    def __init__(self, reporter: Reporter) -> None:
        self.reporter = reporter
        self.mode: str | None = None
        self.captured_note = ""

    @staticmethod
    def _valid_calendar(y: int, m: int, d: int) -> bool:
        if not 1 <= m <= 12:
            return False
        try:
            _dt.date(y, m, d)
        except ValueError:
            return False
        return True

    @staticmethod
    def _parse(text: str):
        match = _DATE_CELL_RE.match(text)
        if not match:
            return None
        return (int(match.group(1)), int(match.group(2)), int(match.group(3)))

    @staticmethod
    def _posix_epoch(text: str) -> str:
        """复刻 bash 的 awk 历法换算(UTC 午夜); awk int() 向零截断。"""
        parts = text.split("-")
        numbers = []
        for index in range(3):
            chunk = parts[index] if index < len(parts) else ""
            numbers.append(int(chunk) if chunk.isdigit() else 0)
        year, month, day = numbers
        if month <= 2:
            year -= 1
            month += 12
        era = int((year if year >= 0 else year - 399) / 400)
        year_of_era = year - era * 400
        day_of_year = int((153 * (month - 3) + 2) / 5) + day - 1
        day_of_era = (
            year_of_era * 365
            + int(year_of_era / 4)
            - int(year_of_era / 100)
            + day_of_year
        )
        return str((era * 146097 + day_of_era - 719468) * 86400)

    def day_epoch(self, text: str) -> str:
        """复刻 bash day_epoch(): 先探 gnu(`date -d`), 再探 bsd(`date -j -f`), 否则 posix。

        模式只探测一次(对应 bash 的全局 DATE_MODE); 探测用的就是本次日期本身,
        所以非法日历日会落到 posix 并额外打印一条降级 note。
        """
        if self.mode is None:
            self.mode = self._probe_mode(text)
        if self.mode in ("gnu", "bsd"):
            return self._local_epoch(text)
        epoch = self._posix_epoch(text)
        if self.captured_note:
            prefix = self.captured_note
            self.captured_note = ""
            return prefix + epoch
        return epoch

    def _probe_mode(self, text: str) -> str:
        """合法日历日 ⇒ gnu(本机 `date -d` 可解析); 否则 posix + 降级 note。

        降级 note 走 `note_captured`: 文本模式下它被 `$(day_epoch)` 捕获(不进 stdout,
        且污染首次 epoch), JSON 模式下它只进 NOTES(epoch 仍是纯数字 ⇒ 过期判断照常执行)。
        """
        parsed = self._parse(text)
        if parsed is not None and self._valid_calendar(*parsed):
            return "gnu"
        self.captured_note = self.reporter.note_captured(self.POSIX_NOTE)
        return "posix"

    def _local_epoch(self, text: str) -> str:
        """gnu/bsd `date -d YYYY-MM-DD +%s` 给的是**本地午夜**的 epoch。"""
        parsed = self._parse(text)
        if parsed is None:
            return ""
        year, month, day = parsed
        try:
            moment = _dt.datetime(year, month, day)
        except ValueError:
            return ""
        try:
            return str(int(moment.timestamp()))
        except (OverflowError, OSError, ValueError):
            return ""

def _parse_repo_map(text: str):
    """复刻 bash parse_repo_map() 的 awk 解析。

    返回 (map_loaded, [(标识, 本地路径), ...])。
    """
    map_loaded = False
    entries: list[tuple[str, str]] = []
    section = False
    id_index = 0
    lp_index = 0
    for line in text.split("\n"):
        if _SECTION_START_RE.match(line):
            section = True
            continue
        if section and _SECTION_END_RE.match(line):
            section = False
        if not section:
            continue
        if not line.startswith("|"):
            continue
        cells = line.split("|")
        hid = 0
        hlp = 0
        for index, cell in enumerate(cells, start=1):
            value = _trim_tab(cell).replace("**", "")
            if value == "标识" and hid == 0:
                hid = index
            elif value == "本地路径" and hlp == 0:
                hlp = index
        if hid > 0 and hlp > 0:
            map_loaded = True
            id_index = hid
            lp_index = hlp
            continue
        if id_index > 0 and lp_index > 0:
            n = len(cells)
            if n <= id_index or n <= lp_index:
                continue
            key = _trim_tab(cells[id_index - 1]).replace("**", "")
            value = _trim_tab(cells[lp_index - 1]).replace("`", "")
            if key == "":
                continue
            if re.match(r"^:?-+:?$", key):
                continue
            # bash 消费端: 本地路径列为占位符时不入 REPO_PATHS
            if value in ("\u2014", "-", ""):
                continue
            entries.append((key, value))
    return map_loaded, entries


def _repo_tokens(entries):
    """复刻 bash: REPO_PATHS=" k=v ..." 之后 `tr ' ' '\n'` 摊平成 token 列表。"""
    tokens = []
    for name, path in entries:
        tokens.extend(("%s=%s" % (name, path)).split(" "))
    return tokens


def _repo_path_of(key: str, entries, root: str) -> str:
    """复刻 bash repo_path_of(): grep "^${key}=" | head -1 | cut -d= -f2-。"""
    pattern = re.compile("^" + key + "=")
    value = ""
    for token in _repo_tokens(entries):
        if pattern.match(token):
            value = token.split("=", 1)[1] if "=" in token else ""
            break
    if not value:
        return ""
    if value.startswith("/"):
        return value
    if value.startswith("./"):
        return "%s/%s" % (root, value[2:])
    return "%s/%s" % (root, value)

def _repo_registered(key: str, entries) -> bool:
    """复刻 bash repo_registered(): `case " $REPO_PATHS " in *" $1="*)`。"""
    haystack = " %s " % " ".join(_repo_tokens(entries))
    return (" %s=" % key) in haystack

def _git(path: str, *args: str):
    """唯一允许的子进程: git。返回 (rc, stdout 文本, stderr 文本)。"""
    try:
        proc = subprocess.run(
            ["git", "-C", path, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        return 1, "", ""
    return (
        proc.returncode,
        proc.stdout.decode("utf-8", "replace").strip(),
        proc.stderr.decode("utf-8", "replace").strip(),
    )


def _extract_baseline_section(text: str) -> str:
    """复刻 bash 抽取 `## 实现基线` 段的 awk。"""
    fence = False
    inside = False
    lines: list[str] = []
    for line in text.split("\n"):
        if _FENCE_RE.match(line):
            fence = not fence
            continue
        if not fence and _BASELINE_HEAD_RE.match(line):
            inside = True
            continue
        if not fence and inside and _ANY_HEADING_RE.match(line):
            inside = False
        if inside:
            lines.append(line)
    return "\n".join(lines).rstrip("\n")


def _split_row(row: str, count: int = 6) -> list[str]:
    """复刻 bash: IFS='|' read -r repo branch sha date items status。

    字段不足则补空; 字段多于变量数时, 最后一个变量拿到剩余全文(含分隔符)。
    """
    parts = row.split("|")
    if len(parts) <= count:
        return parts + [""] * (count - len(parts))
    return parts[: count - 1] + ["|".join(parts[count - 1:])]


def _listdir(path: str) -> list[str]:
    """bash glob `dir/*`: 只列名字、不含隐藏项, 按 C 序(字节序)排序。"""
    try:
        names = os.listdir(path)
    except OSError:
        return []
    return sorted(name for name in names if not name.startswith("."))


def _read_text(path: str) -> str:
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError:
        return ""
    return raw.decode("utf-8", "replace")


def _relative_to_root(path: str, root: str) -> str:
    """复刻 bash `rel=${readme#"$ROOT"/}` —— 相对 root 的路径, 分隔符统一为 `/`。"""
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        rel = path
    return rel.replace("\\", "/")


def check_readme(readme: str, root: str, reporter: Reporter, date_engine: DateEngine,
                 map_loaded: bool, entries, checked: list, max_age_days: int) -> int:
    """复刻 bash check_readme(); 返回 0=通过 1=有违规。"""
    rel = _relative_to_root(readme, root)
    section = _extract_baseline_section(_read_text(readme))

    if section == "":
        reporter.err("%s — 缺少 `## 实现基线` 段 (AGENTS.md §1.6 门禁)" % rel)
        return 1

    section_lines = section.split("\n")
    if not any(line.startswith("|") for line in section_lines):
        joined = "\n".join(section_lines)
        if "不适用" in joined or "N/A" in joined or "无关联代码仓" in joined:
            reporter.note("%s — 实现基线不适用(已声明), 跳过" % rel)
            return 0
        reporter.err("%s — `## 实现基线` 段既无表格行也无「不适用」声明" % rel)
        return 1

    rows = 0
    for line in section_lines:
        if line == "":
            continue
        if not line.startswith("|"):
            continue
        if _SEPARATOR_ROW_RE.match(line):
            continue

        row = line[1:]
        if row.endswith("|"):
            row = row[:-1]
        cells = _split_row(row)

        repo = _trim(cells[0].replace("`", ""))
        branch = _trim(cells[1].replace("`", ""))
        sha = _trim(cells[2].replace("`", ""))
        date_cell = _trim(cells[3].replace("`", ""))
        items = _trim(cells[4].replace("`", ""))
        status = _trim(cells[5].replace("`", ""))

        if repo in _HEADER_CELLS:
            continue

        rows += 1
        checked[0] += 1

        if sha == "" or branch == "":
            reporter.err("%s — `%s` 缺分支或 SHA" % (rel, repo))
            continue
        if items == "":
            reporter.err("%s — `%s` 缺「核对项」" % (rel, repo))

        found = _DATE_IN_CELL_RE.search(date_cell)
        d = found.group(0) if found else ""
        if d == "":
            reporter.err("%s — `%s` 核对日期缺失或格式非 YYYY-MM-DD" % (rel, repo))

        if any(marker in status for marker in _INCOMPLETE_MARKERS):
            reporter.err("%s — `%s` 状态为 `%s`, 基线未完结" % (rel, repo, status))
            continue

        # 状态 ○ = 不适用 / 跳过 → 不做仓存在性校验
        if status == "○":
            continue

        if not _repo_registered(repo, entries):
            if map_loaded:
                reporter.warn("%s — 仓库标识 `%s` 未在 AGENTS.md §1.1 登记, 跳过存在性校验" % (rel, repo))
            else:
                reporter.warn("%s — AGENTS.md §1.1 仓库清单不可解析, 跳过 `%s` 存在性校验" % (rel, repo))
            continue

        path = _repo_path_of(repo, entries, root)
        rc, _out, _err = _git(path, "rev-parse", "--git-dir")
        if rc != 0:
            reporter.warn("%s — 仓库 `%s` 本地未检出 (%s), 跳过存在性校验" % (rel, repo, path))
            continue
        rc, _out, _err = _git(path, "cat-file", "-e", "%s^{commit}" % sha)
        if rc != 0:
            reporter.err("%s — `%s@%s` 在本地不存在" % (rel, repo, sha))
            continue

        rc, sha_full, _err = _git(path, "rev-parse", "%s^{commit}" % sha)
        if rc != 0:
            sha_full = ""
        ref = ""
        for candidate in ("refs/remotes/origin/%s" % branch, "refs/heads/%s" % branch, branch):
            rc, _out, _err = _git(path, "rev-parse", "--verify", "--quiet", candidate)
            if rc == 0:
                ref = candidate
                break
        if ref != "":
            rc, head_full, _err = _git(path, "rev-parse", ref)
            if rc != 0:
                head_full = ""
            if sha_full != head_full:
                rc, head_short, _err = _git(path, "rev-parse", "--short", ref)
                if rc != 0:
                    head_short = ""
                reporter.warn("%s — `%s` 基线 `%s` 落后于 `%s` 头 `%s`(有意钉住请忽略)"
                              % (rel, repo, sha, branch, head_short))

        if d != "":
            epoch = date_engine.day_epoch(d)
            now = int(time.time())
            if epoch != "" and epoch.isdigit() and int(epoch) > 0:
                delta = now - int(epoch)
                age = delta // 86400 if delta >= 0 else -((-delta) // 86400)
                if age > max_age_days:
                    reporter.warn("%s — `%s` 基线已 %d 天未复核(阈值 %d 天)"
                                  % (rel, repo, age, max_age_days))

    if rows == 0:
        reporter.err("%s — `## 实现基线` 段没有有效表格行" % rel)
        return 1
    reporter.ok("%s — 实现基线 %d 行" % (rel, rows))
    return 0


def _has_any_artifact(root: str) -> bool:
    """复刻 bash has_any_artifact()。"""
    prd_dir = os.path.join(root, "prd")
    if os.path.isdir(prd_dir):
        for name in _listdir(prd_dir):
            sub = os.path.join(prd_dir, name)
            if not os.path.isdir(sub):
                continue
            if not _DATE_DIR_RE.match(name):
                continue
            for entry in _listdir(sub):
                if not entry.endswith(".md"):
                    continue
                if not os.path.isfile(os.path.join(sub, entry)):
                    continue
                if not _TOPIC_RE.match(entry[:-3]):
                    continue
                return True
    for layer in ("tech_design", "plan"):
        base = os.path.join(root, layer)
        if not os.path.isdir(base):
            continue
        for name in _listdir(base):
            if not os.path.isdir(os.path.join(base, name)):
                continue
            if _DATETOPIC_DIR_RE.match(name):
                return True
    tc_dir = os.path.join(root, "test_cases")
    if os.path.isdir(tc_dir):
        for name in _listdir(tc_dir):
            sub = os.path.join(tc_dir, name)
            if not os.path.isdir(sub):
                continue
            if not _DATE_DIR_RE.match(name):
                continue
            for entry in _listdir(sub):
                if not entry.endswith(".md"):
                    continue
                if not os.path.isfile(os.path.join(sub, entry)):
                    continue
                if entry[:-3].endswith("-key-points"):
                    continue
                return True
    return False


def _td_readmes(base: str) -> list[str]:
    """bash: for d in "$base"/*/ 且目录名匹配 datetopic, 取其 README.md。"""
    out: list[str] = []
    if not os.path.isdir(base):
        return out
    for name in _listdir(base):
        sub = os.path.join(base, name)
        if not os.path.isdir(sub):
            continue
        if not _DATETOPIC_DIR_RE.match(name):
            continue
        readme = os.path.join(sub, "README.md")
        if os.path.isfile(readme):
            out.append(readme)
    return out


def main(argv) -> int:
    json_mode = False
    root = ""
    target = ""
    max_age_days = "7"

    args = list(argv)
    index = 0
    while index < len(args):
        arg = args[index]
        index += 1
        if arg == "--json":
            json_mode = True
        elif arg == "--root":
            if index >= len(args):
                sys.stderr.write("✗ --root 需要目录参数\n")
                return EXIT_USAGE
            root = args[index]
            index += 1
        elif arg.startswith("--root="):
            root = arg[len("--root="):]
        elif arg == "--stage" or arg.startswith("--stage="):
            sys.stderr.write("%s: 本门禁与阶段无关;--stage 只对 scripts/check-md-schema.py 有效\n" % SCRIPT_PATH)
            return EXIT_USAGE
        elif arg == "--max-age-days":
            if index >= len(args):
                sys.stderr.write("✗ --max-age-days 需要数字参数\n")
                return EXIT_USAGE
            max_age_days = args[index]
            index += 1
        elif arg.startswith("--max-age-days="):
            max_age_days = arg[len("--max-age-days="):]
        elif arg in ("--help", "-h"):
            sys.stdout.write("用法: %s [--json] [--root DIR] [--max-age-days N] [TARGET]\n" % SCRIPT_PATH)
            return EXIT_OK
        elif arg.startswith("-"):
            sys.stderr.write("✗ 未知参数: %s\n" % arg)
            return EXIT_USAGE
        else:
            if target == "":
                target = arg
            else:
                sys.stderr.write("✗ 只能指定一个 TARGET\n")
                return EXIT_USAGE

    if max_age_days == "" or not max_age_days.isdigit():
        sys.stderr.write("✗ --max-age-days 必须是整数: %s\n" % max_age_days)
        return EXIT_USAGE

    if root == "":
        root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if not os.path.isdir(root):
        sys.stderr.write("✗ --root 目录不存在: %s\n" % root)
        return EXIT_USAGE
    root = os.path.realpath(root)

    if target != "" and not target.startswith("/"):
        target = "%s/%s" % (root, target)

    agents_file = os.path.join(root, "AGENTS.md")
    reporter = Reporter(json_mode)
    date_engine = DateEngine(reporter)
    checked = [0]

    map_loaded = False
    entries: list = []
    if os.path.isfile(agents_file):
        map_loaded, entries = _parse_repo_map(_read_text(agents_file))

    if target != "":
        if not os.path.exists(target):
            sys.stderr.write("✗ TARGET 不存在: %s\n" % target)
            return EXIT_USAGE
        if target.endswith("/README.md"):
            check_readme(target, root, reporter, date_engine, map_loaded, entries,
                         checked, int(max_age_days))
        else:
            td_base = os.path.join(target, "tech_design")
            if os.path.isdir(td_base):
                for readme in _td_readmes(td_base):
                    check_readme(readme, root, reporter, date_engine, map_loaded, entries,
                                 checked, int(max_age_days))
            elif os.path.isfile(os.path.join(target, "README.md")):
                check_readme(os.path.join(target, "README.md"), root, reporter, date_engine,
                             map_loaded, entries, checked, int(max_age_days))
            else:
                reporter.note("未找到 tech_design/ 或 TD 目录, 跳过(无可校验的基线段)")
    else:
        td_count = 0
        for readme in _td_readmes(os.path.join(root, "tech_design")):
            td_count += 1
            check_readme(readme, root, reporter, date_engine, map_loaded, entries,
                         checked, int(max_age_days))
        if td_count == 0:
            if _has_any_artifact(root):
                reporter.note("tech_design 层没有 Tech Design 制品, 跳过实现基线校验(该层无制品)")
            else:
                reporter.err("本仓没有任何规格产物,门禁无从校验")

    error_count = len(reporter.errors)
    warning_count = len(reporter.warnings)
    if error_count > 0:
        status = "violation"
        exit_code = EXIT_VIOLATION
    else:
        status = "pass"
        exit_code = EXIT_OK

    if json_mode:
        payload = (
            '{"script":"check-repo-baseline.py","root":"%s","status":"%s","exit_code":%d,'
            '"error_count":%d,"warning_count":%d,"checked":%d,"errors":%s,"warnings":%s,"notes":%s}\n'
            % (
                json_escape(root),
                status,
                exit_code,
                error_count,
                warning_count,
                checked[0],
                json_str_array(reporter.errors),
                json_str_array(reporter.warnings),
                json_str_array(reporter.notes),
            )
        )
        sys.stdout.write(payload)
    else:
        if error_count > 0:
            sys.stdout.write("✗ 实现基线校验: %d 项违规, %d 项警告, 共 %d 行\n"
                             % (error_count, warning_count, checked[0]))
        else:
            reporter.ok("实现基线校验: %d 行全部通过 (%d 项警告)" % (checked[0], warning_count))
    return exit_code


if __name__ == "__main__":
    _configure_stdio()
    sys.exit(main(sys.argv[1:]))
