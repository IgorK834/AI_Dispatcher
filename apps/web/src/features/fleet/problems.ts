'use client';

import { useTranslations } from 'next-intl';
import { useCallback } from 'react';
import { toProblem, type ProblemInfo } from '@/lib/api/errors';
import { ApiError } from '@/lib/api/unwrap';

/** Turns whatever a failed call threw into a translated problem (network errors included). */
export function useProblem(): (error: unknown) => ProblemInfo {
  const t = useTranslations('errors');
  return useCallback(
    (error: unknown) => {
      if (error instanceof ApiError) return toProblem(error.body, t, undefined);
      return toProblem(null, t);
    },
    [t],
  );
}

export function useProblemFromBody(): (body: unknown) => ProblemInfo {
  const t = useTranslations('errors');
  return useCallback((body: unknown) => toProblem(body, t), [t]);
}
