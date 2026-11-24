#!/usr/bin/env python3
"""SSD-Template 仓内机器能力的单入口(契约 §5)。

用法(命令名、参数、退出码一律以实施契约 §5 为准):

    python scripts/ssdctl.py scan [--json] [--layer L] [--check]
    python scripts/ssdctl.py criteria <artifact> [--json]
    python scripts/ssdctl.py gate [--json]
    python scripts/ssdctl.py advance <artifact> --to <Ready|Implemented|Deprecated>
                                     [--actor agent:<id>] [--external <ref>] [--dry-run]
    python scripts/ssdctl.py queue <artifact> [--json]
    python scripts/ssdctl.py verify <artifact>

F9(单载体):仓内**没有控制平面**。状态与评审的唯一权威载体 = 制品本身;
人与 agent 跑的是**同一条** `advance` —— 差异只在署名来源:
agent 用 `--actor agent:<id>`(机器写复审块),人**先**在制品 `## 复审 (Review)`
段自己写好署名再跑同一条命令(机器原样保留、不覆盖)。

退出码(契约 INV-7):0=通过/成功,1=违规/校验失败,2=用法或内部错误。
判据文件缺失时一律退 2 并明确报错 —— **绝不静默放行**。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):  # 允许 `python scripts/ssdctl.py` 直接运行
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import commands  # noqa: E402
from lib.commands import EXIT_OK, EXIT_USAGE, UsageError  # noqa: E402
from lib.paths import find_repo_root  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ssdctl.py",
        description="SSD-Template 仓内机器能力单入口(实施契约 §5)",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    scan = sub.add_parser("scan", help="扫描制品并打印派生视图(不落盘)")
    scan.add_argument("--json", action="store_true", help="输出 JSON")
    scan.add_argument("--layer", default=None, help="只处理某一层(prd/td/plan/test-case)")
    scan.add_argument("--check", action="store_true", help="跨制品一致性检查(上游闸门/三件套原子性/字段自洽),不通过退 1")

    criteria = sub.add_parser("criteria", help="对单个制品跑判据")
    criteria.add_argument("artifact", help="制品路径(仓库相对)")
    criteria.add_argument("--json", action="store_true", help="输出 JSON")

    gate = sub.add_parser("gate", help="跑全部仓内门禁 + 判据 + 制品自洽性")
    gate.add_argument("--json", action="store_true", help="输出 JSON")

    advance = sub.add_parser("advance", help="推进制品状态(先全量校验,再一次性写入)")
    advance.add_argument("artifact", help="制品路径(仓库相对)")
    advance.add_argument("--to", required=True, help="目标状态:Ready/Implemented/Deprecated")
    advance.add_argument("--actor", default="agent:ssdctl", help="操作者(只接受 agent:<id>;人工署名写在制品的 `## 复审 (Review)` 段内)")
    advance.add_argument("--external", default=None, help="外部事实依据 `external:<ref>`(Implemented / Deprecated 必填)")
    advance.add_argument("--dry-run", action="store_true", help="只校验并打印计划,不写任何文件")

    queue = sub.add_parser("queue", help="列出待人工裁决的判据项")
    queue.add_argument("artifact", help="制品路径(仓库相对)")
    queue.add_argument("--json", action="store_true", help="输出 JSON")

    verify = sub.add_parser("verify", help="校验状态块/复审块是否自洽")
    verify.add_argument("artifact", help="制品路径(仓库相对)")

    return parser


def _configure_stdio() -> None:
    """把 stdout/stderr 切到 UTF-8,避免控制台编码把脚本打崩。

    Windows 控制台默认 GBK,打印 `✓` / `✗` 会抛 `UnicodeEncodeError` ——
    契约 INV-7 要求退出码只有 0/1/2,脚本不能因为控制台编码而崩。
    没有 `reconfigure` 的流(被替换过的 stdout)静默跳过。
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):  # pragma: no cover - 极端流实现
            continue


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = build_parser()
    args = parser.parse_args(argv)
    root = find_repo_root()
    handler = {
        "scan": commands.cmd_scan,
        "criteria": commands.cmd_criteria,
        "gate": commands.cmd_gate,
        "advance": commands.cmd_advance,
        "queue": commands.cmd_queue,
        "verify": commands.cmd_verify,
    }[args.command]
    try:
        return handler(root, args)
    except UsageError as exc:
        print(f"✗ 用法错误: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except FileNotFoundError as exc:
        print(f"✗ 内部错误(文件缺失): {exc}", file=sys.stderr)
        return EXIT_USAGE
    except OSError as exc:
        print(f"✗ 内部错误: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
