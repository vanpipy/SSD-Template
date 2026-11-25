"""仓内 skill 目录的「宿主可发现性」断言。

背景:支持 skill 目录的宿主(DSH 等)按**会话工作目录所在项目根**(最近含 `.git` 的祖先)
发现 `<projectRoot>/.agents/skills/<name>/SKILL.md`,并用 front matter 的 `name` 注册它。
目录名与 front matter 的 `name` 一致 ⇒ 目录即调用名;两者脱节 ⇒ 宿主按 front matter 注册,
调用方却按目录名找,skill 被静默跳过。因此本模块把「宿主能发现并注册」变成机器断言:

1. 每个 skill 一个目录,目录内有 `SKILL.md`;
2. `SKILL.md` 的 front matter 存在,且有 `name` 与 `description`;
3. front matter 的 `name` == 目录名;
4. `name` 全局唯一;
5. `AGENTS.md` §3.7 的 skill 清单 == 磁盘上的 skill 目录集合(文档与机器不漂移);
6. 仓内不再残留旧目录名(`LEGACY_DIR_NAME`)的**仓内相对路径形态**引用 ——
   2026-11-25 已迁至 `.agents/skills/`。用户主目录形态(`~/` 与 `$HOME/` 前缀)是
   **宿主用户级 skill 安装目标**(Codex 等),仍然有效,迁移不废掉它 ⇒ 不判违规。

红灯证明:
- 把某个 skill 目录改名(如 `to-prd` → `to-prd-x`)⇒ 断言 3 与断言 5 转红;
- 把某个 `SKILL.md` 的 front matter `name` 改成别的 ⇒ 断言 3 转红;
- 在任一被引用文件里写回旧目录名的**仓内相对路径形态** ⇒ 断言 6 转红
  (写回 `~/` / `$HOME/` 前缀形态不转红:那是宿主用户级安装目标,仍合法)。

退出码沿用仓内约定:0 = 通过,1 = 有断言失败,2 = 用法错误。
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / ".agents" / "skills"
AGENTS_MD = REPO_ROOT / "AGENTS.md"

#: 旧 skill 目录名(迁移前用过)。拼装而非字面量,免得本文件自己命中断言 6。
LEGACY_DIR_NAME = "." + "codex" + "/skills"

#: 旧目录名的**仓内相对路径形态**。用户主目录形态(`~/` 与 `$HOME/` 前缀)是宿主
#: 用户级 skill 安装目标(Codex 等),仍然有效 —— 迁移不废掉它,故不判违规。
LEGACY_REPO_PATH_RE = re.compile(r"(?<!~/)(?<!\$HOME/)" + re.escape(LEGACY_DIR_NAME))

#: 扫描「旧路径残留」时跳过的目录(非仓内内容 / 生成物)。
SKIP_DIR_NAMES = {
    ".git",
    ".swarm",
    ".pytest_cache",
    "__pycache__",
    "workspace",
    "symphony-workspaces",
    "node_modules",
}

#: 参与扫描的文本后缀。
TEXT_SUFFIXES = {".md", ".py", ".sh", ".yml", ".yaml", ".json", ".txt", ".toml", ".cfg", ".ini"}

#: skill 目录名的合法形态(与仓内 topic 命名同族:小写字母 / 数字 / 中划线)。
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

#: `AGENTS.md` §3.7 清单表的一行:`| 1 | `to-prd` | ... |`。
AGENTS_ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*`([^`]+)`\s*\|")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, str] | None:
    """解析 YAML front matter(只支持本仓用到的形态)。

    返回 `None` 表示没有 front matter;`description` 允许 `>-` 折行写法。
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end is None:
        return None
    data: dict[str, str] = {}
    key: str | None = None
    for raw in lines[1:end]:
        if raw[:1] not in (" ", "\t") and ":" in raw:
            name, _, value = raw.partition(":")
            key = name.strip()
            data[key] = value.strip()
        elif key is not None:
            data[key] = (data[key] + " " + raw.strip()).strip()
    return data


def frontmatter_value(value: str) -> str:
    """去掉块标量标记(`>-` / `|` / `>`),只留正文。"""
    return value.lstrip(">|-").strip()


def skill_dirs() -> list[str]:
    """磁盘上的 skill 目录名(排序)。"""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(
        entry.name
        for entry in SKILLS_DIR.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    )


def agents_section_names() -> list[str]:
    """`AGENTS.md` §3.7 清单里列出的 skill 名(排序)。"""
    if not AGENTS_MD.is_file():
        return []
    text = read_text(AGENTS_MD)
    start = text.find("### 3.7")
    end = text.find("### 3.8", start + 1)
    if start < 0 or end < 0:
        return []
    names = []
    for line in text[start:end].splitlines():
        match = AGENTS_ROW_RE.match(line.strip())
        if match:
            names.append(match.group(1).strip())
    return sorted(names)


def tracked_text_files() -> list[Path]:
    """仓内文本文件(遍历磁盘,不信 git —— 未提交的新文件也要被扫)。"""
    result: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            result.append(path)
    return result


class SkillLayoutTests(unittest.TestCase):
    """仓内 skill 目录必须处于宿主可发现并注册的形态。"""

    def setUp(self) -> None:
        self.assertTrue(
            SKILLS_DIR.is_dir(),
            f"skill 目录不存在: {SKILLS_DIR}(宿主按项目根发现 `.agents/skills/`)",
        )
        self.dirs = skill_dirs()
        self.assertTrue(self.dirs, f"skill 目录为空: {SKILLS_DIR}")

    # --- 断言 1:每个 skill 目录都有 SKILL.md --------------------------------
    def test_every_skill_dir_has_skill_md(self) -> None:
        missing = [
            name
            for name in self.dirs
            if not (SKILLS_DIR / name / "SKILL.md").is_file()
        ]
        self.assertEqual(
            [],
            missing,
            "这些 skill 目录没有 SKILL.md(宿主按 `<name>/SKILL.md` 发现,缺文件即静默跳过):\n  "
            + "\n  ".join(missing),
        )

    # --- 断言 2:front matter 有 name 与 description ------------------------
    def test_frontmatter_declares_name_and_description(self) -> None:
        problems: list[str] = []
        for name in self.dirs:
            skill_file = SKILLS_DIR / name / "SKILL.md"
            if not skill_file.is_file():
                continue
            data = parse_frontmatter(read_text(skill_file))
            if data is None:
                problems.append(f"{name}/SKILL.md: 没有 front matter(`---` 包裹)")
                continue
            declared = data.get("name", "").strip()
            if not declared:
                problems.append(f"{name}/SKILL.md: front matter 缺 `name`")
            description = frontmatter_value(data.get("description", ""))
            if not description:
                problems.append(f"{name}/SKILL.md: front matter 缺 `description`")
        self.assertEqual([], problems, "\n".join(problems))

    # --- 断言 3:front matter 的 name == 目录名 -----------------------------
    def test_frontmatter_name_matches_directory(self) -> None:
        problems: list[str] = []
        for name in self.dirs:
            skill_file = SKILLS_DIR / name / "SKILL.md"
            if not skill_file.is_file():
                continue
            data = parse_frontmatter(read_text(skill_file))
            if data is None:
                continue
            declared = data.get("name", "").strip()
            if declared and declared != name:
                problems.append(
                    f"{name}/SKILL.md: front matter `name: {declared}` != 目录名 `{name}`"
                    "(宿主按 front matter 注册,调用方按目录名找 ⇒ skill 被跳过)"
                )
        self.assertEqual([], problems, "\n".join(problems))

    # --- 断言 4:name 唯一 + 目录名合法 -------------------------------------
    def test_skill_names_are_unique_and_well_formed(self) -> None:
        seen: dict[str, str] = {}
        duplicates: list[str] = []
        for name in self.dirs:
            skill_file = SKILLS_DIR / name / "SKILL.md"
            if not skill_file.is_file():
                continue
            data = parse_frontmatter(read_text(skill_file))
            declared = (data or {}).get("name", "").strip() or name
            if declared in seen:
                duplicates.append(f"{declared}({seen[declared]} 与 {name})")
            else:
                seen[declared] = name
        self.assertEqual([], duplicates, "front matter `name` 重复:\n  " + "\n".join(duplicates))
        malformed = [name for name in self.dirs if not SKILL_NAME_RE.match(name)]
        self.assertEqual(
            [],
            malformed,
            "skill 目录名不合规(只允许小写字母 / 数字 / 中划线):\n  " + "\n".join(malformed),
        )

    # --- 断言 5:AGENTS.md §3.7 清单 == 磁盘目录集合 ------------------------
    def test_agents_skill_list_matches_disk(self) -> None:
        documented = agents_section_names()
        self.assertTrue(documented, "AGENTS.md §3.7 没有解析到 skill 清单(格式变了?)")
        on_disk = sorted(self.dirs)
        self.assertEqual(
            on_disk,
            documented,
            "AGENTS.md §3.7 的 skill 清单与磁盘目录不一致(新增 skill 要登记,删 skill 要改清单)",
        )

    # --- 断言 6:旧目录名的仓内相对路径形态不得残留 -------------------------
    def test_no_legacy_skill_path_references(self) -> None:
        hits: list[str] = []
        for path in tracked_text_files():
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if LEGACY_REPO_PATH_RE.search(text):
                rel = path.relative_to(REPO_ROOT).as_posix()
                hits.append(rel)
        self.assertEqual(
            [],
            sorted(set(hits)),
            "这些文件仍以仓内相对路径引用旧 skill 目录(已于 2026-11-25 迁至 `.agents/skills/`):\n  "
            + "\n  ".join(sorted(set(hits))),
        )


if __name__ == "__main__":
    unittest.main()
