#!/usr/bin/env python3
"""measure.py / rubric.py / gate_ids.py 的自检 (test_measure.py)

Stdlib only. 用**合成**的 git 仓与门禁日志跑通整条链路, 不依赖真实业务仓。

跑法:
    python3 scripts/test_measure.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gate_archive as GA  # noqa: E402
import gate_ids as G  # noqa: E402
import rubric as R  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print(f"  [OK] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        FAILURES.append(name)


# ---------------------------------------------------------------------------
# 归档辅助
#
# `measure.py` 现在**只**从归档读门禁产物 (不再读业务仓工作区的
# `target/surefire-reports`)。所以每个测例都得先造一份归档。
# 归档根目录用 `--archive-root` 指到临时目录, 不碰真实规格仓。
#
# `--archive-root` 的语义是**归档根目录本身** (与
# `gate_archive.py --archive-dir` 一致)。写归档时必须用同一个语义,
# 否则「写的地方」与「读的地方」不是同一个目录。
# ---------------------------------------------------------------------------

def make_archive(archive_root, rid, arm, gate_log, repo_path=None,
                 xml_body=None, log_text=None, xml_name=None):
    """造一份归档。返回归档根目录 (传给 measure.py 的 --archive-root)。

    `xml_name` 是 XML 文件名 (默认 `TEST-io.busyming.x.FooTest.xml`)。
    **失败标识是从文件名反推的** (与 measure.py 同口径), 所以要造某个
    特定类的失败, 必须让文件名里的类名对得上。
    """
    os.makedirs(archive_root, exist_ok=True)
    if repo_path is None:
        repo_path = os.path.join(archive_root, "..", "repoB")
    if xml_name is None:
        xml_name = "TEST-io.busyming.x.FooTest.xml"
    entries = []
    if xml_body is not None:
        reports = os.path.join(repo_path, "busyming-merchandising-service",
                               "target", "surefire-reports")
        os.makedirs(reports, exist_ok=True)
        with open(os.path.join(reports, xml_name),
                  "w", encoding="utf-8") as fh:
            fh.write(xml_body)
    if log_text is None:
        log_text = ""
    entries.append({"alias": "B", "repo_path": repo_path,
                    "command": "mvn test", "scope": "service",
                    "log_text": log_text})
    # `root` 传仓库根, 归档根目录用 `archive_root` 显式指定 ——
    # 两者语义不同, 不能混。
    GA.write_archive(tmp_root_for(archive_root), rid, arm, gate_log, entries,
                     archive_root=archive_root)
    return archive_root


def tmp_root_for(archive_root):
    """归档所在临时目录的「仓库根」。

    manifest 里的 `gate_log` 记的是**相对仓库根**的路径, 校验时要用
    同一个根去还原绝对路径, 所以这里需要一个稳定的「根」。
    """
    return os.path.dirname(os.path.abspath(archive_root))


# ---------------------------------------------------------------------------
# 1. gate_ids: 规范化标识
# ---------------------------------------------------------------------------

def test_gate_ids():
    print("== gate_ids ==")
    surefire_log = """
[INFO] BUILD SUCCESS
[ERROR] io.busyming.product.merchandising.service.FooTest.bar -- Time elapsed: 0.003 s <<< FAILURE!
[ERROR] io.busyming.product.merchandising.service.FooTest.baz(int)[1] -- Time elapsed: 0.001 s <<< FAILURE!
[ERROR] io.busyming.product.merchandising.service.FooTest.baz(int)[2] -- Time elapsed: 0.001 s <<< FAILURE!
[ERROR] Errors:
[ERROR]   FooTest.bar:42 expected: <true> but was: <false>
"""
    ids = G.parse_surefire_log_ids(surefire_log)
    check("surefire 解析出 3 个失败", len(ids) == 3, f"实为 {len(ids)}: {ids}")
    check("surefire 保留参数化后缀",
          "io.busyming.product.merchandising.service.FooTest#baz(int)[1]" in ids)

    vitest_log = """
 FAIL  src/a.spec.ts [ src/a.spec.ts ]
 FAIL  src/b.spec.ts > suite > name
 FAIL  src/c.spec.ts > suite > name [ src/c.spec.ts ]
"""
    files, cases = G.parse_vitest_log_ids(vitest_log)
    check("vitest 文件级 3 个", len(files) == 3, f"实为 {len(files)}: {files}")
    check("vitest 用例级 2 个", len(cases) == 2, f"实为 {len(cases)}: {cases}")
    check("vitest 用例级含文件名", any("src/b.spec.ts > suite > name" == c
                                     for c in cases))

    # 差集语义
    base = {"a", "b"}
    cur = {"b", "c"}
    new, fixed, n_new, n_fixed = G.diff_report(cur, base)
    check("差集: 新增 {c}", new == {"c"}, f"实为 {new}")
    check("差集: 消失 {a}", fixed == {"a"}, f"实为 {fixed}")
    check("差集: 计数 1/1", (n_new, n_fixed) == (1, 1))


def test_surefire_xml_uses_filename_not_classname():
    """surefire XML 的 classname 是 @DisplayName 显示名, 必须用文件名反推 FQN。"""
    print("== gate_ids: surefire XML 标识来源 ==")
    tmp = tempfile.mkdtemp(prefix="gate-ids-xml-")
    try:
        mod = os.path.join(tmp, "busyming-merchandising-service")
        rep = os.path.join(mod, "target", "surefire-reports")
        os.makedirs(rep)
        fqn = "io.busyming.product.merchandising.service.FooTest"
        xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<testsuite name="io.busyming.product.merchandising.service.FooTest">
  <testcase classname="小改V2 · 未识别/合格率口径" name="someMethod"/>
  <testcase classname="小改V2 · 未识别/合格率口径" name="failing">
    <failure message="boom">stack</failure>
  </testcase>
</testsuite>
'''
        with open(os.path.join(rep, f"TEST-{fqn}.xml"), "w", encoding="utf-8") as fh:
            fh.write(xml)
        ids = G.parse_surefire_xml_ids(tmp)
        check("XML 用文件名反推 FQN",
              f"{fqn}#failing" in ids, f"实为 {ids}")
        check("XML 不用 @DisplayName 做标识",
              not any("小改V2" in i for i in ids), f"实为 {ids}")

        # **两个入口必须逐字一致**。
        # 基线快照走 `parse_surefire_xml_ids` (扫业务仓目录),
        # 实验期走 `parse_surefire_xml_files` (吃归档里的副本路径)。
        # 口径一旦漂移, 同一个失败在两侧得到两个标识, 差集恒不为空 ——
        # 基线自己的失败会被误判成「新失败」, `D_gate_new` 凭空变大。
        import glob as _glob
        same = G.parse_surefire_xml_files(
            sorted(_glob.glob(os.path.join(rep, "TEST-*.xml"))))
        check("扫目录与吃路径列表的结果逐字一致",
              same == ids, f"目录={ids} 列表={same}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 2. rubric: AC 解析
# ---------------------------------------------------------------------------

SAMPLE_RUBRIC = """# 测试评分表

## 3. 十轮验收标准

### 3.1 F-02 · H5 · 标题

> 说明

| # | AC | 可观测判据 |
|---|-----|-----------|
| AC-2.1 | 文本一 | 判据一 |
| AC-2.2 | 文本二 | 判据二 |

### 3.2 B-01 · 后端 · 标题

> 说明

| # | AC | 可观测判据 |
|---|-----|-----------|
| AC-B01-1 | 文本三 | 判据三 |
"""


def test_rubric_parser(tmp):
    print("== rubric: AC 解析 ==")
    path = os.path.join(tmp, "RUBRIC.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE_RUBRIC)
    acs = R.parse_rubric(path)
    check("解析出 3 条 AC", len(acs) == 3, f"实为 {len(acs)}")
    check("候选分组正确",
          sorted(R.acs_by_candidate(acs)) == ["B-01", "F-02"],
          f"实为 {sorted(R.acs_by_candidate(acs))}")
    check("连字符 AC ID 正确识别",
          any(a["ac_id"] == "AC-B01-1" for a in acs))
    check("AC ID 全局唯一", R.check_uniqueness(acs)[0])

    # 表格分隔行与表头不应被当成 AC
    check("分隔行/表头不计入", len(acs) == 3)

    # 判据列里的转义竖线
    path2 = os.path.join(tmp, "RUBRIC2.md")
    with open(path2, "w", encoding="utf-8") as fh:
        fh.write("""### 3.1 F-01 · x · y

| # | AC | 可观测判据 |
|---|-----|-----------|
| AC-1.1 | 文本 | 判据含 \\| 竖线 |
""")
    acs2 = R.parse_rubric(path2)
    check("转义竖线不拆列", len(acs2) == 1 and "竖线" in acs2[0]["criterion"],
          f"实为 {acs2}")


def test_checklist_roundtrip(tmp):
    print("== rubric: 共享检查表 ==")
    acs = R.parse_rubric(os.path.join(tmp, "RUBRIC.md"))
    groups = R.acs_by_candidate(acs)
    tpl = R.render_template("F-02", groups["F-02"])
    check("模板每条 AC 一行", len(R.parse_verdicts(tpl)) == 2)
    check("模板默认未勾选",
          all(not c for (_i, c, _a, _na) in R.parse_verdicts(tpl)))
    check("模板版本哈希存在", "模板版本" in tpl)

    # 填一份: 勾选一条 + 锚点
    filled = tpl.replace("| 1 | `AC-2.1` | 判据一 | [ ] AC-2.1 |  |",
                          "| 1 | `AC-2.1` | 判据一 | [x] AC-2.1 | {B}@abc1234:src/x.ts#L10 |")
    ok, problems = R.checklist_diff(tpl, filled)
    check("只改勾选+锚点 → 通过", ok, f"实为 {problems}")

    # 改判据列 → 必须失败
    tampered = filled.replace("判据一", "判据被改了")
    ok2, problems2 = R.checklist_diff(tpl, tampered)
    check("改判据列 → 失败", not ok2, f"实为 {problems2}")

    # 删一条 AC → 必须失败
    lines = [l for l in tpl.splitlines() if "AC-2.2" not in l]
    ok3, problems3 = R.checklist_diff(tpl, "\n".join(lines))
    check("删 AC → 失败", not ok3, f"实为 {problems3}")

    # 哈希随 AC 内容变化
    h1 = R.compute_template_hash(acs)
    acs_mod = [dict(a) for a in acs]
    acs_mod[0]["criterion"] = "改了"
    h2 = R.compute_template_hash(acs_mod)
    check("哈希随判据变化", h1 != h2, f"{h1} == {h2}")


# ---------------------------------------------------------------------------
# 3. measure.py: 端到端
# ---------------------------------------------------------------------------

def make_repo(path, files):
    os.makedirs(path, exist_ok=True)
    subprocess.run(["git", "init", "-q", path], check=True)
    for rel, content in files.items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
    subprocess.run(["git", "-C", path, "add", "-A"], check=True)
    subprocess.run(["git", "-C", path, "-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-qm", "init"], check=True)


def test_measure_end_to_end(tmp):
    print("== measure.py: 端到端 ==")
    repo = os.path.join(tmp, "repoB")
    make_repo(repo, {"src/App.java": "line1\nline2\nline3\n"})
    base = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    with open(os.path.join(repo, "src/App.java"), "a", encoding="utf-8") as fh:
        fh.write("line4\n")
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
    subprocess.run(["git", "-C", repo, "-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-qm", "feat: change"], check=True)
    head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    # 造一份共享检查表 (用真实 RUBRIC.md 的第一个候选)
    acs = R.parse_rubric()
    groups = R.acs_by_candidate(acs)
    cand = sorted(groups)[0]
    tpl = R.render_template(cand, groups[cand])
    # 勾选第一条, 锚点指向真实改动文件
    first = groups[cand][0]
    filled = tpl.replace(
        f"| 1 | `{first['ac_id']}` | {first['criterion']} | [ ] {first['ac_id']} |  |",
        f"| 1 | `{first['ac_id']}` | {first['criterion']} | [x] {first['ac_id']} | "
        f"{{B}}@{head}:src/App.java#L2 |")
    check("检查表构造成功", filled != tpl)

    cl_path = os.path.join(tmp, "filled.checklist.md")
    with open(cl_path, "w", encoding="utf-8") as fh:
        fh.write(filled)

    # 门禁日志: 无失败
    gate_path = os.path.join(tmp, "gate.txt")
    with open(gate_path, "w", encoding="utf-8") as fh:
        fh.write("### [B] mvn test\n[INFO] BUILD SUCCESS\n")

    # **归档**: measure.py 只从归档读门禁产物。
    # 本用例的门禁日志没有失败, 所以归档里的 XML 也是全过的。
    arch_root = make_archive(
        os.path.join(tmp, "archives"), "X-01", "ssd", gate_path,
        repo_path=repo,
        xml_body=("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                  "<testsuite name=\"io.busyming.x.FooTest\" tests=\"0\" "
                  "failures=\"0\" errors=\"0\"/>\n"),
        log_text="[INFO] BUILD SUCCESS\nEXIT=0\n")

    # **基线快照必须用真的冻结版**。
    #
    # `measure.py` 会逐字节核对基线快照的哈希, 对不上就拒绝测量 (这是
    # 差集法的命根子)。所以这里不能造一份合成基线, 必须用仓库里那份
    # 冻结的 `docs/efficacy/baseline-gates.json`。
    #
    # 合成基线里 `failing_test_ids` 为空, 而冻结版里 B 仓有一批基线失败,
    # 两者对本用例无影响: 本用例的门禁日志要么没有失败, 要么有一个
    # 冻结版里**不存在**的新失败, 差集结果都是确定的。
    baseline_gates = os.path.join(ROOT, "docs", "efficacy",
                                  "baseline-gates.json")
    check("冻结基线快照存在", os.path.isfile(baseline_gates))

    out = os.path.join(tmp, "round.json")
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "measure.py"), "round",
         "--round-id", "X-01", "--arm", "ssd", "--repo", "B",
         "--repo-path", repo, "--baseline", base, "--head", head,
         "--checklist", cl_path, "--gate-log", gate_path,
         "--baseline-gates", baseline_gates,
         "--archive-root", arch_root, "--out", out],
        capture_output=True, text=True)
    check("measure round 退出码 0", r.returncode == 0, r.stderr[-500:])
    if r.returncode == 0:
        data = json.load(open(out))
        obs = data["observations"]
        n_acs = len(groups[cand])
        check(f"A_spec == {n_acs}", obs["A_spec"] == n_acs,
              f"实为 {obs['A_spec']}")
        check("A_del == 1 (锚点有效)", obs["A_del"] == 1,
              f"实为 {obs['A_del']}: "
              f"{[d for d in data['ac_detail'] if d['reason']!='delivered']}")
        check("CE == 1/n", abs(data["derived"]["CE"] - 1.0 / n_acs) < 1e-9)
        check("D == 0 (无新门禁失败)", obs["D"] == 0, f"实为 {obs['D']}")
        check("T 有值", obs["T_minutes"] >= 0)

    # 锚点指向**未改动**的文件 → 不应计入 A_del
    filled_bad = filled.replace("src/App.java#L2", "src/Nope.java#L2")
    cl2 = os.path.join(tmp, "filled2.checklist.md")
    with open(cl2, "w", encoding="utf-8") as fh:
        fh.write(filled_bad)
    out2 = os.path.join(tmp, "round2.json")
    r2 = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "measure.py"), "round",
         "--round-id", "X-01", "--arm", "ssd", "--repo", "B",
         "--repo-path", repo, "--baseline", base, "--head", head,
         "--checklist", cl2, "--gate-log", gate_path,
         "--baseline-gates", baseline_gates,
         "--archive-root", arch_root, "--out", out2],
        capture_output=True, text=True)
    check("锚点文件未改动 → measure 退出码 0", r2.returncode == 0, r2.stderr[-300:])
    if r2.returncode == 0:
        d2 = json.load(open(out2))
        check("锚点文件未改动 → A_del == 0", d2["observations"]["A_del"] == 0,
              f"实为 {d2['observations']['A_del']}")

    # 空检查表 → **硬失败**, 不再静默 A_spec=0
    empty = os.path.join(tmp, "empty.checklist.md")
    with open(empty, "w", encoding="utf-8") as fh:
        fh.write("# 空\n")
    out3 = os.path.join(tmp, "round3.json")
    r3 = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "measure.py"), "round",
         "--round-id", "X-01", "--arm", "ssd", "--repo", "B",
         "--repo-path", repo, "--baseline", base, "--head", head,
         "--checklist", empty, "--gate-log", gate_path,
         "--baseline-gates", baseline_gates,
         "--archive-root", arch_root, "--out", out3],
        capture_output=True, text=True)
    check("空检查表 → 硬失败 (不静默 CE=0)", r3.returncode != 0,
          f"退出码 {r3.returncode}")

    # 门禁新失败 → D 计入
    gate2 = os.path.join(tmp, "gate2.txt")
    with open(gate2, "w", encoding="utf-8") as fh:
        fh.write("### [B] mvn test\n"
                 "[ERROR] io.busyming.x.NewTest.broken -- Time elapsed: 0.1 s <<< FAILURE!\n")
    # 新失败必须在**归档的 XML** 里 (归档是权威源)。
    arch2 = make_archive(
        os.path.join(tmp, "archives2"), "X-01", "ssd", gate2,
        repo_path=repo,
        xml_body=("<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
                  "<testsuite name=\"io.busyming.x.NewTest\" tests=\"1\" "
                  "failures=\"1\" errors=\"0\">\n"
                  "  <testcase name=\"broken\" "
                  "classname=\"io.busyming.x.NewTest\" time=\"0.1\">\n"
                  "    <failure message=\"x\">stack</failure>\n"
                  "  </testcase>\n"
                  "</testsuite>\n"),
        log_text=("[INFO] BUILD SUCCESS\n"
                  "[ERROR] io.busyming.x.NewTest.broken -- x <<< FAILURE!\n"
                  "EXIT=0\n"))
    out4 = os.path.join(tmp, "round4.json")
    r4 = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "measure.py"), "round",
         "--round-id", "X-01", "--arm", "ssd", "--repo", "B",
         "--repo-path", repo, "--baseline", base, "--head", head,
         "--checklist", cl_path, "--gate-log", gate2,
         "--baseline-gates", baseline_gates,
         "--archive-root", arch2, "--out", out4],
        capture_output=True, text=True)
    check("新门禁失败 → measure 退出码 0", r4.returncode == 0, r4.stderr[-300:])
    if r4.returncode == 0:
        d4 = json.load(open(out4))
        check("新门禁失败 → D_gate_new == 1",
              d4["observations"]["D_gate_new"] == 1,
              f"实为 {d4['observations']['D_gate_new']}")
        check("新门禁失败 → D == 1", d4["observations"]["D"] == 1)

    # **构建失败** → 显式记 delta。
    # 编译失败时 surefire 不产 XML, 失败集**变小**, 差集法算出的 D 会变小 ——
    # 方向完全相反。所以必须显式补一个 delta。
    gate3 = os.path.join(tmp, "gate3.txt")
    with open(gate3, "w", encoding="utf-8") as fh:
        fh.write("### [B] mvn test\n"
                 "[ERROR] COMPILATION ERROR\n"
                 "[ERROR] Failed to execute goal compile\n")
    arch3 = make_archive(
        os.path.join(tmp, "archives3"), "X-01", "ssd", gate3,
        repo_path=repo,
        # 编译失败 → **没有** XML 产出
        xml_body=None,
        log_text="[ERROR] COMPILATION ERROR\nEXIT=1\n")
    out5 = os.path.join(tmp, "round5.json")
    r5 = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "measure.py"), "round",
         "--round-id", "X-01", "--arm", "ssd", "--repo", "B",
         "--repo-path", repo, "--baseline", base, "--head", head,
         "--checklist", cl_path, "--gate-log", gate3,
         "--baseline-gates", baseline_gates,
         "--archive-root", arch3, "--out", out5],
        capture_output=True, text=True)
    check("构建失败 → measure 退出码 0", r5.returncode == 0, r5.stderr[-300:])
    if r5.returncode == 0:
        d5 = json.load(open(out5))
        check("构建失败 → build_status == BUILD_FAILURE",
              d5["gate_detail"]["B"]["build_status"]
              == "BUILD_FAILURE",
              f"实为 {d5['gate_detail']['B']['build_status']}")
        check("构建失败 → D >= 1 (不能因为没产 XML 就记 0)",
              d5["observations"]["D"] >= 1,
              f"实为 {d5['observations']['D']}")

    # **没有归档** → 硬失败 (不能静默出数)
    out6 = os.path.join(tmp, "round6.json")
    r6 = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "measure.py"), "round",
         "--round-id", "X-01", "--arm", "ssd", "--repo", "B",
         "--repo-path", repo, "--baseline", base, "--head", head,
         "--checklist", cl_path, "--gate-log", gate_path,
         "--baseline-gates", baseline_gates,
         "--archive-root", os.path.join(tmp, "no-such-archives"),
         "--out", out6],
        capture_output=True, text=True)
    check("缺归档 → 硬失败", r6.returncode != 0, f"退出码 {r6.returncode}")
    check("缺归档 → 没有产出结果文件", not os.path.isfile(out6))


def test_baseline_vs_baseline_invariant(tmp):
    """基线快照 vs 基线日志: 必须零新增零消失。"""
    print("== 门禁差集不变量 (基线 vs 基线) ==")
    log = ("### [B] mvn test\n"
           "[ERROR] io.busyming.x.FooTest.bar -- Time elapsed: 0.1 s <<< FAILURE!\n"
           "[ERROR] io.busyming.x.FooTest.baz -- Time elapsed: 0.1 s <<< FAILURE!\n")
    parsed = G.parse_surefire_log_ids(log)
    new, fixed, n_new, n_fixed = G.diff_report(parsed, parsed)
    check("基线 vs 基线: 新增 0", n_new == 0, f"实为 {n_new}")
    check("基线 vs 基线: 消失 0", n_fixed == 0, f"实为 {n_fixed}")


# ---------------------------------------------------------------------------
# 8. 基线参照系不可漂移 (负向测试)
# ---------------------------------------------------------------------------

def test_baseline_drift_refused(tmp):
    """基线快照漂移时必须**拒绝测量**, 而不是照样算出一个数。

    这是差集法的命根子。`D` = 本臂失败集 - 基线失败集。如果基线被改过,
    两臂对着不同的参照系, DR/CE 就失去意义, 而 `aggregate` 只按
    `round_id` + `arm` 配对, 照样出数。所以必须在测量入口就硬失败。
    """
    print("== 基线漂移拒绝测量 ==")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_mod", os.path.join(ROOT, "scripts", "measure.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    frozen = os.path.join(ROOT, "docs", "efficacy", "baseline-gates.json")

    # (a) 冻结版本身必须通过
    ok, sha, _ = M.verify_frozen_baseline(frozen)
    check("冻结版基线: 校验通过", ok)
    check("冻结版基线: 哈希等于写死的常量",
          sha == M.FROZEN_BASELINE_GATES_SHA256,
          f"实为 {sha}")

    # (b) 内容被改过的基线必须被拒
    drifted = os.path.join(tmp, "drifted-baseline.json")
    with open(frozen, encoding="utf-8") as fh:
        data = json.load(fh)
    data["__drift__"] = "injected"
    with open(drifted, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    ok2, sha2, _ = M.verify_frozen_baseline(drifted)
    check("漂移的基线: 被拒绝", not ok2, "竟然通过了")
    check("漂移的基线: 报告了实际哈希", sha2 is not None)

    # (c) 读不到的文件同样拒绝 (缺参照系 = 没有参照系)
    ok3, sha3, _ = M.verify_frozen_baseline(
        os.path.join(tmp, "does-not-exist.json"))
    check("不存在的基线: 被拒绝", not ok3, "竟然通过了")

    # (d) 未提供路径也拒绝
    ok4, sha4, _ = M.verify_frozen_baseline("")
    check("空基线路径: 被拒绝", not ok4, "竟然通过了")

    # (e) 关键: 即使字节不同但**解析出的集合相同**, 也必须拒绝。
    #     这证明校验是按字节做的, 不是按语义做的。
    same_semantics = os.path.join(tmp, "reordered.json")
    with open(frozen, encoding="utf-8") as fh:
        data2 = json.load(fh)
    with open(same_semantics, "w", encoding="utf-8") as fh:
        json.dump(data2, fh, indent=4, sort_keys=False)
    ok5, sha5, _ = M.verify_frozen_baseline(same_semantics)
    check("语义相同但字节不同: 被拒绝", not ok5,
          "字节级校验失效, 只比了语义")

    # (f) **真实场景**: `capture-vitest-baseline.py` 会就地重写基线文件
    #     (读出来 → 改几个键 → json.dump(indent=2) 写回)。重新采集一次
    #     基线 (哪怕内容「一样」, 只是 captured_at 变了) 都会改变字节。
    #     这正是 Bonehound 指出的「两臂之间重跑一次 baseline」场景。
    recaptured = os.path.join(tmp, "recaptured.json")
    with open(frozen, encoding="utf-8") as fh:
        data3 = json.load(fh)
    data3["captured_at"] = "2099-01-01T00:00"
    with open(recaptured, "w", encoding="utf-8") as fh:
        json.dump(data3, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    ok6, _sha6, _d6 = M.verify_frozen_baseline(recaptured)
    check("重新采集过的基线: 被拒绝", not ok6,
          "重采集未被检出, 差集法会对着两份参照系算")


def test_aggregate_refuses_mismatched_arms(tmp):
    """聚合时两臂基线不一致必须拒绝, 不能取中位数蒙混过去。"""
    print("== 聚合拒绝基线不一致的两臂 ==")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_mod2", os.path.join(ROOT, "scripts", "measure.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    rounds_dir = os.path.join(tmp, "rounds-mismatch")
    os.makedirs(rounds_dir, exist_ok=True)

    def write_round(name, arm, sha, dr):
        obj = {
            "round_id": "1",
            "arm": arm,
            "baseline_gates_sha256": sha,
            "observations": {"T_minutes": 10.0},
            "derived": {"DR": dr, "CE": 0.5},
        }
        with open(os.path.join(rounds_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    frozen = M.FROZEN_BASELINE_GATES_SHA256
    other = "0" * 64

    # (a) 两臂基线一致 -> 允许聚合
    write_round("a.json", "ssd", frozen, 0.8)
    write_round("b.json", "control", frozen, 0.4)
    class A1:
        rounds = rounds_dir
        out = os.path.join(tmp, "agg-ok.json")
    rc = M.cmd_aggregate(A1())
    check("两臂基线一致: 聚合通过", rc == 0, f"实为 rc={rc}")

    # (b) 两臂基线不一致 -> 拒绝
    write_round("b.json", "control", other, 0.4)
    class A2:
        rounds = rounds_dir
        out = os.path.join(tmp, "agg-bad.json")
    rc2 = M.cmd_aggregate(A2())
    check("两臂基线不一致: 聚合被拒绝", rc2 == 2, f"实为 rc={rc2}")

    # (c) 缺 baseline_gates_sha256 (旧格式) -> 拒绝
    write_round("b.json", "control", frozen, 0.4)
    with open(os.path.join(rounds_dir, "b.json"), encoding="utf-8") as fh:
        obj = json.load(fh)
    obj.pop("baseline_gates_sha256")
    with open(os.path.join(rounds_dir, "b.json"), "w", encoding="utf-8") as fh:
        json.dump(obj, fh)
    class A3:
        rounds = rounds_dir
        out = os.path.join(tmp, "agg-missing.json")
    rc3 = M.cmd_aggregate(A3())
    check("旧格式缺哈希: 聚合被拒绝", rc3 == 2, f"实为 rc={rc3}")


def test_aggregate_quarantine_symmetry(tmp):
    """聚合必须拒绝两臂用**不同**隔离清单的轮次, 并汇总隔离信息。

    隔离是对两臂**对称**的口径 (FORMULA.md §3.4.9.3)。一臂传了
    `--flaky-list` 而另一臂没传, 那一轮两臂的 `D` 就不可比了。
    """
    print("== 聚合的隔离对称性 ==")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_mod_q", os.path.join(ROOT, "scripts", "measure.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    rounds_dir = os.path.join(tmp, "rounds-qsym")
    os.makedirs(rounds_dir, exist_ok=True)
    frozen = M.FROZEN_BASELINE_GATES_SHA256
    LIST_REL = M.FLAKY_LIST_REL

    def write_round(name, arm, list_file, qcount=0, before=0, after=0):
        obj = {
            "round_id": "1",
            "arm": arm,
            "baseline_gates_sha256": frozen,
            "observations": {
                "T_minutes": 10.0,
                "quarantined_count": qcount,
                "D_gate_new": after,
                "D_gate_new_before_quarantine": before,
            },
            "derived": {"DR": 0.5, "CE": 0.5},
            "quarantine": {"list_file": list_file, "by_repo": {"B": []}},
        }
        with open(os.path.join(rounds_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    # (a) 两臂同一份清单 -> 允许聚合, 且汇总里能看到隔离数
    write_round("a.json", "ssd", LIST_REL, qcount=1, before=1, after=0)
    write_round("b.json", "control", LIST_REL, qcount=1, before=1, after=0)
    class A1:
        rounds = rounds_dir
        out = os.path.join(tmp, "agg-q-ok.json")
    rc = M.cmd_aggregate(A1())
    check("两臂同一份清单: 聚合通过", rc == 0, f"实为 rc={rc}")
    if rc == 0:
        agg = json.load(open(A1.out))
        q = agg["quarantine"]
        check("汇总里隔离总数 = 2 (两臂各 1)",
              q["total_quarantined"] == 2, f"实为 {q['total_quarantined']}")
        check("汇总里列出触发隔离的轮次",
              q["rounds_with_quarantine"] == ["1"],
              f"实为 {q['rounds_with_quarantine']}")
        br = q["by_round"]["1"]["ssd"]
        check("汇总里保留隔离前后的 D_gate_new",
              br["D_gate_new"] == 0 and br["D_gate_new_before_quarantine"] == 1,
              f"实为 {br}")

    # (b) 两臂清单不同 -> 拒绝
    write_round("b.json", "control", "some/other-list.json",
                qcount=0, before=0, after=0)
    class A2:
        rounds = rounds_dir
        out = os.path.join(tmp, "agg-q-bad.json")
    rc2 = M.cmd_aggregate(A2())
    check("两臂隔离清单不同: 聚合被拒绝", rc2 == 2, f"实为 rc={rc2}")


def test_scoped_gate_difference_uses_real_baseline(tmp):
    """差集法在**真实冻结基线**上的行为 (承重不变量)。

    这是整个实验的核心: `D_gate_new` = 「本臂门禁失败集 - 基线失败集」。
    两种错误都会毁掉实验结果:

    - **没减**: 基线里已失败的用例被当成新缺陷, `D` 被抬高, 两臂都被污染。
    - **减错**: 新缺陷被当成基线失败减掉, `D` 被压低。

    所以这里用**真实的** `baseline-gates.json` (不是合成数据) 做验证,
    并且专门验证**门禁范围小于基线范围**的情形 —— 门禁按模块定向跑,
    基线是全 reactor 跑的, 所以门禁只会看到基线失败集的一个子集。
    子集之外的基线失败**不应**被算成新增。
    """
    print("== 差集法: 真实基线 + 定向门禁 ==")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_mod3", os.path.join(ROOT, "scripts", "measure.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    bg_path = os.path.join(ROOT, "docs", "efficacy", "baseline-gates.json")
    with open(bg_path, encoding="utf-8") as fh:
        bg = json.load(fh)
    base_B = set(bg["failing_test_ids"])
    check("真实基线有失败集", len(base_B) > 0, f"实为 {len(base_B)}")

    # B-01 的门禁范围是 service 模块 (见 run-round.sh gate_scope_b)。
    # 基线是全 reactor, 所以 service 只是基线失败集的一个子集。
    svc = sorted(i for i in base_B if ".service." in i)
    outside = sorted(i for i in base_B if ".service." not in i)
    check("基线失败集横跨多个模块 (门禁范围 < 基线范围)",
          len(svc) > 0 and len(outside) > 0,
          f"scope 内 {len(svc)}, 范围外 {len(outside)}")

    def log_for(ids):
        out = "### [B] mvn -pl busyming-merchandising-service -am test\n"
        for i in ids:
            out += (f"[ERROR] {i.replace('#', '.')} -- "
                    f"Time elapsed: 0.1 s <<< FAILURE!\n")
        return out

    # (a) 定向门禁, 失败全部已在基线里 → 新增必须为 0
    parsed = G.parse_surefire_log_ids(log_for(svc))
    check("定向门禁解析出全部范围内失败", len(parsed) == len(svc),
          f"实为 {len(parsed)} / {len(svc)}")
    new, fixed, n_new, n_fixed = G.diff_report(parsed, base_B)
    check("定向门禁无新失败 → n_new == 0", n_new == 0, f"实为 {n_new}")
    check("范围外的基线失败不算新增 (只是缺席)",
          len(fixed) == len(outside), f"实为 {len(fixed)} / {len(outside)}")

    # (b) 注入一个**真正的新**失败 → 新增必须恰好 +1
    injected = "io.busyming.product.merchandising.service.component.NewlyBrokenTest#boom"
    parsed2 = G.parse_surefire_log_ids(log_for(svc) + (
        f"[ERROR] {injected.replace('#', '.')} -- "
        f"Time elapsed: 0.1 s <<< FAILURE!\n"))
    new2, _f2, n_new2, _nf2 = G.diff_report(parsed2, base_B)
    check("注入一个新失败 → n_new == 1", n_new2 == 1, f"实为 {n_new2}")
    check("新失败被正确识别",
          new2 == {injected}, f"实为 {sorted(new2)}")

    # (c) 反向: 门禁**只跑新失败**, 基线失败全部缺席 → 仍只算 1
    parsed3 = G.parse_surefire_log_ids(
        f"[ERROR] {injected.replace('#', '.')} -- "
        f"Time elapsed: 0.1 s <<< FAILURE!\n")
    new3, _f3, n_new3, _nf3 = G.diff_report(parsed3, base_B)
    check("门禁只含新失败 → n_new == 1", n_new3 == 1, f"实为 {n_new3}")

    # (d) **绝对不能**把基线失败当新增 (反向断言)
    check("基线失败绝不计入新增", base_B.isdisjoint(new),
          "有基线失败被算成新增")


def test_aggregate_refuses_duplicate_records(tmp):
    """同一个 (round_id, arm) 出现两份记录时必须拒绝聚合。

    否则 `n_rounds` 虚高、同一轮被重复计入中位数, 而读报告的人看不出来。
    """
    print("== 聚合拒绝重复的轮次记录 ==")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_mod_dup", os.path.join(ROOT, "scripts", "measure.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    rounds_dir = os.path.join(tmp, "rounds-dup")
    os.makedirs(rounds_dir, exist_ok=True)

    def write_round(name, arm, rid, dr):
        obj = {
            "round_id": rid,
            "arm": arm,
            "baseline_gates_sha256": M.FROZEN_BASELINE_GATES_SHA256,
            "observations": {"T_minutes": 10.0},
            "derived": {"DR": dr, "CE": 0.5},
        }
        with open(os.path.join(rounds_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    write_round("r0-s.json", "ssd", "R0", 0.2)
    write_round("r0-c.json", "control", "R0", 0.4)
    write_round("r1-s.json", "ssd", "R1", 0.8)
    write_round("r1-c.json", "control", "R1", 0.4)

    class A:
        rounds = rounds_dir
        out = os.path.join(tmp, "agg-dup.json")

    # (a) 无重复 -> 聚合通过, n_rounds == 2
    rc_ok = M.cmd_aggregate(A())
    ok_out = json.load(open(A.out, encoding="utf-8"))
    check("无重复记录: 聚合通过", rc_ok == 0, f"实为 rc={rc_ok}")
    check("无重复记录: n_rounds == 2", ok_out["n_rounds"] == 2,
          f"实为 {ok_out['n_rounds']}")

    # (b) 同一 (round_id, arm) 两份 -> 拒绝
    write_round("r0-s-DUP.json", "ssd", "R0", 0.8)
    rc_dup = M.cmd_aggregate(A())
    check("重复记录: 聚合被拒绝", rc_dup == 2, f"实为 rc={rc_dup}")

    # (c) 重复被拒后, 摘要文件不得被更新成脏数字
    check("重复记录: 旧摘要未被覆盖",
          json.load(open(A.out, encoding="utf-8"))["n_rounds"] == 2,
          "拒绝聚合后摘要仍被写成了含重复记录的数字")


def test_aggregate_medians_use_paired_rounds_only(tmp):
    """中位数只能用**配对完整**的轮次。

    实验是配对设计 (§2.2)。若某轮只跑了一臂, 那一臂的记录不应进中位数,
    否则两臂的中位数建立在轮次数不等的集合上, 且与 `n_rounds` 口径不一致。
    """
    print("== 聚合中位数只取配对轮次 ==")
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_mod_pair", os.path.join(ROOT, "scripts", "measure.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    rounds_dir = os.path.join(tmp, "rounds-paired")
    os.makedirs(rounds_dir, exist_ok=True)

    def write_round(name, arm, rid, dr):
        obj = {
            "round_id": rid,
            "arm": arm,
            "baseline_gates_sha256": M.FROZEN_BASELINE_GATES_SHA256,
            "observations": {"T_minutes": 10.0},
            "derived": {"DR": dr, "CE": 0.5},
        }
        with open(os.path.join(rounds_dir, name), "w", encoding="utf-8") as fh:
            json.dump(obj, fh)

    # 4 个完整配对, ssd 的 DR 分别为 0.1 / 0.2 / 0.3 / 0.4
    for i, dr in enumerate([0.1, 0.2, 0.3, 0.4]):
        write_round(f"r{i}-s.json", "ssd", f"R{i}", dr)
        write_round(f"r{i}-c.json", "control", f"R{i}", 0.4)

    class A:
        rounds = rounds_dir
        out = os.path.join(tmp, "agg-paired.json")

    rc = M.cmd_aggregate(A())
    out = json.load(open(A.out, encoding="utf-8"))
    check("未配对时聚合仍通过 (实验可能未跑完)", rc == 0, f"实为 rc={rc}")

    # (a) 无未配对轮次时, 中位数 = 4 个配对值的中位数
    check("4 个配对轮次: 中位数 = 0.25",
          out["medians"]["DR_ssd"] == 0.25,
          f"实为 {out['medians']['DR_ssd']}")

    # (b) 加一个**未配对**的 ssd 轮次, 极端值。
    #     若中位数用了全部 5 个 ssd 记录, 中位数会变成 0.3。
    write_round("r9-s.json", "ssd", "R9", 0.5)
    rc2 = M.cmd_aggregate(A())
    out2 = json.load(open(A.out, encoding="utf-8"))
    check("未配对轮次: 聚合仍通过", rc2 == 0, f"实为 rc={rc2}")
    check("未配对轮次: 不进中位数 (仍为 0.25)",
          out2["medians"]["DR_ssd"] == 0.25,
          f"实为 {out2['medians']['DR_ssd']}")
    check("未配对轮次: 被单列报告",
          out2["unpaired_rounds"] == ["R9"],
          f"实为 {out2['unpaired_rounds']}")
    check("未配对轮次: n_rounds 只数配对",
          out2["n_rounds"] == 4, f"实为 {out2['n_rounds']}")
    check("未配对轮次: n_ssd 仍报原始记录数",
          out2["n_ssd"] == 5, f"实为 {out2['n_ssd']}")


def test_spec_work_minutes(tmp):
    print("== 规格仓耗时 (T_spec) ==")
    """T_spec 必须从**该臂的分支**读, 且口径对称。

    守的是两件事:
    1. **读分支不读 HEAD**: 读了 HEAD 就等于读「谁最后 checkout 过」,
       两臂的规格耗时会互相覆盖 —— 与这次修的门禁污染同一类错误。
    2. **对照臂恒为 0**: 对照臂不产规格, 那一项必须是 0 而不是被猜出来。
    """
    spec_repo = os.path.join(tmp, "specrepo")
    os.makedirs(spec_repo)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_mod_spec", os.path.join(ROOT, "scripts", "measure.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    run_git = lambda *a: subprocess.run(
        ["git", "-C", spec_repo] + list(a), capture_output=True, text=True)

    run_git("init", "-q", "-b", "main")
    run_git("config", "user.email", "t@example.com")
    run_git("config", "user.name", "T")
    run_git("commit", "-q", "--allow-empty", "-m", "base")

    rel = os.path.join("docs", "efficacy", "spec-output", "F-06", "ssd")

    def commit_spec(stamp, msg):
        d = os.path.join(spec_repo, rel)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{msg}.md"), "w", encoding="utf-8") as fh:
            fh.write(msg + "\n")
        run_git("add", "-A")
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = stamp
        env["GIT_COMMITTER_DATE"] = stamp
        subprocess.run(["git", "-C", spec_repo, "commit", "-q", "-m", msg],
                       capture_output=True, text=True, env=env)

    # 先在 main 上建两个提交 (跨度 30 分钟)
    commit_spec("2026-11-19T10:00:00+08:00", "prd")
    commit_spec("2026-11-19T10:30:00+08:00", "plan")

    branch = "exp/F-06/ssd"
    run_git("branch", branch)

    mins = M.spec_work_minutes(spec_repo, rel, branch=branch)
    check("T_spec 算出跨度 (30 分钟)", mins == 30.0, f"实为 {mins}")
    check("规格提交数 = 2",
          M.spec_work_commits(spec_repo, rel, branch=branch) == 2)

    # **对照臂**: 同一个仓, 同一个相对目录前缀, 但它不产规格
    # → 提交数 0, 时长 0。
    ctrl_rel = os.path.join("docs", "efficacy", "spec-output", "F-06", "control")
    check("对照臂: 提交数 = 0",
          M.spec_work_commits(spec_repo, ctrl_rel,
                               branch="exp/F-06/control") == 0)
    check("对照臂: T_spec = 0",
          M.spec_work_minutes(spec_repo, ctrl_rel,
                              branch="exp/F-06/control") == 0.0)

    # **分支隔离**: 在分支上加一个提交, HEAD (main) 不动。
    # 读 HEAD 的话结果会变 —— 读过 HEAD 的实现会把两臂算成同一个数。
    run_git("checkout", "-q", branch)
    d = os.path.join(spec_repo, rel)
    with open(os.path.join(d, "td.md"), "w", encoding="utf-8") as fh:
        fh.write("td\n")
    run_git("add", "-A")
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = "2026-11-19T11:00:00+08:00"
    env["GIT_COMMITTER_DATE"] = "2026-11-19T11:00:00+08:00"
    subprocess.run(["git", "-C", spec_repo, "commit", "-q", "-m", "td"],
                   capture_output=True, text=True, env=env)
    run_git("checkout", "-q", "main")

    # 分支有 3 个提交 (跨度 60 分钟), main 仍是 2 个 (跨度 30 分钟)。
    mins_branch = M.spec_work_minutes(spec_repo, rel, branch=branch)
    mins_head = M.spec_work_minutes(spec_repo, rel, branch="main")
    check("分支跨度 = 60 分钟", mins_branch == 60.0, f"实为 {mins_branch}")
    check("HEAD 跨度 = 30 分钟", mins_head == 30.0, f"实为 {mins_head}")
    check("分支与 HEAD 读出的跨度不同 (证明读的是分支)",
          mins_branch != mins_head, f"两者都是 {mins_branch}")

    # 分支不存在 → 0 (该臂还没产规格)
    check("分支不存在 → T_spec = 0",
          M.spec_work_minutes(spec_repo, rel,
                              branch="exp/NOPE/ssd") == 0.0)
    check("目录不存在 → T_spec = 0",
          M.spec_work_minutes(spec_repo, "no/such/dir",
                              branch=branch) == 0.0)


def test_flaky_quarantine(tmp):
    """基线 flake 必须从 `D_gate_new` 里**剔除**, 且**必须被报告**。

    背景: 冻结基线上有间歇性失败的用例 (FORMULA.md §3.4.9), 它们不在
    基线快照里 (快照只采了一次), 所以某一臂恰好触发时会被差集法算成
    「新失败」。隔离在**分子侧**做, 对两臂**对称**。
    """
    print("== 基线 flake 隔离 ==")

    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "measure_mod_flaky", os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "measure.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)

    # 读真实的冻结清单, 确认它能用。
    q = M.load_quarantined_flaky()
    check("冻结清单可读且非空", bool(q), f"实为 {q}")
    check("清单只含 B 仓", set(q) <= {"B"}, f"实为 {sorted(q)}")
    check("清单里每个标识都有 #method",
          all("#" in t for ids in q.values() for t in ids))

    # 清单坏掉 → 必须硬失败 (不能静默当成空清单)。
    bad = os.path.join(tmp, "bad-flaky.json")
    with open(bad, "w", encoding="utf-8") as fh:
        fh.write("{not json")
    try:
        M.load_quarantined_flaky(bad)
        check("坏掉的清单 → 报错", False, "竟然读成功了")
    except ValueError:
        check("坏掉的清单 → 报错", True)

    # 清单里的条目没有 test_id → 必须硬失败。
    bad2 = os.path.join(tmp, "bad-flaky2.json")
    with open(bad2, "w", encoding="utf-8") as fh:
        json.dump({"quarantined": [{"alias": "B"}]}, fh)
    try:
        M.load_quarantined_flaky(bad2)
        check("缺 test_id 的条目 → 报错", False, "竟然读成功了")
    except ValueError:
        check("缺 test_id 的条目 → 报错", True)

    # 清单缺失 → 必须硬失败 (隔离清单是尺子的一部分, 不能静默当空清单)。
    try:
        M.load_quarantined_flaky(os.path.join(tmp, "no-such.json"))
        check("清单缺失 → 报错", False, "竟然当成空清单了")
    except ValueError:
        check("清单缺失 → 报错", True)

    # --- 端到端: flake 触发时不计入 D, 且报告里列出来 ---
    repo = os.path.join(tmp, "repoB-flaky")
    make_repo(repo, {"src/App.java": "line1\n"})
    base = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    with open(os.path.join(repo, "src/App.java"), "a", encoding="utf-8") as fh:
        fh.write("line2\n")
    subprocess.run(["git", "-C", repo, "add", "-A"], check=True)
    subprocess.run(["git", "-C", repo, "-c", "user.email=t@t",
                    "-c", "user.name=t", "commit", "-qm", "feat: change"], check=True)
    head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()

    # 用**真实清单里的那个** flake 标识造一个失败。
    flake_id = sorted(q["B"])[0]
    cls, method = flake_id.split("#")
    xml_body = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        f"<testsuite name=\"{cls}\" tests=\"1\" failures=\"1\" errors=\"0\">\n"
        f"  <testcase classname=\"{cls}\" name=\"{method}\">\n"
        "    <failure message=\"boom\">stack</failure>\n"
        "  </testcase>\n"
        "</testsuite>\n")
    # **标识从文件名反推**, 所以文件名里的类名必须与清单一致。
    xml_name = f"TEST-{cls}.xml"

    def make_gate_and_archive(arm):
        gate_path = os.path.join(tmp, f"gate-flaky-{arm}.txt")
        with open(gate_path, "w", encoding="utf-8") as fh:
            fh.write("### [B] mvn test\n[INFO] BUILD SUCCESS\n")
        root = make_archive(
            os.path.join(tmp, f"archives-flaky-{arm}"), "X-02", arm, gate_path,
            repo_path=repo, xml_body=xml_body, xml_name=xml_name,
            log_text="[INFO] BUILD SUCCESS\nEXIT=0\n")
        return gate_path, root

    gate_ssd, arch_ssd = make_gate_and_archive("ssd")
    gate_ctrl, arch_ctrl = make_gate_and_archive("control")

    # 用**真实的**检查表模板 (空填), 这样 D 只可能来自门禁。
    acs = R.parse_rubric()
    groups = R.acs_by_candidate(acs)
    cand = sorted(groups)[0]
    tpl = R.render_template(cand, groups[cand])
    cl_path = os.path.join(tmp, "empty.checklist.md")
    with open(cl_path, "w", encoding="utf-8") as fh:
        fh.write(tpl)

    baseline_gates = os.path.join(ROOT, "docs", "efficacy",
                                  "baseline-gates.json")

    def run_measure(arm, extra):
        out = os.path.join(tmp, f"round-flaky-{arm}.json")
        gate_path = gate_ssd if arm == "ssd" else gate_ctrl
        arch_root = arch_ssd if arm == "ssd" else arch_ctrl
        cmd = [sys.executable, os.path.join(ROOT, "scripts", "measure.py"),
               "round", "--round-id", "X-02", "--arm", arm, "--repo", "B",
               "--repo-path", repo, "--baseline", base, "--head", head,
               "--checklist", cl_path, "--gate-log", gate_path,
               "--baseline-gates", baseline_gates,
               "--archive-root", arch_root, "--out", out] + extra
        r = subprocess.run(cmd, capture_output=True, text=True)
        return r, out

    # 1) **不隔离** → flake 被算成新失败, D_gate_new = 1。
    empty_list = os.path.join(tmp, "empty-flaky.json")
    with open(empty_list, "w", encoding="utf-8") as fh:
        json.dump({"quarantined": []}, fh)
    r1, out1 = run_measure("ssd", ["--flaky-list", empty_list])
    check("空隔离清单: 退出码 0", r1.returncode == 0, r1.stderr[-400:])
    if r1.returncode == 0:
        d1 = json.load(open(out1))
        check("空隔离清单: flake 被算成新失败",
              d1["observations"]["D_gate_new"] == 1,
              f"实为 {d1['observations']['D_gate_new']}")
        check("空隔离清单: 隔离数 = 0",
              d1["observations"]["quarantined_count"] == 0)

    # 2) **隔离** → flake 不计入, D_gate_new = 0, 且报告里列出它。
    r2, out2 = run_measure("ssd", [])
    check("用冻结清单: 退出码 0", r2.returncode == 0, r2.stderr[-400:])
    if r2.returncode == 0:
        d2 = json.load(open(out2))
        check("冻结清单: flake 不计入 D_gate_new",
              d2["observations"]["D_gate_new"] == 0,
              f"实为 {d2['observations']['D_gate_new']}")
        check("冻结清单: 隔离数 = 1",
              d2["observations"]["quarantined_count"] == 1,
              f"实为 {d2['observations']['quarantined_count']}")
        check("冻结清单: 隔离前 D_gate_new = 1 (可核对)",
              d2["observations"]["D_gate_new_before_quarantine"] == 1,
              f"实为 {d2['observations']['D_gate_new_before_quarantine']}")
        check("冻结清单: 隔离明细逐条列出",
              d2["quarantine"]["by_repo"].get("B") == [flake_id],
              f"实为 {d2['quarantine']['by_repo']}")
        check("冻结清单: 报告里提到了隔离",
              "隔离" in r2.stderr, r2.stderr[-300:])

    # 3) **对称性**: 同一份清单对另一臂同样生效 (隔离不偏向某一臂)。
    r3, out3 = run_measure("control", [])
    check("对照臂同样用冻结清单: 退出码 0", r3.returncode == 0,
          r3.stderr[-400:])
    if r3.returncode == 0:
        d3 = json.load(open(out3))
        check("对照臂: flake 同样被隔离",
              d3["observations"]["D_gate_new"] == 0,
              f"实为 {d3['observations']['D_gate_new']}")
        check("对照臂: 隔离数 = 1 (与 SSD 臂一致)",
              d3["observations"]["quarantined_count"] == 1,
              f"实为 {d3['observations']['quarantined_count']}")


def main():
    tmp = tempfile.mkdtemp(prefix="measure-test-")
    try:
        test_gate_ids()
        test_surefire_xml_uses_filename_not_classname()
        test_rubric_parser(tmp)
        test_checklist_roundtrip(tmp)
        test_measure_end_to_end(tmp)
        test_baseline_vs_baseline_invariant(tmp)
        test_baseline_drift_refused(tmp)
        test_aggregate_refuses_mismatched_arms(tmp)
        test_aggregate_refuses_duplicate_records(tmp)
        test_aggregate_medians_use_paired_rounds_only(tmp)
        test_scoped_gate_difference_uses_real_baseline(tmp)
        test_aggregate_quarantine_symmetry(tmp)
        test_spec_work_minutes(tmp)
        test_flaky_quarantine(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print()
    if FAILURES:
        print(f"[FAIL] {len(FAILURES)} 项未通过: {FAILURES}")
        return 1
    print("[OK] 全部自检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
