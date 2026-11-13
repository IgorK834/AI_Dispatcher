'use client';

import { useQueryClient } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { useState } from 'react';
import { Banner } from '@/components/ui/banner';
import { ConfirmDialog } from '@/components/ui/dialog';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import { formatMoney } from '@/lib/format';
import { useProblemFromBody } from '@/lib/use-problem';
import type { RoutePlan } from './types';

type AssignDialogProps = {
  plan: RoutePlan;
  driverName: string | undefined;
  offerNames: Record<string, string>;
  onClose: () => void;
  onAssigned: () => void;
};

/** The error codes of a 409 PLAN_NOT_ASSIGNABLE, read from the raw problem body. */
function staleCodes(body: unknown): string[] {
  const errors = (body as { errors?: { code?: unknown }[] } | null)?.errors;
  return Array.isArray(errors)
    ? errors.flatMap((entry) => (typeof entry?.code === 'string' ? [entry.code] : []))
    : [];
}

export function AssignDialog({
  plan,
  driverName,
  offerNames,
  onClose,
  onAssigned,
}: AssignDialogProps) {
  const t = useTranslations('plans.assign');
  const common = useTranslations('common');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const toast = useToast();
  const queryClient = useQueryClient();
  const toProblem = useProblemFromBody();
  const [busy, setBusy] = useState(false);
  const [stale, setStale] = useState<string[] | null>(null);

  async function confirm() {
    setBusy(true);
    try {
      const outcome = await api.POST('/api/v1/assignments', { body: { routePlanId: plan.id } });
      if (outcome.data) {
        toast.show('success', t('done'));
        await queryClient.invalidateQueries({ queryKey: ['assignments'] });
        onAssigned();
        onClose();
        return;
      }
      const problem = toProblem(outcome.error);
      if (outcome.response.status === 409 && problem.code === 'PLAN_NOT_ASSIGNABLE') {
        setStale(staleCodes(outcome.error));
      } else if (outcome.response.status === 403) {
        toast.show('error', t('noPermission'));
      } else {
        toast.show(
          'error',
          problem.requestId ? `${problem.message} (${problem.requestId})` : problem.message,
        );
      }
    } finally {
      setBusy(false);
    }
  }

  const offers = plan.offerIds.map((id) => offerNames[id] ?? id.slice(0, 8)).join(', ');
  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={t('title')}
      description={t('summary', {
        driver: driverName ?? '—',
        offers,
        profit: formatMoney(plan.netProfit.amountMinor, plan.netProfit.currency, locale),
      })}
      confirmLabel={t('confirm')}
      cancelLabel={common('cancel')}
      loading={busy}
      onConfirm={() => void confirm()}
    >
      {stale && (
        <Banner level="attention" title={t('staleTitle')}>
          <span className="flex flex-col gap-1">
            {stale.length > 0 && (
              <ul className="list-disc pl-5">
                {stale.map((code) => (
                  <li key={code}>
                    {t.has(`reason.${code}`) ? t(`reason.${code}`) : t('reason.UNKNOWN')}
                  </li>
                ))}
              </ul>
            )}
            <Link href="/optimizer" className="font-semibold underline">
              {t('rerun')}
            </Link>
          </span>
        </Banner>
      )}
    </ConfirmDialog>
  );
}
