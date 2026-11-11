# ADR-0014: Van capacity — mass, EUR-pallet equivalents and declared pallet places

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

The fleet consists of curtain-sider vans up to 3.5 t with 8, 9 or 10 euro-pallet places and about 0.8–1.1 t of payload. Findings from [`docs/report.md`](../report.md) §16.2–16.3 (dimensions from vehicle listings, confidence A):

- Mass is often the binding limit (10 pallets at 120 kg each already exceed a 1 085 kg payload).
- Pallets in 8 EP and 10 EP bodies are not placed one behind another. A **mixed layout** — one transverse column plus one longitudinal column across about 2.10 m of width — reproduces the declared capacities: 4.20 m → 5 + 3 = 8; 4.85 m → 6 + 4 = 10.
- No simple two-column layout yields 9 places for any length, and no reliable dimensions were found for 9 EP bodies.
- The freight-exchange format has no pallet fields; pallet data is enrichment with provenance.
- A curtain-sider can be loaded and unloaded from the side.

## Decision

Capacity is checked on **every leg** with three rules:

1. **Mass (exact):** Σ `weight_kg` on board ≤ `payload_kg`.
2. **Pallet places (equivalents):** Σ EUR equivalents ≤ declared `pallet_places`, where a euro pallet 1200×800 = **1.0**, a half pallet 800×600 = **0.5**, an industrial pallet 1200×1000 = **1.5** (a deliberate rounding up), an unknown type = 1.0 plus a flag.
3. **Dimensions:** a load longer or higher than the interior is incompatible, when both values are known.

Further:

- `pallet_places` is the **declared** number from the vehicle data. The layout template is used for display and plausibility only: `EUR_MIXED_5X3` (8 EP, 4.20 × 2.10 m), `EUR_MIXED_6X4` (10 EP, 4.85 × 2.10 m), `DECLARED_ONLY` for 9 EP.
- **Loading order (LIFO) is not modelled** for curtain-siders; every plan carries the flag `LOADING_ORDER_NOT_MODELLED`.
- Missing pallet data is derived from the loading length (`ceil(length_m × 2.4)`, flagged); AI-provided values only as `max(derived, ai)`; no data at all → the offer is rejected with `MISSING_CAPACITY_DATA`.

## Alternatives

| Alternative | Why it was rejected |
|---|---|
| Count pallets only (no mass check) | wrong for vans: mass binds first in many cases (golden case GOLD-003) |
| Loading metres only (as for large trailers) | ignores the mixed layout and pallet types; the exchange's `length_m` is only inferred to mean loading metres |
| Treat every pallet as one place regardless of type | industrial pallets would overfill the body (golden case GOLD-010) |
| Exact 2D packing of pallet footprints on the floor | the right long-term answer for mixed pallet types, but a solver of its own; planned post-MVP (P2: 5 cm grid) |
| Derive 9 EP capacity from a guessed geometry | no verified dimensions exist; a guess presented as a fact would violate the "no invented values" rule; declared capacity is honest |
| Enforce LIFO for all bodies | unnecessary for side-loaded curtain-siders and would remove feasible consolidations; needed later for box bodies with rear access only |

## Consequences

- The model is simple, explainable and conservative for industrial pallets; it can reject a combination that would physically fit, and (rarely) accept one whose real arrangement is awkward.
- The 9 EP van relies on its declared capacity (open question Q11); its layout diagram is not shown.
- Stackability, load securing and axle loads are not modelled.
- Pallet data quality drives feasibility; provenance and flags are shown to the user, and offers without usable capacity data are rejected with a reason.
- A future box-body or 2D model needs a new ADR and specification; the capacity check is isolated in the engine to allow that.
