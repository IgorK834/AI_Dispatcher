'use client';

import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Pill } from '@/components/ui/pill';
import { VanSide } from '@/components/vehicle/van-side';
import { useDriverOfPlan, usePlan } from '@/features/plans';
import { formatCo2, formatDateTime, formatMoney } from '@/lib/format';
import { toNumber } from './format';
import type { Proposal } from './run-state';

const ZONE = 'Europe/Warsaw';

type ProposalCardProps = {
  proposal: Proposal;
  selected: boolean;
  onSelect: () => void;
};

/** One proposed plan: driver and van (from the plan), route, profit, finish and a link to the plan. */
export function ProposalCard({ proposal, selected, onSelect }: ProposalCardProps) {
  const t = useTranslations('chat.proposal');
  const variants = useTranslations('plans.variant');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const plan = usePlan(proposal.routePlanId);
  const driver = useDriverOfPlan(plan.data?.driverId);
  const actions = (plan.data?.stops ?? []).filter(
    (stop) => stop.kind === 'PICKUP' || stop.kind === 'DELIVERY',
  );
  const route = actions.map((stop) => stop.label).join(' → ');
  const title = driver.data ? `${proposal.driverRef} · ${driver.data.name}` : proposal.driverRef;
  const vanLabel = driver.data?.vehicle?.label;

  return (
    <article
      aria-label={title}
      data-selected={selected}
      className="flex flex-col gap-3 rounded-card border border-line bg-surface p-4 data-[selected=true]:border-red"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <h3 className="break-words">{title}</h3>
          <div className="flex flex-wrap items-center gap-2 text-xs text-ink3">
            <span className="font-mono">{proposal.planRef}</span>
            <Pill level="quiet">{variants(proposal.variant)}</Pill>
          </div>
        </div>
        {vanLabel && <VanSide label={vanLabel} width={120} />}
      </div>
      {route !== '' && <p className="break-words text-sm text-ink2">{route}</p>}
      <dl className="grid grid-cols-3 gap-3 text-sm">
        <div>
          <dt className="text-xs text-ink3">{t('netProfit')}</dt>
          <dd className="font-semibold tabular-nums text-ink">
            {formatMoney(proposal.netProfit.amountMinor, proposal.netProfit.currency, locale)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">{t('finish')}</dt>
          <dd className="tabular-nums text-ink">
            {formatDateTime(proposal.finishAt, ZONE, locale)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">{t('co2')}</dt>
          <dd className="tabular-nums text-ink">{formatCo2(toNumber(proposal.co2Kg), locale)}</dd>
        </div>
      </dl>
      <div className="flex flex-wrap gap-2">
        <Link
          href={`/plans/${proposal.routePlanId}`}
          className="inline-flex min-h-9 items-center rounded-control border border-line-strong px-3 text-sm font-semibold text-ink hover:bg-well"
        >
          {t('openPlan')}
        </Link>
        <Button small onClick={onSelect} aria-pressed={selected}>
          {t('showOnMap')}
        </Button>
      </div>
    </article>
  );
}
