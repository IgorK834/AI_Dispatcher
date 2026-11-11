# ADR-0009: API, CRUD, CORS and contracts — REST with problem+json and a committed OpenAPI

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

The web app (`http://localhost:3000`) and the API (`http://localhost:8000`) are separate applications on different origins. The API must support full CRUD for the main resources, behave predictably for a typed client, and be verifiable by AI coding agents and by CI. REST design quality and a correct CORS configuration are delivery standards of the project ([`DEVELOPMENT.md`](../../DEVELOPMENT.md) §1). Source: [`docs/report.md`](../report.md) §11.3, §28, §29.

## Decision

- **Style:** REST over JSON, prefix `/api/v1`, plural kebab-case resources, camelCase fields, UUID ids, UTC timestamps.
- **Full CRUD** for `drivers`, `vehicles`, `cost-profiles` and manual `freight-offers` (`source = manual`). Provider offers are read-only → `409`.
- **Status codes:** `POST` → `201` + `Location`; `PATCH` (partial, with `version`) → `200`; `DELETE` → `204`; conflicts → `409`; validation → `422`; long operations → `202` + a job resource.
- **Errors:** RFC 9457 `application/problem+json` with a stable machine-readable `code`.
- **Lists:** cursor pagination (`limit`, `cursor`) and filters as query parameters.
- **Idempotency:** `Idempotency-Key` header on job-creating `POST`s.
- **Contract-first workflow:** OpenAPI is generated from the FastAPI app into `contracts/openapi.json`, **committed**, checked for drift and for breaking changes (`oasdiff`) in CI; the frontend types are generated from it.
- **CORS:** explicit allowlist `CORS_ALLOWED_ORIGINS` (default `http://localhost:3000`), `allow_credentials=True`, never `*`; allowed headers `Content-Type, Idempotency-Key, X-CSRF-Token`.
- **CSRF:** double-submit `X-CSRF-Token` plus an `Origin` check for state-changing methods (details in ADR-0012).

The practical guide is [`DEVELOPMENT.md`](../../DEVELOPMENT.md) §4; the binding endpoint contracts are in FEAT-001, FEAT-004 and FEAT-006.

## Alternatives

| Alternative | Why it was rejected |
|---|---|
| GraphQL | more moving parts (schema, resolvers, client cache) without a need: the screens map well to resources; REST semantics and status codes are part of what the project wants to demonstrate |
| RPC-style endpoints (`/optimize`, `/createDriver`) | lose HTTP semantics, caching rules and a uniform client; harder to test generically (schemathesis) |
| Same-origin setup through a Next.js proxy (no CORS) | simpler cookies, but it hides the API behind the frontend and removes the explicit CORS configuration that a separate API needs anyway |
| `Access-Control-Allow-Origin: *` | not allowed together with credentials, and it would let any site call the API with the user's cookie |
| Hand-written TypeScript types | drift from the backend; generated types plus a drift gate remove the problem |
| Ad-hoc error bodies | every client would need special cases; problem+json with `code` gives one translation table in the UI |
| Offset pagination | simple, but unstable when rows are inserted; cursors are stable and cheap here |

## Consequences

- Every contract change regenerates two committed files (`contracts/openapi.json`, `schema.d.ts`) and must come with a specification change; breaking changes need the owner's `contract-change-approved` label.
- Clients must send `version` on `PATCH` and handle `409 VERSION_CONFLICT`.
- Problem `code` values are part of the contract; renaming one is a breaking change.
- CORS preflight and CSRF behaviour need their own tests (Gate 8c).
- The API can be used without the web app (API docs page, other clients), which keeps the door open for an MCP server or a mobile client later.
