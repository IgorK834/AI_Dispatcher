'use client';

import { useTranslations } from 'next-intl';
import type { ReactNode } from 'react';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import type { ProblemInfo } from '@/lib/api/errors';

/** Skeleton rows shaped like the table: no layout jump, no spinner (DEVELOPMENT.md section 9). */
export function ListSkeleton({ label }: { label: string }) {
  return (
    <div role="status" aria-busy="true" className="flex flex-col gap-3 p-6">
      <span className="sr-only">{label}</span>
      {[0, 1, 2, 3, 4].map((row) => (
        <div
          key={row}
          data-testid="skeleton-row"
          aria-hidden="true"
          className="h-11 rounded-inner bg-well"
          style={{ animation: 'rp-pulse 1.4s ease-in-out infinite' }}
        />
      ))}
    </div>
  );
}

/** One sentence that says what is missing and one primary action. */
export function EmptyState({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-2 p-6">
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      <p className="text-sm text-ink2">{body}</p>
      {action}
    </div>
  );
}

/** The message chosen by the problem code, "Try again" and the request id for support. */
export function ListError({
  title,
  problem,
  onRetry,
}: {
  title: string;
  problem: ProblemInfo;
  onRetry: () => void;
}) {
  const common = useTranslations('common');
  return (
    <div className="flex flex-col items-start gap-3 p-6">
      <Banner level="error" title={title}>
        {problem.message}
      </Banner>
      {problem.requestId && (
        <span className="text-xs text-ink3">{common('requestId', { id: problem.requestId })}</span>
      )}
      <Button onClick={onRetry}>{common('tryAgain')}</Button>
    </div>
  );
}
