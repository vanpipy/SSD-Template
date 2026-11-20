#!/usr/bin/env bash
# 轮次执行脚本 (run-round.sh)
#
# 为一轮实验准备两臂的工作区, 并在两臂都跑完后做确定性测量。
# 脚本**不实施**代码, 实施由 agent 完成。
#
# 用法:
#   bash scripts/run-round.sh plan                        # 打印冻结执行计划 (只读)
#   bash scripts/run-round.sh init <candidate-id>         # 准备某候选的两臂分支
#   bash scripts/run-round.sh checklist <candidate-id> <arm>
#                                                    # 为某臂复制一份共享检查表模板
#   bash scripts/run-round.sh gate <candidate-id> <arm>   # 跑某臂门禁, 存日志
#   bash scripts/run-round.sh measure <candidate-id> <arm> # 测量某臂 (需先跑 gate)
#   bash scripts/run-round.sh aggregate                   # 聚合并算 SEI
#   bash scripts/run-round.sh gate-baseline-b             # 采集后端基线门禁快照
#   bash scripts/run-round.sh gate-baseline-c             # 采集前端基线门禁快照
#   bash scripts/run-round.sh gate-baseline-h5            # 采集 H5 基线门禁快照
#   bash scripts/run-round.sh gate-baseline-pcold         # 采集 legacy PC 基线门禁快照
#
# 参数:
#   <candidate-id>  候选 ID, 取 CANONICAL_ORDER 之一:
#                   B-01 F-01 F-02 F-03 F-04 F-06 F-08 F-09 F-10 R-01
#   <arm>           臂名, ssd (实验臂) 或 control (对照臂)
#
# 产出路径 (相对本仓根目录):
#   docs/efficacy/gates/<candidate>-<arm>.txt            单臂门禁日志
#   docs/efficacy/gates/baseline-<B|C|H5|PCOLD>-full.txt  基线门禁日志
#   docs/efficacy/rounds/<candidate>-<arm>.checklist.md   该臂的验收检查表
#   docs/efficacy/rounds/<candidate>-<arm>.review.txt     该臂的人工评审记录 (可选)
#   docs/efficacy/rounds/<candidate>-<arm>.measure.json   该臂的单轮观测量
#   docs/efficacy/round-state.json                        **可变**的轮次运行态 (不入冻结)
#   docs/efficacy/summary.json                           聚合结果 (SEI)
#
# 说明: FORMULA.md §8 把单轮观测量写作 `rounds/<round-id>.json`. 本脚本按臂
# 分文件 (`<candidate>-<arm>.measure.json`), 因为一轮有两臂, 且 measure.py
# aggregate 靠文件里的 round_id + arm 字段配对, 靠文件名配不了.
#
# 一次完整的轮次执行顺序:
#   1. bash scripts/run-round.sh init <candidate>
#   2. 两臂各自实施并提交到 exp/<candidate>/<arm>
#   3. bash scripts/run-round.sh gate <candidate> ssd
#   4. bash scripts/run-round.sh gate <candidate> control
#   5. 人工填写 docs/efficacy/rounds/<candidate>-<arm>.checklist.md
#   6. bash scripts/run-round.sh measure <candidate> ssd
#   7. bash scripts/run-round.sh measure <candidate> control
#   8. bash scripts/run-round.sh aggregate
#
# 路径覆盖 (环境变量, 便于在临时目录里试跑):
#   SSD_ROUND_DIR        单轮产物的目录, 默认 docs/efficacy/rounds
#   SSD_GATE_DIR        门禁日志的目录, 默认 docs/efficacy/gates
#   SSD_SUMMARY_OUT     聚合结果文件, 默认 docs/efficacy/summary.json
#   SSD_BASELINE_GATES   基线门禁快照 JSON, 默认 docs/efficacy/baseline-gates.json
#   SSD_ROUND_STATE      可变的轮次运行态 JSON, 默认 docs/efficacy/round-state.json
#   REPO_B REPO_C REPO_H5 REPO_PCOLD  四个业务仓的本地路径
#
# ## 冻结文件 vs 运行态
#
# `docs/efficacy/baseline-commits.json` 是**冻结文件**: 它的内容在第一轮实施
# 开始前一次性定死, 之后**只读**。任何命令都不得写它。
#
# `init` 需要记录「本轮两臂的起点 commit」, 这个状态是**运行态**, 不是冻结参数。
# 它落在 `docs/efficacy/round-state.json` (默认, 见 SSD_ROUND_STATE),
# 该文件**不进冻结提交**。这样 `baseline-commits.json` 在整个实验期内
# 保持字节不变, 冻结门禁可以用 `git diff --exit-code` 直接验它没被动过。
#
# 代价: `round-state.json` 是**派生**状态, 丢了可以由 `init` 重跑重建,
# 不影响任何评分的可复现性。起点 commit 本来就是 4 个硬编码常量。
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# **规格仓** = 本仓 (A, Wiki/Spec 仓)。SSD 臂的 PRD / TD / Plan 产在这里。
#
# 注意与 `merchandising-spec` 的区分 (两者完全不同的东西):
#   - **本仓** (A): SSD 工作流的**产出**仓。SSD 臂把 PRD/TD/Plan 写在这里,
#     所以 `T_spec_minutes` 从这里量。
#   - `merchandising-spec`: merchandising 项目的**需求真源**仓, 实验前只读。
#     它是**输入** (需求原文), 不是输出, 不参与 `T`。
SPEC_DIR="${SSD_SPEC_DIR:-$ROOT}"
# SSD 臂规格产出的**仓内相对目录**。按臂分目录, 否则无法归集耗时。
SPEC_REL_DIR="${SSD_SPEC_REL_DIR:-docs/efficacy/spec-output}"
REPO_B="${REPO_B:-/home/leroy/Project/merchandising-workspace/busyming-merchandising}"
REPO_C="${REPO_C:-/home/leroy/Project/merchandising-workspace/busyming-merchandising-vue-pc}"
REPO_H5="${REPO_H5:-/home/leroy/Project/merchandising-workspace/busyming-merchandising-h5}"
REPO_PCOLD="${REPO_PCOLD:-/home/leroy/Project/merchandising-workspace/busyming-merchandising-pc}"
GATE_DIR="${SSD_GATE_DIR:-$ROOT/docs/efficacy/gates}"
ROUND_DIR="${SSD_ROUND_DIR:-$ROOT/docs/efficacy/rounds}"
SUMMARY_OUT="${SSD_SUMMARY_OUT:-$ROOT/docs/efficacy/summary.json}"
BASELINE_GATES="${SSD_BASELINE_GATES:-$ROOT/docs/efficacy/baseline-gates.json}"
# 基线 flake 隔离清单 (FORMULA.md §3.4.9.4)。默认指向**冻结**的清单。
#
# 两臂必须用**同一份**清单, 否则那一轮两臂的 D 不可比 (FORMULA.md §3.4.9.3)。
# `measure.py aggregate` 会逐轮核对两臂记录的清单路径, 不同就拒绝聚合。
#
# 允许用环境变量覆盖只是为了方便复现实验, 但**不允许**给两臂不同的清单。
FLAKY_LIST="${SSD_FLAKY_LIST:-$ROOT/docs/efficacy/flaky-tests.json}"
# 可变的轮次运行态。**不**是冻结文件, 不进冻结提交。
ROUND_STATE="${SSD_ROUND_STATE:-$ROOT/docs/efficacy/round-state.json}"

# 冻结的实验设置 (v6)。与 docs/efficacy/baseline-commits.json 与
# docs/efficacy/CANDIDATES.md §2.2 同源, 三处必须一致。
#
# ROUND_ORDER 的每个数字是 CANONICAL_ORDER 的索引 (从 1 开始)。
# CANONICAL_ORDER 按候选 ID 升序。
SEED="20261118"
CANONICAL_ORDER=(B-01 F-01 F-02 F-03 F-04 F-06 F-08 F-09 F-10 R-01)
ROUND_ORDER=(3 7 1 9 4 2 8 5 10 6)
# ARM_ORDER 按执行序: S = 先跑 SSD 臂, C = 先跑对照臂
ARM_ORDER=(S C S C S C S C S C)

# 冻结基线 commit (与 docs/efficacy/baseline-gates.json 的采集 head 严格一致)。
# 硬编码而非取 master/HEAD, 避免基线漂移导致门禁差集失真。
FROZEN_BASE_B="688154d7cb1c2e61803d9b480027c34b65bfeb81"
FROZEN_BASE_C="59fdb7601e14802bca213276c7d03b9a9479d20f"
FROZEN_BASE_H5="bce76a00bc12813667ca75b2469914a771770fae"
FROZEN_BASE_PCOLD="1b7e3203ff9a98abe030247a84d049b14b30d9ca"

# 需求 -> 门禁范围映射 (模块级, 保证门禁可跑且覆盖该需求)
gate_scope_b() {
  case "$1" in
    F-03) echo "busyming-merchandising-api,busyming-merchandising-domain,busyming-merchandising-service" ;;
    F-04) echo "busyming-merchandising-service" ;;
    F-06) echo "busyming-merchandising-service" ;;
    B-01) echo "busyming-merchandising-service" ;;
    F-01|F-02|F-08|F-09|F-10|R-01) echo "" ;;
    *) echo "busyming-merchandising-api,busyming-merchandising-domain,busyming-merchandising-service,busyming-merchandising-web" ;;
  esac
}

gate_scope_c() {
  case "$1" in
    F-01) echo "src/modules/display-task-shelf/pages/inspection" ;;
    F-03) echo "src/modules/merchandising-template-manage/store-image-set-manage" ;;
    F-08) echo "src/modules/merchandising-template-manage/store-image-set-manage/components/StoreActualOperatingSkuNumDrawer" ;;
    B-01|F-02|F-04|F-06|F-09|F-10|R-01) echo "" ;;
    *) echo "src/modules" ;;
  esac
}

# vitest >= 4 移除了 `basic` reporter, 按仓内 vitest 主版本选 reporter。
# 返回 "basic" (vitest 2/3) 或 "dot" (vitest >=4)。
vitest_reporter() {
  local repo="$1" major
  major="$(node -e "try{console.log(require('$repo/node_modules/vitest/package.json').version.split('.')[0])}catch(e){console.log('2')}" 2>/dev/null)"
  if [[ "$major" =~ ^[0-9]+$ ]] && [[ "$major" -ge 4 ]]; then
    echo "dot"
  else
    echo "basic"
  fi
}

# H5 仓门禁范围 (vitest 路径前缀, 逗号分隔; 空 = 该轮不跑 H5 门禁)
gate_scope_h5() {
  case "$1" in
    F-02) echo "src/pages/organizeGoods/taskDetail" ;;
    F-09) echo "src/pages/organizeGoods/taskDetail" ;;
    R-01) echo "src/pages/organizeGoods/imageDetail" ;;
    *) echo "" ;;
  esac
}

# legacy PC 仓门禁范围 (vitest 路径前缀; 空 = 该轮不跑 legacy PC 门禁)
gate_scope_pcold() {
  case "$1" in
    F-10) echo "src/routes/storeDetail" ;;
    *) echo "" ;;
  esac
}

# 候选 -> 涉及仓标识 (空格分隔)。
# 这是「该候选改动落在哪些仓」的唯一真源, cmd_plan 的「涉及仓」列与
# cmd_measure 的测量范围都从这里取, 两者不会漂移。
# F-03 是唯一的跨仓候选 (B + C), 其余候选只涉及单仓。
candidate_repos() {
  case "$1" in
    B-01|F-04|F-06) echo "B" ;;
    F-01|F-08) echo "C" ;;
    F-02|F-09|R-01) echo "H5" ;;
    F-03) echo "B C" ;;
    F-10) echo "PCOLD" ;;
    *) echo "" ;;
  esac
}

# 仓标识 + 候选 -> 该仓在该候选上的门禁范围
gate_scope_of() {
  local alias="$1" cand="$2"
  case "$alias" in
    B) gate_scope_b "$cand" ;;
    C) gate_scope_c "$cand" ;;
    H5) gate_scope_h5 "$cand" ;;
    PCOLD) gate_scope_pcold "$cand" ;;
    *) echo "" ;;
  esac
}

# 仓标识 -> 业务仓本地路径
repo_path_of() {
  case "$1" in
    B) echo "$REPO_B" ;;
    C) echo "$REPO_C" ;;
    H5) echo "$REPO_H5" ;;
    PCOLD) echo "$REPO_PCOLD" ;;
    *) echo "" ;;
  esac
}

# 仓标识 -> 冻结基线 commit (与 baseline-gates.json 的采集 head 一致)
frozen_base_of() {
  case "$1" in
    B) echo "$FROZEN_BASE_B" ;;
    C) echo "$FROZEN_BASE_C" ;;
    H5) echo "$FROZEN_BASE_H5" ;;
    PCOLD) echo "$FROZEN_BASE_PCOLD" ;;
    *) echo "" ;;
  esac
}

cmd_init() {
  local rid="$1"
  validate_candidate "$rid"
  local base_b base_c base_h5 base_pcold
  base_b="$FROZEN_BASE_B"
  base_c="$FROZEN_BASE_C"
  base_h5="$FROZEN_BASE_H5"
  base_pcold="$FROZEN_BASE_PCOLD"

  echo "== 轮次 $rid =="
  echo "B 起点: $base_b"
  echo "C 起点: $base_c"
  echo "H5 起点: $base_h5"
  echo "PCOLD 起点: $base_pcold"

  # 基线 commit 必须与 baseline-gates.json 采集 head 一致, 否则门禁差集失真
  if ! git -C "$REPO_B" cat-file -e "$base_b^{commit}" 2>/dev/null; then
    echo "错误: B 仓不存在冻结基线 commit $base_b" >&2; exit 1
  fi
  if ! git -C "$REPO_C" cat-file -e "$base_c^{commit}" 2>/dev/null; then
    echo "错误: C 仓不存在冻结基线 commit $base_c" >&2; exit 1
  fi
  if ! git -C "$REPO_H5" cat-file -e "$base_h5^{commit}" 2>/dev/null; then
    echo "错误: H5 仓不存在冻结基线 commit $base_h5" >&2; exit 1
  fi
  if ! git -C "$REPO_PCOLD" cat-file -e "$base_pcold^{commit}" 2>/dev/null; then
    echo "错误: legacy PC 仓不存在冻结基线 commit $base_pcold" >&2; exit 1
  fi

  # 只在该候选真正涉及的仓里建分支 (候选 -> 仓的映射与 cmd_plan 同源)。
  local aliases; aliases="$(candidate_repos "$rid")"
  local alias repo base branch arm
  for arm in ssd control; do
    for alias in $aliases; do
      repo="$(repo_path_of "$alias")"
      base="$(frozen_base_of "$alias")"
      branch="exp/$rid/$arm"
      # 已实施过的分支不重置. 重置会毁掉该臂已有的提交。
      local current ahead
      current="$(git -C "$repo" rev-parse --verify --quiet "refs/heads/$branch^{commit}" 2>/dev/null || true)"
      if [[ -n "$current" ]]; then
        ahead="$(git -C "$repo" rev-list --count "$base..$current" 2>/dev/null || echo 0)"
        if [[ "$ahead" -ge 1 ]]; then
          echo "    $alias:$branch 已有 $ahead 个提交, 保留不动"
          continue
        fi
      fi
      git -C "$repo" branch -f "$branch" "$base" 2>/dev/null || true
      echo "    $alias:$branch -> $base"
    done
  done

  # 落两份共享检查表模板 (已存在的不覆盖)。
  cmd_checklist "$rid" ssd
  cmd_checklist "$rid" control

  # 记录起点 commit 到**运行态**文件 (不是冻结文件)。
  # `baseline-commits.json` 是冻结产物, 全程只读, 不得被任何命令改写。
  mkdir -p "$(dirname "$ROUND_STATE")"
  python3 - "$ROUND_STATE" "$rid" "$base_b" "$base_c" "$base_h5" "$base_pcold" <<'PY'
import json, os, sys
out, rid, base_b, base_c, base_h5, base_pcold = sys.argv[1:7]
data = {}
if os.path.isfile(out):
    with open(out, encoding="utf-8") as fh:
        data = json.load(fh)
data.setdefault("version", "v1")
data.setdefault("rounds", {})[rid] = {
    "B": base_b, "C": base_c, "H5": base_h5, "PCOLD": base_pcold,
}
with open(out, "w", encoding="utf-8") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
print(f"  起点已记录 -> {out}")
PY
}

# 切到某仓某臂的实验分支。
# 必须**硬失败**: checkout 失败 (工作区脏 / 分支不存在) 时若继续跑门禁,
# 日志里记的是另一个分支的结果, 后续 measure 会把错的门禁结果算进该臂。
checkout_arm() {
  local alias="$1" repo="$2" branch="$3"
  if ! git -C "$repo" rev-parse --verify --quiet "refs/heads/$branch^{commit}" >/dev/null 2>&1; then
    die "仓 $alias 缺少实验分支 $branch (先跑: bash scripts/run-round.sh init <candidate>)"
  fi
  if ! git -C "$repo" checkout -q "$branch"; then
    die "仓 $alias 无法切到 $branch (工作区可能有未提交改动)"
  fi
}

# 归档根目录。Python 侧与 bash 侧必须指向**同一个**地方:
# 之前 bash 打印 `SSD_ARCHIVE_DIR` 但 Python 写到默认路径, 于是
# 「打印的路径」与「实际写入的路径」不一致 —— measure.py 按打印的路径
# 去找归档, 必然找不到。路径只有一个来源: 环境变量传给 Python。
ARCHIVE_DIR="${SSD_ARCHIVE_DIR:-$ROOT/docs/efficacy/gates/archives}"
ARCHIVE_DIR="$(cd "$ARCHIVE_DIR" 2>/dev/null && pwd || echo "$ARCHIVE_DIR")"

# 把本轮本臂的门禁产物归档。写盘 + 逐文件 sha256 交给 Python 做
# (scripts/gate_archive.py), bash 只负责把各仓的日志段传过去。
#
# 归档失败 = 硬失败。没有归档就没有可信的 `D`, 与其出一个来路不明的
# 数字, 不如当场停。
#
# 日志段**直接写进规格文件** (不经过 shell 变量): 后端全量门禁的日志
# 有 72 MB (约 50 万行), 塞进变量再 `printf` 出去既浪费内存, 又可能
# 撞上 `ARG_MAX`。规格文件本来就是流式读的, 所以流式写才对。
#
# 段落的行号由 `gate_segment_write` 记录, 避免二次扫描整份日志。
archive_write() {
  local rid="$1" arm="$2" log="$3"
  local spec
  spec="$(mktemp)"
  {
    printf 'ROOT\t%s\n' "$ROOT"
    printf 'GATE_LOG\t%s\n' "$log"
    printf 'CAPTURED_AT\t%s\n' "$(date -Iseconds)"
    local alias start end cmd scope repo
    for alias in B C H5 PCOLD; do
      case "$alias" in
        B) start="$GATE_B_START"; end="$GATE_B_END"; cmd="$GATE_B_COMMAND"; scope="$GATE_B_SCOPE"; repo="$REPO_B" ;;
        C) start="$GATE_C_START"; end="$GATE_C_END"; cmd="$GATE_C_COMMAND"; scope="$GATE_C_SCOPE"; repo="$REPO_C" ;;
        H5) start="$GATE_H5_START"; end="$GATE_H5_END"; cmd="$GATE_H5_COMMAND"; scope="$GATE_H5_SCOPE"; repo="$REPO_H5" ;;
        PCOLD) start="$GATE_PCOLD_START"; end="$GATE_PCOLD_END"; cmd="$GATE_PCOLD_COMMAND"; scope="$GATE_PCOLD_SCOPE"; repo="$REPO_PCOLD" ;;
        *) continue ;;
      esac
      [[ -n "$start" && -n "$end" ]] || continue
      printf 'REPO\t%s\t%s\t%s\t%s\n' "$alias" "$repo" "$cmd" "$scope"
      printf 'SEGMENT_BEGIN\t%s\n' "$alias"
      sed -n "$((start + 1)),${end}p" "$log"
      printf 'SEGMENT_END\t%s\n' "$alias"
    done
  } > "$spec"
  if ! python3 "$ROOT/scripts/gate_archive.py" archive \
      --root "$ROOT" --round-id "$rid" --arm "$arm" --spec "$spec" \
      --archive-dir "$ARCHIVE_DIR"; then
    rm -f "$spec"
    die "门禁归档失败: $rid/$arm (没有归档就没有可信的 D, 测量中止)"
  fi
  rm -f "$spec"
}

cmd_gate() {
  local rid="$1" arm="$2"
  validate_candidate "$rid"
  validate_arm "$arm"
  mkdir -p "$GATE_DIR"
  local log="$GATE_DIR/$rid-$arm.txt"

  # 归档累积器: 每仓一段日志 + 命令 + 范围, 门禁跑完一次性归档。
  # 段落的**行号**记在 START/END (不把正文塞进变量), 见 archive_write。
  GATE_B_START=""; GATE_B_END=""; GATE_B_COMMAND=""; GATE_B_SCOPE=""
  GATE_C_START=""; GATE_C_END=""; GATE_C_COMMAND=""; GATE_C_SCOPE=""
  GATE_H5_START=""; GATE_H5_END=""; GATE_H5_COMMAND=""; GATE_H5_SCOPE=""
  GATE_PCOLD_START=""; GATE_PCOLD_END=""; GATE_PCOLD_COMMAND=""; GATE_PCOLD_SCOPE=""

  {
    echo "### 轮次 $rid / 臂 $arm 门禁日志"
    echo "### 时间: $(date -Iseconds)"
    echo ""
  } > "$log"

  # 后端门禁
  local scope_b; scope_b="$(gate_scope_b "$rid")"
  if [[ -n "$scope_b" ]]; then
    # 清理上一轮 surefire 报告, 否则 measure.py 会读到陈旧结果
    rm -rf "$REPO_B"/busyming-merchandising-*/target/surefire-reports 2>/dev/null || true
    echo "### [B] mvn -o -fae -Dmaven.test.failure.ignore=true test -pl $scope_b -am" >> "$log"
    checkout_arm B "$REPO_B" "exp/$rid/$arm"
    local b_start b_end
    b_start="$(wc -l < "$log")"
    # `set +e` 不可省: `set -e` 下 mvn 失败会让子shell 直接退出,
    # 下面的 `echo EXIT=$?` 就跑不到, 退出码就丢了。
    (
      cd "$REPO_B"
      set +e
      mvn -o -fae -Dmaven.test.failure.ignore=true test -pl "$scope_b" -am 2>&1
      echo "EXIT=$?"
    ) >> "$log" || true
    b_end="$(wc -l < "$log")"
    GATE_B_START="$b_start"; GATE_B_END="$b_end"
    GATE_B_COMMAND="mvn -o -fae -Dmaven.test.failure.ignore=true test -pl $scope_b -am"
    GATE_B_SCOPE="$scope_b"
    echo "" >> "$log"
  fi

  # 前端门禁
  local scope_c; scope_c="$(gate_scope_c "$rid")"
  if [[ -n "$scope_c" ]]; then
    local rep_c; rep_c="$(vitest_reporter "$REPO_C")"
    echo "### [C] npx vitest run $scope_c --reporter=$rep_c" >> "$log"
    checkout_arm C "$REPO_C" "exp/$rid/$arm"
    local c_start c_end
    c_start="$(wc -l < "$log")"
    (
      cd "$REPO_C"
      set +e
      npx vitest run $scope_c --reporter="$rep_c" 2>&1
      echo "EXIT=$?"
    ) >> "$log" || true
    c_end="$(wc -l < "$log")"
    GATE_C_START="$c_start"; GATE_C_END="$c_end"
    GATE_C_COMMAND="npx vitest run $scope_c --reporter=$rep_c"
    GATE_C_SCOPE="$scope_c"
    echo "" >> "$log"
  fi

  # H5 门禁
  local scope_h5; scope_h5="$(gate_scope_h5 "$rid")"
  if [[ -n "$scope_h5" ]]; then
    local rep_h5; rep_h5="$(vitest_reporter "$REPO_H5")"
    echo "### [H5] npx vitest run $scope_h5 --reporter=$rep_h5" >> "$log"
    checkout_arm H5 "$REPO_H5" "exp/$rid/$arm"
    local h5_start h5_end
    h5_start="$(wc -l < "$log")"
    (
      cd "$REPO_H5"
      set +e
      npx vitest run $scope_h5 --reporter="$rep_h5" 2>&1
      echo "EXIT=$?"
    ) >> "$log" || true
    h5_end="$(wc -l < "$log")"
    GATE_H5_START="$h5_start"; GATE_H5_END="$h5_end"
    GATE_H5_COMMAND="npx vitest run $scope_h5 --reporter=$rep_h5"
    GATE_H5_SCOPE="$scope_h5"
    echo "" >> "$log"
  fi

  # legacy PC 门禁
  local scope_pcold; scope_pcold="$(gate_scope_pcold "$rid")"
  if [[ -n "$scope_pcold" ]]; then
    local rep_pcold; rep_pcold="$(vitest_reporter "$REPO_PCOLD")"
    echo "### [PCOLD] npx vitest run $scope_pcold --reporter=$rep_pcold" >> "$log"
    checkout_arm PCOLD "$REPO_PCOLD" "exp/$rid/$arm"
    local p_start p_end
    p_start="$(wc -l < "$log")"
    (
      cd "$REPO_PCOLD"
      set +e
      npx vitest run $scope_pcold --reporter="$rep_pcold" 2>&1
      echo "EXIT=$?"
    ) >> "$log" || true
    p_end="$(wc -l < "$log")"
    GATE_PCOLD_START="$p_start"; GATE_PCOLD_END="$p_end"
    GATE_PCOLD_COMMAND="npx vitest run $scope_pcold --reporter=$rep_pcold"
    GATE_PCOLD_SCOPE="$scope_pcold"
    echo "" >> "$log"
  fi

  # **归档**: 把本轮本臂的门禁产物 + 归属元数据落盘。
  #
  # 为什么必须在这里 (门禁跑完**立刻**) 做: 后端仓的
  # `<module>/target/surefire-reports` 是**跨臂共享**的, 下一臂的门禁
  # 会覆盖它。旧的实现在测量时刻才去读那个目录, 于是所有臂都读到
  # **最后一臂**的 XML —— 这已经污染过一次完整演练。
  #
  # 归档失败必须**硬失败**: 没有归档就没有可信的 `D`。
  archive_write "$rid" "$arm" "$log"

  echo "  门禁日志 -> $log"
  echo "  门禁归档 -> $ARCHIVE_DIR/$rid/$arm"
}

# ============================================================
# 基线门禁采集
#
# 关键约束: 基线快照 **必须在冻结基线 SHA 上采集**, 否则 §3.4 的门禁差分失真
# (会把基线本身的失败误判成某臂引入的新失败)。
#
# 实现方式: 用 `git worktree add --detach` 在 **冻结 SHA** 上开一个独立工作树,
# 门禁只在该工作树里跑, 业务仓的当前 HEAD 完全不受影响。
# ============================================================

# 报错并退出。所有子命令共用, 保证失败路径的退出码是 1。
die() {
  echo "错误: $*" >&2
  exit 1
}

# 校验候选 ID 在冻结清单里。
validate_candidate() {
  local cand="$1" c
  for c in "${CANONICAL_ORDER[@]}"; do
    if [[ "$c" == "$cand" ]]; then
      return 0
    fi
  done
  die "未知候选 ID: $cand (可用: ${CANONICAL_ORDER[*]})"
}

# 校验臂名。
validate_arm() {
  case "$1" in
    ssd|control) return 0 ;;
    *) die "未知臂名: $1 (可用: ssd | control)" ;;
  esac
}

# 为某仓在冻结 SHA 上准备一个只读工作树, 打印工作树路径。
# 已存在则复用 (不重建, 避免重复安装依赖), 但必须核对它确实停在冻结 SHA 上:
# 工作树是 detached 的, 人为 checkout 会让它偏离, 偏离后基线门禁就失真了。
prepare_baseline_worktree() {
  local repo="$1" sha="$2" wt="$3" head
  if ! git -C "$repo" cat-file -e "$sha^{commit}" 2>/dev/null; then
    echo "错误: $repo 不存在冻结基线 commit $sha" >&2
    return 1
  fi
  if [[ ! -d "$wt" ]]; then
    git -C "$repo" worktree add --detach "$wt" "$sha" >&2 || return 1
  fi
  head="$(git -C "$wt" rev-parse --verify --quiet HEAD 2>/dev/null || true)"
  if [[ "$head" != "$sha" ]]; then
    echo "错误: 基线工作树 $wt 当前在 ${head:-<无>}, 不是冻结基线 $sha" >&2
    echo "      请先 git -C $wt checkout --detach $sha, 或删掉该目录后重跑" >&2
    return 1
  fi
  echo "$wt"
}

# 后端基线: 跑一次全部 spec, 记录失败集
cmd_gate_baseline_b() {
  local log="$GATE_DIR/baseline-B-full.txt"
  local wt
  wt="$(prepare_baseline_worktree "$REPO_B" "$FROZEN_BASE_B" "${JCODE_SCRATCH_DIR:-/tmp}/ssd-gate-wt/B")" || return 1
  {
    echo "### 后端基线门禁日志 (v4, 冻结基线)"
    echo "### 时间: $(date -Iseconds)"
    echo "### HEAD: $FROZEN_BASE_B"
    echo ""
  } > "$log"
  echo "### [B] mvn -o -fae -Dmaven.test.failure.ignore=true test" >> "$log"
  (
    cd "$wt"
    mvn -o -fae -Dmaven.test.failure.ignore=true test 2>&1
  ) >> "$log" || true
  echo "  基线日志 -> $log"
}

# 前端基线: 跑一次全部 spec, 记录失败集
cmd_gate_baseline_c() {
  local log="$GATE_DIR/baseline-C-full.txt"
  local wt
  wt="$(prepare_baseline_worktree "$REPO_C" "$FROZEN_BASE_C" "${JCODE_SCRATCH_DIR:-/tmp}/ssd-gate-wt/C")" || return 1
  {
    echo "### 前端基线门禁日志 (v4, 冻结基线)"
    echo "### 时间: $(date -Iseconds)"
    echo "### HEAD: $FROZEN_BASE_C"
    echo ""
  } > "$log"
  echo "### [C] npx vitest run" >> "$log"
  (
    cd "$wt"
    npx vitest run --reporter="$(vitest_reporter "$REPO_C")" 2>&1
  ) >> "$log" || true
  echo "  基线日志 -> $log"
}

# H5 基线: 跑一次全部 spec, 记录失败集
cmd_gate_baseline_h5() {
  local log="$GATE_DIR/baseline-H5-full.txt"
  local wt
  wt="$(prepare_baseline_worktree "$REPO_H5" "$FROZEN_BASE_H5" "${JCODE_SCRATCH_DIR:-/tmp}/ssd-gate-wt/H5")" || return 1
  {
    echo "### H5 基线门禁日志 (v4, 冻结基线)"
    echo "### 时间: $(date -Iseconds)"
    echo "### HEAD: $FROZEN_BASE_H5"
    echo ""
  } > "$log"
  echo "### [H5] npx vitest run" >> "$log"
  (
    cd "$wt"
    npx vitest run --reporter="$(vitest_reporter "$REPO_H5")" 2>&1
  ) >> "$log" || true
  echo "  基线日志 -> $log"
}

# legacy PC 基线: 跑一次全部 spec, 记录失败集
cmd_gate_baseline_pcold() {
  local log="$GATE_DIR/baseline-PCOLD-full.txt"
  local wt
  wt="$(prepare_baseline_worktree "$REPO_PCOLD" "$FROZEN_BASE_PCOLD" "${JCODE_SCRATCH_DIR:-/tmp}/ssd-gate-wt/PCOLD")" || return 1
  {
    echo "### legacy PC 基线门禁日志 (v4, 冻结基线)"
    echo "### 时间: $(date -Iseconds)"
    echo "### HEAD: $FROZEN_BASE_PCOLD"
    echo ""
  } > "$log"
  echo "### [PCOLD] npx vitest run" >> "$log"
  (
    cd "$wt"
    npx vitest run --reporter="$(vitest_reporter "$REPO_PCOLD")" 2>&1
  ) >> "$log" || true
  echo "  基线日志 -> $log"
}

# 打印用法
cmd_help() {
  cat <<EOF
用法: bash scripts/run-round.sh <子命令> [参数]

子命令:
  plan                        打印冻结执行计划 (只读, 不做任何改动)
  init <candidate-id>         准备某候选的两臂分支, 并落一份共享检查表模板
  checklist <candidate-id> <arm>
                              为某臂复制一份共享检查表模板 (目标已存在时不覆盖)
  gate <candidate-id> <arm>   跑某臂门禁, 日志存到 docs/efficacy/gates/
  measure <candidate-id> <arm>
                              测量某臂, 结果存到 docs/efficacy/rounds/
  aggregate                   聚合并算 SEI, 结果存到 docs/efficacy/summary.json
  gate-baseline-b             采集后端基线门禁快照
  gate-baseline-c             采集前端基线门禁快照
  gate-baseline-h5            采集 H5 基线门禁快照
  gate-baseline-pcold         采集 legacy PC 基线门禁快照

参数:
  <candidate-id>  候选 ID, 取 CANONICAL_ORDER 之一:
                  ${CANONICAL_ORDER[*]}
  <arm>           臂名, ssd (实验臂) 或 control (对照臂)

产出路径:
  docs/efficacy/gates/<candidate>-<arm>.txt            单臂门禁日志
  docs/efficacy/gates/baseline-<B|C|H5|PCOLD>-full.txt  基线门禁日志
  docs/efficacy/rounds/<candidate>-<arm>.checklist.md   该臂的验收检查表
  docs/efficacy/rounds/<candidate>-<arm>.review.txt     该臂的人工评审记录 (可选)
  docs/efficacy/rounds/<candidate>-<arm>.measure.json   该臂的单轮观测量
  docs/efficacy/summary.json                           聚合结果 (SEI)
EOF
}

# ============================================================
# 单轮测量与聚合
#
# 口径 (docs/efficacy/FORMULA.md §3):
#   - 每臂一份单轮观测量 JSON, 全部落在同一个扁平目录 ROUND_DIR 下;
#   - 聚合读的就是这个目录里的全部 .json (measure.py aggregate 不递归),
#     所以观测量、检查表、评审记录共用一个目录, 只有观测量是 .json。
# ============================================================

# 校验某仓某臂的实验分支, 把 head SHA 与超出基线的提交数写进全局变量
# RESOLVED_SHA / RESOLVED_AHEAD (不用 stdout 传值, 避免命令替换吃掉错误信息)。
# 四项校验 (全部只读, 不改动业务仓):
#   1. 分支存在;
#   2. head 解析为真实 commit;
#   3. 基于冻结基线 (冻结基线是 head 的祖先);
#   4. 相对冻结基线至少有一个提交 (该臂确实实施过)。
resolve_arm_head() {
  local alias="$1" cand="$2" arm="$3"
  local repo base branch sha ahead
  repo="$(repo_path_of "$alias")"
  base="$(frozen_base_of "$alias")"
  branch="exp/$cand/$arm"
  RESOLVED_SHA=""
  RESOLVED_AHEAD=0

  if [[ ! -d "$repo" ]]; then
    die "仓 $alias 的本地路径不存在: $repo"
  fi
  if ! git -C "$repo" cat-file -e "$base^{commit}" 2>/dev/null; then
    die "仓 $alias 不存在冻结基线 commit $base"
  fi
  sha="$(git -C "$repo" rev-parse --verify --quiet "refs/heads/$branch^{commit}" 2>/dev/null || true)"
  if [[ -z "$sha" ]]; then
    die "仓 $alias 缺少实验分支 $branch (先跑: bash scripts/run-round.sh init $cand)"
  fi
  if ! git -C "$repo" cat-file -e "$sha^{commit}" 2>/dev/null; then
    die "仓 $alias 的 $branch 的 head 不是真实 commit: $sha"
  fi
  if ! git -C "$repo" merge-base --is-ancestor "$base" "$sha"; then
    die "仓 $alias 的 $branch 不基于冻结基线 $base (该臂起点被改动过)"
  fi
  ahead="$(git -C "$repo" rev-list --count "$base..$sha")"
  if [[ "$ahead" -lt 1 ]]; then
    die "仓 $alias 的 $branch 相对冻结基线 $base 没有新提交 (该臂未实施)"
  fi
  RESOLVED_SHA="$sha"
  RESOLVED_AHEAD="$ahead"
}

# 测量单臂。
# 只读业务仓 (git rev-parse / cat-file / merge-base / rev-list), 不切分支、不建提交。
cmd_measure() {
  local cand="$1" arm="$2"
  validate_candidate "$cand"
  validate_arm "$arm"

  local aliases
  aliases="$(candidate_repos "$cand")"
  if [[ -z "$aliases" ]]; then
    die "候选 $cand 没有关联的业务仓"
  fi

  local checklist="$ROUND_DIR/$cand-$arm.checklist.md"
  local gate_log="$GATE_DIR/$cand-$arm.txt"
  local review="$ROUND_DIR/$cand-$arm.review.txt"
  local out="$ROUND_DIR/$cand-$arm.measure.json"

  [[ -f "$checklist" ]] || die "缺少检查表: $checklist (先跑: bash scripts/run-round.sh checklist $cand $arm, 再人工填写)"
  [[ -f "$gate_log" ]] || die "缺少门禁日志: $gate_log (先跑: bash scripts/run-round.sh gate $cand $arm)"
  [[ -f "$BASELINE_GATES" ]] || die "缺少基线门禁快照: $BASELINE_GATES (门禁差分的前提)"

  # 逐仓解析并校验实验分支, 同时拼出 measure.py 需要的两个映射。
  # 多仓候选 (F-03) 必须每仓各自的起点/终点, 故用 --repo-ranges。
  local repo_paths="" repo_ranges=""
  local primary_alias="" primary_path="" primary_base="" primary_sha=""
  local alias repo base sha
  for alias in $aliases; do
    repo="$(repo_path_of "$alias")"
    base="$(frozen_base_of "$alias")"
    resolve_arm_head "$alias" "$cand" "$arm"
    sha="$RESOLVED_SHA"
    repo_paths="${repo_paths}${repo_paths:+,}$alias=$repo"
    repo_ranges="${repo_ranges}${repo_ranges:+,}$alias=$base:$sha"
    if [[ -z "$primary_alias" ]]; then
      primary_alias="$alias"
      primary_path="$repo"
      primary_base="$base"
      primary_sha="$sha"
    fi
    echo "  分支已校验: $alias exp/$cand/$arm = $sha (基线 $base, 超出 $RESOLVED_AHEAD 个提交)"
  done

  # 预校验: 填写稿必须只改了勾选/锚点/NA, 否则测量结果不可信。
  python3 "$ROOT/scripts/measure.py" checklist \
    --candidate "$cand" --checklist "$checklist" \
    || die "检查表与共享模板不一致, 测量中止"

  # **归档根目录必须同时传给测量**。
  #
  # 归档写在 `ARCHIVE_DIR` (可能被 `SSD_ARCHIVE_DIR` 覆盖), 而 measure.py
  # 默认去 `<root>/docs/efficacy/gates/archives` 找。两边不一致时,
  # 测量会报「归档缺失」而中止。或者更糟, 读到**上一次**留在默认
  # 路径里的旧归档 (跨臂污染的老毛病)。
  #
  # 路径只有一个来源: 上面解析出来的 `ARCHIVE_DIR`。
  local archive_arg=(--archive-root "$ARCHIVE_DIR")

  local argv=(
    round
    --round-id "$cand"
    --arm "$arm"
    --repo "$primary_alias"
    --repo-path "$primary_path"
    --baseline "$primary_base"
    --head "$primary_sha"
    --repo-paths "$repo_paths"
    --repo-ranges "$repo_ranges"
    --checklist "$checklist"
    --gate-log "$gate_log"
    --baseline-gates "$BASELINE_GATES"
    --flaky-list "$FLAKY_LIST"
    --out "$out"
  )
  argv+=("${archive_arg[@]}")
  # **规格仓耗时** (SSD 臂的 PRD / TD / Plan 产出)。
  #
  # 不传这个参数, `T_spec_minutes` 恒为 0, 于是 `T` 只量代码提交跨度 ——
  # SSD 臂的流程成本整段被抹掉, `TR` 被压低, `SI` 被抬高。方向不利,
  # 所以**必须**传。
  #
  # 对照臂也传同一组参数 (同一个仓、同一个相对目录前缀), 只是它不产规格,
  # 那个目录没有提交 → `T_spec_minutes` 自然为 0。口径对称。
  argv+=(--spec-repo "$SPEC_DIR" --spec-rel-dir "$SPEC_REL_DIR")
  if [[ -f "$review" ]]; then
    argv+=(--review-findings "$review")
    echo "  评审记录: $review"
  fi

  mkdir -p "$ROUND_DIR"
  python3 "$ROOT/scripts/measure.py" "${argv[@]}"

  # A_del = 0 时 DR 为空, 聚合时该轮不参与配对。显式告警, 避免静默失效。
  python3 - "$out" <<'PY'
import json, os, sys
p = sys.argv[1]
with open(p, encoding="utf-8") as fh:
    d = json.load(fh)
obs = d.get("observations", {})
if obs.get("A_del", 0) == 0:
    print("[警告] 该臂 A_del = 0 (检查表没有勾选任何 AC), "
          "DR 为空, 聚合时该轮不参与配对", file=sys.stderr)
PY
  echo "  单轮观测量 -> $out"
}

# 聚合并算 SEI。
# measure.py aggregate 读的是目录里的全部 .json, 不递归, 因此这里先校验
# 目录里没有混入非观测量 JSON, 避免 measure.py 内部 KeyError。
cmd_aggregate() {
  [[ -d "$ROUND_DIR" ]] || die "轮次目录不存在: $ROUND_DIR"
  python3 - "$ROUND_DIR" <<'PY'
import json, os, sys
d = sys.argv[1]
bad = []
n = 0
for f in sorted(os.listdir(d)):
    if not f.endswith(".json"):
        continue
    p = os.path.join(d, f)
    try:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        bad.append(f"{f}: 不是合法 JSON ({exc})")
        continue
    if not isinstance(data, dict) or "round_id" not in data or "arm" not in data:
        bad.append(f"{f}: 不是单轮观测量 (缺 round_id / arm)")
        continue
    n += 1
if bad:
    print("轮次目录里混入了非观测量 JSON, 聚合中止:", file=sys.stderr)
    for b in bad:
        print(f"  - {b}", file=sys.stderr)
    sys.exit(1)
if n == 0:
    print(f"轮次目录里没有任何单轮观测量 JSON: {d}", file=sys.stderr)
    sys.exit(1)
print(f"  待聚合观测量: {n} 份")
PY
  mkdir -p "$(dirname "$SUMMARY_OUT")"
  python3 "$ROOT/scripts/measure.py" aggregate --rounds "$ROUND_DIR" --out "$SUMMARY_OUT"
  echo "  聚合结果 -> $SUMMARY_OUT"
}

# 为某臂复制一份共享检查表模板。
# 目标已存在时**不覆盖**. 已填写的检查表是这一臂的观测记录, 覆盖即毁证据。
#
# 复制前先校验模板与当前 RUBRIC.md 一致 (measure.py 的 checklist 子命令):
# RUBRIC.md 改动后磁盘上的模板会变旧, 旧模板填写出来的稿子无法通过
# measure.py 的校验, 到 measure 阶段才发现会浪费一整轮实施。
cmd_checklist() {
  local cand="$1" arm="$2"
  validate_candidate "$cand"
  validate_arm "$arm"
  local tpl="$ROOT/docs/efficacy/checklists/$cand.checklist.md"
  local dst="$ROUND_DIR/$cand-$arm.checklist.md"
  [[ -f "$tpl" ]] || die "缺少共享检查表模板: $tpl (先跑: python3 scripts/gen-checklists.py)"

  # 模板与 RUBRIC.md 不一致时硬失败, 并给出重新生成命令。
  # measure.py 的详细差异输出重定向到 /dev/null, 只留本脚本的可执行提示。
  if ! python3 "$ROOT/scripts/measure.py" checklist --candidate "$cand" --checklist "$tpl" >/dev/null 2>&1; then
    die "共享检查表模板与 RUBRIC.md 不一致: $tpl (先跑: python3 scripts/gen-checklists.py, 再重试)"
  fi

  if [[ -f "$dst" ]]; then
    echo "  检查表已存在, 不覆盖: $dst"
    return 0
  fi
  mkdir -p "$ROUND_DIR"
  cp "$tpl" "$dst"
  echo "  检查表模板已复制: $tpl -> $dst"
}

# 打印冻结的执行计划 (轮次 -> 候选 -> 首跑臂 -> 涉及仓 -> 门禁范围)
# 不做任何改动, 只读。用于执行前核对与 docs/efficacy/CANDIDATES.md §2.2 是否一致。
cmd_plan() {
  echo "== 冻结执行计划 (v4) =="
  echo "SEED: $SEED"
  echo "ROUND_ORDER (规范序索引): ${ROUND_ORDER[*]}"
  echo "ARM_ORDER: ${ARM_ORDER[*]}"
  echo "CANONICAL_ORDER: ${CANONICAL_ORDER[*]}"
  echo ""
  printf "%-5s %-5s %-8s %-6s %-28s %s\n" "轮次" "索引" "候选" "首跑臂" "涉及仓" "门禁范围"
  local i idx cand arm
  for i in "${!ROUND_ORDER[@]}"; do
    idx="${ROUND_ORDER[$i]}"
    cand="${CANONICAL_ORDER[$((idx - 1))]}"
    arm="${ARM_ORDER[$i]}"
    local repos="" scopes="" sep="" sep2=""
    local alias scope
    for alias in $(candidate_repos "$cand"); do
      scope="$(gate_scope_of "$alias" "$cand")"
      [[ -z "$scope" ]] && continue
      repos="${repos}${sep}${alias}"; sep="+"
      scopes="${scopes}${sep2}${alias}: ${scope}"; sep2=" | "
    done
    printf "%-5s %-5s %-8s %-6s %-28s %s\n" "$((i + 1))" "$idx" "$cand" "$arm" "$repos" "$scopes"
  done
  echo ""
  echo "起点 commit (两臂共用):"
  echo "  B:     $FROZEN_BASE_B"
  echo "  C:     $FROZEN_BASE_C"
  echo "  H5:    $FROZEN_BASE_H5"
  echo "  PCOLD: $FROZEN_BASE_PCOLD"
}

case "${1:-}" in
  plan) cmd_plan ;;
  init) cmd_init "${2:?需要候选 ID}" ;;
  checklist) cmd_checklist "${2:?需要候选 ID}" "${3:?需要臂名}" ;;
  gate) cmd_gate "${2:?需要候选 ID}" "${3:?需要臂名}" ;;
  measure) cmd_measure "${2:?需要候选 ID}" "${3:?需要臂名}" ;;
  aggregate) cmd_aggregate ;;
  gate-baseline-b) cmd_gate_baseline_b ;;
  gate-baseline-c) cmd_gate_baseline_c ;;
  gate-baseline-h5) cmd_gate_baseline_h5 ;;
  gate-baseline-pcold) cmd_gate_baseline_pcold ;;
  help|-h|--help) cmd_help ;;
  *) echo "用法: $0 plan | $0 init <candidate-id> | $0 checklist <candidate-id> <arm> | $0 gate <candidate-id> <arm> | $0 measure <candidate-id> <arm> | $0 aggregate | $0 gate-baseline-{b,c,h5,pcold}" >&2; exit 2 ;;
esac
