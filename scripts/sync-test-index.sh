#!/usr/bin/env bash
# sync-test-index.sh — 再生成 test_cases/_index.md 索引表（幂等）
#
# 扫描 test_cases/{date}/ 下全部主用例/冒烟文档的「元信息」表，
# 在 _index.md 标记块内再生成索引表。数据唯一真理源 = 各文档元信息。
#
# 背景 (2026-08-06 机制建设):
#   旧机制要求 step6 手工追加索引行且「不删已有记录」→ 必然漂移
#   (曾出现幽灵批次 2026-07-31 五行 / 错日期归属 / 死链)。
#   现改为机器再生成，标记块内手改会被覆盖。
#
# 排序: 按 (批次日期, topic, 主用例先于冒烟) 排序。
#
# 用法:
#   ./scripts/sync-test-index.sh           # 再生成 _index.md
#   ./scripts/sync-test-index.sh --check   # 只比对差异，有差异 exit 1（不写文件）
#
# 退出码: 0=一致/已更新 1=--check 发现差异 2=调用错误

set -uo pipefail
export LC_ALL="${LC_ALL:-C.UTF-8}"

INDEX="test_cases/_index.md"
BEGIN_MARK="<!-- test-index:begin — 由 scripts/sync-test-index.sh 自动生成，勿手改 -->"
END_MARK="<!-- test-index:end -->"

if [[ ! -d test_cases ]]; then
  echo "✗ test_cases/ 不存在，请从仓库根目录运行" >&2
  exit 2
fi

# 从文档元信息表取字段值（首行匹配）
meta_field() {
  local f="$1" k="$2"
  awk -F'|' -v k="$k" '/^\|/ {
    key=$2; val=$3;
    gsub(/^[ \t]+|[ \t]+$/, "", key); gsub(/^[ \t]+|[ \t]+$/, "", val);
    if (key==k) { print val; exit }
  }' "$f"
}

keys=()
vals=()

while IFS= read -r f; do
  base="$(basename "$f" .md)"
  [[ "$base" == *-key-points ]] && continue
  date_dir="$(basename "$(dirname "$f")")"
  rel="${date_dir}/${base}.md"

  if [[ "$base" == *-smoke ]]; then
    topic="${base%-smoke}"
    is_smoke=1
  else
    topic="$base"
    is_smoke=0
  fi

  subject=$(meta_field "$f" "主题")
  [[ -z "$subject" ]] && subject="$topic"
  biz=$(meta_field "$f" "业务产品")
  plat=$(meta_field "$f" "目标平台")
  total_line=$(meta_field "$f" "用例总数")
  n=$(printf '%s' "$total_line" | grep -oE '^[0-9]+' || true)
  [[ -z "$n" ]] && n="?"
  if printf '%s' "$total_line" | grep -q '全部 P0'; then
    p0="$n"
  else
    p0=$(printf '%s' "$total_line" | sed -nE 's/.*P0: ?([0-9]+).*/\1/p')
    [[ -z "$p0" ]] && p0="0"
  fi
  st=$(meta_field "$f" "状态")

  kp_rel="${date_dir}/${topic}-key-points.md"
  if [[ -f "test_cases/$kp_rel" ]]; then
    kp_link="[key-points](${kp_rel})"
  else
    kp_link="—"
  fi

  keys+=("${date_dir}/${topic}/${is_smoke}")
  vals+=("| ${date_dir} | ${subject} | ${biz} | ${plat} | ${n} | ${p0} | ${st} | [${base}.md](${rel}) | ${kp_link} |")
done < <(find test_cases -mindepth 2 -maxdepth 2 -type f -name '*.md' ! -name '*-key-points.md' 2>/dev/null | sort)

generate_block() {
  echo "$BEGIN_MARK"
  echo "| 日期 | 主题 | 业务产品 | 平台 | 用例数 | P0 | 状态 | 用例文件 | 要点文件 |"
  echo "|------|------|---------|------|--------|----|----|---------|--------|"
  if [[ ${#keys[@]} -gt 0 ]]; then
    while IFS= read -r k; do
      for i in "${!keys[@]}"; do
        if [[ "${keys[$i]}" == "$k" ]]; then
          echo "${vals[$i]}"
          break
        fi
      done
    done < <(printf '%s\n' "${keys[@]}" | sort)
  fi
  echo "$END_MARK"
}

generate_file() {
  echo "# 测试用例索引"
  echo
  echo "> 由 \`scripts/sync-test-index.sh\` 自动生成（标记块内勿手改）。数据源：各用例文档元信息表。"
  echo "> 伴生要点文件不单独登记。"
  echo
  generate_block
}

if [[ "${1:-}" == "--check" ]]; then
  tmp=$(mktemp)
  generate_file > "$tmp"
  if [[ ! -f "$INDEX" ]]; then
    echo "✗ $INDEX 不存在（运行 ./scripts/sync-test-index.sh 生成）" >&2
    rm -f "$tmp"
    exit 1
  fi
  if ! diff -u "$INDEX" "$tmp"; then
    echo "✗ $INDEX 与文档元信息不一致，运行 ./scripts/sync-test-index.sh 再生成" >&2
    rm -f "$tmp"
    exit 1
  fi
  rm -f "$tmp"
  echo "✓ $INDEX 与文档元信息一致"
  exit 0
fi

generate_file > "$INDEX"
count=${#keys[@]}
echo "✓ $INDEX 已再生成（$count 行）"
