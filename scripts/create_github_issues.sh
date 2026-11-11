#!/usr/bin/env bash
# create_github_issues.sh — create one GitHub issue per backlog slice and per owner action.
#
# Source of truth: backlog.md (slices), specs/FEAT-*.md (acceptance criteria, read at run time),
# context.md (rules). The issue data lives in scripts/github_issues/*.sh.
#
# Usage:
#   scripts/create_github_issues.sh --dry-run [DIR]     render every issue to DIR (no GitHub calls)
#   scripts/create_github_issues.sh [--repo OWNER/NAME] create or update the issues on GitHub
#
# Options:
#   --repo OWNER/NAME   target repository (default: the repository of the current directory)
#   --dry-run [DIR]     write the rendered issues as Markdown files to DIR
#                       (default: ${TMPDIR:-/tmp}/routepilot-issues-preview); nothing is sent
#   --only ID[,ID…]     render or update only these items (for example 001/4,O-5); numbers of the
#                       other items are still looked up so that cross-links stay correct
#   --no-labels         do not create labels and do not attach them
#   --no-milestones     do not create milestones and do not attach them
#   -h, --help          show this help
#
# Behaviour on GitHub:
#   pass 1  find an existing issue whose title starts with "[ID] " (open or closed) or create it
#           with a placeholder body; this fixes every issue number first
#   pass 2  render the full body with cross-links (#numbers) and update every issue
#   The script is idempotent: running it again updates the bodies and labels and creates nothing twice.
#   Closed issues stay closed.
#
# Requirements: bash 3.2+, awk, grep, sed; gh (authenticated, `gh auth status`) unless --dry-run.
# The script sends only the content of this repository's documents to GitHub. It contains no secrets.

set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
DATA_DIR="$ROOT/scripts/github_issues"

REPO=""
DRY_RUN=0
PREVIEW_DIR="${TMPDIR:-/tmp}/routepilot-issues-preview"
ONLY=""
USE_LABELS=1
USE_MILESTONES=1

usage() { sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
log() { printf '%s\n' "$*" >&2; }

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) [ $# -ge 2 ] || die "--repo needs a value"; REPO=$2; shift 2 ;;
    --dry-run)
      DRY_RUN=1; shift
      if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then PREVIEW_DIR=$1; shift; fi ;;
    --only) [ $# -ge 2 ] || die "--only needs a value"; ONLY=",$2,"; shift 2 ;;
    --no-labels) USE_LABELS=0; shift ;;
    --no-milestones) USE_MILESTONES=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1 (see --help)" ;;
  esac
done

cd "$ROOT"
[ -f context.md ] && [ -d specs ] || die "run this script inside the RoutePilot AI repository"
[ -d "$DATA_DIR" ] || die "missing $DATA_DIR"

if [ "$DRY_RUN" -eq 0 ]; then
  command -v gh >/dev/null 2>&1 || die "gh is not installed (https://cli.github.com)"
  gh auth status >/dev/null 2>&1 || die "gh is not authenticated; run: gh auth login"
  if [ -z "$REPO" ]; then
    REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null) \
      || die "no GitHub repository found here; pass --repo OWNER/NAME (backlog owner action O-1)"
  fi
else
  REPO=${REPO:-OWNER/REPO}
  mkdir -p "$PREVIEW_DIR"
fi

WORK=$(mktemp -d "${TMPDIR:-/tmp}/rp-issues.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
META="$WORK/meta.tsv"   # id \t kind \t deps \t full title \t day
MAP="$WORK/map.tsv"     # id \t issue number
: > "$META"; : > "$MAP"

BLOB="https://github.com/$REPO/blob/main"

# ---------------------------------------------------------------------------
# Item registry and variables
# ---------------------------------------------------------------------------

ITEMS=""
register() { ITEMS="$ITEMS $1"; }

# Read a quoted here-document into a variable: txt NAME <<'EOF' … EOF
txt() { IFS= read -r -d '' "$1" || true; }

item_reset() {
  I_ID=""; I_KIND="slice"; I_TITLE=""; I_FEAT=""; I_AREA=""; I_PRIORITY="P0"
  I_ACS=""; I_DEPS=""; I_SIZE="M"; I_DAY=""; I_CATCHUP=""; I_GATES=""; I_LOCK="—"
  I_APPROVAL="no"; I_BRANCH=""; I_REQS=""; I_ADRS=""; I_SCOPE_TAG=""; I_ROLE=""
  T_GOAL=""; T_CONTEXT=""; T_SCOPE=""; T_OUT=""; T_FILES=""; T_IFACE=""; T_TESTS=""
  T_VERIFY=""; T_TIPS=""; T_DECISIONS=""; T_EXTRA_TITLE=""; T_EXTRA=""
  T_STEPS=""; T_DONE=""; T_WHY=""
}

full_title() {
  if [ "$I_KIND" = "owner" ]; then printf '[%s] Owner action: %s' "$I_ID" "$I_TITLE"
  else printf '[%s] %s (FEAT-%s)' "$I_ID" "$I_TITLE" "$I_FEAT"; fi
}

selected() { [ -z "$ONLY" ] || case "$ONLY" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------

meta_field() { awk -F'\t' -v id="$1" -v f="$2" '$1==id {print $f; exit}' "$META"; }
num_of() { awk -F'\t' -v id="$1" '$1==id {print $2; exit}' "$MAP"; }
ref() { local n; n=$(num_of "$1"); if [ -n "$n" ]; then printf '#%s' "$n"; else printf '%s' "$1"; fi; }
unblocks_of() {
  awk -F'\t' -v id="$1" '{ n = split($3, d, " "); for (i = 1; i <= n; i++) if (d[i] == id) { print $1; break } }' "$META"
}
items_of_day() { awk -F'\t' -v day="$1" '$5==day {print $1}' "$META"; }

spec_path() {
  local f
  for f in specs/FEAT-"$1"-*.md; do [ -f "$f" ] && { printf '%s' "$f"; return 0; }; done
  die "no specification for FEAT-$1"
}
spec_status() { grep -m1 '^status:' "$(spec_path "$1")" | sed 's/^status: *//'; }
spec_revision() { grep -m1 '^revision:' "$(spec_path "$1")" | sed 's/^revision: *//'; }

adr_path() {
  local f
  for f in docs/adr/ADR-"$1"-*.md; do [ -f "$f" ] && { printf '%s' "$f"; return 0; }; done
  die "no ADR-$1"
}
adr_title() { head -1 "$(adr_path "$1")" | sed 's/^# *//'; }

feat_name() {
  case "$1" in
    000) echo "Monorepo and ci-fast" ;;
    001) echo "Domain, SQLite, CRUD, auth" ;;
    002) echo "Demo data generators and import" ;;
    003) echo "Optimizer and working time" ;;
    004) echo "Routing and jobs" ;;
    005) echo "Frontend" ;;
    006) echo "Runtime agents" ;;
    007) echo "Quality, README, ci-full" ;;
    009) echo "Demo media and release" ;;
    *) die "unknown FEAT-$1" ;;
  esac
}

# Delivery checkpoints = the day plan of docs/report.md §33 and context.md → Delivery Deadline.
day_title() {
  case "$1" in
    2026-11-10) echo "Foundation, CRUD and data" ;;
    2026-11-11) echo "Engine, working time and routing" ;;
    2026-11-12) echo "Runtime agents" ;;
    2026-11-13) echo "Frontend" ;;
    2026-11-14) echo "Quality and README" ;;
    2026-11-15) echo "Recording and release" ;;
    post-MVP) echo "After the MVP" ;;
    *) die "unknown day $1" ;;
  esac
}
day_done() {
  case "$1" in
    2026-11-10) echo "\`ci-fast\` is green; CRUD works (tests + Swagger UI); login works locally" ;;
    2026-11-11) echo "invariants are green; the benchmark is measured" ;;
    2026-11-12) echo "the \"find and assign\" scenario works on fake models (and once on the owner's model)" ;;
    2026-11-13) echo "the demo scenario is clickable in the browser" ;;
    2026-11-14) echo "a clean clone starts by following the README; \`ci-full\` is green" ;;
    2026-11-15) echo "the public repository is complete: recording, screenshots, tag \`v0.1.0\`" ;;
    post-MVP) echo "not part of the MVP" ;;
  esac
}
day_fallback() {
  case "$1" in
    2026-11-10) echo "account lockout stays P1" ;;
    2026-11-11) echo "horizon 3 days, at most 4 offers in a plan" ;;
    2026-11-12) echo "Freight Scout merged into the Dispatcher (cut order item 5)" ;;
    2026-11-13) echo "map → ordered list" ;;
    2026-11-14) echo "E2E smoke only (cut order item 7)" ;;
    2026-11-15) echo "a recording of the shorter fallback scenario" ;;
    post-MVP) echo "—" ;;
  esac
}
milestone_of() {
  [ "$1" = "post-MVP" ] && { echo "After the MVP"; return; }
  printf '%s — %s' "$1" "$(day_title "$1")"
}

size_text() {
  case "$1" in
    S) echo "S (≤ 2 h of agent work + review)" ;;
    M) echo "M (2–4 h of agent work + review)" ;;
    L) echo "L (4–8 h of agent work + review; justify a PR above ~400 manual lines)" ;;
    *) echo "$1" ;;
  esac
}

role_of() {
  [ -n "$I_ROLE" ] && { echo "$I_ROLE"; return; }
  case " $I_AREA " in
    *" agents "*) echo "Implementation Agent (agents)" ;;
    *" engine "*) echo "Implementation Agent (backend/engine)" ;;
    *" frontend "*) echo "Implementation Agent (frontend)" ;;
    *" infra "*) echo "Implementation Agent (infra)" ;;
    *" docs "*) echo "Implementation Agent (infra/docs)" ;;
    *) echo "Implementation Agent (backend)" ;;
  esac
}

has_area() { case " $I_AREA " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }

# ---------------------------------------------------------------------------
# Body sections — slices
# ---------------------------------------------------------------------------

sec_header() {
  local spec status rev
  spec=$(spec_path "$I_FEAT"); status=$(spec_status "$I_FEAT"); rev=$(spec_revision "$I_FEAT")
  printf '## 🎯 Goal\n\n%s\n' "$T_GOAL"
  printf '| Field | Value |\n|---|---|\n'
  printf '| Task | %s — %s |\n' "$I_ID" "$I_TITLE"
  printf '| Epic | FEAT-%s — %s ([spec](%s/%s), status `%s`, revision %s) |\n' "$I_FEAT" "$(feat_name "$I_FEAT")" "$BLOB" "$spec" "$status" "$rev"
  printf '| Priority | %s (MVP, must have) |\n' "$I_PRIORITY"
  printf '| Delivery checkpoint | %s — %s (`context.md` → Delivery Deadline) |\n' "$I_DAY" "$(day_title "$I_DAY")"
  if [ -n "$I_CATCHUP" ]; then
    printf '| Catch-up proposal | %s (`backlog.md` §3 — needs the owner'"'"'s decision) |\n' "$I_CATCHUP"
  fi
  printf '| Size | %s |\n' "$(size_text "$I_SIZE")"
  printf '| Required gates | %s |\n' "$I_GATES"
  printf '| Shared files (owner lock) | %s |\n' "$I_LOCK"
  printf '| Human approval needed | %s |\n' "$( [ "$I_APPROVAL" = "yes" ] && echo "yes — see 🔒 in the shared-files row" || echo "no (beyond the normal review and merge)")"
  printf '| Requirements | %s |\n' "${I_REQS:-—}"
  printf '| Implementer | %s |\n' "$(role_of)"
  printf '| Reviewer | Review & QA Agent; merge by the owner (human) |\n'
  printf '| Branch | `%s` (own worktree) |\n\n' "$I_BRANCH"
}

sec_context() {
  printf '## 📚 Context — read before you start\n\n'
  printf 'Read [`context.md`](%s/context.md) in full first (it overrides every other file on project rules), then [`AGENTS.md`](%s/AGENTS.md) (and [`CLAUDE.md`](%s/CLAUDE.md) in Claude Code). Then the documents and sections below (§ numbers point to sections of the named file).\n\n' "$BLOB" "$BLOB" "$BLOB"
  printf '%s\n' "$T_CONTEXT"
}

sec_technical() {
  printf '## 🛠️ Technical details\n\n'
  printf '### Scope\n\n%s\n' "$T_SCOPE"
  printf '### Out of scope (binding)\n\n%s\n' "$T_OUT"
  printf '### Files (= Allowed paths of the task brief)\n\n%s\n' "$T_FILES"
  printf 'Forbidden: every path not listed above (except generated files named here), `context.md`, `specs/**` (propose changes in the PR instead), other modules'"'"' internals, `.env`, `*.db*`.\n\n'
  if [ -n "$T_IFACE" ]; then
    printf '### Interface (binding where the specification fixes it — implement exactly: names, signatures, shapes)\n\n'
    printf 'Names marked *suggested* are not fixed by the specification; keep them unless there is a reason, and say so in the completion report.\n\n%s\n' "$T_IFACE"
  fi
  printf '### Tests to write (first, with AC markers)\n\n%s\n' "$T_TESTS"
  printf '### Verification\n\n%s\n' "$T_VERIFY"
  printf '### Tips and pitfalls\n\n%s\n' "$T_TIPS"
}

sec_decisions() {
  [ -n "$T_DECISIONS" ] || return 0
  printf '## 🧾 Owner decisions and open points that apply here\n\n%s\n' "$T_DECISIONS"
}

sec_extra() {
  [ -n "$T_EXTRA" ] || return 0
  printf '## %s\n\n%s\n' "$T_EXTRA_TITLE" "$T_EXTRA"
}

rules_common() {
  cat <<'EOF'
- **No approved specification → no implementation.** Check the spec status before you start; a `draft` spec means stop.
- **Stay inside the Allowed paths.** Shared files have one author at a time and change only when this issue names them.
- **Never weaken a test** (delete, skip, loosen, `xfail` without a linked bug and human consent). If a test can pass only that way: stop and ask.
- **No suppressions** (`# type: ignore`, `# noqa`, `eslint-disable`, `@ts-ignore`) without a rule code and a written reason; no `--no-verify`; no lowered thresholds.
- **No secrets, `.env` or database files** in code, tests, fixtures, logs or commits. No real personal data — demo data comes only from the generators.
- **Do not add a package** whose existence and version you have not verified in its registry; every new runtime dependency is justified in the completion report (problem, alternatives, licence). No GPL/AGPL at runtime.
- **Do not present planned things as implemented**, and describe the project only as an MVP with a deadline (2026-11-15), later a portfolio project — nothing about why or for whom.
- **Stop and report `blocked`** when documents contradict each other, an AC is ambiguous, or you need a contract, migration, prompt or module change the spec did not foresee.
EOF
}
rules_infra() {
  cat <<'EOF'
- **Local run in a few steps is a hard requirement:** no Docker, no database server, no required API keys. Anything that breaks it is rejected.
- **Workflows** (`.github/workflows/**`) change only with the owner's approval; actions are pinned to a commit SHA; `ci-fast`/`ci-full` make no network call to an LLM, ORS, TIMOCOM or Cloudflare.
- **The Makefile is an optional shortcut** — the README always gives the direct commands.
EOF
}
rules_backend() {
  cat <<'EOF'
- **Units:** kg (int), m and km (Decimal, 2 places), minutes (int), money as **int minor units + ISO-4217** — `float` for money is forbidden. In the DB: lengths in mm, distances in m, masses in kg (`INTEGER`).
- **Time:** aware UTC datetimes only; the IANA zone of a stop is stored separately; `datetime.now()` is forbidden in domain logic — inject `Clock`.
- **Missing data:** `None` + `missing_fields`; never invent values; substitutes only with provenance and a flag.
- **Layers:** `api → service → domain / repository`; routers hold no business logic; repositories hold no rules; module imports follow `context.md` → Module Boundaries (import-linter enforces them).
- **REST:** plural resources, `POST` → `201` + `Location`, `PATCH` partial with `version`, `DELETE` → `204`, `409` for conflicts, `422` validation; all errors are problem+json with a stable `code` and `requestId`; JSON is camelCase, Python is snake_case; request models use `extra="forbid"`.
- **SQLite portability:** no dialect-specific functions in models or queries; short transactions; migrations only through Alembic (`render_as_batch=True`), with `downgrade`, human review, never edit a merged migration.
EOF
}
rules_data() {
  cat <<'EOF'
- **Synthetic data only from the generators** (`data/mock/`), always `is_synthetic = true`, `MOCK-*` ids, fictional people and phone numbers; never presented as real exchange offers or real people; no TIMOCOM branding.
- **TIMOCOM rules:** attribute to TIMOCOM no field outside OpenAPI 3.0.6 (everything else is enrichment with provenance); tolerant mapper; zero network calls to TIMOCOM; the mock uses the same mapper (`source = "mock_timocom_v3"`).
- **Offer texts are untrusted** — stored unchanged, flagged `SUSPICIOUS_TEXT` when instruction-like, never interpreted.
EOF
}
rules_engine() {
  cat <<'EOF'
- **Pure core:** `optimization.engine` and `compliance` do no IO — no DB, HTTP, environment or system clock; they receive a snapshot and a travel matrix.
- **Invariants 1–17** (`context.md` → Optimization Engine Invariants) hold for every result; `RouteValidator`/`FleetValidator` are separate implementations from the search. **Weakening a validator so that results pass is forbidden.**
- **Determinism:** sorting by id, explicit seeds, a node budget; the result never depends on wall-clock time except `truncated` and `runtimeMs`.
- **Golden values are binding** (approved 2026-11-11). A mismatch means stop and report — never edit a golden file or a test value to make it pass.
- **Never claim that a schedule complies with the law.** Model assumptions are named constants with the comment "assumption" and provenance `assumption`.
- Changes to invariants, objectives, legal rules or validators need human approval.
EOF
}
rules_agents() {
  cat <<'EOF'
- **The only write tool is `assign_plan`**, executed only by `ApprovalGate` after `interrupt()` and a resume with `approve` from a `dispatcher`/`demo`/`admin` user. A write tool without `interrupt` = rejected PR.
- **Code before `interrupt()` is idempotent** (the node restarts on resume); never wrap `interrupt()` in a bare `try/except`; the order of interrupts is fixed.
- **Tools are thin adapters** over the same services as the HTTP API: Pydantic schemas with `extra="forbid"`, `read`/`write` kind, size limits, exported facts; zero business logic; no repository access.
- **Offer text is untrusted:** only in `untrusted_text` of a tool result, never in a system prompt; prompts say it is data, not instructions.
- **Data minimisation:** the model sees `D1…`, `PLAN-xxxxxxxx`, `MOCK-…`, positions and counters — never names, phone numbers, emails or UUIDs.
- **Models only through `agents/models.py`** and `AGENT_MODEL_POLICY`; no provider SDK import anywhere else; no hard-coded model names.
- **Prompts** are versioned files `agents/prompts/<agent>.v<N>.md`; a content change = new version + spec change + `ai-evals` run; owner approval.
- **CI tests use fake models only** (no network). Agents never change engine results — every correction goes through the engine and the validator again.
EOF
}
rules_frontend() {
  cat <<'EOF'
- **Structure:** thin pages in `app/*`; logic in `features/{agent-chat,fleet,offers,plans,optimizer,admin,auth}`; a feature imports another only through its `index.ts`.
- **API access only through `lib/api/client.ts`** (types generated into `schema.d.ts` — never edited by hand); SSE only through `lib/api/sse.ts`.
- **All UI text through next-intl** in `messages/en.json` and `messages/pl.json` (same keys; append, do not reorder); hard-coded strings in components are forbidden.
- **Formatting only through `lib/format/*`** with the active locale.
- **Honesty in the UI:** the "SYNTHETIC DATA" badge wherever demo data is shown; the working-time notice next to every schedule; fuel, CO₂, tolls and travel times labelled as estimates.
- **TypeScript strict** with `noUncheckedIndexedAccess`; no `any`, no `@ts-ignore`; accessible names, keyboard operation, text next to colour.
- **Design system "Clear Route v3"** (`docs/design/README.md`, ADR-0015): colours, fonts, radii and shadows only from `docs/design/tokens.json` via `styles/tokens.css` — no raw colour values in components; **red `#D42A22` is the only accent**, every other status is grey and written in text; destructive buttons are outlined. Components are our own on Radix UI primitives — **no shadcn/ui**. Layout and copy follow `docs/design/mockups/`; the spec wins where they differ.
EOF
}
rules_docs() {
  cat <<'EOF'
- **Fixed purpose statement** (`context.md` → Project Constraints 10): only "an MVP with a deadline (2026-11-15), later a portfolio project" — nothing about why or for whom, no third-party organisation in that role.
- **The working-time notice** stays wherever schedules are shown, including media and the README limitations.
- **No secrets or personal data** in any file, frame or caption. Publishing media and releases needs the owner's approval.
EOF
}

sec_rules() {
  printf '## ⚖️ Rules from `context.md` that matter most here\n\n'
  printf 'Breaking any of them means the PR goes back. Always:\n\n'
  rules_common
  has_area infra && { printf '\nInfrastructure and CI:\n\n'; rules_infra; }
  has_area backend && { printf '\nBackend and API:\n\n'; rules_backend; }
  has_area data && { printf '\nDemo data and the TIMOCOM format:\n\n'; rules_data; }
  has_area engine && { printf '\nEngine and working time:\n\n'; rules_engine; }
  has_area agents && { printf '\nRuntime agents (AI Architecture Rules):\n\n'; rules_agents; }
  has_area frontend && { printf '\nFrontend:\n\n'; rules_frontend; }
  has_area docs && { printf '\nDocumentation and media:\n\n'; rules_docs; }
  printf '\n'
}

sec_sources() {
  local spec a
  spec=$(spec_path "$I_FEAT")
  printf '## 🔎 Sources and decisions\n\n'
  printf -- '- Specification: [`%s`](%s/%s)\n' "$spec" "$BLOB" "$spec"
  for a in $I_ADRS; do
    printf -- '- [%s](%s/%s)\n' "$(adr_title "$a")" "$BLOB" "$(adr_path "$a")"
  done
  printf -- '- Backlog: [`backlog.md`](%s/backlog.md) — slice %s\n' "$BLOB" "$I_ID"
  printf -- '- Requirements and traceability: [`specs/requirements.md`](%s/specs/requirements.md)\n' "$BLOB"
  printf -- '- Rules: [`context.md`](%s/context.md) · how-to: [`DEVELOPMENT.md`](%s/DEVELOPMENT.md) · rationale: [`docs/report.md`](%s/docs/report.md)\n' "$BLOB" "$BLOB" "$BLOB"
  has_area engine && printf -- '- Golden cases: [`specs/golden/README.md`](%s/specs/golden/README.md)\n' "$BLOB"
  has_area frontend && printf -- '- Design system: [`docs/design/README.md`](%s/docs/design/README.md) · tokens [`docs/design/tokens.json`](%s/docs/design/tokens.json) · mockups [`docs/design/mockups/`](%s/docs/design/mockups)\n' "$BLOB" "$BLOB" "$BLOB"
  printf '\n📏 **Estimated size:** %s\n\n' "$(size_text "$I_SIZE")"
}

sec_acs() {
  local spec n line
  spec=$(spec_path "$I_FEAT")
  printf '## ✅ Acceptance criteria\n\n'
  if [ -n "$I_ACS" ]; then
    printf 'Copied verbatim from [`%s`](%s/%s) §7 (the spec wins if this copy is stale). Each AC needs at least one test that names it — `@pytest.mark.ac("AC-…")` in Python, `[AC-…]` in a TypeScript or Playwright test title.\n\n' "$spec" "$BLOB" "$spec"
    for n in $I_ACS; do
      line=$(grep -m1 -F -e "- **AC-FEAT-${I_FEAT}-${n}**" "$spec") || die "AC-FEAT-${I_FEAT}-${n} not found in $spec"
      printf -- '- [ ] %s\n' "${line#- }"
    done
    printf '\n'
  else
    printf 'This slice has no AC of its own; its checklist is in the section above.\n\n'
  fi
}

sec_dod() {
  printf '### Definition of Done (`context.md` → Definition of Done) — tick where it applies\n\n'
  printf -- '- [ ] All acceptance criteria above pass and are ticked in the PR description.\n'
  printf -- '- [ ] `make check` is green (lint, types, unit) and its output is quoted in the completion report. Where `make check` does not exist yet, run the commands under "Verification" and say so.\n'
  printf -- '- [ ] Extra gates: %s.\n' "$I_GATES"
  printf -- '- [ ] Coverage thresholds of the touched packages hold (`context.md` → Testing Standards).\n'
  printf -- '- [ ] No new suppressions without a rule code and a reason; no weakened test; no lowered threshold.\n'
  if has_area backend || has_area agents; then
    printf -- '- [ ] If the API changed: `contracts/openapi.json` regenerated (`make openapi`) and committed; no unintended breaking change; status codes, CORS and problem+json follow `DEVELOPMENT.md` §4; tests in `tests/api` and `tests/security`.\n'
  fi
  has_area agents && printf -- '- [ ] Agent tests (`make test-agents`) green; `ai-evals` run when a prompt, policy or tool changed.\n'
  has_area frontend && printf -- '- [ ] Every new UI text exists in EN and PL; no hard-coded strings; MSW handlers typed from the OpenAPI schema.\n'
  printf -- '- [ ] The README run steps still work from a clean clone (when dependencies, environment variables, migrations or the seed changed).\n'
  printf -- '- [ ] No data, database files, `.env`, secrets or real personal data in the diff.\n'
  printf -- '- [ ] Specification changelog and traceability (`make trace`, once it exists) updated; completion report (`AGENTS.md` §8) in the PR.\n'
  [ "$I_APPROVAL" = "yes" ] && printf -- '- [ ] Owner approval recorded for: %s.\n' "$I_LOCK"
  printf -- '- [ ] `ci-fast` green (once it exists); PR ≤ ~400 manually changed lines or justified; Review & QA passed; squash merge by the owner.\n\n'
}

dep_line() {
  local id=$1 t d
  t=$(meta_field "$id" 4); d=$(meta_field "$id" 5)
  printf -- '- %s — %s (checkpoint %s)\n' "$(ref "$id")" "$t" "$d"
}

sec_deps() {
  local d u any=0 day
  printf '## 🔗 Dependencies\n\n'
  if [ -n "$I_DEPS" ]; then
    printf '**Blocked by** (all must be closed first — otherwise comment here and stop instead of implementing ahead):\n\n'
    for d in $I_DEPS; do dep_line "$d"; done
  else
    printf '**Blocked by:** nothing.\n'
  fi
  printf '\n**Unblocks:**\n\n'
  for u in $(unblocks_of "$I_ID"); do dep_line "$u"; any=1; done
  [ "$any" -eq 1 ] || printf -- '- nothing directly (end of a chain)\n'
  day=$I_DAY
  printf '\n**Delivery checkpoint %s — %s.** Done when: %s. Fallback if it slips: %s. Items of this checkpoint: ' "$day" "$(day_title "$day")" "$(day_done "$day")" "$(day_fallback "$day")"
  local first=1 x
  for x in $(items_of_day "$day"); do
    [ $first -eq 1 ] || printf ', '
    printf '%s (%s)' "$x" "$(ref "$x")"; first=0
  done
  printf '.\n\n'
}

sec_start() {
  local spec acs n slug
  spec=$(spec_path "$I_FEAT")
  acs=""; for n in $I_ACS; do acs="$acs AC-FEAT-${I_FEAT}-${n}"; done
  printf '## 🧭 How to start\n\n'
  printf '1. Check that every issue under "Blocked by" is closed and that the spec is approved: `grep -m1 "^status:" %s`.\n' "$spec"
  printf '2. Read `context.md` in full, `AGENTS.md`, this issue and the sections under "Context".\n'
  printf '3. Write the task brief (template: `context.md` → Specification Templates → Task Brief): ACs in scope =%s; Allowed paths = "Files"; shared files = %s; gates = %s.\n' "${acs:- none}" "$I_LOCK" "$I_GATES"
  printf '4. State your understanding and assumptions, then a numbered plan with one line per step ending in `→ verify: <check>` (`AGENTS.md` §2.4, `CLAUDE.md`).\n'
  printf '5. Create the branch in its own worktree: `git worktree add ../rp-%s -b %s`.\n' "$(printf '%s' "$I_ID" | tr '/' '-')" "$I_BRANCH"
  printf '6. Write the tests first (with AC markers), then the smallest change that makes them pass. "Out of scope" is binding; a needed change outside it → stop and ask.\n'
  printf '7. Run "Verification" and the gates of the Definition of Done; quote the results.\n'
  printf '8. Commit with Conventional Commits naming the spec and ACs, for example `%s(%s): <description> (FEAT-%s%s)`.\n' "${I_BRANCH%%/*}" "${I_SCOPE_TAG:-core}" "$I_FEAT" "$( [ -n "$I_ACS" ] && printf ', AC-FEAT-%s-%s' "$I_FEAT" "$(printf '%s' "$I_ACS" | awk '{print $1 ($NF!=$1 ? ".." $NF : "")}')")"
  printf '9. Open one PR for this issue (`Closes %s`) with the completion report (`AGENTS.md` §8: status, changes, AC → test, gates run, assumptions, unverified items, risks).\n\n' "$(ref "$I_ID")"
}

render_slice() {
  sec_header
  sec_context
  sec_technical
  sec_decisions
  sec_extra
  sec_rules
  sec_sources
  sec_acs
  sec_dod
  sec_deps
  sec_start
  printf -- '---\n_Generated by `scripts/create_github_issues.sh` from `backlog.md` and the specifications. Edit the sources and re-run the script instead of editing this issue by hand._\n'
}

# ---------------------------------------------------------------------------
# Body sections — owner actions
# ---------------------------------------------------------------------------

render_owner() {
  local u any=0
  printf '## 🎯 Goal\n\n%s\n' "$T_GOAL"
  printf '| Field | Value |\n|---|---|\n'
  printf '| Action | %s — %s |\n' "$I_ID" "$I_TITLE"
  printf '| Who | the owner (human) — a coding agent cannot do this alone (`context.md` → Operations that need human confirmation) |\n'
  printf '| Needed by | %s — %s |\n' "$I_DAY" "$(day_title "$I_DAY")"
  printf '| Size | %s |\n' "$I_SIZE"
  printf '| Backlog | [`backlog.md`](%s/backlog.md) §2, row %s |\n\n' "$BLOB" "$I_ID"
  printf '## 📚 Why\n\n%s\n' "$T_WHY"
  printf '## 🛠️ Steps\n\n%s\n' "$T_STEPS"
  [ -n "$T_DECISIONS" ] && printf '## 🧾 Decisions and open points\n\n%s\n' "$T_DECISIONS"
  printf '## ✅ Done when\n\n%s\n' "$T_DONE"
  printf '## ⚖️ Rules\n\n'
  printf -- '- Never paste keys, passwords or tokens into an issue, a PR, a chat with an agent, a commit or a fixture. Keys live only in `.env` (gitignored) or GitHub Secrets.\n'
  printf -- '- Approval is per action and per change: approving one workflow or prompt version does not approve the next one.\n'
  printf -- '- Record the decision in this issue (a short comment) so that the implementing slice can quote it.\n\n'
  printf '## 🔗 Unblocks\n\n'
  for u in $(unblocks_of "$I_ID"); do dep_line "$u"; any=1; done
  [ "$any" -eq 1 ] || printf -- '- no slice directly\n'
  printf '\n---\n_Generated by `scripts/create_github_issues.sh` from `backlog.md`. Edit the sources and re-run the script instead of editing this issue by hand._\n'
}

render_item() { if [ "$I_KIND" = "owner" ]; then render_owner; else render_slice; fi; }

# ---------------------------------------------------------------------------
# Labels and milestones
# ---------------------------------------------------------------------------

LABELS_SPEC='slice|0e8a16|One backlog slice = one task brief = one PR
owner-action|d93f0b|Needs the owner (human); a coding agent cannot do it alone
needs-approval|b60205|Touches a file or action that needs the owner'"'"'s approval before merge
P0|5319e7|MVP, must have
FEAT-000|c5def5|Monorepo and ci-fast
FEAT-001|c5def5|Domain, SQLite, CRUD, auth
FEAT-002|c5def5|Demo data generators and import
FEAT-003|c5def5|Optimizer and working time
FEAT-004|c5def5|Routing and jobs
FEAT-005|c5def5|Frontend
FEAT-006|c5def5|Runtime agents
FEAT-007|c5def5|Quality, README, ci-full
FEAT-009|c5def5|Demo media and release
area:infra|fbca04|Tooling, CI, scripts
area:backend|1d76db|FastAPI, SQLite, services
area:data|0052cc|Demo data, generators, TIMOCOM format
area:engine|006b75|Optimizer and working-time rules (pure core)
area:agents|5319e7|LangGraph runtime agents
area:frontend|bfd4f2|Next.js web app
area:docs|cccccc|Documentation and media
size:S|ededed|Up to about 2 hours of agent work
size:M|ededed|About 2 to 4 hours of agent work
size:L|ededed|About 4 to 8 hours of agent work'

ensure_labels() {
  [ "$USE_LABELS" -eq 1 ] || return 0
  local name color desc
  log "labels: creating or updating"
  printf '%s\n' "$LABELS_SPEC" | while IFS='|' read -r name color desc; do
    gh label create "$name" --repo "$REPO" --color "$color" --description "$desc" --force >/dev/null
  done
}

ensure_milestones() {
  [ "$USE_MILESTONES" -eq 1 ] || return 0
  local existing day title
  existing=$(gh api "repos/$REPO/milestones?state=all&per_page=100" --jq '.[].title')
  for day in 2026-11-10 2026-11-11 2026-11-12 2026-11-13 2026-11-14 2026-11-15 post-MVP; do
    title=$(milestone_of "$day")
    if ! printf '%s\n' "$existing" | grep -qxF "$title"; then
      log "milestone: creating '$title'"
      if [ "$day" = "post-MVP" ]; then
        gh api "repos/$REPO/milestones" --method POST -f title="$title" \
          -f description="Owner actions that are not needed for the MVP." >/dev/null
      else
        gh api "repos/$REPO/milestones" --method POST -f title="$title" -f due_on="${day}T23:59:59Z" \
          -f description="Done when: $(day_done "$day"). Fallback: $(day_fallback "$day")." >/dev/null
      fi
    fi
  done
}

item_labels() {
  local a out
  if [ "$I_KIND" = "owner" ]; then out="owner-action needs-approval"
  else
    out="slice $I_PRIORITY FEAT-$I_FEAT size:$I_SIZE"
    for a in $I_AREA; do out="$out area:$a"; done
    [ "$I_APPROVAL" = "yes" ] && out="$out needs-approval"
  fi
  printf '%s' "$out"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

for f in "$DATA_DIR"/*.sh; do
  # shellcheck source=/dev/null
  . "$f"
done
[ -n "$ITEMS" ] || die "no items registered in $DATA_DIR"

# Pass 0: metadata of every item (needed for cross-links and "Unblocks").
for fn in $ITEMS; do
  item_reset; "$fn"
  [ -n "$I_ID" ] && [ -n "$I_TITLE" ] && [ -n "$I_DAY" ] || die "$fn: I_ID, I_TITLE and I_DAY are required"
  if [ "$I_KIND" = "slice" ]; then
    [ -n "$I_FEAT" ] && [ -n "$I_BRANCH" ] && [ -n "$I_GATES" ] || die "$fn: I_FEAT, I_BRANCH and I_GATES are required"
  fi
  [ -z "$(meta_field "$I_ID" 1)" ] || die "duplicate item id $I_ID"
  printf '%s\t%s\t%s\t%s\t%s\n' "$I_ID" "$I_KIND" "$I_DEPS" "$(full_title)" "$I_DAY" >> "$META"
done
unknown=$(awk -F'\t' 'NR == FNR { known[$1] = 1; next }
  { n = split($3, d, " "); for (i = 1; i <= n; i++) if (!(d[i] in known)) print $1 " depends on unknown item " d[i] }' "$META" "$META")
[ -z "$unknown" ] || die "$unknown"
log "items: $(wc -l < "$META" | tr -d ' ')"

# Pass 1: fix issue numbers.
if [ "$DRY_RUN" -eq 1 ]; then
  awk -F'\t' '{print $1 "\t" NR}' "$META" > "$MAP"
else
  ensure_labels
  ensure_milestones
  gh issue list --repo "$REPO" --state all --limit 1000 --json number,title \
    --jq '.[] | "\(.number)\t\(.title)"' > "$WORK/existing.tsv"
  for fn in $ITEMS; do
    item_reset; "$fn"
    title=$(full_title)
    num=$(awk -F'\t' -v p="[$I_ID] " 'index($2, p) == 1 {print $1; exit}' "$WORK/existing.tsv")
    if [ -z "$num" ]; then
      if ! selected "$I_ID"; then continue; fi
      args=(--repo "$REPO" --title "$title" --body "Being generated by scripts/create_github_issues.sh — the full text follows in a moment.")
      if [ "$USE_LABELS" -eq 1 ]; then for l in $(item_labels); do args+=(--label "$l"); done; fi
      [ "$USE_MILESTONES" -eq 1 ] && args+=(--milestone "$(milestone_of "$I_DAY")")
      url=$(gh issue create "${args[@]}")
      num=${url##*/}
      log "created #$num $title"
      sleep 1   # stay below GitHub's secondary rate limit for content creation
    fi
    printf '%s\t%s\n' "$I_ID" "$num" >> "$MAP"
  done
fi

# Pass 2: render bodies and update the issues.
for fn in $ITEMS; do
  item_reset; "$fn"
  selected "$I_ID" || continue
  num=$(num_of "$I_ID")
  safe=$(printf '%s' "$I_ID" | tr '/' '-')
  body="$WORK/$safe.md"
  render_item > "$body"
  if [ "$DRY_RUN" -eq 1 ]; then
    { printf '# %s\n\n<!-- dry run: issue #%s, labels: %s, milestone: %s -->\n\n' \
        "$(full_title)" "$num" "$(item_labels)" "$(milestone_of "$I_DAY")"; cat "$body"; } > "$PREVIEW_DIR/$safe.md"
  else
    [ -n "$num" ] || die "no issue number for $I_ID"
    args=(--repo "$REPO" --title "$(full_title)" --body-file "$body")
    if [ "$USE_LABELS" -eq 1 ]; then for l in $(item_labels); do args+=(--add-label "$l"); done; fi
    [ "$USE_MILESTONES" -eq 1 ] && args+=(--milestone "$(milestone_of "$I_DAY")")
    gh issue edit "$num" "${args[@]}" >/dev/null
    log "updated #$num $(full_title)"
  fi
done

if [ "$DRY_RUN" -eq 1 ]; then
  awk -F'\t' '{printf "- #%s %s\n", NR, $4}' "$META" > "$PREVIEW_DIR/INDEX.md"
  log "dry run: $(ls "$PREVIEW_DIR" | wc -l | tr -d ' ') files written to $PREVIEW_DIR"
else
  log "done: issues are up to date in $REPO"
fi
