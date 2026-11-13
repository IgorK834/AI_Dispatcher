import createClient, { type Client, type Middleware } from 'openapi-fetch';
import type { paths } from './schema';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

const STATE_CHANGING = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
// Login must not trigger the "session expired" redirect: a 401 there is a wrong password.
const PUBLIC_PATHS = ['/api/v1/auth/login', '/api/v1/auth/captcha-config', '/api/v1/auth/me'];

let csrfToken: string | null = null;
let unauthorized: (() => void) | null = null;

/** The CSRF token lives in memory only (FR-5); a reload fetches a fresh one from /auth/me. */
export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export function getCsrfToken(): string | null {
  return csrfToken;
}

/** Registers what happens after any 401 from a data request; returns an unsubscribe function. */
export function onUnauthorized(handler: () => void): () => void {
  unauthorized = handler;
  return () => {
    if (unauthorized === handler) unauthorized = null;
  };
}

const session: Middleware = {
  onRequest({ request }) {
    if (STATE_CHANGING.has(request.method) && csrfToken) {
      request.headers.set('X-CSRF-Token', csrfToken);
    }
    return request;
  },
  onResponse({ request, response }) {
    const path = new URL(request.url).pathname;
    if (response.status === 401 && !PUBLIC_PATHS.includes(path)) unauthorized?.();
    return undefined;
  },
};

/** The only HTTP entry point of the app: typed from contracts/openapi.json (FR-26). */
export const api: Client<paths> = createClient<paths>({
  baseUrl: API_BASE_URL,
  credentials: 'include',
  // Resolved on every call, so a test server that patches the global fetch later still applies.
  fetch: (request) => globalThis.fetch(request),
});
api.use(session);
