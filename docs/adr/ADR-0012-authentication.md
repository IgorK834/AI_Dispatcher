# ADR-0012: Authentication — cookie sessions, Argon2id, Turnstile, CSRF token, roles

- Status: accepted (2026-11-11)
- Date: 2026-11-09

## Context

The application has three roles (`admin`, `dispatcher`, `demo`) and a public demo account. The frontend and the API run on different origins of the same site (`localhost:3000` and `localhost:8000`). The local run must need no external account or key. The login must resist automated attempts, and the repository is public, so no secret may be committed. Source: [`docs/report.md`](../report.md) §15.4, §29; rules in [`context.md`](../../context.md) → Security Requirements.

## Decision

- **Credentials:** email + password, hashed with **Argon2id** (argon2-cffi). No self-registration in the MVP.
- **Accounts on first start:** `admin` and `demo` are created from `.env`. Local default credentials are documented; any non-local environment requires its own passwords.
- **Sessions:** server-side. A random token of at least 256 bits in a cookie `HttpOnly; SameSite=Lax` (`Secure` on HTTPS); only a hash of the token in the database; expiry; invalidation on logout and password change.
- **Captcha:** Cloudflare **Turnstile** on login, verified on the server **before** the password check, behind the port `CaptchaVerifier`. Locally and in CI the official test keys are used (`1x00000000000000000000AA` / `1x0000000000000000000000000000000AA` always pass; `2x…` always fail, for negative tests). Test keys with `APP_ENV=production` stop the startup.
- **CSRF:** double-submit token in the `X-CSRF-Token` header plus an `Origin` check against the CORS allowlist for state-changing methods.
- **Rate limiting:** slowapi on login, per IP and per account. Account lockout after repeated failures is P1.
- **Authorisation:** roles checked in FastAPI dependencies; a permission-matrix test covers every endpoint.

## Alternatives

The report does not score authentication options in a matrix; the reasons below follow from its security section and the project constraints.

| Alternative | Why it was rejected |
|---|---|
| JWT stored in the browser (local storage) | readable by any injected script; revocation needs extra machinery; a server-side session in an `HttpOnly` cookie is simpler and safer for a single API |
| Stateless signed cookies | no server-side invalidation on logout or password change |
| An external identity provider (OAuth/OIDC) | needs external accounts and secrets, which breaks "no required keys" for the local run; unnecessary for three fixed roles |
| bcrypt or PBKDF2 for passwords | acceptable, but Argon2id is the current recommendation and is available through a maintained library |
| No captcha | the public demo login would be open to automated attempts; Turnstile is free and its test keys keep local runs and CI offline-friendly |
| Another captcha service | no advantage; Turnstile's documented always-pass and always-fail test keys make deterministic tests possible |
| `SameSite=Strict` or `None` cookies | `Strict` breaks normal navigation into the app; `None` needs `Secure` and widens cross-site exposure; `Lax` plus a CSRF token fits a same-site, cross-origin setup |
| Self-registration | adds email verification and abuse handling; out of the MVP |

## Consequences

- The frontend must send `credentials: 'include'` and the CSRF header on every state-changing request; the API must answer with exact-origin CORS headers (ADR-0009).
- The public Turnstile test keys and the local demo passwords appear in `.env.example`; they are valid only locally and must be allow-listed in the secret scanner (FEAT-001 OQ-001-04).
- Turnstile processes browser data of the user (risk L9); the demo's privacy note must say so.
- Session lifetime, rate-limit values and password length are not fixed by the report; proposed defaults are in FEAT-001 (OQ-001-02).
- HTTPS, HSTS and server hardening come with the VPS version (ADR-0007).
