"""单元测试的公共支撑。

要点:
- 把 `scripts/` 放进 `sys.path`,这样 `import ssdctl` / `from lib import criteria` 可用;
- 搭「临时仓库」:同时含 `scripts/` 与 `schema/`(仓库根的判据);
  **F9(R-1/R-5)后不再预建 `control/`** —— 仓内控制平面已删除,测试仓也不该有它,
  这样「advance 之后 `control/` 仍不存在」才是一条真断言而不是恒真。
- 判据用**测试夹具** `fixtures/criteria.fixture.json`,不碰 `schema/criteria.json`
  —— 后者是契约 §4 的唯一权威,由 schema 侧 lane 交付(见本轮任务书)。
  需要变体判据时用 `make_criteria()` 派生,**不改**共享夹具。
- 跑 CLI 一律用当前解释器(`sys.executable`),避免系统 `python` 桩。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = TESTS_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
FIXTURES_DIR = TESTS_DIR / "fixtures"
ARTIFACTS_DIR = FIXTURES_DIR / "artifacts"
CRITERIA_FIXTURE = FIXTURES_DIR / "criteria.fixture.json"
CLI = SCRIPTS_DIR / "ssdctl.py"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def read_fixture(name: str) -> str:
    """读一个夹具文件的正文。"""
    return (ARTIFACTS_DIR / name).read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> Path:
    """写文件,强制 LF 行尾(仓库 `.gitattributes` 规定 `eol=lf`)。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return path


def make_repo(base: Path, files: dict[str, str] | None = None, criteria: Path | None = None) -> Path:
    """搭一个最小仓库。

    `scripts/` 只为让 `find_repo_root()` 认出仓库根(判据 = 同时含 `scripts/` 与 `schema/`);
    判据文件从夹具复制到 `schema/criteria.json`,这样 CLI 的默认路径就是契约规定的那个。

    F9(R-1):**不建 `control/`** —— 仓内控制平面已整体删除;测试仓也不预建,
    「跑完 advance 之后 `control/` 仍然不存在」才是可判定的断言。
    """
    repo = base / "repo"
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "schema").mkdir(parents=True, exist_ok=True)
    source = criteria if criteria is not None else CRITERIA_FIXTURE
    shutil.copyfile(source, repo / "schema" / "criteria.json")
    for rel, text in (files or {}).items():
        write_text(repo / rel, text)
    return repo


def make_criteria(
    base: Path,
    drop: set[str] | None = None,
    extra: list[dict] | None = None,
) -> Path:
    """派生一份判据文件(可删判据 / 可加判据),落盘返回路径 —— 给 `make_repo(criteria=…)` 用。

    共享夹具 `fixtures/criteria.fixture.json` 被所有用例共用,改它会连累别的用例;
    这里只派生副本。`extra` 里的判据必须符合契约 §4.1 的 12 kind 词表与参数契约。
    """
    payload = json.loads(CRITERIA_FIXTURE.read_text(encoding="utf-8"))
    if drop:
        payload["criteria"] = [
            item for item in payload["criteria"] if str(item.get("id")) not in drop
        ]
    if extra:
        payload["criteria"].extend(extra)
    path = base / "criteria-variant.json"
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def run_cli(repo: Path, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """跑 CLI:当前解释器 + 仓库根作工作目录。

    `env` 里的键会覆盖继承来的环境变量(用来模拟 GBK 控制台等情形)。
    """
    child_env = dict(os.environ)
    child_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        child_env.update(env)
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=child_env,
    )


def control_files(repo: Path) -> list[Path]:
    """控制平面下的任何文件。

    F9(R-1/R-5):`control/` 整体删除 ⇒ 跑完任何命令后这个列表都必须是空的。
    旧模型(证据链 + state.json)下它非空 ⇒ 这条断言能失败。
    """
    directory = repo / "control"
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.rglob("*") if path.is_file())


def sha256_of(path: Path) -> str:
    """文件字节的 sha256 —— 「零改动」断言用。"""
    return hashlib.sha256(path.read_bytes()).hexdigest()
