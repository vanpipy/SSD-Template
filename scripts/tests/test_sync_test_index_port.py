#!/usr/bin/env python3
"""`scripts/sync-test-index.py` 的端口等价测试。

覆盖三件事:
  1. **逐字节等价**:同一 corpus、同一 `--root` 下,端口与 bash 原件的
     stdout / stderr(归一化后)、退出码、以及**结果文件树**都相同;
  2. **corpus 契约**:语料覆盖每条规则(每条规则至少一个用例;要求失败的规则
     至少一个反例),语料记录的原件指纹与当前原件一致;
  3. **变异自证**:把端口源码里的判定改坏,对应规则的用例必须转红
     (证明这些用例能真的区分对错,不是「怎么都过」的自证)。

集成期原件(`scripts/sync-test-index.sh`)会被删除,依赖原件的用例用
`@unittest.skipUnless` 跳过;不依赖原件的用例(corpus 契约 / 写模式幂等 /
变异自证)始终执行。
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
PORT = REPO / "scripts" / "sync-test-index.py"
ORIGINAL = REPO / "scripts" / "sync-test-index.sh"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sync-test-index-corpus.json"
BASH = r"C:\Program Files\Git\bin\bash.exe"
INDEX_REL = "test_cases/_index.md"

NEEDS_ORIGINAL = "bash 原件已删除(集成期)或 bash 解释器不可用,无法现场重跑原件"

# 归一化用的身份表:两侧的脚本名归到同一个占位符,身份差异不计入判定。
IDENT = {
    "sync-test-index.sh": "{SYNC-idx}",
    "sync-test-index.py": "{SYNC-idx}",
}

# 每个用例的输出( stdout + stderr + 生成的 `test_cases/_index.md` )里必须出现的标记。
CASE_MARKERS = {
    "cli-help": ["用法:", "--check]"],
    "cli-unknown-arg": ["未知参数"],
    "cli-positional-arg": ["不接受位置参数"],
    "cli-root-missing-value": ["--root 需要目录参数"],
    "cli-root-missing-dir": ["--root 目录不存在"],
    "cli-root-equals-form": ["已再生成 (0 行)"],
    "layer-not-enabled": ["测试用例层未启用", "跳过索引同步"],
    "layer-not-enabled-json": ['"skipped":true', '"rows":0'],
    "empty-layer": ["已再生成 (0 行)", "|------|------|"],
    "single-case": ["已再生成 (1 行)", "[alpha.md](2026-01-01/alpha.md)"],
    "single-case-json": ['"rows":1', '"status":"pass"'],
    "multi-dir-multi-topic": ["已再生成 (4 行)", "[gamma.md](2026-02-02/gamma.md)"],
    "smoke-ordering": ["已再生成 (2 行)", "[alpha-smoke.md](2026-01-01/alpha-smoke.md)"],
    "p0-all-p0": ["| 2026-01-01 | alpha | POS | Web | 12 | 12 |"],
    "p0-count": ["| 2026-01-01 | alpha | POS | Web | 20 | 0\n5 |"],
    "p0-absent": ["| 2026-01-01 | alpha | POS | Web | 7 | 0 |"],
    "p0-count-no-digit": ["| 2026-01-01 | alpha | POS | Web | 9 | 0 |"],
    "metadata-missing": ["| 2026-01-01 | alpha |  |  | 12 | 0 |  |"],
    "metadata-empty-subject": ["| 2026-01-01 | alpha | POS |"],
    "key-points-present": ["[key-points](2026-01-01/alpha-key-points.md)"],
    "key-points-absent": ["| — |"],
    "invalid-names-skipped": ["[ok.md](2026-01-01/ok.md)"],
    "check-missing-index": ["_index.md 不存在"],
    "check-drift": ["与文档元信息不一致", "  --- ", "  +++ ", "  @@ "],
    "check-drift-json": ['"exit_code":1', "与文档元信息不一致"],
    "write-overwrites-index": ["已再生成 (1 行)"],
}

# 每个用例的输出里**不该**出现的标记。
CASE_ABSENT_MARKERS = {
    "layer-not-enabled": ["已再生成", "已是最新", "不一致"],
    "empty-layer": ["1 行", "2 行"],
    "check-missing-index": ["--- ", "@@ "],
    "check-drift-json": ["--- ", "@@ ", "  --- "],
    "invalid-names-skipped": ["bad-dir", "BadTopic", "hidden"],
    "key-points-present": ["[alpha-key-points.md]"],
    "layer-not-enabled-json": ['"rows":1'],
}


def canon(data: bytes, root: str = "", posix: str = "") -> bytes:
    """把两侧输出的机器相关部分归一化(根路径 / 调用前缀 / 脚本身份 / diff 时间戳)。"""
    text = data.decode("utf-8", "replace")
    if root:
        text = text.replace(root.replace("\\", "\\\\"), "{ROOT}")
        text = text.replace(root, "{ROOT}")
    if posix:
        text = text.replace(posix, "{ROOT}")
    # diff 头里的时间戳:路径保留,只剥掉制表符之后的部分。
    text = re.sub(r"(?m)^([ \t]*(?:---|\+\+\+) [^\t\n]*)\t[^\n]*$", r"\1", text)
    text = text.replace("bash scripts/", "{RUN} scripts/").replace("python scripts/", "{RUN} scripts/")
    for name, placeholder in IDENT.items():
        text = text.replace(name, placeholder)
    return text.encode("utf-8")


def canon_tree(root: Path) -> list[tuple[str, bytes]]:
    """结果文件树的归一化快照(排除差分时暂存的门禁副本 `scripts/`)。"""
    snapshot: list[tuple[str, bytes]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith("scripts/"):
            continue
        snapshot.append((rel, canon(path.read_bytes(), str(root))))
    return snapshot


def sha1_of(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def materialize(files: dict, root: Path) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="")


def stage_port(root: Path, source: bytes | None = None) -> None:
    """把端口(可以是变异后的源码)放到 `<root>/scripts/` 下,按相对路径调用。"""
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    (scripts / "sync-test-index.py").write_bytes(PORT.read_bytes() if source is None else source)


def stage_original(root: Path) -> None:
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ORIGINAL, scripts / ORIGINAL.name)


def posix_root(root: Path) -> str:
    proc = subprocess.run([BASH, "-c", f'cd "{root}" && pwd'], capture_output=True)
    return proc.stdout.decode("utf-8", "replace").strip()


def child_env() -> dict:
    return {**os.environ, "NO_COLOR": "1", "LC_ALL": "C.UTF-8"}


def run_port(case: dict, source: bytes | None = None) -> tuple[int, bytes, bytes, list]:
    root = Path(tempfile.mkdtemp(prefix="sync-idx-py-"))
    try:
        materialize(case["files"], root)
        stage_port(root, source)
        proc = subprocess.run(
            [sys.executable, "scripts/sync-test-index.py", *case["args"]],
            cwd=str(root),
            capture_output=True,
            env=child_env(),
        )
        posix = posix_root(root)
        return (
            proc.returncode,
            canon(proc.stdout, str(root), posix),
            canon(proc.stderr, str(root), posix),
            canon_tree(root),
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def run_original(case: dict) -> tuple[int, bytes, bytes, list]:
    root = Path(tempfile.mkdtemp(prefix="sync-idx-bash-"))
    try:
        materialize(case["files"], root)
        stage_original(root)
        proc = subprocess.run(
            [BASH, "scripts/sync-test-index.sh", *case["args"]],
            cwd=str(root),
            capture_output=True,
            env=child_env(),
        )
        posix = posix_root(root)
        return (
            proc.returncode,
            canon(proc.stdout, str(root), posix),
            canon(proc.stderr, str(root), posix),
            canon_tree(root),
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def observable(case: dict) -> str:
    """用例的可观测文本 = stdout + stderr + 生成的索引内容(写模式门禁的产物在这里)。"""
    _rc, out, err, tree = run_port(case)
    parts = [out.decode("utf-8", "replace"), err.decode("utf-8", "replace")]
    for rel, data in tree:
        if rel == INDEX_REL:
            parts.append(data.decode("utf-8", "replace"))
    return "\n".join(parts)


# 变异自证:把源码里的判定改坏,对应规则的用例必须转红。
MUTATIONS = {
    "p0-parsing": {
        "anchor": 'p0 = "\\n".join(p0_digits)',
        "replacement": 'p0 = p0_digits[-1] if p0_digits else "0"',
        "case": "p0-count",
        "rule": "p0-count",
        "why": "P0 解析:原件的管道会把 'P0' 里的 0 也算进数字 run,改掉后 P0 单元格内容变了",
    },
    "sort-key": {
        "anchor": 'key = f"{date_dir}/{topic}/{is_smoke}"',
        "replacement": 'key = f"{topic}/{date_dir}/{is_smoke}"',
        "case": "multi-dir-multi-topic",
        "rule": "sort-key",
        "why": "排序 key 必须是 ${date_dir}/${topic}/${is_smoke}",
    },
    "key-points": {
        "anchor": 'if base.endswith("-key-points"):',
        "replacement": 'if False:',
        "case": "key-points-present",
        "rule": "key-points-not-registered",
        "why": "*-key-points.md 不单独登记成行",
    },
    "diff-output": {
        "anchor": '_emit("  " + line + "\\n")',
        "replacement": '_emit(" " + line + "\\n")',
        "case": "check-drift",
        "rule": "diff-output",
        "why": "diff -u 的每行前缀两个空格",
    },
}


class SyncTestIndexPortTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_fixture()
        cls.cases = {case["name"]: case for case in cls.fixture["cases"]}
        cls.rules = cls.fixture["rules"]

    # --- 1. 逐字节等价(需要原件) ---

    @unittest.skipUnless(BASH and ORIGINAL.exists(), NEEDS_ORIGINAL)
    def test_port_matches_bash_original_byte_for_byte(self) -> None:
        if not ORIGINAL.exists():
            self.skipTest("原件在测试运行期间被删除(集成期),跳过现场重跑")
        for name, case in self.cases.items():
            with self.subTest(case=name):
                rc_b, out_b, err_b, tree_b = run_original(case)
                rc_p, out_p, err_p, tree_p = run_port(case)
                self.assertEqual(rc_b, rc_p, f"退出码不同: bash={rc_b} py={rc_p}")
                self.assertEqual(out_b, out_p, "stdout 归一化后不同")
                self.assertEqual(err_b, err_p, "stderr 归一化后不同")
                self.assertEqual(tree_b, tree_p, "结果文件树不同")

    # --- 2. corpus 契约(不依赖原件) ---

    def test_port_matches_recorded_golden(self) -> None:
        for name, case in self.cases.items():
            with self.subTest(case=name):
                rc, out, err, _tree = run_port(case)
                self.assertEqual(rc, case["expect_exit"], f"退出码与语料不符: {name}")
                self.assertEqual(
                    canon(out), canon(case["expect_stdout"].encode("utf-8")), f"stdout 与语料不符: {name}"
                )
                self.assertEqual(
                    canon(err), canon(case["expect_stderr"].encode("utf-8")), f"stderr 与语料不符: {name}"
                )

    def test_golden_records_the_original_fingerprint(self) -> None:
        digest = self.fixture.get("source_sha1", "")
        self.assertRegex(digest, r"^[0-9a-f]{40}$", "语料必须记录原件的 SHA-1")
        self.assertEqual(self.fixture.get("source_gate"), "scripts/sync-test-index.sh")
        self.assertEqual(self.fixture.get("gate"), "scripts/sync-test-index.py")
        self.assertEqual(self.fixture.get("mode"), "tree")

    @unittest.skipUnless(ORIGINAL.exists(), NEEDS_ORIGINAL)
    def test_golden_provenance_matches_current_original(self) -> None:
        if not ORIGINAL.exists():
            self.skipTest("原件在测试运行期间被删除(集成期),跳过指纹核对")
        self.assertEqual(
            self.fixture["source_sha1"],
            sha1_of(ORIGINAL),
            "原件在语料采集之后被改过,语料的 golden 已失效",
        )

    def test_corpus_has_at_least_fourteen_cases(self) -> None:
        self.assertGreaterEqual(len(self.cases), 14)

    def test_every_rule_has_a_firing_case(self) -> None:
        for rule, spec in self.rules.items():
            with self.subTest(rule=rule):
                related = [c for c in self.fixture["cases"] if rule in c["rules"]]
                self.assertTrue(related, f"规则 {rule} 没有任何用例")
                if spec.get("require_fail_case"):
                    failing = [c for c in related if c["expect_exit"] != 0]
                    self.assertTrue(failing, f"规则 {rule} 没有反例(要求一个非 0 退出的用例)")

    def test_rule_markers_appear_in_their_cases(self) -> None:
        for case_name, markers in CASE_MARKERS.items():
            with self.subTest(case=case_name):
                self.assertIn(case_name, self.cases, f"语料里没有用例 {case_name}")
                text = observable(self.cases[case_name])
                for marker in markers:
                    self.assertIn(marker, text, f"用例 {case_name} 的可观测输出里缺少标记 {marker!r}")

    def test_absent_markers_never_appear(self) -> None:
        for case_name, markers in CASE_ABSENT_MARKERS.items():
            with self.subTest(case=case_name):
                self.assertIn(case_name, self.cases, f"语料里没有用例 {case_name}")
                text = observable(self.cases[case_name])
                for marker in markers:
                    self.assertNotIn(marker, text, f"用例 {case_name} 的可观测输出里不该出现 {marker!r}")

    # --- 3. 写模式行为(不依赖原件) ---

    def test_write_mode_only_touches_the_index_file(self) -> None:
        case = self.cases["multi-dir-multi-topic"]
        root = Path(tempfile.mkdtemp(prefix="sync-idx-tree-"))
        try:
            materialize(case["files"], root)
            stage_port(root)
            proc = subprocess.run(
                [sys.executable, "scripts/sync-test-index.py", *case["args"]],
                cwd=str(root),
                capture_output=True,
                env=child_env(),
            )
            self.assertEqual(proc.returncode, 0)
            produced = sorted(
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
                if path.is_file() and not path.relative_to(root).as_posix().startswith("scripts/")
            )
            expected = sorted(list(case["files"]) + [INDEX_REL])
            self.assertEqual(produced, expected, "写模式只应新增 test_cases/_index.md 一个文件")
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_write_mode_is_idempotent(self) -> None:
        case = self.cases["multi-dir-multi-topic"]
        root = Path(tempfile.mkdtemp(prefix="sync-idx-idem-"))
        try:
            materialize(case["files"], root)
            stage_port(root)
            runs = []
            for _ in range(2):
                proc = subprocess.run(
                    [sys.executable, "scripts/sync-test-index.py", *case["args"]],
                    cwd=str(root),
                    capture_output=True,
                    env=child_env(),
                )
                runs.append((proc.returncode, proc.stdout, canon_tree(root)))
            self.assertEqual(runs[0][0], runs[1][0], "两次运行的退出码不同")
            self.assertEqual(runs[0][2], runs[1][2], "第二次运行后结果文件树变了(不幂等)")
            self.assertIn("已再生成", runs[0][1].decode("utf-8", "replace"))
            self.assertIn("已是最新", runs[1][1].decode("utf-8", "replace"))
        finally:
            shutil.rmtree(root, ignore_errors=True)

    # --- 4. 身份与卫生 ---

    def test_new_implementation_uses_the_new_identity(self) -> None:
        source = PORT.read_text(encoding="utf-8")
        self.assertIn('"script":"sync-test-index.py"', source)
        self.assertNotIn('"script":"sync-test-index.sh"', source)
        self.assertIn("由 scripts/sync-test-index.py 自动生成", source)
        self.assertNotIn("由 scripts/sync-test-index.sh 自动生成", source)
        self.assertIn("scripts/sync-test-index.py", source)

    def test_port_has_no_orchestration_paths(self) -> None:
        source = PORT.read_text(encoding="utf-8")
        self.assertNotIn(".swarm/", source, "端口里不得出现指向编排目录的路径")

    def test_port_does_not_fork(self) -> None:
        source = PORT.read_text(encoding="utf-8")
        for forbidden in ("subprocess", "os.system", "os.popen"):
            self.assertNotIn(forbidden, source, f"端口不得调用 {forbidden}(必须是单进程)")

    # --- 5. 变异自证 ---

    def test_mutation_anchors_are_unique(self) -> None:
        source = PORT.read_text(encoding="utf-8")
        for name, mutation in MUTATIONS.items():
            with self.subTest(mutation=name):
                self.assertEqual(
                    source.count(mutation["anchor"]),
                    1,
                    f"变异锚点在源码里必须唯一: {mutation['anchor']!r}",
                )

    def _assert_mutation_flips_case(self, mutation_name: str) -> None:
        mutation = MUTATIONS[mutation_name]
        case = self.cases[mutation["case"]]
        source = PORT.read_text(encoding="utf-8")
        mutated = source.replace(mutation["anchor"], mutation["replacement"], 1)
        self.assertNotEqual(mutated, source, "变异没有生效(锚点没换掉)")
        rc_a, out_a, err_a, tree_a = run_port(case)
        rc_b, out_b, err_b, tree_b = run_port(case, source=mutated.encode("utf-8"))
        changed = (rc_a, out_a, err_a, tree_a) != (rc_b, out_b, err_b, tree_b)
        self.assertTrue(
            changed,
            f"变异 {mutation_name} 之后用例 {mutation['case']} 没有转红 —— "
            f"该用例无法区分对错(规则 {mutation['rule']}: {mutation['why']})",
        )

    def test_mutation_breaks_p0_parsing_rule(self) -> None:
        self._assert_mutation_flips_case("p0-parsing")

    def test_mutation_breaks_sort_key_rule(self) -> None:
        self._assert_mutation_flips_case("sort-key")

    def test_mutation_breaks_key_points_rule(self) -> None:
        self._assert_mutation_flips_case("key-points")

    def test_mutation_breaks_diff_output_rule(self) -> None:
        self._assert_mutation_flips_case("diff-output")


if __name__ == "__main__":
    unittest.main()
