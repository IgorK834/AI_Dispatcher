/** A failed API call: the HTTP status, the problem+json body and the Retry-After header. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
    readonly retryAfter: string | null = null,
  ) {
    super(`API request failed with status ${status}`);
    this.name = 'ApiError';
  }
}

type Result<T> = { data?: T; error?: unknown; response: Response };

/** The data of a successful call, or an ApiError that carries the problem body. */
export function unwrap<T>(result: Result<T>): T {
  if (result.data !== undefined) return result.data;
  throw new ApiError(
    result.response.status,
    result.error,
    result.response.headers.get('Retry-After'),
  );
}

/** For calls without a body (204): succeeds on any 2xx answer. */
export function unwrapEmpty(result: Result<unknown>): void {
  if (result.response.ok) return;
  throw new ApiError(
    result.response.status,
    result.error,
    result.response.headers.get('Retry-After'),
  );
}
