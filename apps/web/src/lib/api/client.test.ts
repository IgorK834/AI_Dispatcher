import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiUrl } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { api, getCsrfToken, onUnauthorized, setCsrfToken } from './client';

afterEach(() => setCsrfToken(null));

describe('typed API client', () => {
  it('sends the CSRF token on state-changing requests only and keeps it in memory', async () => {
    const seen: Record<string, string | null> = {};
    server.use(
      http.get(apiUrl('/api/v1/drivers'), ({ request }) => {
        seen.get = request.headers.get('X-CSRF-Token');
        return HttpResponse.json({ items: [] });
      }),
      http.delete(apiUrl('/api/v1/drivers/:id'), ({ request }) => {
        seen.delete = request.headers.get('X-CSRF-Token');
        return new HttpResponse(null, { status: 204 });
      }),
    );
    setCsrfToken('token-1');
    expect(getCsrfToken()).toBe('token-1');
    await api.GET('/api/v1/drivers', {});
    await api.DELETE('/api/v1/drivers/{driver_id}', {
      params: { path: { driver_id: '00000000-0000-4000-8000-000000000000' } },
    });
    expect(seen.get).toBeNull();
    expect(seen.delete).toBe('token-1');
  });

  it('calls the unauthorized handler on a 401 of a data request but not of login', async () => {
    server.use(
      http.get(apiUrl('/api/v1/drivers'), () => HttpResponse.json({}, { status: 401 })),
      http.post(apiUrl('/api/v1/auth/login'), () => HttpResponse.json({}, { status: 401 })),
    );
    const handler = vi.fn();
    const off = onUnauthorized(handler);
    await api.POST('/api/v1/auth/login', {
      body: { email: 'a@b.c', password: 'x', captchaToken: 't' },
    });
    expect(handler).not.toHaveBeenCalled();
    await api.GET('/api/v1/drivers', {});
    expect(handler).toHaveBeenCalledTimes(1);
    off();
    await api.GET('/api/v1/drivers', {});
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('includes credentials so the session cookie crosses origins', async () => {
    server.use(http.get(apiUrl('/api/v1/drivers'), () => HttpResponse.json({ items: [] })));
    const original = globalThis.fetch;
    const credentials: string[] = [];
    vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      credentials.push(input instanceof Request ? input.credentials : String(init?.credentials));
      return original(input, init);
    });
    await api.GET('/api/v1/drivers', {});
    vi.restoreAllMocks();
    expect(credentials).toEqual(['include']);
  });
});
