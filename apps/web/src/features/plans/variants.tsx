'use client';

import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { Pill } from '@/components/ui/pill';
import {
  formatCo2,
  formatDateTime,
  formatDistance,
  formatDuration,
  formatFuel,
  formatMoney,
} from '@/lib/format';
import { minutesBetween, signed } from './format';
import { OBJECTIVES, PLAN_TIME_ZONE, type Objective, type PlanSummary } from './types';

type VariantsProps = {
  variants: Partial<Record<Objective, PlanSummary>>;
  /** The plan on screen; its card is marked "Shown". */
  currentId: string;
  jobId: string;
};

/** Two variants are the same plan when they visit the same offers with the same result. */
function samePlan(left: PlanSummary, right: PlanSummary): boolean {
  return (
    left.id === right.id ||
    (left.offerIds.join() === right.offerIds.join() &&
      left.netProfit.amountMinor === right.netProfit.amountMinor &&
      left.finishAt === right.finishAt &&
      left.fuelL === right.fuelL)
  );
}

export function Variants({ variants, currentId, jobId }: VariantsProps) {
  const t = useTranslations('plans.variants');
  const names = useTranslations('plans.variant');
  const legal = useTranslations('legal');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const base = variants.profit;
  const shown = OBJECTIVES.filter((objective) => variants[objective]);

  return (
    <section className="flex flex-col gap-3" aria-label={t('title')}>
      <h2>{t('title')}</h2>
      <div className="flex flex-wrap gap-4">
        {shown.map((objective, index) => {
          const plan = variants[objective] as PlanSummary;
          const twin = shown
            .slice(0, index)
            .find((other) => samePlan(variants[other] as PlanSummary, plan));
          const isShown = plan.id === currentId;
          const delta = base && base.id !== plan.id ? base : null;
          return (
            <article
              key={objective}
              aria-label={names(objective)}
              className={`flex min-w-64 flex-[1_1_260px] flex-col gap-3 rounded-card bg-surface p-5 shadow-card ${
                isShown ? 'ring-2 ring-inset ring-red' : ''
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <h3>{names(objective)}</h3>
                {isShown && <Pill level="brand">{t('shown')}</Pill>}
              </div>
              {twin && <p className="text-sm text-ink2">{t('coincide', { name: names(twin) })}</p>}
              <p className="font-display text-3xl font-medium tabular-nums text-ink">
                {formatMoney(plan.netProfit.amountMinor, plan.netProfit.currency, locale)}
              </p>
              <dl className="grid grid-cols-2 gap-x-3 gap-y-2 text-sm">
                <div>
                  <dt className="text-xs text-ink3">{t('finish')}</dt>
                  <dd>{formatDateTime(plan.finishAt, PLAN_TIME_ZONE, locale)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-ink3">{t('distance')}</dt>
                  <dd>{formatDistance(Number(plan.distanceKm), locale)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-ink3">
                    {t('fuel')} · {t('estimate')}
                  </dt>
                  <dd>{formatFuel(Number(plan.fuelL), locale)}</dd>
                </div>
                <div>
                  <dt className="text-xs text-ink3">
                    {t('co2')} · {t('estimate')}
                  </dt>
                  <dd>{formatCo2(Number(plan.co2Kg), locale)}</dd>
                </div>
              </dl>
              {delta && (
                <ul className="flex flex-col gap-0.5 rounded-inner bg-well p-3 text-xs text-ink2">
                  <li>
                    {t('deltaProfit')}{' '}
                    {signed(
                      plan.netProfit.amountMinor - delta.netProfit.amountMinor,
                      formatMoney(
                        Math.abs(plan.netProfit.amountMinor - delta.netProfit.amountMinor),
                        plan.netProfit.currency,
                        locale,
                      ),
                    )}
                  </li>
                  <li>
                    {t('deltaTime')}{' '}
                    {signed(
                      minutesBetween(delta.finishAt, plan.finishAt),
                      formatDuration(Math.abs(minutesBetween(delta.finishAt, plan.finishAt))),
                    )}
                  </li>
                  <li>
                    {t('deltaFuel')}{' '}
                    {signed(
                      Number(plan.fuelL) - Number(delta.fuelL),
                      formatFuel(Math.abs(Number(plan.fuelL) - Number(delta.fuelL)), locale),
                    )}
                  </li>
                  <li>
                    {t('deltaCo2')}{' '}
                    {signed(
                      Number(plan.co2Kg) - Number(delta.co2Kg),
                      formatCo2(Math.abs(Number(plan.co2Kg) - Number(delta.co2Kg)), locale),
                    )}
                  </li>
                </ul>
              )}
              {!isShown && (
                <Link
                  href={`/plans/${plan.id}?job=${jobId}`}
                  className="text-sm font-semibold text-red hover:text-red-hover"
                >
                  {t('open')}
                </Link>
              )}
            </article>
          );
        })}
      </div>
      <p className="text-xs text-ink3">{legal('notice')}</p>
    </section>
  );
}
