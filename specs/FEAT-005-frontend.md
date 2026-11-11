---
id: FEAT-005
title: Frontend — login, AI Dispatcher, fleet, offers, plans, optimizer, admin
status: approved
owner: project owner
requirements: [REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-011, REQ-015, REQ-016, REQ-017, REQ-019, REQ-021, REQ-031, NFR-005, NFR-010]
adrs: [ADR-0001, ADR-0009, ADR-0012, ADR-0015]
modules: [apps/web: app, features/{auth,agent-chat,fleet,offers,plans,optimizer,admin}, components/{ui,vehicle}, styles, lib/api, lib/format, messages]
revision: 4
---

# FEAT-005: Frontend — login, AI Dispatcher, fleet, offers, plans, optimizer, admin

Priority: **P0** (key screens in EN and PL). Nothing in this specification is implemented yet.

> Every screen that shows a schedule displays the notice (translated for the PL locale; Polish wording in the Polish summary of [`README.md`](../README.md)): "The work/driving/rest schedule is a planning estimate based on a simplified model of selected rules (Polish Act on Drivers' Working Time; Regulation (EC) No 561/2006). It does not certify legal compliance."

## 1. Goal

A web interface in which a dispatcher can log in, manage the fleet and offers with full CRUD, talk to the AI Dispatcher while watching the agents work, compare three plan variants with their CO₂ footprint, approve or reject assignments, and run the optimizer by hand when AI is off — in English and Polish, with clear loading, empty and error states.

## 2. Business context

The interface is how the API's quality becomes visible: smooth communication with the backend and care for UX/UI are delivery standards ([`DEVELOPMENT.md`](../DEVELOPMENT.md) §1, rows 3, 6, 7c, 7d). The screens follow [`docs/report.md`](../docs/report.md) §11.4; the UX rules follow `DEVELOPMENT.md` §9, which this specification makes testable.

## 3. Scope / Out of scope

**In scope:** the seven screens of §4.1; the typed API client and SSE helper; session and CSRF handling; i18n EN/PL for all texts on these screens; the UX rules of `DEVELOPMENT.md` §9; the design system "Clear Route v3" of [`docs/design/`](../docs/design/README.md) (tokens, own components on Radix UI primitives — ADR-0015); the vehicle components (van side view, top-view load plan); a map with a list fallback; component tests with MSW. Screen mockups: [`docs/design/mockups/`](../docs/design/mockups/) (reference for layout and copy; this specification wins where they differ).

**Out of scope:** user administration and model-policy editing (P1); full translation coverage beyond the listed screens (P1); automated axe checks (P1); road alternatives in the plan view (FEAT-008); a mobile-first layout (the app is desktop-first, usable down to tablet width); offline mode; dark theme.

## 4. Functional requirements

### 4.1 Screens

| Route | Feature folder | Content | Roles |
|---|---|---|---|
| `/login` | `auth` | email, password, Turnstile widget, language switch; in `APP_ENV=local` a hint with the demo account names | public |
| `/` | `agent-chat` | AI Dispatcher: chat thread; side panel with the live agent trace and approval cards; map of drivers and proposed routes | all |
| `/fleet` | `fleet` | table of drivers with van, base, position, availability, bars of remaining working and driving time, `home_by`; add/edit/delete driver and vehicle; add driver state | read: all; write: per FEAT-001 §6.5 |
| `/offers` | `offers` | table of offers with filters, completeness, provenance, quality flags, "SYNTHETIC DATA" badge; add/edit/delete manual offers | all |
| `/plans/[id]` | `plans` | one plan in detail; when opened from a job result: three variants side by side (profit / fastest / fuel) with profit, finish time, litres, **kg CO₂** and deltas; map; timeline; occupancy; cost breakdown; explanation; assign button | all |
| `/optimizer` | `optimizer` | manual optimisation without AI: choose scope, drivers, objectives; progress; result with fleet solutions, baselines and the rejection list | all |
| `/admin` | `admin` | demo data: generate (seed, reference date) and reset; read-only view of the cost profile and of the AI status | admin |

- **FR-1 Navigation.** A top bar with the screens allowed for the role, the language switch, the user menu (email, role, logout) and a permanent "SYNTHETIC DATA" badge while demo data is present.
- **FR-2 Route protection.** Without a session every route except `/login` redirects to `/login?next=…`. A `401` from any API call clears the client session state and redirects the same way. `/admin` shows a "no access" page for non-admins.

### 4.2 Login

- **FR-3.** The form validates email format and non-empty password before sending. The Turnstile widget is rendered with the site key from `GET /auth/captcha-config`; the submit button is enabled only when a captcha token exists.
- **FR-4.** Errors by problem `code`: `INVALID_CREDENTIALS` ("Wrong email or password"), `CAPTCHA_FAILED` (message + the widget resets), `RATE_LIMITED` (message with the wait time from `Retry-After`). The password field is cleared after a failed attempt; the email stays.
- **FR-5.** After login the client stores `csrfToken` in memory, loads `/auth/me` on every full page load, and sends `X-CSRF-Token` and `credentials: 'include'` on every state-changing request.

### 4.3 Fleet and offers (CRUD)

- **FR-6 Lists.** Cursor-paginated tables ("Load more"); filters in the URL query so that a view can be shared; each list implements loading (skeleton rows), empty (message + primary action), error (message by `code` + "Try again") and data states.
- **FR-7 Forms.** Create and edit in a side sheet, built with react-hook-form and a Zod schema that mirrors the API limits (FEAT-001 §6.1). Messages appear under the field. Server `422` errors are mapped to fields through `errors[].field`; unknown fields go to a form-level alert.
- **FR-8 Concurrency.** Edit forms send the `version` they loaded. On `409 VERSION_CONFLICT` the sheet stays open with the user's input and shows "This record was changed elsewhere" with a "Reload" action.
- **FR-9 Delete.** A confirmation dialog names the item; the confirm button is labelled with the verb. Conflicts (`DRIVER_HAS_ACTIVE_ASSIGNMENT`, `VEHICLE_ASSIGNED_TO_DRIVER`, `COST_PROFILE_IN_USE`) are shown as an explanation, not as a generic error.
- **FR-10 Feedback.** A toast after every successful create, update and delete; the list refreshes through TanStack Query invalidation without a full reload.
- **FR-11 Role-dependent actions.** Buttons the role may not use are hidden (not just disabled). A `403` that still happens shows a "no permission" toast.
- **FR-12 Offers.** Provider offers have no edit or delete actions and show the tooltip "Imported offers are read-only". The detail view shows per-field provenance (`source`, `derived`, `inferred`, `default`, `generated_mock`, `user`), missing fields and quality flags. Free text from offers is rendered as plain text (never as HTML).
- **FR-13 Working-time bars.** For each driver two bars per profile-relevant limit (remaining daily and weekly work; in the detail also the 561 driving limits), computed by the API (`driver` + `state`), with the legal notice in a tooltip.

### 4.4 Plans and optimizer

- **FR-14 Variants.** Three cards side by side: Most profitable, Fastest, Lowest fuel. Each shows net profit, finish time, distance, litres, kg CO₂ and the difference to the `profit` variant (Δ profit, Δ time, Δ litres, Δ CO₂). If two variants are the same plan the cards say so. Fuel and CO₂ carry the label "estimate".
- **FR-15 Plan detail.** Ordered stop list with arrival, service start and departure in the stop's local time; a timeline with coloured segments for driving, service/work, waiting, break and rest (each with a text label); occupancy after each stop in EUR equivalents and kg against the van's limits; a **top-view load plan** (`docs/design/README.md` §7.2): the van floor from above with the pallet places of `EUR_MIXED_6X4` (T1–T6 + L1–L4) or `EUR_MIXED_5X3` (T1–T5 + L1–L3), a stop selector ("Start", "1" … "n", `aria-pressed`), and for the selected stop the occupied places with offer id and kg per place, free places marked "Free", weight and pallet places against the limits, and the notice that positions are illustrative (loading order is not modelled). Positions are derived in the browser from `RoutePlan.stops`: per offer `EP` and kg are the load deltas at its pickup, places taken = `ceil(EP)`, a pickup takes the lowest-numbered free places (T before L), pallets on board never move, a delivery frees its places; each offer gets the next red cargo tint. For `DECLARED_ONLY` only a counter ("6 / 9 EP") is shown; the cost breakdown with "assumption" markers; plan warnings in plain language; the legal notice.
- **FR-16 Explanation.** A button "Explain this plan" calls `POST /route-plans/{id}/explanations` and shows headline, reasons and trade-offs with a small label "AI" or "Template".
- **FR-17 Assign.** "Assign this plan" opens a confirmation with driver, offers and profit, then calls `POST /assignments`. `409 PLAN_NOT_ASSIGNABLE` explains which part is stale and offers to re-run the optimisation. Baseline plans have no assign button.
- **FR-18 Optimizer.** The form posts a job with a fresh `Idempotency-Key`, then polls the job every second, showing the phase and `driversDone / driversTotal`. On success it shows per objective the fleet solution (table of drivers → plan → profit, finish, litres, CO₂), the two baselines with the uplift, and a collapsible rejection list grouped by reason code with translated explanations. A failed job shows `error.code` and a "Run again" button.
- **FR-19 Map.** MapLibre map with the driver positions and, for a selected plan, the numbered stops and the route geometry (dashed when `approximate`). Attribution for the map data is always visible. If the map cannot load (no tile provider or network), the same information is shown as an ordered list and nothing else breaks.

### 4.5 AI Dispatcher

- **FR-20 AI status.** On load the screen calls `GET /agent/status`. With `aiEnabled = false` the chat input is replaced by a panel "AI is off — no model key is configured" with a button to the manual optimizer.
- **FR-21 Sending.** Sending a message creates a thread if needed, posts the message with an `Idempotency-Key`, opens the SSE stream for the returned run and disables the input until `run_finished`. `409 RUN_IN_PROGRESS`, `429 AI_BUDGET_EXCEEDED` and `503 AI_UNAVAILABLE` have their own messages.
- **FR-22 Trace.** The side panel lists steps as they arrive: agent name, step type (model, tool, check, waiting for you), tool name, a one-line result, duration and tokens. Rejected and failed steps are visibly marked. The run status is announced in an `aria-live="polite"` region.
- **FR-23 Answer.** `message_delta` text is shown as a greyed draft; `final_answer` replaces it. Proposals are rendered as cards linking to `/plans/{id}`; a label shows "verified numbers" when `grounded = true` and "template answer" when `source = "template"`.
- **FR-24 Approval card.** On `approval_required` a card shows the plans (driver, offers, profit, finish time, home in time yes/no), totals and the legal notice, with the buttons Approve and Reject and an optional comment. The buttons call `POST …/resume`; they are disabled after the first click. `approval_resolved` updates the card; after approval the fleet view shows the assignments.
- **FR-25 Reconnect.** If the stream drops, the client reconnects with `Last-Event-ID` (the browser's `EventSource` does this) and, after three failures, falls back to polling `GET /agent/runs/{id}` every 2 s.

### 4.6 Cross-cutting

- **FR-26 Typed client.** All HTTP calls go through `lib/api/client.ts` (`openapi-fetch` with types generated by `openapi-typescript` from `contracts/openapi.json`). Hand-written request or response types are forbidden. One error helper turns a problem+json body into `{ code, message, fieldErrors, requestId }`.
- **FR-27 i18n.** All texts come from `messages/en.json` and `messages/pl.json` through next-intl; both files have the same keys; the locale is stored in a cookie and applied on the server render. Error messages are keyed by problem `code` (`errors.VERSION_CONFLICT`, …) and rejection reasons by engine code (`rejections.OVERWEIGHT`, …), with a generic fallback for unknown codes.
- **FR-28 Formatting.** Money, distance, mass, duration, date-time, fuel and CO₂ are formatted only through `lib/format/*` as specified in `DEVELOPMENT.md` §9.
- **FR-29 Accessibility.** The basics of `DEVELOPMENT.md` §9 and `docs/design/README.md` §10: labels, keyboard operation, focus management in dialogs, text next to colour, contrast, text alternatives for charts and drawings.
- **FR-30 Admin.** The generate form (seed, reference date) and the reset button (with a typed confirmation "RESET") call the endpoints of FEAT-002 §6.7 and show the returned counts.
- **FR-31 Design system.** Colours, fonts, radii and shadows come only from [`docs/design/tokens.json`](../docs/design/tokens.json), mapped to CSS variables in `styles/tokens.css` and the Tailwind theme. Red (`#D42A22`) is the only accent: primary actions, the active page, routes and stop markers, cargo and attention states; every other status is grey and spelled out in text (`docs/design/README.md` §2.2). Components live in `components/ui/` and use Radix UI primitives only for behaviour (ADR-0015). Timeline and chart colours follow `docs/design/README.md` §8.
- **FR-32 Vehicle illustration.** A drawn side view of the van (`components/vehicle/van-side.tsx`, `docs/design/README.md` §7.1) with the vehicle label is shown wherever a vehicle operates a route: plan header (400 px), Dispatcher proposal cards (120 px), fleet table rows (96 px) and optimizer result rows (88 px). Its accessible name is "Curtain-sider van up to 3.5 t, <label>". No photographs.
- **FR-33 Vehicle card and route progress.** The plan view shows a vehicle card (label, type, body, pallet places and layout, payload, interior, sleeper cab, fuel assumption) and, under the route map, a progress line from origin to destination with the current position (before departure: at the origin, "Not started").

## 5. Non-functional requirements (with a measure)

| ID | Requirement | Measure |
|---|---|---|
| NFR-005 | The UI is fully usable without AI | E2E path through `/optimizer` with no LLM key |
| NFR-010 | Accessibility of key views | manual checklist of §"UX acceptance checklist" (P0); axe (P1) |
| — | No contract drift | generated `schema.d.ts` matches `contracts/openapi.json` (CI Gate 4) |
| — | Type safety | `tsc --noEmit` with `strict` and `noUncheckedIndexedAccess`; no `any`, no `@ts-ignore` |
| — | Perceived speed | a skeleton or spinner appears within 100 ms of any navigation or submit; no blank screen |
| — | Coverage | `lib/` ≥ 80 % lines |

## 6. Contracts (API, data/migrations, ports, agent tools)

- **API consumed:** FEAT-000 (`/health`), FEAT-001 (auth, CRUD), FEAT-002 (admin demo data), FEAT-004 (jobs, plans, assignments), FEAT-006 (agent status, threads, runs, SSE, explanations). This feature defines no endpoint.
- **Generated files (never edited by hand):** `apps/web/src/lib/api/schema.d.ts`.
- **SSE:** event names and payloads of FEAT-006 §6.3; `lib/api/sse.ts` exposes a typed `subscribeToRun(runId, handlers)` with reconnect.
- **Configuration:** `NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000`), `NEXT_PUBLIC_MAP_STYLE_URL` (optional; empty → list fallback, see OQ-005-01).
- **Message keys:** namespaces `common`, `auth`, `fleet`, `offers`, `plans`, `optimizer`, `chat`, `admin`, `errors`, `rejections`, `warnings`, `legal`.
- **Data / ports / agent tools:** No change.

## 7. Acceptance criteria

Component tests use Vitest, Testing Library and MSW handlers typed from the OpenAPI schema. E2E criteria run in Playwright against locally started API and web (FEAT-007).

- **AC-FEAT-005-01** [e2e] Given the seeded local app When the user enters the demo credentials, the Turnstile test widget passes and the form is submitted Then the user lands on `/`, the top bar shows the email and role, and a reload keeps the session.
- **AC-FEAT-005-02** [unit] Given MSW answers `401 INVALID_CREDENTIALS`, `400 CAPTCHA_FAILED` and `429 RATE_LIMITED` (with `Retry-After: 30`) When the login form is submitted in each case Then the form shows the three distinct translated messages, clears the password, keeps the email, and resets the captcha in the second case.
- **AC-FEAT-005-03** [unit] Given no session When `/fleet` is opened Then the app redirects to `/login?next=/fleet`; Given a `401` on a data request Then the same redirect happens; Given a dispatcher opening `/admin` Then a "no access" page is shown.
- **AC-FEAT-005-04** [unit] Given the drivers request is pending, returns an empty list, fails with a `500` problem, or returns five drivers When the fleet screen renders in each case Then the fleet screen shows respectively skeleton rows, the empty state with an "Add driver" action, an error message with "Try again" and the `requestId`, and the table with working-time bars.
- **AC-FEAT-005-05** [unit] Given the driver form When it is submitted with an empty name and latitude 123 Then both fields show messages under them and no request is sent; Given a server `422` with `errors[].field = "homeLon"` Then that field shows the server message.
- **AC-FEAT-005-06** [unit] Given an edit form loaded with `version = 3` When the server answers `409 VERSION_CONFLICT` Then the sheet stays open, the typed values are preserved, the conflict message with "Reload" is shown, and "Reload" refetches the driver.
- **AC-FEAT-005-07** [unit] Given a driver row When Delete is clicked Then a dialog names the driver and nothing is sent until the confirm button is pressed; on `204` a success toast appears and the row disappears; on `409 DRIVER_HAS_ACTIVE_ASSIGNMENT` the dialog explains the reason.
- **AC-FEAT-005-08** [unit] Given any logged-in role (`admin`, `dispatcher`, `demo`) When the vehicle section of the fleet screen is used Then a vehicle can be created, edited and deleted through the UI with the same form, conflict and toast behaviour, and `409 VEHICLE_ASSIGNED_TO_DRIVER` is explained.
- **AC-FEAT-005-09** [unit] Given the offers screen When filters for source, origin country and minimum completeness are set Then the request carries those query parameters, the URL reflects them, the "SYNTHETIC DATA" badge is visible on synthetic rows, and the detail shows provenance per field and the quality flags.
- **AC-FEAT-005-10** [unit] Given a dispatcher When the offers screen is used Then a manual offer with two stops can be created, edited and deleted; Given a provider offer Then no edit/delete controls exist and the tooltip explains why; offer free text containing `<script>` is rendered as text.
- **AC-FEAT-005-11** [unit] Given a job result with three different variants When the plan view renders Then three cards show profit, finish time, distance, litres and kg CO₂ with deltas to the `profit` variant, fuel and CO₂ are labelled as estimates, and the legal notice is visible; Given two variants that reference the same plan Then their cards say they coincide.
- **AC-FEAT-005-12** [unit] Given the GOLD-001 plan as fixture data When the plan detail renders Then the detail shows 6 pickup/delivery stops in order, the timeline has two break segments and one rest segment with text labels, occupancy peaks at 8.0 / 10 EP and 800 / 1 085 kg, and the cost breakdown marks assumption-based parameters.
- **AC-FEAT-005-13** [e2e] Given no LLM key When the user opens `/optimizer`, starts a fleet optimisation and waits Then progress is shown, the result lists a fleet solution per objective with baselines and rejections, a plan can be opened and assigned after a confirmation, and the fleet screen then shows the assignment.
- **AC-FEAT-005-14** [unit] Given a mocked SSE stream (`run_started`, steps for three agents, `final_answer`, `run_finished`) When a message is sent Then the input is disabled during the run, each step appears in the trace panel with agent, tool, status and duration, the draft text is replaced by the final answer with proposal cards, and the input is enabled again.
- **AC-FEAT-005-15** [unit] Given an `approval_required` event When it arrives on the stream Then an approval card shows plans, totals and the legal notice; clicking Approve sends one `resume` request with `decision = "approve"` and disables both buttons; `approval_resolved` updates the card; clicking Reject with a comment sends `decision = "reject"` and the comment.
- **AC-FEAT-005-16** [unit] Given `GET /agent/status` returns `aiEnabled = false` When the AI Dispatcher screen loads Then the chat input is replaced by the "AI is off" panel with a link to `/optimizer`; Given `503 AI_UNAVAILABLE` on send Then the same panel appears.
- **AC-FEAT-005-17** [unit] Given an admin on `/admin` When Generate is submitted with a seed Then the returned counts are shown; Reset requires typing the confirmation word before the request is sent.
- **AC-FEAT-005-18** [unit] Given `messages/en.json` and `messages/pl.json` When they are compared and the language is switched Then they have identical key sets; switching the language changes all visible texts of the login, fleet and plan screens without a reload of data; and the lint rule fails on a hard-coded string literal in a component fixture.
- **AC-FEAT-005-19** [unit] Given the login form, the driver form and the delete dialog When they are rendered and operated with the keyboard Then every input has an accessible name, the dialog traps focus and closes with Escape returning focus to the trigger, status badges contain text, and the run status region has `aria-live="polite"`.
- **AC-FEAT-005-20** [contract] Given `contracts/openapi.json` When the type generation runs Then `schema.d.ts` is unchanged (no drift), and a repository search finds no `fetch(` call outside `lib/api/`.
- **AC-FEAT-005-21** [unit] Given a stream that errors after event 4 When the connection drops Then the SSE helper reconnects with `Last-Event-ID: 4` and no step is shown twice; after three failed reconnects it polls the run until it finishes.
- **AC-FEAT-005-22** [unit] Given problem bodies with the codes of `DEVELOPMENT.md` §4.5 When they are passed to the error helper Then the error helper returns the translated message for each known code in EN and PL and a generic message plus `requestId` for an unknown code.
- **AC-FEAT-005-23** [unit] Given a plan with geometry When the plan map renders Then the map shows numbered stop markers in plan order and the route (dashed when `approximate`) with attribution; Given the map fails to initialise Then the ordered stop list is shown instead and no error boundary is triggered.
- **AC-FEAT-005-24** [unit] Given the locales `en` and `pl` When values are formatted Then `lib/format` renders 123450 minor EUR as "€1,234.50" and "1 234,50 €", 624.81 km as "625 km" in lists, 805 minutes as "13 h 25 min", and a stop time in the stop's time zone with the zone abbreviation.
- **AC-FEAT-005-25** [unit] Given viewport widths 1280, 900 and 600 px When the chat screen renders at each width Then the chat screen shows respectively the three-column layout, the trace panel as a drawer, and stacked cards; no horizontal page scroll appears.

- **AC-FEAT-005-26** [unit] Given the GOLD-001 plan as fixture data and vehicle layout `EUR_MIXED_6X4` When the top-view load plan renders and the stop selector is set to each stop in turn Then the number of occupied places is 4, 8, 4, 6, 2 and 0 after stops 1 to 6, every occupied place shows its place id, an offer id and the kg per place, every other place shows "Free", the weight and pallet-place figures match the plan's load after that stop, the notice about illustrative positions is visible, and the selector is a keyboard-operable button group whose current button has `aria-pressed="true"`; and Given a vehicle with layout `DECLARED_ONLY` Then no floor drawing is rendered and only the counter is shown.
- **AC-FEAT-005-27** [unit] Given the web source and `docs/design/tokens.json` When the design checks run Then the lint rule fails on a component fixture that contains a raw colour value or a `font-family` outside `styles/tokens.css` and passes on the real source, every text/background token pair used for text reaches a contrast of at least 4.5:1, and the van illustration with the accessible name "Curtain-sider van up to 3.5 t, BUS-01" renders in the plan header, a Dispatcher proposal card, a fleet table row and an optimizer result row.

### UX acceptance checklist (reviewed by a human before FEAT-005 is marked implemented)

- [ ] Every list has loading, empty, error and data states (AC-04, 09).
- [ ] Every delete asks for confirmation and names the item (AC-07).
- [ ] Every create, update and delete ends with a toast (AC-07, 08, 10).
- [ ] Validation messages are under the fields, in plain words, in both languages (AC-05, 18).
- [ ] A version conflict never loses the user's input (AC-06).
- [ ] The whole CRUD flow works with the keyboard only (AC-19).
- [ ] The language switch is on every screen, including login (AC-18).
- [ ] The "SYNTHETIC DATA" badge is visible wherever demo data is shown (AC-09).
- [ ] The legal notice is next to every schedule: plan view, variants, approval card, optimizer result (AC-11, 15).
- [ ] Fuel, CO₂, tolls and travel times are labelled as estimates (AC-11).
- [ ] The app is usable without AI and says so clearly (AC-13, 16).
- [ ] Numbers, dates and money are formatted consistently (AC-24).
- [ ] Nothing important is conveyed by colour alone (AC-19).
- [ ] At 1024 px width nothing overlaps or scrolls sideways (AC-25).
- [ ] Red is the only accent colour; every status is readable as text; screens match `docs/design/mockups/` in layout and hierarchy (AC-27).
- [ ] The van appears wherever a vehicle operates a route, and the top-view load plan says that positions are illustrative (AC-26, 27).

## 8. Edge cases

- Session expires while a form is open → on submit the `401` redirects to login with `next`; unsaved input is lost (accepted in the MVP; a warning toast says the session expired).
- The API is down → a full-page message "Cannot reach the API at <base URL>" with a retry button and a hint to check that the API is running on port 8000.
- A CORS failure (no response readable) → the same full-page message; the console hint points to `CORS_ALLOWED_ORIGINS`.
- Double click on a submit button → one request (button disabled; jobs and messages also carry an `Idempotency-Key`).
- A very long offer description or remark → truncated with "show more"; never rendered as HTML.
- A plan with warnings `ROUTING_FALLBACK` or `GEOMETRY_APPROXIMATE` → a visible note "distances are rough estimates".
- An approval card that expired → buttons disabled, text "This request expired".
- Two browser tabs: one approves → the other receives `approval_resolved` and updates.
- Unknown rejection or warning code from a newer API → generic translated text plus the raw code.
- Polish plural forms (1 offer / 2–4 / 5+) → ICU plural rules in the messages.

## 9. Dependencies

- Contracts of FEAT-001, 002, 004, 006. Development before those APIs exist uses MSW handlers generated from `contracts/openapi.json`.
- ADR-0001, ADR-0009, ADR-0012, ADR-0015.
- Design system: [`docs/design/README.md`](../docs/design/README.md), [`docs/design/tokens.json`](../docs/design/tokens.json), mockups in [`docs/design/mockups/`](../docs/design/mockups/).
- Libraries (versions in [`docs/report.md`](../docs/report.md) §9.2; verify in the registry): next, react, typescript, tailwindcss, Radix UI primitives for dialog, alert dialog, popover, tooltip, tabs and toggle group (ADR-0015; no shadcn/ui), @tanstack/react-query, react-hook-form, zod, maplibre-gl, react-map-gl, next-intl, openapi-typescript, openapi-fetch, @marsidev/react-turnstile (or the Cloudflare script), vitest, @testing-library/react, msw.
- Shared files: `apps/web/messages/*.json`, `pnpm-lock.yaml`.

## 10. Test plan (AC → test, fixtures, golden, eval scenarios)

| AC | Test location | Fixtures / data |
|---|---|---|
| 02–12, 14–19, 21–26 | `apps/web/src/features/**/*.test.tsx`, `apps/web/src/lib/**/*.test.ts` (titles contain `[AC-FEAT-005-nn]`) | MSW handlers; fixture JSON built from the golden cases (GOLD-001 plan for AC-12 and AC-26) |
| 27 | `apps/web/src/styles/tokens.test.ts` (contrast of token pairs), lint rule with a fixture under `apps/web/src/test/fixtures/`, `apps/web/src/components/vehicle/van-side.test.tsx` and the four screen tests | `docs/design/tokens.json` |
| 20 | CI Gate 4 + `apps/web/scripts/check-fetch-usage` | `contracts/openapi.json` |
| 01, 13 | `tests/e2e/*.spec.ts` (Playwright) | locally started API and web with seeded data, no LLM key |

## 11. Open questions

**Owner decisions (2026-11-11):** all proposed defaults in this table are accepted, with these changes. OQ-005-02: the driver and vehicle write buttons are shown to every role (FEAT-001 OQ-001-01); cost profiles stay read-only. OQ-005-01: the suggested value of `NEXT_PUBLIC_MAP_STYLE_URL` is `https://tiles.openfreemap.org/styles/liberty` (no key; the owner checks its terms before a public deployment); empty still means the list fallback. OQ-005-04: use `@marsidev/react-turnstile` (1.6.3 declares React 19 support).

| ID | Question | Proposed default | Blocks |
|---|---|---|---|
| OQ-005-01 | Map tile provider (Q8 in `context.md`). | A free style with OSM attribution set through `NEXT_PUBLIC_MAP_STYLE_URL`; when empty, the list fallback. The owner chooses the provider and checks its terms. | AC-FEAT-005-23 (map path) |
| OQ-005-02 | Fleet write buttons for `dispatcher` — depends on OQ-001-01. | Hidden for non-admins. | AC-FEAT-005-08 |
| OQ-005-03 | Show `message_delta` drafts or only the final answer (OQ-006-08)? | Show greyed drafts. | AC-FEAT-005-14 |
| OQ-005-04 | Turnstile integration: `@marsidev/react-turnstile` or the plain Cloudflare script. | The library, if its version works with React 19; otherwise the script. | AC-FEAT-005-01 |
| OQ-005-05 | Should the UI offer editing of cost profiles in the MVP (the API has full CRUD)? | Read-only view in `/admin`; editing through the API docs page. Report §11.4 puts cost profiles under P1 for the admin screen. | scope of `/admin` |

## 12. Changelog

| Revision | Date | Change |
|---|---|---|
| 1 | 2026-11-09 | Initial draft |
| 2 | 2026-11-11 | Owner decisions on the open questions recorded (§11); fleet write buttons for all roles (AC-FEAT-005-04, 08) |
| 3 | 2026-11-11 | Status `draft` → `approved` by the owner |
| 4 | 2026-11-11 | Owner decisions: design system "Clear Route v3" (`docs/design/`) and ADR-0015 (no shadcn/ui). FR-15 extended with the top-view load plan; new FR-31 (design tokens), FR-32 (vehicle illustration), FR-33 (vehicle card, route progress); new AC-FEAT-005-26, AC-FEAT-005-27; UX checklist +2 lines; §3, §9, §10 updated. Front-matter `revision` aligned with this changelog |
