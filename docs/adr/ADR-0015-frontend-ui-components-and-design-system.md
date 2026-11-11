# ADR-0015: Frontend UI — own design system on Tailwind and Radix primitives, no shadcn/ui

- Status: accepted (2026-11-11)
- Date: 2026-11-11

## Context

ADR-0001 fixed Next.js 16 for the frontend, and `context.md`, FEAT-000 and FEAT-005 named "Tailwind + shadcn/ui" for components. During the design work the owner approved a dedicated design system, "Clear Route v3" ([`docs/design/README.md`](../design/README.md), values in [`docs/design/tokens.json`](../design/tokens.json)): neutral surfaces with red as the only accent, a red-tint cargo palette, drawn vehicle components (van side view, top-view load plan) and its own component anatomy. The owner decided not to use shadcn/ui, so that the interface does not carry the look of a stock component kit. The application still needs accessible dialogs, menus, tooltips and tabs, and the deadline (2026-11-15) leaves no room for hand-written focus management.

This ADR supersedes the shadcn/ui part of [`docs/report.md`](../report.md) §9 and of the web row in `context.md` → Selected Technology Stack.

## Decision

- **Styling:** Tailwind CSS with a theme generated from `docs/design/tokens.json` (colours, fonts, radii, shadows) plus CSS custom properties in `apps/web/src/styles/tokens.css`. Tailwind's default colour palette is not used.
- **Behaviour:** Radix UI primitives (MIT) for dialog, alert dialog, popover, tooltip, tabs and toggle group — unstyled, styled only with the tokens. Each package and version is verified in the npm registry when it is added (FEAT-000 / FEAT-005).
- **Components:** own components in `apps/web/src/components/ui/` (button, icon button, segmented control, pill, field, choice card, table, meter, route track, banner, toast, dialog, sheet, tooltip, tabs); vehicle components in `apps/web/src/components/vehicle/` and `apps/web/src/features/plans/`.
- **Fonts:** Inter, Inter Tight and JetBrains Mono through `next/font/google` (self-hosted at build time, SIL Open Font Licence).
- **Guard:** a lint check rejects raw colour values and `font-family` outside `styles/tokens.css`, and a test checks that every text/background token pair reaches 4.5:1 (AC-FEAT-005-27).

## Alternatives

| Option | Why not |
|---|---|
| shadcn/ui, restyled with the tokens | owner decision: avoid the stock-kit look and its copied component code; the restyle would touch every component anyway |
| Headless UI | fewer primitives than Radix (no tooltip, toggle group); smaller ecosystem for React 19 |
| MUI, Chakra UI, Mantine | strong default look to override, runtime styling, larger bundles; conflicts with Tailwind |
| No primitives at all | dialogs, focus traps, tooltips and tabs written by hand — accessibility risk within the deadline |

## Consequences

- More component code of our own (about fifteen small components); they are covered by component tests in FEAT-005 slices.
- The look is consistent and owned: one accent, documented status levels, documented vehicle components.
- New dependencies: Radix UI primitive packages (behaviour only). No GPL/AGPL; versions pinned in `pnpm-lock.yaml`.
- `context.md`, `AGENTS.md`, `README.md`, FEAT-000 (revision 4) and FEAT-005 (revision 4) are updated to name this stack.
- Replacing the design system later is a new ADR.
