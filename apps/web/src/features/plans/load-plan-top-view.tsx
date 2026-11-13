'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';
import { Meter } from '@/components/ui/meter';
import { Segmented } from '@/components/ui/segmented';
import { formatDateTime, formatMass, formatPalletEquivalents } from '@/lib/format';
import { lane, loadPlan, type Occupant } from './load-plan-placement';
import { PLAN_TIME_ZONE, type PlanStop, type VanLimits } from './types';

const TINTS = ['bg-cargo-a', 'bg-cargo-b', 'bg-cargo-c', 'bg-cargo-d', 'bg-cargo-e'] as const;

type TopViewProps = {
  stops: PlanStop[];
  van: VanLimits;
  /** Source ids of the offers (TC-1001) by offer id, shown in the legend when known. */
  offerNames?: Record<string, string>;
};

function Cell({
  id,
  occupant,
  tall,
  freeLabel,
}: {
  id: string;
  occupant: Occupant | null;
  tall: boolean;
  freeLabel: string;
}) {
  const t = useTranslations('plans.topView');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  return (
    <div
      data-place={id}
      data-occupied={occupant ? 'true' : 'false'}
      className={`flex flex-col justify-between rounded-segment p-1.5 text-xs text-ink ${
        tall ? 'min-h-24' : 'min-h-16'
      } ${occupant ? (TINTS[occupant.tint] ?? 'bg-cargo-a') : 'border border-dashed bg-surface text-ink3'}`}
      style={
        occupant
          ? { backgroundImage: 'var(--cargo-stripe)' }
          : { borderColor: 'var(--cargo-free-border)' }
      }
    >
      <span className="flex flex-wrap justify-between gap-x-1 font-semibold">
        <span>{id}</span>
        {occupant && <span>{formatMass(occupant.kg, locale)}</span>}
      </span>
      {occupant ? (
        <span className="font-mono">{t('offerTag', { tag: occupant.tag })}</span>
      ) : (
        <span>{freeLabel}</span>
      )}
    </div>
  );
}

/** The van floor from above with illustrative pallet positions (design README section 7.2). */
export function LoadPlanTopView({ stops, van, offerNames = {} }: TopViewProps) {
  const t = useTranslations('plans.topView');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const plan = useMemo(() => loadPlan(stops, van.layoutTemplate), [stops, van.layoutTemplate]);
  const peak = useMemo(
    () =>
      plan.steps.reduce(
        (best, step) => (step.eq > (plan.steps[best]?.eq ?? 0) ? step.step : best),
        0,
      ),
    [plan],
  );
  const [selected, setSelected] = useState(peak);
  const current = plan.steps[selected] ?? plan.steps[0];
  if (!current) return null;

  const declaredOnly = current.places.length === 0;
  const occupied = current.places.filter((entry) => entry.occupant);
  const tagOf = (offerId: string | null) =>
    plan.offers.find((offer) => offer.offerId === offerId)?.tag;
  const where = current.stop
    ? t(current.stop.kind === 'PICKUP' ? 'afterPickup' : 'afterDelivery', {
        tag: tagOf(current.stop.offerId) ?? '?',
        place: current.stop.label,
        time: formatDateTime(current.stop.departureAt, PLAN_TIME_ZONE, locale),
      })
    : t('atStart');
  const used = Math.round((current.eq / van.palletPlaces) * 100);
  const options = plan.steps.map((step) => ({
    value: String(step.step),
    label: step.step === 0 ? t('start') : String(step.step),
  }));
  const alt = t('alt', {
    where,
    used: occupied.length,
    places: current.places.length,
    kg: formatMass(current.kg, locale),
    max: formatMass(van.payloadKg, locale),
  });
  const transverse = current.places.filter((entry) => entry.place.row === 'T');
  const longitudinal = current.places.filter((entry) => entry.place.row === 'L');

  return (
    <section className="flex flex-col gap-4" aria-label={t('title')}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2>{t('title')}</h2>
        <Segmented
          label={t('selector')}
          options={options}
          value={String(selected)}
          onValueChange={(value) => setSelected(Number(value))}
        />
      </div>

      <div className="flex flex-wrap gap-6">
        {!declaredOnly && (
          <div className="flex min-w-80 flex-[3_1_480px] flex-col gap-3">
            <div role="img" aria-label={alt} className="rounded-inner bg-well p-3">
              <div className="flex items-stretch gap-2">
                <div aria-hidden="true" className="w-1.5 flex-none rounded-segment bg-ink2" />
                <div className="flex flex-1 flex-col gap-2 rounded-inner border-2 border-ink bg-surface p-2">
                  <div
                    className="grid gap-2"
                    style={{ gridTemplateColumns: `repeat(${transverse.length}, minmax(0, 1fr))` }}
                  >
                    {transverse.map((entry) => (
                      <Cell
                        key={entry.place.id}
                        id={entry.place.id}
                        occupant={entry.occupant}
                        tall
                        freeLabel={t('free')}
                      />
                    ))}
                  </div>
                  <div
                    className="grid gap-2"
                    style={{
                      gridTemplateColumns: `repeat(${longitudinal.length}, minmax(0, 1fr))`,
                    }}
                  >
                    {longitudinal.map((entry) => (
                      <Cell
                        key={entry.place.id}
                        id={entry.place.id}
                        occupant={entry.occupant}
                        tall={false}
                        freeLabel={t('free')}
                      />
                    ))}
                  </div>
                </div>
                <div
                  aria-hidden="true"
                  className="flex w-12 flex-none flex-col justify-center gap-1 rounded-r-inner border-2 border-ink bg-surface p-1"
                >
                  <div className="h-10 rounded-segment bg-window" />
                </div>
              </div>
              <div className="mt-2 flex justify-between text-xs text-ink3" aria-hidden="true">
                <span>{t('rear')}</span>
                <span>{t('cab')}</span>
              </div>
            </div>

            <ul
              className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-ink2"
              aria-label={t('legend')}
            >
              {plan.offers.map((offer) => {
                const ids = current.places
                  .filter((entry) => entry.occupant?.offerId === offer.offerId)
                  .map((entry) => entry.place.id);
                return (
                  <li key={offer.offerId} className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className={`size-3 rounded-segment ${TINTS[offer.tint] ?? 'bg-cargo-a'}`}
                    />
                    <span className="font-mono">{t('offerTag', { tag: offer.tag })}</span>
                    {offerNames[offer.offerId] && (
                      <span className="font-mono text-ink3">{offerNames[offer.offerId]}</span>
                    )}
                    <span>{ids.length > 0 ? lane(ids, van.layoutTemplate) : t('notOnBoard')}</span>
                  </li>
                );
              })}
              <li className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="size-3 rounded-segment border border-dashed bg-surface"
                  style={{ borderColor: 'var(--cargo-free-border)' }}
                />
                {t('free')}
              </li>
            </ul>
          </div>
        )}

        <div className="flex min-w-60 flex-[1_1_240px] flex-col gap-4">
          <p className="text-sm font-semibold text-ink">{where}</p>
          {declaredOnly ? (
            <>
              <p className="font-display text-3xl font-medium tabular-nums text-ink">
                {formatPalletEquivalents(current.eq, van.palletPlaces, locale)}
              </p>
              <p className="text-sm text-ink2">{t('declaredOnly')}</p>
            </>
          ) : (
            <>
              <Meter
                name={t('weightMeter')}
                tone="brand"
                value={current.kg}
                max={van.payloadKg}
                label={t('weight', {
                  kg: formatMass(current.kg, locale),
                  max: formatMass(van.payloadKg, locale),
                })}
              />
              <Meter
                name={t('placesMeter')}
                tone="brand"
                value={current.eq}
                max={van.palletPlaces}
                label={formatPalletEquivalents(current.eq, van.palletPlaces, locale)}
              />
              <p className="text-sm text-ink2">{t('spaceUsed', { percent: used })}</p>
            </>
          )}
        </div>
      </div>

      <p className="text-xs text-ink3">{t('illustrative')}</p>
    </section>
  );
}
