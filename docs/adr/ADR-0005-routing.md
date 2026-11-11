# ADR-0005: Routing — demo city matrix in the repository, optional OpenRouteService, haversine fallback

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

The engine needs distances and travel times between all relevant points. The application must work offline and without any API key, tests must be deterministic, and the MVP must cost nothing to run. Vans up to 3.5 t can use a car / light-commercial routing profile: truck restrictions and the German truck toll do not apply to them (verified in [`docs/report.md`](../report.md) §17.4, §21), so a truck routing engine is not required. The demo offers lie in about 40 cities.

## Decision

- **Port `RoutingProvider`** (`matrix`, `route`). The engine receives a ready matrix and never calls a provider.
- **Default source: a committed matrix** `data/mock/routing-matrix.json` for the demo cities (deterministic, offline).
- **Optional: OpenRouteService API** when `ORS_API_KEY` is set — profile `driving-car`, durations multiplied by `van_speed_factor` (default 1.08, an assumption), every response cached in `routing_cache`.
- **Fallback: haversine estimation** (`HaversineRoutingProvider`); plans computed with it carry the warning `ROUTING_FALLBACK`.
- Tests never call ORS; they use the repo matrix, recorded fixtures or the haversine provider.

## Alternatives

Weighted matrix from report §10.4:

| Criterion | Weight | **ORS API (free)** | Self-hosted OSRM/Valhalla | Haversine only | HERE/Google (paid) |
|---|---|---|---|---|---|
| Realism for vans | 25 | 4 | 4 | 1 | 5 |
| Cost | 20 | 5 | 4 | 5 | 2 |
| Implementation time | 20 | 5 | 2 | 5 | 4 |
| Test determinism | 15 | 3 (4 with cache) | 5 | 5 | 2 |
| Road alternatives / avoiding motorways | 10 | 4 | 4 | 1 | 5 |
| Independence | 10 | 3 | 5 | 5 | 2 |
| **Score** | 100 | **86** (with cache) | 77 | 72 | 69 |

| Alternative | Why it was rejected for the MVP |
|---|---|
| Self-hosted OSRM or Valhalla | realistic and deterministic, but needs a server, RAM and a graph build — against "no Docker, no extra services" and the deadline; planned for the portfolio version |
| Haversine only | free and deterministic, but unrealistic distances and no road geometry; kept as the fallback |
| HERE / Google (paid) | best data and tolls, but cost, a key requirement and changing results; a possible commercial option later |

The engine comparison of report §21 (HERE, PTV, GraphHopper, OSRM, Valhalla, ORS, haversine) gives the same picture; prices there are approximate (confidence A).

## Consequences

- A fresh clone computes plans without network access.
- The committed matrix must be generated once with a real ORS key (one matrix request for 39 × 39 cities fits the free-plan limit of 3 500 elements) — an operation that needs the owner's approval; until then a haversine-based matrix can be committed (FEAT-004 OQ-004-02).
- Travel times are estimates: a car profile with a van factor ignores country speed limits and driving bans (report §19.3).
- ORS free-plan limits (report §21: 2 000 directions and 500 matrix requests per day, 40 per minute — values conflict between sources) are respected by caching and by fetching geometries only for displayed plans.
- Arbitrary addresses outside the demo cities need ORS or fall back to haversine.
- Road alternatives (P1, FEAT-008) are possible only with an ORS key.
