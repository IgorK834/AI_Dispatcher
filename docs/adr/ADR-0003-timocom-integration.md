# ADR-0003: TIMOCOM integration — ports and adapters with a mock in the TIMOCOM v3 format

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

Freight offers in a real deployment would come from a freight exchange. The best-documented candidate is the TIMOCOM Freight Exchange API v3.0.6 (public OpenAPI). There is **no access** to it: access needs a customer relationship, test credentials and a Business Approval (findings T23–T25 in [`docs/report.md`](../report.md) §5.1). The API has usage rules that shape a design: an identical search no more often than every 45 s, at most 30 offers per page, two-step search without contact persons, no generic "download everything" searches, retention limits (T11–T15, L1–L4 in §6). The API has no fields for pallets, temperature or service time (T20), and `price` and coordinates are optional (T19, §5.2).

## Decision

- **Ports:** `FreightProvider` (search, lookup, capabilities) and `OfferMapper` (raw record → normalised offer or mapping failure). The optimizer and the agents know only the normalised model.
- **MVP adapter:** `MockFreightProvider` returns **synthetic** payloads in the TIMOCOM v3 format (`meta` + `payload`), produced by a deterministic generator. Every record is `is_synthetic = true`.
- **One mapper for mock and real data:** `TimocomV3Mapper`, tolerant of the inconsistencies found in the official OpenAPI (T29).
- **Three data layers:** raw (provider payload 1:1, with `retention_until`), normalised (SI units, UTC), enrichment (pallets, service time, geocoding, time zone — each with provenance). Nothing outside OpenAPI 3.0.6 is ever attributed to TIMOCOM.
- **Real adapter:** `TimocomFreightProvider` exists only as a skeleton tested offline (auth strategy interface for Basic/OAuth2, 45-second limiter, page limit). No network calls in the MVP or in CI.
- **No scraping** of any exchange.

## Alternatives

| Alternative | Why it was rejected |
|---|---|
| An own, simpler offer format for the mock | the path to a real adapter would be untested; the report verified all needed fields in the official schema, so the real format costs little |
| Building against the TIMOCOM sandbox now | needs credentials and a test user from TIMOCOM; not available; production integration is outside the MVP |
| Scraping exchange web pages | forbidden by project rules and by the providers' terms (risk L13) |
| Letting the optimizer read provider payloads directly | couples the engine to one provider and mixes source data with enrichment |

## Consequences

- The demo runs entirely on synthetic data, and the UI says so ("SYNTHETIC DATA" badge, no TIMOCOM branding).
- Pallet counts are enrichment (`generated_mock`, `derived`, `ai`, `user`), never "a fact from TIMOCOM"; the capacity model must handle their absence (ADR-0014).
- The mapper carries tolerance and failure paths that need contract tests on fixtures taken from the official OpenAPI examples.
- Real integration later needs: answers to the open questions Q1–Q7 (report §38), the Business Approval, an auth decision (Basic vs OAuth2) and a retention job. The design already respects the usage rules.
- Real offer data must not be sent to an external LLM without consent (Q4); the MVP sends only synthetic data.
