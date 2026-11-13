'use client';

import { useLocale, useTranslations } from 'next-intl';
import { formatMass, formatPalletEquivalents } from '@/lib/format';
import { useStopLabel } from './stop-list';
import { isAction, type PlanStop, type VanLimits } from './types';

const HEIGHT = 96;

export function Occupancy({ stops, van }: { stops: PlanStop[]; van: VanLimits }) {
  const t = useTranslations('plans.occupancy');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const labelOf = useStopLabel();
  const actions = stops.filter(isAction);
  const peakEq = Math.max(0, ...actions.map((stop) => Number(stop.loadPalletEqAfter)));
  const peakKg = Math.max(0, ...actions.map((stop) => stop.loadKgAfter));
  const alt = actions
    .map((stop, index) =>
      t('altStop', {
        number: index + 1,
        eq: formatPalletEquivalents(Number(stop.loadPalletEqAfter), van.palletPlaces, locale),
        kg: formatMass(stop.loadKgAfter, locale),
      }),
    )
    .join('; ');

  return (
    <section
      className="flex flex-col gap-3 rounded-card bg-surface p-6 shadow-card"
      aria-label={t('title')}
    >
      <h2>{t('title')}</h2>
      <p className="text-sm text-ink2" data-testid="occupancy-peak">
        {t('peak', {
          eq: formatPalletEquivalents(peakEq, van.palletPlaces, locale),
          kg: formatMass(peakKg, locale),
          max: formatMass(van.payloadKg, locale),
        })}
      </p>
      <div role="img" aria-label={`${t('alt')} ${alt}`} className="flex gap-4 overflow-x-auto pt-2">
        {actions.map((stop, index) => {
          const eq = Number(stop.loadPalletEqAfter);
          return (
            <div
              key={stop.sequence}
              className="flex min-w-16 flex-col items-center gap-1 text-xs text-ink2"
            >
              <div className="flex items-end gap-1" style={{ height: HEIGHT }} aria-hidden="true">
                <div className="flex h-full flex-col items-center justify-end gap-1">
                  <span className="tabular-nums">{eq.toFixed(1)}</span>
                  <div
                    className="w-4 rounded-segment bg-red"
                    style={{
                      height: `${Math.max(2, (eq / van.palletPlaces) * (HEIGHT - 18))}px`,
                      opacity: eq / van.palletPlaces > 0.9 ? 1 : 0.85,
                    }}
                  />
                </div>
                <div className="flex h-full flex-col items-center justify-end gap-1">
                  <span className="tabular-nums">{stop.loadKgAfter}</span>
                  <div
                    className="w-4 rounded-segment bg-neutral-data"
                    style={{
                      height: `${Math.max(2, (stop.loadKgAfter / van.payloadKg) * (HEIGHT - 18))}px`,
                    }}
                  />
                </div>
              </div>
              <span className="font-semibold text-ink">{index + 1}</span>
              <span className="max-w-20 truncate text-center" title={labelOf(stop)}>
                {labelOf(stop)}
              </span>
            </div>
          );
        })}
      </div>
      <ul className="flex flex-wrap gap-x-6 text-xs text-ink2">
        <li className="flex items-center gap-2">
          <span aria-hidden="true" className="size-3 rounded-segment bg-red" />
          {t('legendEq')}
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden="true" className="size-3 rounded-segment bg-neutral-data" />
          {t('legendKg')}
        </li>
      </ul>
    </section>
  );
}
