"""单元测试的公共支撑。

要点:
- 把 `scripts/` 放进 `sys.path`,这样 `import ssdctl` / `from lib import criteria` 可用;
- 搭「临时仓库」:同时含 `scripts/` 与 `schema/`(仓库根的判据),外加 `control/` 控制平面;
- 判据用**测试夹具** `fixtures/criteria.fixture.json`,不碰 `schema/criteria.json`
  —— 后者是契约 §4 的唯一权威,由 schema 侧 lane 交付(见本轮任务书)。
- 跑 CLI 一律用当前解释器(`sys.executable`),避免系统 `python` 桩。
"""

from __future__ import annotations

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
    """
    repo = base / "repo"
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "schema").mkdir(parents=True, exist_ok=True)
    (repo / "control" / "decisions").mkdir(parents=True, exist_ok=True)
    (repo / "control" / "evidence").mkdir(parents=True, exist_ok=True)
    source = criteria if criteria is not None else CRITERIA_FIXTURE
    shutil.copyfile(source, repo / "schema" / "criteria.json")
    for rel, text in (files or {}).items():
        write_text(repo / rel, text)
    return repo


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


def evidence_files(repo: Path) -> list[Path]:
    """控制平面里的证据文件(用于「零写」断言)。"""
    directory = repo / "control" / "evidence"
    if not directory.is_dir():
        return []
    return sorted(path for path in directory.rglob("*.jsonl") if path.is_file())
