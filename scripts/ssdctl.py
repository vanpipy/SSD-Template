#!/usr/bin/env python3
"""SSD-Template 仓内机器能力的单入口(契约 §5)。

用法(命令名、参数、退出码一律以实施契约 §5 为准):

    python scripts/ssdctl.py scan [--json] [--layer L] [--check]
    python scripts/ssdctl.py criteria <artifact> [--json]
    python scripts/ssdctl.py gate [--json]
    python scripts/ssdctl.py advance <artifact> --to <Ready|Implemented|Deprecated>
                                     [--actor A] [--decision <path>#<anchor>] [--dry-run]
    python scripts/ssdctl.py queue <artifact> [--json]
    python scripts/ssdctl.py decide --artifact <path> --action <approve|reject|hold|override>
                                    --actor <name> --reason <text> [--criterion <id>]
    python scripts/ssdctl.py evidence [--artifact <path>] [--json]
    python scripts/ssdctl.py verify <artifact>

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

    scan = sub.add_parser("scan", help="扫描制品并生成派生状态 control/state.json")
    scan.add_argument("--json", action="store_true", help="输出 JSON")
    scan.add_argument("--layer", default=None, help="只处理某一层(prd/td/plan/test-case)")
    scan.add_argument("--check", action="store_true", help="只比对 control/state.json 与磁盘,不一致退 1")

    criteria = sub.add_parser("criteria", help="对单个制品跑判据")
    criteria.add_argument("artifact", help="制品路径(仓库相对)")
    criteria.add_argument("--json", action="store_true", help="输出 JSON")

    gate = sub.add_parser("gate", help="跑全部仓内门禁 + 判据,并写派生数据")
    gate.add_argument("--json", action="store_true", help="输出 JSON")

    advance = sub.add_parser("advance", help="推进制品状态(先全量校验,再一次性写入)")
    advance.add_argument("artifact", help="制品路径(仓库相对)")
    advance.add_argument("--to", required=True, help="目标状态:Ready/Implemented/Deprecated")
    advance.add_argument("--actor", default="agent:sddctl", help="操作者(默认 agent:sddctl)")
    advance.add_argument("--decision", default=None, help="授权决定 `control/decisions/<file>#<id>`")
    advance.add_argument("--dry-run", action="store_true", help="只校验并打印计划,不写任何文件")

    queue = sub.add_parser("queue", help="列出待人工裁决的判据项")
    queue.add_argument("artifact", help="制品路径(仓库相对)")
    queue.add_argument("--json", action="store_true", help="输出 JSON")

    decide = sub.add_parser("decide", help="写一条人工介入决定")
    decide.add_argument("--artifact", required=True, help="目标制品路径")
    decide.add_argument("--action", required=True, help="approve/reject/hold/override")
    decide.add_argument("--actor", required=True, help="操作人")
    decide.add_argument("--reason", required=True, help="理由")
    decide.add_argument("--criterion", default=None, help="作用范围:某条判据 id(默认 all)")

    evidence = sub.add_parser("evidence", help="读回证据链")
    evidence.add_argument("--artifact", default=None, help="只看某个制品")
    evidence.add_argument("--json", action="store_true", help="输出 JSON")

    verify = sub.add_parser("verify", help="校验状态块/复审块/证据链是否自洽")
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
        "decide": commands.cmd_decide,
        "evidence": commands.cmd_evidence,
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
