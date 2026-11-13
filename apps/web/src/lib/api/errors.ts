import type { components } from './schema';

/** What the UI works with after a problem+json body (RFC 9457, `Problem` in the contract). */
export type ProblemInfo = {
  code: string;
  message: string;
  fieldErrors: Record<string, string>;
  requestId?: string;
  status?: number;
};

/** The shape of next-intl's `t` for the `errors` namespace (a plain function with `has`). */
export type Translator = {
  (key: string, values?: Record<string, string | number>): string;
  has(key: string): boolean;
};

type ProblemBody = Partial<Record<keyof components['schemas']['Problem'], unknown>>;

/** Key of the generic message; never a real problem code. */
export const GENERIC_KEY = 'UNKNOWN';

export function toProblem(
  body: unknown,
  t: Translator,
  values?: Record<string, string | number>,
): ProblemInfo {
  const source: ProblemBody = typeof body === 'object' && body !== null ? body : {};
  const code = typeof source.code === 'string' ? source.code : GENERIC_KEY;
  const known = code !== GENERIC_KEY && t.has(code);
  const fieldErrors: Record<string, string> = {};
  if (Array.isArray(source.errors)) {
    for (const entry of source.errors as Record<string, unknown>[]) {
      if (typeof entry?.field === 'string' && typeof entry.message === 'string') {
        fieldErrors[entry.field] ??= entry.message;
      }
    }
  }
  return {
    code,
    message: known ? t(code, values) : t(GENERIC_KEY, values),
    fieldErrors,
    requestId: typeof source.requestId === 'string' ? source.requestId : undefined,
    status: typeof source.status === 'number' ? source.status : undefined,
  };
}
