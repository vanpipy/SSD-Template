#!/usr/bin/env python3
"""check-naming.py —— 目录 / 文件命名与层结构(形状)门禁(`check-naming.sh` 的 Python 端口)。

本文件是 bash 原件 `scripts/check-naming.sh` 的**逐字节等价**实现:同一 corpus、同一
`--root` 下,stdout 逐字节相同、退出码相同。唯一的凭据是
`scripts/tests/fixtures/naming-corpus.json` 里的 golden —— golden 由 **bash 原件**采集
(原件的 SHA-1 记在 fixture 的 `source_sha1` 里);端口实现**不得**自己生成 golden
(那是同源污染,验收会被推翻)。

端口的硬约束(需求集 phase-b-gate-python-port R-1 / R-2):
  - **单进程**:不 spawn 任何子进程。原件的 `find | sed | sort`、`tr | wc`、`basename`、
    `dirname`、`grep -Eq`、`cut`、`awk` 全部由 `pathlib` + `re` 复现。
  - **逐字节**:符号、全角标点、空格、输出顺序、行尾换行全部照抄原件;比对按 bytes。
  - **CLI 契约不变**:`--json` / `--root DIR` / `TARGET` / `--help`;退出码
    0=通过 1=违规 2=用法或环境错误。

用法:
    scripts/check-naming.py [--json] [--root DIR] [TARGET]
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# --- 退出码(契约 M6) ---
EXIT_OK = 0
EXIT_VIOLATION = 1
EXIT_USAGE = 2

# --- 形状常量(契约 §1 M2)—— 与 bash 原件逐字一致 ---
TOPIC_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
DATETOPIC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$")
DATE_PREFIX_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-")

#: 层目录(扫描顺序与 bash 原件一致)。
LAYERS = ("prd", "tech_design", "plan", "test_cases", "material")

#: 层根目录里免于内容校验的两个文件。
ROOT_DOCS = ("README.md", "_index.md")

#: `--help` 的正文 —— 与 bash 原件**归一化后逐字节相同**(R-1:身份串归一为 {GATE} / {RUN})。
#: 按 Phase B1 的 R-1,新实现一律用新名:`python scripts/` + `check-naming.py`;
#: 归一化规则(basename → {GATE}、调用前缀 → {RUN} scripts/)由仓内差分口径对两侧同时施加。
USAGE = (
    "用法: python scripts/check-naming.py [--json] [--root DIR] [TARGET]\n"
    "\n"
    "  --json         以 JSON 输出(供 CI 消费)\n"
    "  --root DIR     仓根目录(默认: 本脚本所在目录的上一级)\n"
    "  --stage        本门禁与阶段无关:阶段相关必填项由 scripts/check-md-schema.py 判定。\n"
    "                 收到 --stage 立即退出 2(不接受,也不回显)。\n"
    "  TARGET         可选, 只检查这一个文件或目录\n"
    "  --help         显示本帮助\n"
    "\n"
    "退出码: 0=通过 1=存在违规 2=调用/环境错误\n"
)


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


def posix_basename(path: str) -> str:
    """`basename`(POSIX 语义):取最后一个 `/` 之后的部分。"""
    return path.rsplit("/", 1)[-1]


def posix_dirname(path: str) -> str:
    """`dirname`(POSIX 语义):去掉最后一个 `/` 之后的部分;没有 `/` 时返回 `.`。"""
    head, sep, _ = path.rpartition("/")
    return head if sep else "."


def split_date_topic(name: str) -> str:
    """`split_date_topic()` 的等价实现:匹配日期前缀时输出 `date topic`,否则无输出。"""
    if DATE_PREFIX_RE.match(name):
        return f"{name[:10]} {name[11:]}"
    return ""


def find_md_files(layer_dir: Path) -> list[str]:
    """`find . -type f -name '*.md' | sed 's|^\\./||' | LC_ALL=C sort` 的等价实现。

    - 不跟随符号链接(`find` 默认 `-P`):符号链接文件与符号链接目录都不算 `-type f`;
    - 只收 `.md` 结尾的**普通文件**(后缀匹配大小写敏感);
    - 相对路径以 `/` 分隔,按字节序排序(UTF-8 的字节序 == Python 的码点序)。
    """
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(layer_dir, followlinks=False):
        dirnames[:] = [
            name for name in dirnames if not os.path.islink(os.path.join(dirpath, name))
        ]
        for name in filenames:
            full = Path(dirpath) / name
            if full.is_symlink():
                continue
            if not name.endswith(".md"):
                continue
            if not full.is_file():
                continue
            found.append(full.relative_to(layer_dir).as_posix())
    return sorted(found)


class Reporter:
    """结果收集与打印 —— 复现 bash 原件「即时打印 + JSON 模式只收集」的两种行为。"""

    def __init__(self, json_mode: bool) -> None:
        self.json_mode = json_mode
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []
        self.color_ok, self.color_err, self.color_warn, self.color_dim, self.color_reset = (
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


def _color_codes() -> tuple[str, str, str, str, str]:
    """复现原件的着色判定:`NO_COLOR` 非空或 stdout 不是 tty ⇒ 不着色。"""
    if os.environ.get("NO_COLOR", "") or not sys.stdout.isatty():
        return ("", "", "", "", "")
    return ("\x1b[32m", "\x1b[31m", "\x1b[33m", "\x1b[2m", "\x1b[0m")


def _emit(text: str) -> None:
    sys.stdout.write(text)


def scan_layer(root: Path, layer: str, reporter: Reporter, counters: dict[str, int]) -> None:
    """逐层扫描 —— 与原件的 `scan_layer()` 同构(判定顺序、消息文本、计数口径一致)。"""
    layer_dir = root / layer
    if not layer_dir.is_dir():
        reporter.note(f"层未启用(目录不存在,跳过): {layer}/")
        return

    rels = find_md_files(layer_dir)
    if not rels:
        reporter.warn(f"层已启用但没有任何制品(仅可能有 README.md / _index.md): {layer}/")
        return

    layer_artifacts = 0

    for rel in rels:
        depth = rel.count("/") + 1
        base = posix_basename(rel)
        parent = posix_dirname(rel)
        stem = base[:-3] if base.endswith(".md") else base

        # 深度 1: 层根目录
        if depth == 1:
            if base in ROOT_DOCS:
                continue
            counters["files"] += 1
            layer_artifacts += 1
            if layer == "material":
                reporter.warn(
                    f"素材区根目录出现 .md(建议放 {layer}/{{YYYY-MM-DD}}/): {layer}/{base}"
                )
            else:
                reporter.err(
                    f"层根目录不允许放规格文件(只允许 README.md / _index.md): {layer}/{base}"
                )
            continue

        counters["files"] += 1
        layer_artifacts += 1

        if layer == "prd":
            if depth != 2:
                reporter.err(
                    f"形状错误: prd/ 下只允许 {{YYYY-MM-DD}}/{{topic}}.md 两级结构, "
                    f"实际深度 {depth}: prd/{rel}"
                )
                continue
            if not DATE_RE.fullmatch(parent):
                reporter.err(f"日期目录格式错误(期望 YYYY-MM-DD): prd/{parent}")
                continue
            if TOPIC_RE.fullmatch(stem):
                counters["artifacts"] += 1
            else:
                reporter.warn(
                    "疑似 PRD 命名不合规(topic 必须小写连字符), "
                    f"按暂存素材处理并跳过字段校验: prd/{rel}"
                )
        elif layer == "tech_design":
            pdir = parent.split("/")[0]
            if depth != 2:
                reporter.err(
                    "形状错误: tech_design/ 下只允许 {YYYY-MM-DD}-{topic}/*.md 两级结构, "
                    f"实际深度 {depth}: tech_design/{rel}"
                )
                continue
            if not DATETOPIC_RE.fullmatch(pdir):
                reporter.err(f"Tech Design 目录名必须为 {{YYYY-MM-DD}}-{{topic}}: tech_design/{pdir}")
                continue
            counters["artifacts"] += 1
        elif layer == "plan":
            pdir = parent.split("/")[0]
            if depth != 2:
                reporter.err(
                    "形状错误: plan/ 下只允许 {YYYY-MM-DD}-{topic}/{topic}.md 三级结构, "
                    f"实际深度 {depth}: plan/{rel}"
                )
                continue
            if not DATETOPIC_RE.fullmatch(pdir):
                reporter.err(f"Plan 目录名必须为 {{YYYY-MM-DD}}-{{topic}}: plan/{pdir}")
                continue
            fields = split_date_topic(pdir).split(" ")
            ptopic = fields[1] if len(fields) > 1 else ""
            if stem != ptopic:
                reporter.err(f"Plan 文件名必须等于目录 topic(目录 {pdir}): plan/{rel}")
                continue
            counters["artifacts"] += 1
        elif layer == "test_cases":
            if depth != 2:
                reporter.err(
                    "形状错误: test_cases/ 下只允许 {YYYY-MM-DD}/{topic}.md 两级结构, "
                    f"实际深度 {depth}: test_cases/{rel}"
                )
                continue
            if not DATE_RE.fullmatch(parent):
                reporter.err(f"日期目录格式错误(期望 YYYY-MM-DD): test_cases/{parent}")
                continue
            tstem = stem
            if tstem.endswith("-key-points"):
                tstem = tstem[: -len("-key-points")]
            elif tstem.endswith("-smoke"):
                tstem = tstem[: -len("-smoke")]
            if not TOPIC_RE.fullmatch(tstem):
                reporter.err(
                    "测试用例文件名不合法(topic 小写连字符, 允许 -smoke / -key-points 后缀): "
                    f"test_cases/{rel}"
                )
                continue
            counters["artifacts"] += 1
        elif layer == "material":
            if depth != 2:
                reporter.err(
                    "形状错误: material/ 下只允许 {YYYY-MM-DD}/*.md 两级结构, "
                    f"实际深度 {depth}: material/{rel}"
                )
                continue
            if not DATE_RE.fullmatch(parent):
                reporter.err(f"素材批次目录格式错误(期望 YYYY-MM-DD): material/{parent}")
                continue

    if layer_artifacts == 0:
        reporter.warn(f"层已启用但没有任何规格制品(只有 README.md / _index.md): {layer}/")


def check_single_file(
    trel: str, layer: str, reporter: Reporter, counters: dict[str, int]
) -> None:
    """单文件模式 —— 与原件的 TARGET 文件分支同构。

    注意原件的判定口径:**只查深度**,不查目录名 / topic / 日期(与整层扫描不同)。
    """
    prefix = layer + "/"
    rel_in_layer = trel[len(prefix) :] if trel.startswith(prefix) else trel
    depth = rel_in_layer.count("/") + 1
    base = posix_basename(rel_in_layer)
    stem = base[:-3] if base.endswith(".md") else base

    if layer == "prd":
        if depth != 2:
            reporter.err(
                f"形状错误: prd/ 下只允许 {{YYYY-MM-DD}}/{{topic}}.md 两级结构: {trel}"
            )
        elif not TOPIC_RE.fullmatch(stem):
            reporter.warn(f"疑似 PRD 命名不合规, 按暂存素材处理并跳过字段校验: {trel}")
        else:
            counters["artifacts"] = 1
    elif layer == "tech_design":
        if depth != 2:
            reporter.err(
                "形状错误: tech_design/ 下只允许 {YYYY-MM-DD}-{topic}/*.md 两级结构: "
                f"{trel}"
            )
        else:
            counters["artifacts"] = 1
    elif layer == "plan":
        if depth != 2:
            reporter.err(
                f"形状错误: plan/ 下只允许 {{YYYY-MM-DD}}-{{topic}}/{{topic}}.md 三级结构: {trel}"
            )
        else:
            counters["artifacts"] = 1
    elif layer == "test_cases":
        if depth != 2:
            reporter.err(
                f"形状错误: test_cases/ 下只允许 {{YYYY-MM-DD}}/{{topic}}.md 两级结构: {trel}"
            )
        else:
            counters["artifacts"] = 1
    elif layer == "material":
        if depth != 2:
            reporter.err(
                f"形状错误: material/ 下只允许 {{YYYY-MM-DD}}/*.md 两级结构: {trel}"
            )


def main(argv: list[str]) -> int:
    _configure_stdio()
    script_path = sys.argv[0] if sys.argv else "check-naming.py"

    json_mode = False
    root_arg = ""
    target = ""

    # --- 参数解析(逐条复现原件的 while/case 循环) ---
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--json":
            json_mode = True
        elif arg == "--root":
            index += 1
            if index >= len(argv):
                sys.stderr.write(f"{script_path}: --root 需要参数\n")
                return EXIT_USAGE
            root_arg = argv[index]
        elif arg.startswith("--root="):
            root_arg = arg[len("--root=") :]
        elif arg == "--stage" or arg.startswith("--stage="):
            sys.stderr.write(
                f"{script_path}: 本门禁与阶段无关;--stage 只对 scripts/check-md-schema.py 有效\n"
            )
            return EXIT_USAGE
        elif arg in ("--help", "-h"):
            sys.stdout.write(USAGE)
            return EXIT_OK
        elif arg == "--":
            break
        elif arg.startswith("-"):
            sys.stderr.write(f"{script_path}: 未知参数: {arg}\n")
            sys.stderr.write(USAGE)
            return EXIT_USAGE
        else:
            if target:
                sys.stderr.write(f"{script_path}: 只接受一个 TARGET\n")
                return EXIT_USAGE
            target = arg
        index += 1

    # --- 根目录解析(原件: 空则用默认,不存在则退 2,存在则取物理路径) ---
    default_root = Path(__file__).resolve().parent.parent
    root_display = root_arg if root_arg else str(default_root)
    root_input = Path(root_display)
    if not root_input.is_dir():
        sys.stderr.write(f"{script_path}: 根目录不存在: {root_display}\n")
        return EXIT_USAGE
    root = Path(os.path.realpath(str(root_input)))

    # --- TARGET 解析(原件: 绝对路径原样,相对路径挂到根下;不存在则退 2) ---
    target_path = ""
    if target:
        if target.startswith("/"):
            target_path = target
        else:
            target_path = str(root) + "/" + target
        if not os.path.exists(target_path):
            sys.stderr.write(f"{script_path}: TARGET 不存在: {target_path}\n")
            return EXIT_USAGE

    reporter = Reporter(json_mode)
    counters = {"files": 0, "artifacts": 0}

    if target:
        # 相对 TARGET 时,原件的 `trel` 就是去掉 `$ROOT/` 前缀后的 TARGET 本身。
        trel = target
        layer = trel.split("/")[0]
        if os.path.isdir(target_path):
            if layer in LAYERS:
                reporter.note(f"单目录模式: 只检查 {layer}/")
                # 原件在此分支**不进入扫描循环**(扫描循环在 `else` 分支里)——
                # 逐字节等价要求保留这个行为,见交付报告「已知问题 §K2」。
            else:
                sys.stderr.write(f"{script_path}: 无法识别的层目录: {trel}\n")
                return EXIT_USAGE
        else:
            if layer not in LAYERS:
                sys.stderr.write(f"{script_path}: 无法识别的层路径: {trel}\n")
                return EXIT_USAGE
            reporter.note(f"单文件模式: 只检查 {trel}")
            counters["files"] = 0
            counters["artifacts"] = 0
            check_single_file(trel, layer, reporter, counters)
    else:
        for layer in LAYERS:
            scan_layer(root, layer, reporter, counters)

    # --- M6: 全仓没有任何规格产物 ---
    if not target and counters["files"] == 0:
        reporter.err("本仓没有任何规格产物,门禁无从校验")

    if not reporter.errors:
        reporter.ok(f"命名与层结构检查通过 (制品 {counters['artifacts']} 个)")

    status = "violation" if reporter.errors else "pass"
    code = EXIT_VIOLATION if reporter.errors else EXIT_OK

    if json_mode:
        payload = (
            '{"script":"check-naming.py",'
            f'"root":"{json_escape(str(root))}",'
            f'"status":"{status}",'
            f'"exit_code":{code},'
            f'"error_count":{len(reporter.errors)},'
            f'"warning_count":{len(reporter.warnings)},'
            f'"artifacts":{counters["artifacts"]},'
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
