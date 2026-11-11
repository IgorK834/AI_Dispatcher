---
id: FEAT-009
title: Demo media — video, GIF and screenshots in the repository
status: approved
owner: project owner
requirements: [REQ-033]
adrs: []
modules: [docs/media, README.md]
revision: 1
---

# FEAT-009: Demo media — video, GIF and screenshots in the repository

Priority: **P0** (the recording is on the "never cut" list). Nothing in this specification is produced yet.

## 1. Goal

A short demo recording and a set of screenshots are committed to the repository and embedded in the README, so that someone can see the app working without running it. The recording is made from a version started from a clean clone.

## 2. Business context

A committed demo video (`.gif` or `.mp4`) is a delivery standard ([`DEVELOPMENT.md`](../DEVELOPMENT.md) §1, row 8c; REQ-033). The script follows the demo scenario of [`docs/report.md`](../docs/report.md) §34 and shows the standards that are hard to see in code: UX care, CRUD, the creative twist and the path without AI.

## 3. Scope / Out of scope

**In scope:** the recording script; recording settings; file names, formats and size limits; the screenshot list; embedding in the README; a pre-publication checklist; the release tag `v0.1.0`.

**Out of scope:** voice-over (optional), background music (none), marketing material, hosting the video outside the repository.

## 4. Functional requirements

### 4.1 Recording script (2–4 minutes)

Recorded in English, starting from a fresh database (first-start seed), with an LLM key configured for scenes 3–5 and removed for scene 6. Target length per scene is a guide; the total must stay within 2–4 minutes.

| # | Scene | What is shown | Proves | Target time |
|---|---|---|---|---|
| 1 | Login | `/login`: Turnstile widget passes, login as admin; switch EN → PL → EN; the "SYNTHETIC DATA" badge | auth with captcha, i18n, honesty about data | 0:00–0:20 |
| 2 | Fleet CRUD | `/fleet`: 5 drivers, vans 8/9/10 EP, remaining working and driving time bars; add a vehicle and a driver (form validation message shown once), edit, toast; delete with confirmation | CRUD, form UX, states | 0:20–1:00 |
| 3 | Ask the AI Dispatcher | `/`: type "Find the best loads for all vans for tomorrow; everyone must get home for the weekend." The trace fills: Dispatcher → Fleet & Compliance → Freight Scout (an offer with suspicious text is excluded) → Route Planner → validator | multi-agent orchestration, live trace, prompt-injection handling | 1:00–1:50 |
| 4 | Compare variants | open the recommended plan: three variants (profit / fastest / lowest fuel) with **kg CO₂** and deltas; the map; the timeline with breaks and rests; EP and kg occupancy; cost breakdown; the legal notice | optimizer, working time, creative twist | 1:50–2:40 |
| 5 | Human approval | back in the chat: the approval card; click **Reject** once (nothing is assigned), ask again or re-open, click **Approve**; `/fleet` shows the assignments | human-in-the-loop, the only write | 2:40–3:15 |
| 6 | Without AI | restart the API without the LLM key (cut in the edit); `/` shows "AI is off"; `/optimizer` runs the same optimisation by hand and shows the same kind of result | the app works without AI | 3:15–3:45 |

A shorter fallback (≤ 2 minutes: scenes 1, 2, 4 from the manual optimizer, 6) is recorded if the agent scenes are not stable on recording day (report §33, fallback plan).

- **FR-1.** Each scene has on-screen captions (one short line) because the video may be watched without sound. Captions are burned into the video or added as text overlays in the edit.
- **FR-2.** The closing frame shows the working-time notice — "The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance." — and the line "All data is synthetic."

### 4.2 Recording settings

- **FR-3.** Browser window 1440 × 900 CSS pixels, 100 % zoom, light theme, bookmarks bar and extensions hidden, a clean browser profile. Cursor visible; no notifications; system clock and unrelated tabs out of frame.
- **FR-4.** Capture at 30 fps; export `demo.mp4` as H.264 video (no audio track unless a voice-over is added), 1440 × 900 or 1280 × 800, with a bitrate chosen so that the file is **≤ 25 MB**.
- **FR-5.** `demo.gif` is a 20–40 second highlight (scenes 3–5 shortened), 960 px wide, ≤ 12 fps, **≤ 10 MB**, so that it loads inline in the README.
- **FR-6.** Git LFS is not used. Files stay well below GitHub's 100 MB per-file limit and below the 50 MB size at which GitHub warns.

### 4.3 Files

| Path | Content | Limit |
|---|---|---|
| `docs/media/demo.mp4` | full demo, 2–4 min | ≤ 25 MB |
| `docs/media/demo.gif` | highlight loop, 20–40 s | ≤ 10 MB |
| `docs/media/screenshots/01-login.png` | login with captcha and language switch | each PNG ≤ 1 MB, 1440 × 900 |
| `docs/media/screenshots/02-fleet.png` | fleet table with working-time bars | |
| `docs/media/screenshots/03-driver-form.png` | driver form with a validation message | |
| `docs/media/screenshots/04-offers.png` | offers with filters, provenance and the synthetic badge | |
| `docs/media/screenshots/05-ai-dispatcher-trace.png` | chat with the agent trace | |
| `docs/media/screenshots/06-plan-variants-co2.png` | three variants with CO₂ | |
| `docs/media/screenshots/07-plan-timeline.png` | timeline, occupancy and cost breakdown | |
| `docs/media/screenshots/08-approval-card.png` | approval card | |
| `docs/media/screenshots/09-optimizer-no-ai.png` | manual optimizer result with baselines | |
| `docs/media/screenshots/10-pl-locale.png` | one key screen in Polish | |

File names are lower-case, hyphenated and numbered in scenario order.

### 4.4 README embedding

- **FR-7.** README §8 "Demo" shows `demo.gif` inline (Markdown image with alt text that describes the scene), a link to `docs/media/demo.mp4`, and 3–4 selected screenshots in a table with captions. Relative paths only.
- **FR-8.** The README status table marks the demo row ✅ only after the files are committed.

### 4.5 Pre-publication checklist (human)

- [ ] Recorded from a clean clone started with the README steps.
- [ ] No API key, password, token, `.env` content, email of a real person or terminal with secrets is visible in any frame. The demo login uses the local demo account.
- [ ] Only synthetic data is visible; the "SYNTHETIC DATA" badge is on screen in data views; no third-party logos or branding of a freight exchange.
- [ ] The working-time notice is visible where a schedule is shown and on the closing frame.
- [ ] Nothing in the recording or captions states why or for whom the project is built (fixed purpose statement, `context.md` → Project Constraints 10).
- [ ] File sizes are within the limits; the MP4 plays in the GitHub file viewer.
- [ ] The owner approved publication (publishing media needs human approval).

- **FR-9.** After the media is merged and `ci-full` is green, the owner creates the tag `v0.1.0`.

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| — | Length | `demo.mp4` duration between 120 and 240 s |
| — | Size | limits of §4.3 |
| — | Readability | UI text legible at 100 % zoom in the exported resolution (spot check of 3 frames) |
| — | Accessibility | captions for every scene; alt text for every embedded image |

## 6. Contracts (API, data/migrations, ports, agent tools)

No API, data, port or tool change. Files and paths as in §4.3. `scripts/check_docs.py --media` (FEAT-007) is extended to check existence, extensions and size limits and, if `ffprobe` is available, the duration.

## 7. Acceptance criteria

- **AC-FEAT-009-01** [integration] Given the repository When `scripts/check_docs.py --media` runs Then `docs/media/demo.mp4` and/or `docs/media/demo.gif` exist (at least one; target both), each within its size limit, and the MP4 duration is between 120 and 240 seconds.
- **AC-FEAT-009-02** [e2e] Given the recording script of §4.1 When the owner reviews the final video against it Then all six scenes (or the documented fallback set) are present in order with captions, the reject-then-approve sequence is visible, and the closing frame shows the notice (manual review recorded in the completion report).
- **AC-FEAT-009-03** [integration] Given `docs/media/screenshots/` When `scripts/check_docs.py --media` runs Then the ten files of §4.3 exist with those names, are PNG, and each is ≤ 1 MB.
- **AC-FEAT-009-04** [unit] Given `README.md` When `check_docs.py --readme` runs Then §8 contains an inline image that points to an existing file under `docs/media/`, a link to the video when it exists, alt texts, and the status table row for the demo matches the presence of the files.
- **AC-FEAT-009-05** [e2e] Given the final media When the pre-publication checklist of §4.5 is completed by the owner Then every box is ticked and recorded in the completion report; a single unticked box blocks the merge.
- **AC-FEAT-009-06** [integration] Given the merged media and a green `ci-full` When the release is prepared Then the tag `v0.1.0` exists on that commit and the README describes that state.

## 8. Edge cases

- The MP4 exceeds 25 MB → lower the bitrate or resolution; do not split the file; do not use Git LFS.
- GIF larger than 10 MB → shorten it or reduce the frame rate.
- The agent run is slow on recording day → speed up waiting parts in the edit with a visible "×4" marker; never cut out an approval step.
- The LLM answer contains a mistake during recording → re-record; do not edit text in post-production.
- The Turnstile widget shows an error with test keys → check that the site key is the "always pass" test key.

## 9. Dependencies

- FEAT-007 done (`ci-full` green, clean-clone check passed).
- A screen recorder and an editor of the owner's choice; `ffmpeg`/`ffprobe` for export and checks (local tools, not project dependencies).
- An LLM key for scenes 3–5 (the owner's; never visible on screen).

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Check | Evidence |
|---|---|---|
| 01, 03, 04 | `scripts/check_docs.py --media --readme` in `ci-full` | job log |
| 02, 05 | manual review by the owner | completion report with the ticked checklist |
| 06 | `git tag --list v0.1.0` | repository |

## 11. Open questions

**Owner decisions (2026-11-11):** all proposed defaults in this table are accepted.

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-009-01 | MP4, GIF or both? The standard asks for one of them. | Both: the GIF inline in the README, the MP4 as the full demo. | AC-FEAT-009-01 |
| OQ-009-02 | Voice-over or captions only? | Captions only. | FR-1 |
| OQ-009-03 | Recording language. | English UI; one screenshot in Polish. | §4.1 |
| OQ-009-04 | Size limits (25 MB / 10 MB / 1 MB) — are they acceptable? | Yes; they keep the clone small and avoid GitHub's large-file warning. | AC-FEAT-009-01, 03 |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-09 | Initial draft |
| 2 | 2026-11-11 | Owner decisions on the open questions recorded (§11) |
| 3 | 2026-11-11 | Status `draft` → `approved` by the owner |
