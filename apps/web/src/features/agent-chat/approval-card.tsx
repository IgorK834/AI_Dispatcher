'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useId, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Pill } from '@/components/ui/pill';
import { Table, TBody, Td, Th, THead, Tr } from '@/components/ui/table';
import { formatCo2, formatDateTime, formatDuration, formatFuel, formatMoney } from '@/lib/format';
import { toNumber } from './format';
import { LinkButton } from './link-button';
import type { Approval } from './run-state';

const ZONE = 'Europe/Warsaw';

function useNow(active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

type ApprovalCardProps = {
  approval: Approval;
  onDecide: (decision: 'approve' | 'reject', comment: string) => void;
};

/**
 * The approval request of the `assign_plan` tool (FR-24): plans, totals, the legal notice and
 * Approve / Reject. Nothing is assigned until Approve is sent; the buttons are disabled after
 * the first click and when the request has been resolved (possibly in another tab) or expired.
 */
export function ApprovalCard({ approval, onDecide }: ApprovalCardProps) {
  const t = useTranslations('chat.approval');
  const legal = useTranslations('legal');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const commentId = useId();
  const [comment, setComment] = useState('');
  const open = approval.resolved === undefined;
  const now = useNow(open);
  const msLeft = Date.parse(approval.expiresAt) - now;
  const expired = open && approval.submitted === undefined && msLeft <= 0;
  const locked = !open || approval.submitted !== undefined || expired;
  const money = (amount: { amountMinor: number; currency: string }) =>
    formatMoney(amount.amountMinor, amount.currency, locale);

  return (
    <section
      aria-labelledby={`${commentId}-title`}
      className="flex flex-col gap-4 rounded-card border border-red bg-surface p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 id={`${commentId}-title`}>{t('title', { count: approval.plans.length })}</h3>
        {open && !expired && msLeft > 0 && (
          <Pill level="quiet">
            {t('expiresIn', { time: formatDuration(Math.max(1, Math.ceil(msLeft / 60_000))) })}
          </Pill>
        )}
        {expired && <Pill level="attention">{t('expired')}</Pill>}
      </div>
      <p className="text-sm text-ink2">{t('note')}</p>
      <div className="overflow-x-auto">
        <Table>
          <THead>
            <Tr>
              <Th scope="col">{t('driver')}</Th>
              <Th scope="col" numeric>
                {t('net')}
              </Th>
              <Th scope="col">{t('finish')}</Th>
              <Th scope="col">{t('home')}</Th>
            </Tr>
          </THead>
          <TBody>
            {approval.plans.map((plan) => (
              <Tr key={plan.planRef}>
                <Td>
                  <span className="font-semibold">{plan.driverRef}</span> {plan.driverLabel}
                </Td>
                <Td numeric>{money(plan.netProfit)}</Td>
                <Td>{formatDateTime(plan.finishAt, ZONE, locale)}</Td>
                <Td>{plan.homeReached ? t('yes') : t('no')}</Td>
              </Tr>
            ))}
          </TBody>
        </Table>
      </div>
      <dl className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <dt className="text-xs text-ink3">{t('totalNet')}</dt>
          <dd className="font-semibold tabular-nums">{money(approval.totals.netProfit)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">{t('fuel')}</dt>
          <dd className="tabular-nums">{formatFuel(toNumber(approval.totals.fuelL), locale)}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">{t('co2')}</dt>
          <dd className="tabular-nums">{formatCo2(toNumber(approval.totals.co2Kg), locale)}</dd>
        </div>
      </dl>
      <p className="text-xs text-ink3">{legal('notice')}</p>

      {approval.resolved !== undefined ? (
        <div className="flex flex-col gap-3" role="status">
          <p className="font-semibold text-ink">
            {approval.resolved === 'approve'
              ? t('resolvedApprove')
              : approval.resolved === 'reject'
                ? t('resolvedReject')
                : t('resolvedOther')}
          </p>
          {approval.resolved === 'approve' && (
            <LinkButton href="/fleet">{t('openFleet')}</LinkButton>
          )}
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-1">
            <label htmlFor={commentId} className="text-sm font-semibold text-ink">
              {t('comment')}
            </label>
            <textarea
              id={commentId}
              rows={2}
              maxLength={500}
              value={comment}
              disabled={locked}
              onChange={(event) => setComment(event.target.value)}
              className="min-w-0 rounded-control border border-line-strong bg-surface px-3 py-2 text-ink disabled:bg-well disabled:text-ink3"
            />
            <p className="text-xs text-ink3">{t('commentHint')}</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="primary"
              disabled={locked}
              onClick={() => onDecide('approve', comment)}
            >
              {t('approve')}
            </Button>
            <Button variant="danger" disabled={locked} onClick={() => onDecide('reject', comment)}>
              {t('reject')}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
