import { createTranslator } from 'next-intl';
import { describe, expect, it } from 'vitest';
import en from '../../../messages/en.json';
import pl from '../../../messages/pl.json';
import { GENERIC_KEY, toProblem } from './errors';

// The code catalogue of DEVELOPMENT.md section 4.5.
const CODES = [
  'VALIDATION_ERROR',
  'MALFORMED_REQUEST',
  'CAPTCHA_FAILED',
  'UNAUTHENTICATED',
  'INVALID_CREDENTIALS',
  'FORBIDDEN',
  'CSRF_FAILED',
  'ORIGIN_NOT_ALLOWED',
  'NOT_FOUND',
  'VERSION_CONFLICT',
  'DUPLICATE_RESOURCE',
  'PROVIDER_OFFER_READ_ONLY',
  'DRIVER_HAS_ACTIVE_ASSIGNMENT',
  'VEHICLE_ASSIGNED_TO_DRIVER',
  'COST_PROFILE_IN_USE',
  'IDEMPOTENCY_KEY_REUSED',
  'JOB_NOT_FINISHED',
  'PLAN_NOT_ASSIGNABLE',
  'APPROVAL_NOT_PENDING',
  'RUN_IN_PROGRESS',
  'RATE_LIMITED',
  'AI_BUDGET_EXCEEDED',
  'AI_UNAVAILABLE',
  'NOT_READY',
  'INTERNAL_ERROR',
] as const;

const bundles = { en, pl } as const;

function translator(locale: 'en' | 'pl') {
  // Messages typed as plain strings: the helper must work for any code, known or not.
  const messages: Record<string, string> = bundles[locale].errors;
  return createTranslator({ locale, messages });
}

describe('[AC-FEAT-005-22] problem+json to a translated message', () => {
  for (const locale of ['en', 'pl'] as const) {
    it(`translates every known code in ${locale}`, () => {
      const t = translator(locale);
      for (const code of CODES) {
        const problem = toProblem({ code, requestId: 'r-1', status: 409 }, t);
        expect(problem.code).toBe(code);
        expect(problem.message, code).toBe(bundles[locale].errors[code]);
        expect(problem.message, code).not.toBe(bundles[locale].errors[GENERIC_KEY]);
        expect(problem.requestId).toBe('r-1');
      }
    });

    it(`gives a generic message and the request id for an unknown code in ${locale}`, () => {
      const problem = toProblem({ code: 'BRAND_NEW_CODE', requestId: 'r-42' }, translator(locale));
      expect(problem.code).toBe('BRAND_NEW_CODE');
      expect(problem.message).toBe(bundles[locale].errors[GENERIC_KEY]);
      expect(problem.requestId).toBe('r-42');
    });
  }

  it('keeps English and Polish messages different for every code', () => {
    for (const code of CODES) expect(en.errors[code]).not.toBe(pl.errors[code]);
  });

  it('maps errors[] to field messages and keeps the first message per field', () => {
    const problem = toProblem(
      {
        code: 'VALIDATION_ERROR',
        errors: [
          { field: 'homeLon', code: 'LT', message: 'must be at most 180' },
          { field: 'homeLon', code: 'X', message: 'second' },
          { field: 'name', message: 'required' },
          { nonsense: true },
        ],
      },
      translator('en'),
    );
    expect(problem.fieldErrors).toEqual({ homeLon: 'must be at most 180', name: 'required' });
  });

  it('survives a body that is not a problem document', () => {
    const t = translator('en');
    for (const body of [null, undefined, 'oops', 42, []]) {
      const problem = toProblem(body, t);
      expect(problem.code).toBe(GENERIC_KEY);
      expect(problem.message).toBe(en.errors[GENERIC_KEY]);
      expect(problem.fieldErrors).toEqual({});
    }
  });
});
