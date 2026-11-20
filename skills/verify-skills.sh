#!/usr/bin/env bash
# Skills-lane verification sweep.
#
# Sweeps:
#   A  every scripts/<name> referenced in skills/ exists in scripts/
#   B  every section reference (§N / §N.M) in skills/ resolves to an AGENTS.md heading
#   C  per-file section reference usage (informational)
#   D  every <repo>/... cross-reference target exists
#   E  Tech Design generation wording (v4 default, v3 explicit opt-in)
#   F  zero business-domain terms in skills/
#   G  zero em dashes (U+2014) in skills/
#   H  frontmatter key parity across all skills
#
# NOTE: this file is excluded from its own scans, so it may legitimately
#       contain the very literals it looks for.
#
# Usage: bash skills/verify-skills.sh
# Exit: 0 = all checks pass, 1 = at least one violation

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; NC=$'\033[0m'
FAIL=0

# Scan targets: everything under skills/ except this script.
scan() { rg --glob "!verify-skills.sh" "$@" skills/ 2>/dev/null; }

echo "=============================================="
echo " Skills verification sweep"
echo " repo: $REPO_ROOT"
echo "=============================================="
echo ""

# ---------------------------------------------------------------
# Sweep A: script references
# ---------------------------------------------------------------
echo "--- Sweep A: scripts/*.sh referenced in skills/ ---"

mapfile -t REFS < <(
  scan -o --no-filename 'scripts/[A-Za-z0-9_.-]+\.(sh|py)' | sort -u
)

if [[ ${#REFS[@]} -eq 0 ]]; then
  echo -e "${YELLOW}○${NC} no scripts/ references found under skills/"
else
  for ref in "${REFS[@]}"; do
    if [[ -f "$ref" ]]; then
      echo -e "${GREEN}✓${NC} $ref  (exists)"
    else
      echo -e "${RED}✗${NC} $ref  (DANGLING - not found in repo)"
      FAIL=1
    fi
  done
fi
echo ""

# ---------------------------------------------------------------
# Sweep B: section references (§N / §N.M) vs AGENTS.md headings
# ---------------------------------------------------------------
echo "--- Sweep B: §N.M section references vs AGENTS.md headings ---"

mapfile -t HEADINGS < <(
  rg -o '^#{2,4} [0-9]+(\.[0-9]+)*' AGENTS.md \
    | sed -E 's/^#+ //' \
    | sed -E 's/[[:space:]].*$//' \
    | sort -u
)

echo "AGENTS.md heading numbers found:"
printf '  %s\n' "${HEADINGS[@]}"
echo ""

mapfile -t SECS < <(
  scan -o --no-filename '§[0-9]+(\.[0-9]+)*' | sed 's/^§//' | sort -u
)

if [[ ${#SECS[@]} -eq 0 ]]; then
  echo -e "${YELLOW}○${NC} no section references found under skills/"
else
  for sec in "${SECS[@]}"; do
    # Strict: the section number must exist as an AGENTS.md heading number.
    # A subsection (§1.5) is NOT satisfied by the parent heading (§1).
    if printf '%s\n' "${HEADINGS[@]}" | grep -qxF "$sec"; then
      echo -e "${GREEN}✓${NC} §$sec  (resolves to AGENTS.md heading)"
    else
      echo -e "${RED}✗${NC} §$sec  (DANGLING - no AGENTS.md heading '$sec')"
      FAIL=1
    fi
  done
fi
echo ""

# ---------------------------------------------------------------
# Sweep C: per-file breakdown of section refs (informational)
# ---------------------------------------------------------------
echo "--- Sweep C: per-file section reference usage ---"
scan -o --with-filename '§[0-9]+(\.[0-9]+)*' \
  | awk -F: '{print $1}' | sort | uniq -c | sort -rn
echo ""

# ---------------------------------------------------------------
# Sweep D: <repo>/path cross-references must exist
# ---------------------------------------------------------------
echo "--- Sweep D: <repo>/... cross-reference targets exist ---"

mapfile -t XREFS < <(
  scan -o --no-filename '<repo>/[A-Za-z0-9_./-]+' \
    | sed 's|^<repo>/||' \
    | grep -vE '^\.\.\.$|^path$' \
    | sort -u
)

if [[ ${#XREFS[@]} -eq 0 ]]; then
  echo -e "${YELLOW}○${NC} no <repo>/... cross-references found under skills/"
else
  for xref in "${XREFS[@]}"; do
    if [[ -e "$xref" ]]; then
      echo -e "${GREEN}✓${NC} <repo>/$xref  (exists)"
    else
      echo -e "${RED}✗${NC} <repo>/$xref  (DANGLING - not found in repo)"
      FAIL=1
    fi
  done
fi
echo ""

# ---------------------------------------------------------------
# Sweep E: Tech Design generation defaults (v4 default, v3 opt-in)
# ---------------------------------------------------------------
echo "--- Sweep E: Tech Design generation wording ---"

# E1: forbidden phrases. v3 must never be the default, v4 must never be opt-in.
# Adjacent quoted strings concatenate at parse time, so the file on disk never
# contains the searched literals as contiguous text.
BAD_DEFAULT_V3="默认 ""v3"
BAD_OPTIN_V4="opt-in ""v4"
if scan -q -F "$BAD_DEFAULT_V3" || scan -q -F "$BAD_OPTIN_V4"; then
  echo -e "${RED}✗${NC} forbidden generation phrasing found:"
  scan -n -F -e "$BAD_DEFAULT_V3" -e "$BAD_OPTIN_V4" | sed 's/^/       /'
  FAIL=1
else
  echo -e "${GREEN}✓${NC} no forbidden generation phrasing"
fi

# E2: required phrase
if scan -q -F "默认 v4"; then
  echo -e "${GREEN}✓${NC} '默认 v4' present in $(scan -l -F "默认 v4" | wc -l | tr -d ' ') file(s)"
else
  echo -e "${RED}✗${NC} '默认 v4' NOT found"
  FAIL=1
fi

# E3: legacy v3 file names must not be referenced at the schema/tech_design/ top level
for legacy in decisions api-contracts scenario-mapping quality interactions; do
  hits=$(scan -n "schema/tech_design/${legacy}\.md" || true)
  if [[ -n "$hits" ]]; then
    echo -e "${RED}✗${NC} schema/tech_design/${legacy}.md referenced at top level:"
    echo "$hits" | sed 's/^/       /'
    FAIL=1
  else
    echo -e "${GREEN}✓${NC} schema/tech_design/${legacy}.md not referenced at top level"
  fi
done
echo ""

# ---------------------------------------------------------------
# Sweep F: zero business-domain terms in skills/
# ---------------------------------------------------------------
echo "--- Sweep F: zero business-domain terms in skills/ ---"

# Adjacent quoted strings concatenate at parse time, so the file on disk never
# contains the searched terms as contiguous text.
BUSINESS_TERMS=(
  "busy""ming" "yu""que" "store-order""-h5" "requirement""-center"
  "神""策" "AR""MS" "陈列""域" "门店""订货" "订货""草稿" "品牌""切换" "门店""切换"
)
BIZ_HITS=0
for term in "${BUSINESS_TERMS[@]}"; do
  if scan -q -F "$term"; then
    echo -e "${RED}✗${NC} business term present: ${term}"
    scan -n -F "$term" | sed 's/^/       /'
    BIZ_HITS=1
    FAIL=1
  fi
done
if [[ $BIZ_HITS -eq 0 ]]; then
  echo -e "${GREEN}✓${NC} zero business terms (${#BUSINESS_TERMS[@]} terms checked)"
fi
echo ""

# ---------------------------------------------------------------
# Sweep G: no em dashes (U+2014) in skills/
# ---------------------------------------------------------------
echo "--- Sweep G: no em dashes in skills/ ---"

EM_DASH=$'\u2014'
if scan -q -F "$EM_DASH"; then
  echo -e "${RED}✗${NC} em dash (U+2014) found:"
  scan -n -F "$EM_DASH" | sed 's/^/       /'
  FAIL=1
else
  echo -e "${GREEN}✓${NC} zero em dashes"
fi
echo ""

# ---------------------------------------------------------------
# Sweep H: frontmatter key parity across all skills
# ---------------------------------------------------------------
echo "--- Sweep H: frontmatter key parity ---"

EXPECTED_KEYS="name description skill-type version type skill-role"
for f in skills/*/SKILL.md; do
  keys=$(awk '/^---$/{n++; next} n==1 && /^[a-zA-Z][a-zA-Z0-9_-]*:/{sub(/:.*/, "", $1); printf "%s ", $1}' "$f")
  keys="${keys% }"
  if [[ "$keys" == "$EXPECTED_KEYS" ]]; then
    echo -e "${GREEN}✓${NC} $f"
  else
    echo -e "${RED}✗${NC} $f  key mismatch"
    echo "       expected: $EXPECTED_KEYS"
    echo "       actual:   $keys"
    FAIL=1
  fi
done
echo ""

# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------
echo "=============================================="
if [[ $FAIL -eq 0 ]]; then
  echo -e "${GREEN}RESULT: PASS${NC} - skills lane clean"
else
  echo -e "${RED}RESULT: FAIL${NC} - violations listed above"
fi
echo "=============================================="
exit $FAIL
