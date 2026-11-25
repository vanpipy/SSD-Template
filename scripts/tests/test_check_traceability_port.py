# -*- coding: utf-8 -*-
"""check-traceability 门禁的 Python 端口 vs bash 原件 —— 等价性测试。

契约：端口等价口径 R-1(归一化后逐字节相同 + 同退出码)

R-1(等价判据)：同一 corpus、同一 `--root` 下，端口与 bash 原件的
stdout / stderr 归一化后逐字节相同、退出码相同。归一化三类：
  1. 门禁 basename（`check-*.sh` 与 `check-*.py` 一律归一为 `{GATE}`，
     md-schema 为 `{GATE-md}`）；
  2. 调用前缀（`bash scripts/` 与 `python scripts/` → `{RUN} scripts/`）；
  3. 临时根路径（Windows 形态与 POSIX 形态 `/tmp/...` → `{ROOT}`）。
归一化之外任何一个字节不同即判失败。新实现必须用新身份
`check-traceability.py`（JSON `script` 字段、用法文本、错误前缀），
不得让用户看到指向已删除脚本的用法文本。

本文件同时承担两件事：
  1. 差分：现场重跑 bash 原件与 Python 端口，逐字节比较
     （原件被集成阶段删除后自动 skip —— 判据是「脚本原件是否存在」，
     不是「bash 解释器是否存在」）；
  2. corpus 契约：仓内 golden（`fixtures/traceability-corpus.json`）
     由 bash 原件采集，本测试验证端口输出与 golden 一致、golden 的
     provenance（原件 SHA-1）未漂移、每条规则都有触发用例、标记确实
     出现在对应输出里，且变异自证（改坏判定后对应反例必须转红）。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PORT = REPO / "scripts" / "check-traceability.py"
ORIGINAL = REPO / "scripts" / "check-traceability.sh"
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "traceability-corpus.json"
BASH = r"C:\Program Files\Git\bin\bash.exe"

IDENT = [
    ("check-naming.sh", "{GATE}"),
    ("check-naming.py", "{GATE}"),
    ("check-md-schema.sh", "{GATE-md}"),
    ("check-md-schema.py", "{GATE-md}"),
    ("check-traceability.sh", "{GATE-tr}"),
    ("check-traceability.py", "{GATE-tr}"),
]

NEEDS_ORIGINAL = ("bash 原件已删除(R-4 集成阶段)或 bash 解释器不可用，"
                   "无法现场重跑原件")

# 变异自证锚点：每个元组 = (锚点串, 改坏后的串, 目标用例名, 说明)
MUTATIONS = [
    (
        "LEDGER_ID_RE = r'^(PRD|TECH|TEST|PLAN)-[0-9]{8}-[0-9]{2}$'",
        "LEDGER_ID_RE = r'^(PRD|TECH|TEST|PLAN)-[0-9]{4}-[0-9]{2}$'",
        "t6-ledger-bad-id",
        "台账 ID 格式放宽 → 非法 ID 不再报错",
    ),
    (
        "REL_TYPE_RE = r'^(supersede|inherit|depend|shared|conflict|relate|split-from|merge-into)$'",
        "REL_TYPE_RE = r'^(supersedeX|inherit|depend|shared|conflict|relate|split-from|merge-into)$'",
        "t8-supersede-not-deprecated",
        "关系类型枚举去掉 supersede → supersede 一致性核对失效",
    ),
    (
        "r'*\\*\\*状态\\*\\*'",
        "r'*\\*\\*状态值\\*\\*'",
        "t12-prd-deprecated",
        "状态行字段名被改坏 → Deprecated 父级识别不到，级联校验失效",
    ),
    (
        "+\\|$'",
        "+\\|X$'",
        "t1-scenario-file-short",
        "场景映射表行正则被改坏 → 映射行数统计为 0",
    ),
    (
        "r'\\*\\*参考 Test Cases\\*\\*'",
        "r'\\*\\*参考 Test Case\\*\\*'",
        "t11-tc-ref-missing",
        "参考 Test Cases 行匹配被改坏 → T11 引用校验失效",
    ),
]


def canon(data, root=None, posix_root=""):
    """按 R-1 的三类归一化规则处理一段输出。"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    text = data.decode("utf-8", "replace")
    if root is not None:
        root_text = str(root)
        text = text.replace(root_text, "{ROOT}")
        text = text.replace(root_text.replace("\\", "\\\\"), "{ROOT}")
    if posix_root:
        text = text.replace(posix_root, "{ROOT}")
    text = text.replace("bash scripts/", "{RUN} scripts/")
    text = text.replace("python scripts/", "{RUN} scripts/")
    for old, new in IDENT:
        text = text.replace(old, new)
    return text


def sha1_of(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def materialize(case, root):
    for rel, content in case.get("files", {}).items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)


def stage_port(root, source=None):
    """把端口源码放进 <root>/scripts/（相对路径调用，与 golden 采集同形态）。"""
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    payload = source if source is not None else PORT.read_text(encoding="utf-8")
    with open(scripts / "check-traceability.py", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(payload)


def stage_gates(root):
    """把 bash 原件与端口都放进 <root>/scripts/。

    相对路径是刻意的：bash 原件的错误前缀是 `$0`，端口的是
    `sys.argv[0]`；两侧都用 `scripts/<name>` 调用，前缀才落在同一形态上
    （归一化后 `{GATE-tr}`）。
    """
    scripts = root / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)
    if ORIGINAL.exists():
        shutil.copy2(ORIGINAL, scripts / "check-traceability.sh")
    shutil.copy2(PORT, scripts / "check-traceability.py")


def posix_root(root):
    if not os.path.exists(BASH):
        return ""
    proc = subprocess.run([BASH, "-c", 'cd "%s" && pwd' % root], capture_output=True)
    return proc.stdout.decode("utf-8", "replace").strip()


def _run(cmd, root):
    proc = subprocess.run(cmd, cwd=str(root), capture_output=True)
    return (proc.returncode,
            proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"))


def run_bash(root, args):
    return _run([BASH, "scripts/check-traceability.sh"] + list(args), root)


def run_port(root, args):
    return _run([sys.executable, "scripts/check-traceability.py"] + list(args), root)


_PORT_CACHE = {}


def port_output(case):
    """跑一次端口并缓存归一化后的结果。

    同一用例会被多个断言引用（golden 比对 / 标记出现 / 标记缺席 /
    通过用例不含错误措辞），缓存一次即可把端口调用数压到用例数。
    """
    name = case["name"]
    if name in _PORT_CACHE:
        return _PORT_CACHE[name]
    with tempfile.TemporaryDirectory(prefix="trace-port-run-") as tmp:
        root = Path(tmp)
        materialize(case, root)
        stage_port(root)
        posix = posix_root(root)
        rc, out, err = run_port(root, case.get("args", []))
    _PORT_CACHE[name] = (rc, canon(out, root, posix), canon(err, root, posix))
    return _PORT_CACHE[name]


class CheckTraceabilityPortTest(unittest.TestCase):
    maxDiff = None

    # --- 差分：现场重跑原件（原件删除后 skip）--------------------------
    @unittest.skipUnless(os.path.exists(BASH) and ORIGINAL.exists(), NEEDS_ORIGINAL)
    def test_port_matches_bash_original_byte_for_byte(self):
        data = load_fixture()
        cases = data["cases"]
        self.assertGreaterEqual(len(cases), 40)
        for case in cases:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory(prefix="trace-port-diff-") as tmp:
                    root = Path(tmp)
                    materialize(case, root)
                    stage_gates(root)
                    posix = posix_root(root)
                    args = case.get("args", [])
                    rc_b, out_b, err_b = run_bash(root, args)
                    rc_p, out_p, err_p = run_port(root, args)
                    self.assertEqual(rc_b, rc_p)
                    self.assertEqual(canon(out_b, root, posix), canon(out_p, root, posix))
                    self.assertEqual(canon(err_b, root, posix), canon(err_p, root, posix))

    # --- corpus 契约：原件删除后仍必须成立（唯一行为真源）---------------
    def test_port_matches_recorded_golden(self):
        data = load_fixture()
        for case in data["cases"]:
            with self.subTest(case=case["name"]):
                rc_p, out_p, err_p = port_output(case)
                self.assertEqual(rc_p, case["expect_exit"])
                self.assertEqual(
                    out_p,
                    canon(case["expect_stdout"].encode("utf-8")),
                )
                self.assertEqual(
                    err_p,
                    canon(case.get("expect_stderr", "").encode("utf-8")),
                )

    def test_golden_records_the_original_fingerprint(self):
        data = load_fixture()
        self.assertEqual(data["source_gate"], "scripts/check-traceability.sh")
        self.assertEqual(data["gate"], "scripts/check-traceability.py")
        self.assertTrue(data["source_sha1"])
        self.assertEqual(data["root_placeholder"], "{ROOT}")
        self.assertIn("{ROOT}", data["normalization"])

    @unittest.skipUnless(ORIGINAL.exists(), NEEDS_ORIGINAL)
    def test_golden_provenance_matches_current_original(self):
        data = load_fixture()
        self.assertEqual(data["source_sha1"], sha1_of(ORIGINAL))

    # --- 规则覆盖 ---------------------------------------------------------
    def test_every_rule_has_a_firing_case(self):
        data = load_fixture()
        declared = set(data["rules"])
        used = set()
        for case in data["cases"]:
            used.update(case.get("rules", []))
        self.assertEqual(used - declared, set(), "用例引用了未登记的规则")
        self.assertEqual(declared - used, set(), "登记的规则没有任何用例触发")

    def test_rule_markers_appear_in_their_cases(self):
        data = load_fixture()
        for case in data["cases"]:
            markers = case.get("expect_contains", [])
            if not markers:
                continue
            with self.subTest(case=case["name"]):
                _, out_p, err_p = port_output(case)
                haystack = out_p + err_p
                for marker in markers:
                    self.assertIn(marker, haystack)

    def test_absent_markers_never_appear(self):
        data = load_fixture()
        for case in data["cases"]:
            markers = case.get("expect_absent", [])
            if not markers:
                continue
            with self.subTest(case=case["name"]):
                _, out_p, err_p = port_output(case)
                haystack = out_p + err_p
                for marker in markers:
                    self.assertNotIn(marker, haystack)

    def test_fail_rules_have_nonzero_exit_cases(self):
        data = load_fixture()
        for rule, meta in data["rules"].items():
            if not meta.get("require_fail_case"):
                continue
            failing = [c for c in data["cases"]
                       if rule in c.get("rules", []) and c["expect_exit"] != 0]
            self.assertTrue(failing, "规则 %s 没有任何反例（要求非 0 退出）" % rule)

    def test_error_markers_absent_from_passing_cases(self):
        data = load_fixture()
        for case in data["cases"]:
            if case["expect_exit"] != 0:
                continue
            with self.subTest(case=case["name"]):
                _, out_p, err_p = port_output(case)
                self.assertNotIn("✗", out_p + err_p)

    # --- 身份政策：端口必须用新身份自称 -----------------------------------
    def test_new_implementation_uses_the_new_identity(self):
        source = PORT.read_text(encoding="utf-8")
        self.assertIn('"script":"check-traceability.py"', source)
        self.assertNotIn('"script":"check-traceability.sh"', source)
        self.assertIn("scripts/check-md-schema.py", source)
        self.assertNotIn("scripts/check-md-schema.sh", source)
        self.assertNotIn("bash scripts/check-traceability.sh", source)
        self.assertNotIn("self_display_name", source)
        self.assertNotIn("LEGACY_SELF_BASENAME", source)

    # --- 变异自证：改坏判定 → 对应反例必须转红 ---------------------------
    def _mutated_source(self, anchor, replacement):
        source = PORT.read_text(encoding="utf-8")
        self.assertEqual(source.count(anchor), 1, "变异锚点必须唯一：%r" % anchor)
        return source.replace(anchor, replacement, 1)

    def _run_source(self, case, source):
        with tempfile.TemporaryDirectory(prefix="trace-port-mutate-") as tmp:
            root = Path(tmp)
            materialize(case, root)
            stage_port(root, source=source)
            posix = posix_root(root)
            return run_port(root, case.get("args", []))

    def _assert_mutation_flips_case(self, anchor, replacement, case_name):
        data = load_fixture()
        cases = {c["name"]: c for c in data["cases"]}
        self.assertIn(case_name, cases)
        case = cases[case_name]
        source = self._mutated_source(anchor, replacement)
        rc_m, out_m, err_m = self._run_source(case, source)
        self.assertNotEqual(
            (rc_m, canon(out_m), canon(err_m)),
            (case["expect_exit"], canon(case["expect_stdout"]), canon(case.get("expect_stderr", ""))),
            "变异后用例 %s 的输出没有变化 —— 该反例不会红" % case_name,
        )

    def test_mutation_relaxes_ledger_id_rule(self):
        anchor, replacement, case_name, _ = MUTATIONS[0]
        self._assert_mutation_flips_case(anchor, replacement, case_name)

    def test_mutation_breaks_relation_type_rule(self):
        anchor, replacement, case_name, _ = MUTATIONS[1]
        self._assert_mutation_flips_case(anchor, replacement, case_name)

    def test_mutation_breaks_state_line_rule(self):
        anchor, replacement, case_name, _ = MUTATIONS[2]
        self._assert_mutation_flips_case(anchor, replacement, case_name)

    def test_mutation_breaks_scenario_mapping_row_rule(self):
        anchor, replacement, case_name, _ = MUTATIONS[3]
        self._assert_mutation_flips_case(anchor, replacement, case_name)

    def test_mutation_breaks_reference_test_cases_rule(self):
        anchor, replacement, case_name, _ = MUTATIONS[4]
        self._assert_mutation_flips_case(anchor, replacement, case_name)

    def test_mutation_anchors_are_unique(self):
        source = PORT.read_text(encoding="utf-8")
        for anchor, _replacement, _case, _desc in MUTATIONS:
            self.assertEqual(source.count(anchor), 1, "变异锚点不唯一：%r" % anchor)


if __name__ == "__main__":
    unittest.main()
