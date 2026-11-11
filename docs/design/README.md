# RoutePilot AI — Design system "Clear Route v3"

> **Status (2026-11-11):** approved by the owner. Nothing is implemented yet; `apps/web` (FEAT-000, FEAT-005) builds on this document.
> **Sources of truth:** values → [`tokens.json`](tokens.json); behaviour and screens → [`specs/FEAT-005-frontend.md`](../../specs/FEAT-005-frontend.md); stack decision → [ADR-0015](../adr/ADR-0015-frontend-ui-components-and-design-system.md); how-to → [`DEVELOPMENT.md` §9](../../DEVELOPMENT.md#9-uxui-guidelines). If this file and FEAT-005 disagree, FEAT-005 wins — report the difference.
> **Mockups:** the owner's design canvas (a private Claude artifact, `https://claude.ai/artifact/G27w1YPWW9AQWNLEDU8KfT`) and its source files in [`mockups/`](mockups/). The `.dc.html` files render only inside that canvas; in the repository they are a markup and copy reference, not runnable code.

Contents: [1 Principles](#1-principles) · [2 Colour](#2-colour) · [3 Type](#3-type) · [4 Space, shape, elevation](#4-space-shape-and-elevation) · [5 Layout](#5-layout) · [6 Components](#6-components) · [7 Vehicle components](#7-vehicle-components) · [8 Data visualisation](#8-data-visualisation) · [9 Screens](#9-screens) · [10 Honesty and accessibility](#10-honesty-and-accessibility) · [11 Implementation notes](#11-implementation-notes) · [12 Do and don't](#12-do-and-dont)

---

## 1. Principles

1. **One accent: red.** Red means "act here or look here": primary actions, the active page, the route and its stops, cargo on the van, anything that needs attention. Everything else is grey. No second accent colour, no gradients for decoration.
2. **Numbers first.** Large tabular figures with units. Fuel, CO₂, tolls and travel times always carry the word "estimate".
3. **Show the vehicle.** A drawn van marks who operates a route; the top view shows where pallets sit on the floor.
4. **Honest by design.** The "SYNTHETIC DATA" badge, the working-time notice and value provenance are components, not afterthoughts.
5. **Calm surfaces.** White cards with a hairline edge on a cool light-grey page. Only sheets and dialogs float.

## 2. Colour

All colours come from [`tokens.json`](tokens.json). Components never contain raw hex, `rgb()` or named colours (AC-FEAT-005-27).

### 2.1 Core

| Token | Hex | Role | Contrast |
|---|---|---|---|
| `ground` | `#F4F5F7` | page background | — |
| `surface` | `#FFFFFF` | cards, sheets, dialogs, inputs | — |
| `well` | `#F7F8FA` | table heads, inner panels, timeline track | — |
| `line` | `#E9EBEF` | row dividers, meter track | — |
| `lineStrong` | `#D5D9E0` | input and button borders, free pallet place outline | — |
| `ink` | `#1A1D23` | primary text, vehicle drawing lines | ≈ 17:1 on white |
| `ink2` | `#474C55` | secondary text | ≈ 8.6:1 on white |
| `ink3` | `#656C76` | captions, table heads | ≈ 5.3:1 on white, ≈ 4.8:1 on `ground` |
| `red` | `#D42A22` | the accent (see §1) | ≈ 5.1:1 on white; white text on red ≈ 5.1:1 |
| `redHover` | `#B5221B` | hover of primary, red text on tints, error text | ≈ 5.8:1 on `redTint` |
| `redTint` | `#FDEDEC` | active nav, selected rows and cards, attention pills | — |
| `redSoft` | `#F5AAA6` | second data series (loading time), offer B | never used for text |
| `neutralData` | `#B6BCC6` | breaks, mass bars, baselines | never used for text |
| `window` | `#CFE3F5` | vehicle windows in illustrations only | — |

Rules:
- Red is used for **fills, lines and short labels**. Long red text is avoided; red text sits on white or `redTint` only.
- Never rely on colour alone: every status has a text label, every chart a legend and a text alternative.
- Destructive buttons are **outlined** red (red border and text on white), so they never look like the primary action.

### 2.2 Status levels

Status is either "needs attention" (red) or one of four greys. There is no green, amber or blue.

| Level | Background / text | Use | CSS class (mockups) |
|---|---|---|---|
| Done | `#E6E8EC` / `#1A1D23` | assigned, valid, yes | `rp-pill--ok` |
| Attention | `#FDEDEC` / `#B5221B` | assumption, conflict, flagged text | `rp-pill--warn` |
| Error | `#D42A22` / `#FFFFFF` | error, rejected | `rp-pill--bad` |
| Info | `#EFF1F4` / `#474C55` | derived value, waiting for you | `rp-pill--info` |
| Quiet | `#F4F5F7` / `#5B626C` | free, read-only, source | `rp-pill--mute` |
| Brand | `#FDEDEC` / `#D42A22` | the variant or item currently shown | `rp-pill--brand` |
| Synthetic | white, `#474C55` text, `#D5D9E0` outline | the SYNTHETIC DATA badge | `rp-pill--synthetic` |

Provenance tags in the offer detail map to levels: `source`, `user` → Quiet/Done; `derived`, `inferred` → Info; `default`, `assumption` → Attention; `generated_mock` → Synthetic.

### 2.3 Cargo

Pallets on the van use red tints, strong to pale, one per offer in pickup order (dark `ink` text on all of them, ≥ 6:1):

| Offer | Fill |
|---|---|
| 1st | `#EC7A74` |
| 2nd | `#F5AAA6` |
| 3rd | `#FAD4D1` |
| 4th | `#F8BFBB` |
| 5th | `#FCE6E4` |
| 6th and later | the sequence repeats; the offer id on each place keeps them apart |

A fine vertical stripe (`cargo.stripe`) is laid over every filled place. Free places are white with a dashed `#C3C9D2` outline and the text "Free".

## 3. Type

| Style | Font | Size / weight | Use |
|---|---|---|---|
| Display | Inter Tight | 40 / 500, −0.025em | plan title, sign-in headline |
| H1 | Inter Tight | 32 / 500, −0.025em | page titles |
| H2 | Inter Tight | 18 / 600 | card titles |
| H3 | Inter | 15 / 600 | sub-titles, variant names |
| Body | Inter | 14 / 400, line-height 1.5 | everything else |
| Small | Inter | 12 / 400 | captions, hints, units |
| Eyebrow / table head | Inter | 11.5 / 600, +0.06em, upper-case | table headers, section labels |
| Mono | JetBrains Mono | 12.5 / 400 | ids: `PLAN-1a2b3c4d`, `MOCK-000117`, `MAN-…`, `BUS-01` |
| KPI | Inter Tight | 28–34 / 500, tabular numbers | profit, kg, pallet places |

All numbers use tabular figures (`font-feature-settings: "tnum"`). Fonts load through `next/font/google`, self-hosted at build time (SIL Open Font Licence).

## 4. Space, shape and elevation

- **Spacing scale:** 4 · 8 · 12 · 16 · 24 · 32 · 40 px. Card padding 24, gaps between cards 16, page gutter 40.
- **Radii:** card 16 · inner panel 12 · control (button, input, segmented) 10 · segment 8 · pill 6 · circle for avatars and stop markers.
- **Elevation:** cards carry a 1 px hairline shadow (`shadow.card`); sheets and dialogs `shadow.sheet` over a `scrim`; nothing else floats.
- **Touch targets:** at least 44 × 44 px (icon buttons 44, small buttons 36 inside dense tables only).
- **Focus:** 2 px red outline with 2 px offset; inputs show a red border plus a 3 px `redTint` ring.

## 5. Layout

- Content max width 1440 px, centred, gutter 40 px; top bar 80 px.
- Layouts use flex-wrap with basis values so columns stack by themselves: main content `flex: 999 1 560–720px`, side columns `flex: 1 1 340–420px`.
- Breakpoints (FEAT-005 AC-25, DEVELOPMENT §9): ≥ 1280 px three columns on the AI Dispatcher; 768–1279 px side panels become a drawer or stack; < 768 px tables become cards, wide tables scroll inside their card.
- Desktop first; usable down to tablet width.

## 6. Components

Components are built in `apps/web/src/components/ui/` on Radix UI primitives where behaviour matters (ADR-0015). Mockup class names (`rp-…`) are listed so the reference CSS in [`mockups/routepilot.css`](mockups/routepilot.css) can be read alongside.

| Component | Anatomy and states | Mockup class |
|---|---|---|
| Top bar | logo (red box + dark cab), centred nav, SYNTHETIC DATA badge, EN/PL segmented control, account button (role + email + initials). Active page: red text on `redTint`. Admin link only for admins. | `TopBar.dc.html` |
| Button | 44 px, radius 10. Primary: red fill, white text, hover `redHover`. Secondary: white, `lineStrong` border. Danger: white, red border and text. Small: 36 px. Disabled: `well` fill, `ink3` text. | `rp-btn`, `--primary`, `--danger`, `--sm` |
| Icon button | 44 × 44 (36 in tables), always `aria-label`; optional red count badge. | `rp-icon-btn`, `rp-count` |
| Segmented control | grey track, selected segment white with red text and a soft shadow; `aria-pressed` or `role="tab"` + `aria-selected`. Used for language, objectives, map/list, stop selector. | `rp-seg` |
| Pill | 6 px radius, 12 px / 600; levels of §2.2. | `rp-pill--*` |
| Field | label above, input 44 px, hint below; focus red; error: red border, message under the field with an icon, `aria-invalid` + `aria-describedby`. | `rp-field`, `rp-input`, `rp-error` |
| Choice card | radio or checkbox as a card; selected: red border on `redTint`. | `rp-choice`, `--on` |
| Table | upper-case grey head on `well`, 14 px rows with hairline dividers, hover tint, checkbox column optional, sort icons in the head, numeric columns right-aligned. | `rp-table` |
| Meter | 6 px track on `line`; fill `ink` (normal), red (low remaining time, brand meters). Always paired with a text value. | `rp-meter`, `--low`, `--brand` |
| Route track | origin and destination labels, 4 px track, dark progress, red dot with a tint halo at the current position. | `rp-track` |
| Banner | Attention/Error on `redTint` (error adds a red hairline), Info on grey. Used for conflicts, notices, AI states. | `rp-banner--*` |
| Toast | dark `ink` pill-rectangle, white text, bottom-left; success toasts auto-dismiss, error toasts stay. | `rp-toast` |
| List row | 36 px round icon on `redTint` with a red glyph, title + pill, one-line detail, time on the right. Used in the agent trace and alerts. | `rp-row` |
| Map | grey base, white street grid, red route (3 px), red numbered stop markers with a white ring, zoom and fit controls bottom-right, attribution bottom-left; list fallback when the map cannot load. | `rp-map` |
| Card | white, radius 16, hairline shadow, header row with title left and meta/action right. | `rp-card` |

Icons: 1.4–1.6 px stroke line icons, 16 px in text, `currentColor`, `aria-hidden` unless they are the only label.

## 7. Vehicle components

### 7.1 `VanSide` — side view of the van

A drawn curtain-sider van up to 3.5 t (no photographs): grey curtain box with vertical stripes, a red band at the bottom of the box, a white label plate with the vehicle label (`BUS-01`), white cab with blue-grey windows, dark chassis and wheels, grey headlight.

| Size | Where (FEAT-005 FR-32) |
|---|---|
| 400 px | plan header |
| 460 px | sign-in page (decorative) |
| 120 px | Dispatcher proposal cards |
| 96 px | fleet table rows (Van column) |
| 88 px | optimizer result rows |

- Props: `label` (vehicle label), `width`, `accent` (red by default; dark `ink` for an inactive vehicle).
- Accessible name: `Curtain-sider van up to 3.5 t, <label>` (`role="img"`); decorative uses on the sign-in page are `aria-hidden`.
- Mockup: [`mockups/VanSide.dc.html`](mockups/VanSide.dc.html).

### 7.2 `LoadPlanTopView` — pallet placement from above (FEAT-005 FR-15, AC-FEAT-005-26)

The van floor seen from above: rear doors on the left, cab on the right (with mirrors, windscreen, headlights), both curtain sides open, wheels at the edges. Inside the cargo box the pallet places of the vehicle's layout template.

| `layout_template` | Places | Drawing |
|---|---|---|
| `EUR_MIXED_6X4` (10 EP) | T1–T6 transverse (pallet 1 200 mm across the width) + L1–L4 longitudinal | two rows: 6 tall cells, 4 wide cells |
| `EUR_MIXED_5X3` (8 EP) | T1–T5 + L1–L3 | two rows: 5 + 3 |
| `DECLARED_ONLY` (9 EP) | no floor drawing | a counter "6 / 9 EP" and the note "interior dimensions unknown" |

Numbering runs from the rear doors towards the cab, transverse row first.

**Placement rule (illustrative, front-end only).** The engine checks pallet places and mass but not positions (`LOADING_ORDER_NOT_MODELLED`). The view derives positions from the plan, so no API change is needed:
1. For each offer, `EP = loadPalletEqAfter(pickup stop) − loadPalletEqAfter(previous stop)` and `kg` likewise, from `RoutePlan.stops`.
2. Places taken by an offer = `ceil(EP)`; kg per place = `round(kg / places)`.
3. At a pickup the offer takes the lowest-numbered free places (T before L); pallets already on board never move; at the delivery its places become free.
4. Each offer gets the next cargo tint (§2.3).

Each filled place shows: place id and kg (top line), offer id in mono and "Offer A · EUR" (bottom). Free places show "Free".

**Controls and side panel.** A segmented stop selector ("Start", "1" … "n") steps through the plan; each button has `aria-pressed`. A side column shows: where the van is ("After pick-up B · Opole, Mon 08:53"), weight loaded with a red meter (`800 kg of 1 085`), pallet places with a red meter (`8 / 10 EP`), space used (`80 %`). Below the drawing: a legend (one row per offer with id and lane, plus "Free place") and the notice "Positions are illustrative. The engine checks pallet places and mass; it does not model loading order for curtain-siders, which open on both sides."

The drawing is one `role="img"` with a text alternative ("Van floor from above, after pick-up B: 8 of 10 pallet places used, 800 of 1085 kg").

Mockup: [`mockups/VanTopView.dc.html`](mockups/VanTopView.dc.html) (GOLD-001 data; its third offer sits on L3–L4, while rule 3 above places it on T1–T2 — the rule is binding).

## 8. Data visualisation

| Chart | Encoding |
|---|---|
| Timeline (plan) | track on `well` with a hairline; rounded segments with 3 px gaps, width proportional to minutes: driving red, loading/unloading `redSoft`, breaks `neutralData`, daily rest light grey hatch, waiting white with an outline. Hour labels under the track; legend with totals; a text summary of breaks and rests for screen readers. |
| Occupancy after each stop | two rounded vertical bars per stop: pallet places in red (fade to `#F6BDB9`), mass in `neutralData`; value above, stop label below; text alternative with all values. |
| Baselines (optimizer) | three rounded bars: engine result red, greedy and best single grey; values above; uplift in a well below. |
| Variants (plan) | three cards; the shown variant has a 2 px red inset border and a "Shown" brand pill; identical variants say "Same as …". |
| Map | red route and markers only; base map grey. |

No chart uses a colour outside this list.

## 9. Screens

| Route / state | Content | FEAT-005 | Mockup |
|---|---|---|---|
| `/login` | headline, van illustration, three fact tiles; sign-in card with email, password, Turnstile state, primary button, local demo hint, error banners | FR-3 … FR-5; AC-01 … 03 | `Login.dc.html` |
| `/` AI Dispatcher | conversation (user bubble dark, answer with "Verified numbers" pill, proposal cards with van, excluded-offer banner, notice, locked composer); approval card (red border, plans table, totals, comment, Approve / Reject, notice); agent trace (list rows with status pills, `aria-live`); map | FR-20 … FR-25, FR-32; AC-14, 15, 25 | `Main.dc.html` |
| `/` AI is off | panel "AI is off — no model key is configured", link to the optimizer, admin hint; budget and busy messages | FR-20, FR-21; AC-16 | `AiOff.dc.html` |
| `/fleet` | KPI cards; drivers/vehicles tabs; filters; table with van illustration, remaining-time meters, status, edit/delete; loading, empty and error states | FR-6 … FR-13, FR-32; AC-04 … 08, 19 | `Fleet.dc.html` |
| `/fleet` edit sheet | side sheet: conflict banner with Reload, fields with one error, profile choice cards, van select, Cancel / Save; toast example | FR-7, FR-8; AC-05, 06 | `DriverForm.dc.html` |
| `/fleet` delete | alert dialog naming the driver, consequences, blocked-case note, Cancel / outlined "Delete driver" | FR-9; AC-07 | `DeleteDialog.dc.html` |
| `/offers` | filter bar; offers table (source pill, route, load, price, completeness meter, flags, read-only lock for imported); detail panel with provenance per field, untrusted remark, suspicious-text banner | FR-6, FR-12; AC-09, 10 | `Offers.dc.html` |
| `/plans/[id]` | breadcrumb; title, pills, Assign / Explain, large van; variants; notice; **top-view load plan**; timeline; stops table; explanation; costs; route map with progress track; vehicle card; occupancy chart | FR-14 … FR-17, FR-31 … FR-33; AC-11, 12, 23, 26 | `Plan.dc.html` |
| `/optimizer` | run form (scope, drivers, objectives, horizon); progress; fleet solution with van per driver; baselines chart; rejections grouped by reason | FR-18, FR-32; AC-13 | `Optimizer.dc.html` |
| `/admin` | generate demo data with last-run counts; reset with typed confirmation; AI status with budget meter; read-only cost profile with basis pills | FR-30; AC-17 | `Admin.dc.html` |

Shared: top bar on every screen except sign-in; design-system board `DesignSystem.dc.html`.

Number and date formats follow the table in [`DEVELOPMENT.md` §9](../../DEVELOPMENT.md#9-uxui-guidelines) (AC-FEAT-005-24); where a mockup shows a different precision, the table wins.

Demo figures in the mockups: the D1 plan uses GOLD-001 values exactly (€323.54, 624.81 km, 76.601 l, 199.16 kg CO₂, stop times). Other drivers' figures are illustrative and must not be reused as test values.

## 10. Honesty and accessibility

- SYNTHETIC DATA badge in the top bar and on synthetic rows; no freight-exchange branding.
- The working-time notice next to every schedule (variants, approval card, plan, optimizer result, fleet table footer); fuel, CO₂, tolls and travel times labelled as estimates.
- Text contrast ≥ 4.5:1 for every text/background token pair (checked by AC-FEAT-005-27); large KPI text ≥ 3:1.
- Real `<button>`, `<a href>`, `<input>` with `<label>`; icon-only buttons have `aria-label`; dialogs trap focus and close with Escape; status changes of an agent run go to one `aria-live="polite"` region.
- Every chart and drawing has a text alternative; nothing is conveyed by colour alone.

## 11. Implementation notes

- Map `tokens.json` to CSS custom properties in `apps/web/src/styles/tokens.css` and to the Tailwind theme (`theme.colors`, `fontFamily`, `borderRadius`, `boxShadow`); Tailwind's default palette is not used.
- A lint check forbids raw colour values and `font-family` in `apps/web/src/**/*.{ts,tsx,css}` outside `styles/tokens.css` (AC-FEAT-005-27).
- Components: `components/ui/` (button, icon-button, segmented, pill, field, choice, table, meter, track, banner, toast, dialog, sheet, tooltip, tabs), `components/vehicle/van-side.tsx`, `features/plans/load-plan-top-view.tsx`.
- Radix UI primitives provide behaviour for dialog, alert dialog, popover, tooltip, tabs and toggle group; their default look is never used (ADR-0015).
- All copy comes from `messages/en.json` and `messages/pl.json`; the mockups contain English copy only.

## 12. Do and don't

| Do | Don't |
|---|---|
| Use red for the one thing to do or look at on a card | Add a second accent (green, blue, yellow) |
| Write status as text in a pill | Use colour dots without words |
| Show the van with its label wherever a vehicle operates a route | Use photos or third-party vehicle imagery |
| Label positions in the top view as illustrative | Suggest the engine planned the loading order |
| Keep destructive buttons outlined | Make "Delete" look like the primary action |
| Keep numbers tabular with units | Mix fonts or weights for figures |
