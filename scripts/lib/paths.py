"""仓库根、判据文件路径解析。

契约来源:`docs/contracts/agent-first-implementation.md` §4(判据文件)。
F9:仓内**不再有控制平面**(`control/` 目录已整体删除)—— 状态与评审的唯一
权威载体是制品本身,所以这里不再解析任何控制面路径。
本模块不读任何环境变量以外的配置;唯一的例外是 `SSDCTL_CRITERIA`(测试与临时判据用)。
"""

from __future__ import annotations

import os
from pathlib import Path

CRITERIA_RELPATH = Path("schema") / "criteria.json"
CRITERIA_ENV = "SSDCTL_CRITERIA"


def _looks_like_repo(candidate: Path) -> bool:
    """仓库根的判据:同时含 `scripts/` 与 `schema/`。"""
    return (candidate / "scripts").is_dir() and (candidate / "schema").is_dir()


def find_repo_root(start: Path | None = None) -> Path:
    """定位仓库根目录。

    依次尝试:显式起点 → 当前工作目录 → 本文件所在位置;每个起点向上找仓库根。
    找不到时退回包所在目录的上上级(安装了本仓脚本的仓库)。
    """
    starts: list[Path] = []
    if start is not None:
        starts.append(Path(start))
    starts.append(Path.cwd())
    starts.append(Path(__file__).resolve().parent.parent.parent)

    seen: set[Path] = set()
    for raw in starts:
        try:
            base = raw.resolve()
        except OSError:  # pragma: no cover - 极端文件系统错误
            continue
        for candidate in (base, *base.parents):
            if candidate in seen:
                continue
            seen.add(candidate)
            if _looks_like_repo(candidate):
                return candidate
            if (candidate / ".git").exists() and (candidate / "scripts").is_dir():
                return candidate
    return Path(__file__).resolve().parent.parent.parent


def criteria_path(root: Path) -> Path:
    """判据文件路径。

    默认 `schema/criteria.json`(契约 §4 规定的唯一权威);环境变量 `SSDCTL_CRITERIA`
    可指向别的文件(相对路径按仓库根解析),供单元测试与临时判据使用。
    """
    override = os.environ.get(CRITERIA_ENV, "").strip()
    if override:
        candidate = Path(override)
        return candidate if candidate.is_absolute() else (root / candidate)
    return root / CRITERIA_RELPATH


def relative_to_root(path: Path, root: Path) -> str:
    """把绝对路径转成仓库相对路径(统一用 `/` 分隔)。"""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()
