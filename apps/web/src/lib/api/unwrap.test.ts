import { describe, expect, it } from 'vitest';
import { ApiError, unwrap, unwrapEmpty } from './unwrap';

const answer = (status: number, headers: Record<string, string> = {}) =>
  new Response(null, { status, headers });

describe('unwrap', () => {
  it('returns the data of a successful call', () => {
    expect(unwrap({ data: { id: 1 }, response: answer(200) })).toEqual({ id: 1 });
  });

  it('throws an ApiError that carries the status, the problem body and Retry-After', () => {
    const problem = { code: 'RATE_LIMITED' };
    const call = () => unwrap({ error: problem, response: answer(429, { 'Retry-After': '30' }) });
    expect(call).toThrow(ApiError);
    try {
      call();
    } catch (error) {
      expect(error).toMatchObject({ status: 429, body: problem, retryAfter: '30' });
    }
  });
});

describe('unwrapEmpty', () => {
  it('accepts any 2xx answer', () => {
    expect(() => unwrapEmpty({ response: answer(204) })).not.toThrow();
  });

  it('throws an ApiError for a failed answer, with a missing Retry-After as null', () => {
    try {
      unwrapEmpty({ error: { code: 'NOT_FOUND' }, response: answer(404) });
      expect.unreachable();
    } catch (error) {
      expect(error).toMatchObject({ status: 404, retryAfter: null });
    }
  });
});
