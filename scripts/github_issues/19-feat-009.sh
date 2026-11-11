# FEAT-009 — Demo media and release. Sourced by scripts/create_github_issues.sh.
# shellcheck shell=bash disable=SC2034

s_009_1() {
  I_ID="009/1"; I_FEAT="009"; I_TITLE="Demo recording (MP4 + GIF), ten screenshots, media check, pre-publication checklist"
  I_AREA="docs"; I_SIZE="L"; I_DAY="2026-11-15"; I_CATCHUP="2026-11-15"
  I_ACS="01 02 03 05"; I_DEPS="007/4 O-6 O-11"
  I_GATES="scripts/check_docs.py --media; owner review of every frame"
  I_LOCK="🔒 publication of media (\`docs/media/**\`)"; I_APPROVAL="yes"
  I_ROLE="the owner (recording) + Implementation Agent (infra/docs) for the media check"
  I_BRANCH="docs/FEAT-009-media"; I_REQS="REQ-033"; I_ADRS="0007"; I_SCOPE_TAG="media"
  txt T_GOAL <<'EOF'
A 2–4 minute captioned video and a short GIF show the product working end to end — login, fleet CRUD, the AI Dispatcher with its trace, variants with CO₂, human approval, and the no-AI path — together with ten screenshots, all within size limits and free of secrets.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-009-demo-media.md` §4.1 (six-scene script and the fallback set), §4.2 (recording settings), §4.3 (files and limits), §4.5 (pre-publication checklist), §8, §11
- `docs/report.md` §34 (demo scenario)
- `context.md` → Project Constraints 7, 10; Core Domain Rule 15
EOF
  txt T_SCOPE <<'EOF'
- Record from a clean clone started with the README steps; English UI; LLM key for scenes 3–5, removed for scene 6; captions per scene; closing frame with the working-time notice and "All data is synthetic."
- Settings: 1440 × 900 CSS px, 100 % zoom, light theme, clean profile, 30 fps; `demo.mp4` H.264 ≤ 25 MB, 120–240 s; `demo.gif` 20–40 s, 960 px wide, ≤ 12 fps, ≤ 10 MB; no Git LFS.
- Ten screenshots `docs/media/screenshots/01-login.png` … `10-pl-locale.png`, PNG, ≤ 1 MB each.
- Extend `scripts/check_docs.py --media` (existence, extensions, sizes, duration via `ffprobe` when available).
- Tick the pre-publication checklist below and record it in the PR.
EOF
  txt T_OUT <<'EOF'
- Voice-over, music, hosting outside the repository; editing an LLM answer in post-production (re-record instead).
EOF
  txt T_FILES <<'EOF'
- `docs/media/demo.mp4`, `docs/media/demo.gif`, `docs/media/screenshots/*.png` — new
- `scripts/check_docs.py` (`--media`), `scripts/tests/test_check_docs.py` — changed
EOF
  txt T_TESTS <<'EOF'
- `check_docs.py --media` — `demo.mp4` and/or `demo.gif` exist within limits; MP4 120–240 s. → AC-01
- Owner review against the script: six scenes (or the documented fallback) in order with captions, reject-then-approve visible, closing frame with the notice. → AC-02
- `check_docs.py --media` — the ten screenshots exist with those names, PNG, ≤ 1 MB. → AC-03
- Pre-publication checklist completely ticked in the PR; one unticked box blocks the merge. → AC-05
EOF
  txt T_VERIFY <<'EOF'
```bash
uv run python scripts/check_docs.py --media
ffprobe -v error -show_entries format=duration -of csv=p=0 docs/media/demo.mp4
du -h docs/media/demo.* docs/media/screenshots/*.png
```
EOF
  txt T_TIPS <<'EOF'
- If an agent run is slow, speed up waiting parts with a visible "×4" marker; never cut out an approval step.
- No API key, `.env`, terminal with secrets, real email or third-party branding in any frame.
- If the agent scenes are unstable on the day, record the shorter fallback (scenes 1, 2, 4 from the optimizer, 6).
EOF
  T_EXTRA_TITLE="🧪 Pre-publication checklist (FEAT-009 §4.5 — the owner ticks every box)"
  T_EXTRA=$(awk '/^### 4.5 Pre-publication checklist/{p=1; next} /^- \*\*FR-9/{p=0} /^##/{p=0} p' "$(spec_path 009)")
  T_EXTRA="$T_EXTRA
"
}
register s_009_1

s_009_2() {
  I_ID="009/2"; I_FEAT="009"; I_TITLE="Embed the media in README §8, update the status table, tag v0.1.0"
  I_AREA="docs"; I_SIZE="S"; I_DAY="2026-11-15"; I_CATCHUP="2026-11-15"
  I_ACS="04 06"; I_DEPS="009/1 O-11"
  I_GATES="scripts/check_docs.py --readme --media; ci-full green on the release commit"
  I_LOCK="\`README.md\`; 🔒 release tag \`v0.1.0\` (owner)"; I_APPROVAL="yes"
  I_BRANCH="docs/FEAT-009-readme-release"; I_REQS="REQ-033"; I_ADRS="0007"; I_SCOPE_TAG="docs"
  txt T_GOAL <<'EOF'
The README shows the demo inline and links the full video, its status table tells the truth about the finished state, and the release `v0.1.0` marks the green commit that delivers the MVP.
EOF
  txt T_CONTEXT <<'EOF'
- `specs/FEAT-009-demo-media.md` §4.4 FR-7, FR-8, FR-9, §10 (rows 04, 06)
- `README.md` §8 "Demo" and the status table
EOF
  txt T_SCOPE <<'EOF'
- README §8: `demo.gif` inline with descriptive alt text, a link to `docs/media/demo.mp4`, 3–4 screenshots in a table with captions; relative paths only.
- Status table: the demo row ✅ only after the files are committed; every other row matches what `ci-full` proves.
- After merge and a green `ci-full`, the owner creates the annotated tag `v0.1.0` on that commit (O-11).
EOF
  txt T_OUT <<'EOF'
- A GitHub release page with binaries (not needed); deployment (post-MVP).
EOF
  txt T_FILES <<'EOF'
- `README.md` — changed
EOF
  txt T_TESTS <<'EOF'
- `check_docs.py --readme` — §8 has an inline image to an existing file under `docs/media/`, a video link when it exists, alt texts, and the demo status row matches the files. → AC-04
- `git tag --list v0.1.0` shows the tag on the green commit and the README describes that state. → AC-06
EOF
  txt T_VERIFY <<'EOF'
```bash
uv run python scripts/check_docs.py --readme --media
git tag --list v0.1.0 && git show --no-patch v0.1.0
```
EOF
  txt T_TIPS <<'EOF'
- Creating and pushing the tag is the owner's step (publishing needs approval); the agent prepares the PR only.
EOF
}
register s_009_2
