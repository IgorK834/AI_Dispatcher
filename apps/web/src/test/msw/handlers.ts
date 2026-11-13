import { HttpResponse } from 'msw';
import { API_BASE_URL } from '@/lib/api/client';

/** Absolute URL of an API path, as the typed client requests it. */
export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

/** An RFC 9457 problem+json response with the fields the API always sends. */
export function problem(
  status: number,
  code: string,
  extra: {
    errors?: { field: string; code?: string; message: string }[];
    headers?: HeadersInit;
  } = {},
) {
  return HttpResponse.json(
    {
      type: `https://routepilot.local/problems/${code.toLowerCase()}`,
      title: code,
      status,
      code,
      instance: '/test',
      requestId: 'req-test-1',
      errors: extra.errors ?? [],
    },
    {
      status,
      headers: { 'Content-Type': 'application/problem+json', ...extra.headers },
    },
  );
}
