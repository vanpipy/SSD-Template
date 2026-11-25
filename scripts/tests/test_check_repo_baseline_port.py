"""check-repo-baseline 门禁的 Python 端口 vs bash 原件 —— 等价性测试。

契约(端口等价口径 R-1:归一化后逐字节相同 + 同退出码):

* 等价判据 = **归一化后逐字节相同 + 同退出码**,stdout 与 stderr 都要比;
* 归一化规则(对两侧同时施加,本文件下方给出同规则实现):
  - 门禁 basename:`check-repo-baseline.sh` / `check-repo-baseline.py` → `{GATE-base}`;
  - 调用前缀:`bash scripts/` 与 `python scripts/` → `{RUN} scripts/`;
  - 临时根路径:Windows 形态、JSON 转义后的 Windows 形态、POSIX 形态 → `{ROOT}`;
  - git SHA(随提交内容与时间变化)→ `{SHA0}` / `{HEAD_SHA}` / `{HEAD_SHA7}`;
  - 分支名 → `{BRANCH}`;基线复核天数 → `{AGE}`;
* 归一化之外的任何一个字节不同即判失败;
* 新实现必须用新身份(`check-repo-baseline.py`)—— 这是**唯一**允许的差异。

本文件同时承担两件事:

1. **差分**:现场重跑 bash 原件与 Python 端口,逐字节比较;
2. **corpus 契约**:仓内 golden(`fixtures/baseline-corpus.json`)由 bash 原件采集,
   本测试验证端口输出与 golden 一致、golden 的 provenance(原件 SHA-1)未漂移、
   每条规则都有触发用例、标记确实出现在对应输出里、且变异自证(反例真的能红)。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PORT = REPO / "scripts" / "check-repo-baseline.py"
ORIGINAL = REPO / "scripts" / "check-repo-baseline.sh"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "baseline-corpus.json"
BASH = r"C:\Program Files\Git\bin\bash.exe"

#: 基线复核天数的归一化(天数随「今天」漂移 ⇒ 不能进 golden)。
AGE_RE = re.compile(r"(基线已 )[0-9]+( 天未复核)")

#: 集成阶段删除 bash 原件后,需要原件在场的用例必须 **skip**,不能 fail/error;
#: 而只依赖仓内 corpus 的用例必须继续跑 —— 原件删除后 corpus 是唯一的行为真源。
NEEDS_ORIGINAL = "bash 原件已删除(集成阶段)或 bash 解释器不可用,无法现场重跑原件"


def canon(data: bytes, root: Path | None = None, posix_root: str = "",
          subs: dict | None = None) -> bytes:
    """R-1 的归一化:两侧同时施加,归一化之外必须逐字节相同。"""
    text = data.decode("utf-8", "replace")
    if root is not None:
        windows = str(root)
        real = os.path.realpath(str(root))
        for variant in (windows, windows.replace("\\", "\\\\"), real, real.replace("\\", "\\\\")):
            if variant:
                text = text.replace(variant, "{ROOT}")
    if posix_root:
        text = text.replace(posix_root, "{ROOT}")
    text = text.replace("bash scripts/", "{RUN} scripts/").replace("python scripts/", "{RUN} scripts/")
    text = text.replace("check-repo-baseline.sh", "{GATE-base}")
    text = text.replace("check-repo-baseline.py", "{GATE-base}")
    if subs:
        for key in sorted(subs, key=lambda k: -len(subs[k] or "")):
            value = subs[key]
            if not value:
                continue
            text = text.replace(value, "{%s}" % key)
        head = subs.get("HEAD_SHA", "")
        if len(head) >= 7:
            text = text.replace(head[:7], "{HEAD_SHA7}")
        branch = subs.get("BRANCH", "")
        if branch:
            text = text.replace(branch, "{BRANCH}")
    text = AGE_RE.sub(r"\1{AGE}\2", text)
    return text.encode("utf-8")


def sha1_of(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def git_env() -> dict:
    """固定身份与时间 ⇒ 同样的文件树得到同样的 SHA(golden 才可复现)。"""
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "Port Fixture",
            "GIT_AUTHOR_EMAIL": "port@example.invalid",
            "GIT_COMMITTER_NAME": "Port Fixture",
            "GIT_COMMITTER_EMAIL": "port@example.invalid",
            "GIT_AUTHOR_DATE": "2020-01-02T03:04:05+00:00",
            "GIT_COMMITTER_DATE": "2020-01-02T03:04:05+00:00",
        }
    )
    return env


def build_git(root: Path, spec: dict) -> dict:
    """按 corpus 的 `git` 段建一个真 git 仓,返回 SHA/分支占位符表。"""
    repo = root / spec.get("repo_dir", "localrepo")
    repo.mkdir(parents=True, exist_ok=True)

    def run(args: list[str]):
        return subprocess.run(
            ["git", *args], cwd=str(repo), env=git_env(), capture_output=True, text=True
        )

    run(["init", "-q"])
    run(["symbolic-ref", "HEAD", "refs/heads/" + spec.get("branch", "main")])
    run(["config", "user.name", "Port Fixture"])
    run(["config", "user.email", "port@example.invalid"])
    shas: list[str] = []
    for commit in spec.get("commits", []):
        for rel, content in commit.get("files", {}).items():
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8", newline="")
        run(["add", "-A"])
        run(["commit", "-q", "-m", commit.get("message", "c")])
        shas.append(run(["rev-parse", "HEAD"]).stdout.strip())
    return {
        "SHA0": shas[0] if shas else "",
        "SHA1": shas[1] if len(shas) > 1 else (shas[0] if shas else ""),
        "HEAD_SHA": shas[-1] if shas else "",
        "BRANCH": spec.get("branch", "main"),
    }


def materialize(case: dict, root: Path) -> dict:
    """把用例的文件树铺到临时仓根;返回占位符表(SHA/分支)。"""
    subs: dict = {}
    if case.get("git"):
        subs = build_git(root, case["git"])
    for rel, content in case.get("files", {}).items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        text = content
        for key, value in subs.items():
            text = text.replace("{%s}" % key, value)
        path.write_text(text, encoding="utf-8", newline="")
    return subs


def stage_port(root: Path, source: str | None = None) -> None:
    """把端口放进临时仓的 `scripts/`,以便**相对路径**调用。

    相对路径是刻意的:bash 原件的错误前缀是 `$0`,端口的是 `sys.argv[0]`;
    两侧都用 `scripts/<name>` 调用,前缀才落在同一形态上(归一化后 `{GATE-base}`)。
    端口的默认根 = 脚本所在目录的父目录 ⇒ 放在 `<root>/scripts/` 即 `<root>`。
    """
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    target = scripts / "check-repo-baseline.py"
    if source is None:
        shutil.copyfile(PORT, target)
    else:
        target.write_text(source, encoding="utf-8", newline="\n")


def posix_root(root: Path) -> str:
    """问 bash 要临时根的 POSIX 形态(Git Bash 下是 `/c/Users/...`)。"""
    if not os.path.exists(BASH):
        return ""
    try:
        proc = subprocess.run([BASH, "-c", f'cd "{root}" && pwd'], capture_output=True)
    except OSError:
        return ""
    return proc.stdout.decode("utf-8", "replace").strip()


def run_port(root: Path, args: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [sys.executable, "scripts/check-repo-baseline.py", *args],
        cwd=str(root),
        capture_output=True,
    )
    return proc.returncode, proc.stdout, proc.stderr


def run_bash(root: Path, args: list[str]) -> tuple[int, bytes, bytes]:
    proc = subprocess.run(
        [BASH, "scripts/check-repo-baseline.sh", *args], cwd=str(root), capture_output=True
    )
    return proc.returncode, proc.stdout, proc.stderr


class CheckRepoBaselinePortTest(unittest.TestCase):
    """端口与 bash 原件的差分 + corpus 契约。"""

    maxDiff = None

    # ---------- 差分 ----------

    @unittest.skipUnless(
        os.path.exists(BASH) and ORIGINAL.exists(), NEEDS_ORIGINAL
    )
    def test_port_matches_bash_original_byte_for_byte(self) -> None:
        """R-1:每个用例的 (exit, stdout, stderr) 归一化后逐字节相同。

        需要 bash 原件在场:集成阶段删除原件后本用例 skip,
        而不是 fail —— 届时仓内 corpus 是唯一的行为真源。
        """
        data = load_fixture()
        self.assertGreaterEqual(len(data["cases"]), 14)
        for case in data["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    subs = materialize(case, root)
                    stage_port(root)
                    shutil.copyfile(ORIGINAL, root / "scripts" / "check-repo-baseline.sh")
                    rc_b, out_b, err_b = run_bash(root, case["args"])
                    rc_p, out_p, err_p = run_port(root, case["args"])
                    posix = posix_root(root)
                    self.assertEqual(rc_b, rc_p, "退出码不一致")
                    self.assertEqual(
                        canon(out_b, root, posix, subs),
                        canon(out_p, root, posix, subs),
                        "stdout 归一化后不一致",
                    )
                    self.assertEqual(
                        canon(err_b, root, posix, subs),
                        canon(err_p, root, posix, subs),
                        "stderr 归一化后不一致",
                    )

    def test_port_matches_recorded_golden(self) -> None:
        """端口输出与仓内 golden(采集自 bash 原件)一致。"""
        data = load_fixture()
        self.assertGreaterEqual(len(data["cases"]), 14)
        for case in data["cases"]:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    subs = materialize(case, root)
                    stage_port(root)
                    rc_p, out_p, err_p = run_port(root, case["args"])
                    posix = posix_root(root)
                    self.assertEqual(rc_p, case["expect_exit"], "退出码与 golden 不一致")
                    self.assertEqual(
                        canon(out_p, root, posix, subs),
                        canon(case["expect_stdout"].encode("utf-8")),
                        "stdout 与 golden 不一致",
                    )
                    self.assertEqual(
                        canon(err_p, root, posix, subs),
                        canon(case.get("expect_stderr", "").encode("utf-8")),
                        "stderr 与 golden 不一致",
                    )

    def test_golden_records_the_original_fingerprint(self) -> None:
        """corpus 必须保留原件指纹与身份字段(原件被删后也要成立)。"""
        data = load_fixture()
        self.assertEqual(data["source_gate"], "scripts/check-repo-baseline.sh")
        self.assertEqual(data["gate"], "scripts/check-repo-baseline.py")
        self.assertTrue(
            data["source_sha1"], "corpus 必须保留 source_sha1(采集时的原件指纹)"
        )

    @unittest.skipUnless(ORIGINAL.exists(), NEEDS_ORIGINAL)
    def test_golden_provenance_matches_current_original(self) -> None:
        """golden 记录的 SHA-1 必须等于当前 bash 原件的 SHA-1(原件被删后跳过)。"""
        data = load_fixture()
        self.assertEqual(data["source_sha1"], sha1_of(ORIGINAL))

    # ---------- corpus 契约 ----------

    def test_every_rule_has_a_firing_case(self) -> None:
        """每条规则至少有一个触发用例。"""
        data = load_fixture()
        used: set[str] = set()
        for case in data["cases"]:
            used.update(case.get("rules", []))
        missing = sorted(set(data["rules"]) - used)
        self.assertEqual(missing, [], f"这些规则没有触发用例: {missing}")
        unknown = sorted(used - set(data["rules"]))
        self.assertEqual(unknown, [], f"用例引用了规则表里没有的规则: {unknown}")

    def test_rule_markers_appear_in_their_cases(self) -> None:
        """规则标记必须真的出现在**至少一个**触发用例的输出里(否则映射表就是假的)。

        口径说明:标记按**规则**判定,不按「每个携带该规则的用例」判定 ——
        有些规则是环境性的(如「基线不适用」只在声明了不适用的用例里出现)。
        """
        data = load_fixture()
        for rule, marker in data["rules"].items():
            cases = [c for c in data["cases"] if rule in c.get("rules", [])]
            self.assertTrue(cases, f"规则 {rule} 没有触发用例")
            hits = []
            for case in cases:
                haystack = (case["expect_stdout"] + case.get("expect_stderr", ""))
                if marker in haystack:
                    hits.append(case["name"])
            self.assertTrue(
                hits,
                f"规则 {rule} 的标记 {marker!r} 未出现在任何触发用例的输出里",
            )

    def test_error_markers_absent_from_passing_cases(self) -> None:
        """通过用例的输出里不得出现任何错误措辞(防止「规则其实没生效」)。"""
        data = load_fixture()
        error_markers = [
            "缺少 `## 实现基线` 段",
            "既无表格行也无「不适用」声明",
            "没有有效表格行",
            "缺分支或 SHA",
            "在本地不存在",
            "本仓没有任何规格产物",
            "目录不存在",
            "TARGET 不存在",
            "未知参数",
        ]
        for case in data["cases"]:
            if case["expect_exit"] != 0:
                continue
            with self.subTest(case=case["name"]):
                haystack = case["expect_stdout"] + case.get("expect_stderr", "")
                for marker in error_markers:
                    self.assertNotIn(
                        marker, haystack, f"通过用例里出现了错误措辞 {marker!r}"
                    )

    def test_new_implementation_uses_the_new_identity(self) -> None:
        """新实现必须用 `check-repo-baseline.py` 身份,不得让用户看到将被删除的 .sh。"""
        source = PORT.read_text(encoding="utf-8")
        self.assertIn('"script":"check-repo-baseline.py"', source)
        self.assertNotIn('"script":"check-repo-baseline.sh"', source)
        self.assertNotIn("scripts/check-md-schema.sh", source)

    # ---------- 变异自证 ----------

    def _mutated_source(self, anchor: str, old: str, new: str) -> str:
        source = PORT.read_text(encoding="utf-8")
        index = source.index(anchor)
        head, tail = source[:index], source[index:]
        self.assertIn(old, tail, f"锚点 {anchor!r} 之后找不到 {old!r}")
        return head + tail.replace(old, new, 1)

    def _run_source(self, case: dict, source: str) -> tuple[int, bytes, bytes]:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            materialize(case, root)
            stage_port(root, source)
            rc, out, err = run_port(root, case["args"])
            return rc, canon(out, root), canon(err, root)

    def _assert_mutation_flips_case(
        self, anchor: str, old: str, new: str, case_name: str
    ) -> None:
        data = load_fixture()
        case = next(c for c in data["cases"] if c["name"] == case_name)
        golden = (
            case["expect_exit"],
            canon(case["expect_stdout"].encode("utf-8")),
            canon(case.get("expect_stderr", "").encode("utf-8")),
        )
        mutated = self._mutated_source(anchor, old, new)
        rc, out, err = self._run_source(case, mutated)
        self.assertNotEqual(
            (rc, out, err),
            golden,
            f"变异 {old!r} → {new!r} 后,{case_name} 的结果没有变化 ⇒ 该反例不会红",
        )

    def test_mutation_breaks_missing_baseline_section_rule(self) -> None:
        """把「缺少 ## 实现基线 段」从错误降级为提示,反例必须转红。"""
        self._assert_mutation_flips_case(
            'reporter.err("%s — 缺少 `## 实现基线` 段',
            'reporter.err("%s — 缺少 `## 实现基线` 段',
            'reporter.note("%s — 缺少 `## 实现基线` 段',
            "td-missing-baseline-section",
        )

    def test_mutation_breaks_sha_existence_rule(self) -> None:
        """把 `git cat-file -e` 的失败分支改成恒不触发,SHA 不存在的反例必须转红。"""
        self._assert_mutation_flips_case(
            'rc, _out, _err = _git(path, "cat-file", "-e", "%s^{commit}" % sha)',
            "if rc != 0:",
            "if False:",
            "row-sha-not-found",
        )

    def test_mutation_breaks_stage_rejection_rule(self) -> None:
        """把 `--stage` 的拒绝改成放行,反例必须转红。"""
        self._assert_mutation_flips_case(
            'elif arg == "--stage" or arg.startswith("--stage="):',
            "return EXIT_USAGE",
            "return EXIT_OK",
            "stage-flag",
        )


if __name__ == "__main__":
    unittest.main()
