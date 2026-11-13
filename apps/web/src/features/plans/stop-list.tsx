'use client';

import { useLocale, useTranslations } from 'next-intl';
import { Pill } from '@/components/ui/pill';
import { Table, TBody, Td, Th, THead, Tr } from '@/components/ui/table';
import { formatDateTime, formatDistance, formatMass, formatPalletEquivalents } from '@/lib/format';
import { isAction, PLAN_TIME_ZONE, type PlanStop, type VanLimits } from './types';

type StopListProps = {
  stops: PlanStop[];
  van?: VanLimits;
  offerNames: Record<string, string>;
};

/** The stop label of a rest is a reason code from the engine; show it in words when known. */
export function useStopLabel() {
  const reason = useTranslations('plans.reason');
  return (stop: PlanStop) =>
    !isAction(stop) && stop.kind !== 'START' && stop.kind !== 'END' && reason.has(stop.label)
      ? reason(stop.label)
      : stop.label;
}

export function StopList({ stops, van, offerNames }: StopListProps) {
  const t = useTranslations('plans.stops');
  const kinds = useTranslations('plans.kind');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const labelOf = useStopLabel();
  const clock = (iso: string) => formatDateTime(iso, PLAN_TIME_ZONE, locale);
  const numbers = new Map<number, number>();
  stops.filter(isAction).forEach((stop, index) => numbers.set(stop.sequence, index + 1));
  return (
    <section className="flex flex-col gap-3" aria-label={t('title')}>
      <h2>{t('title')}</h2>
      <div className="rounded-card bg-surface shadow-card">
        <Table>
          <THead>
            <Tr>
              <Th scope="col">{t('number')}</Th>
              <Th scope="col">{t('stop')}</Th>
              <Th scope="col">{t('arrival')}</Th>
              <Th scope="col">{t('serviceStart')}</Th>
              <Th scope="col">{t('departure')}</Th>
              <Th scope="col" numeric>
                {t('leg')}
              </Th>
              <Th scope="col" numeric>
                {t('load')}
              </Th>
            </Tr>
          </THead>
          <TBody>
            {stops.map((stop) => {
              return (
                <Tr key={stop.sequence} data-kind={stop.kind}>
                  <Td className="tabular-nums text-ink3">{numbers.get(stop.sequence) ?? '·'}</Td>
                  <Td>
                    <div className="flex flex-col gap-0.5">
                      <span className="flex flex-wrap items-center gap-2">
                        <Pill level={isAction(stop) ? 'brand' : 'quiet'}>
                          {kinds.has(stop.kind) ? kinds(stop.kind) : stop.kind}
                        </Pill>
                        <span className="font-semibold text-ink">{labelOf(stop)}</span>
                      </span>
                      {stop.offerId && offerNames[stop.offerId] && (
                        <span className="font-mono text-xs text-ink3">
                          {offerNames[stop.offerId]}
                        </span>
                      )}
                    </div>
                  </Td>
                  <Td className="whitespace-nowrap">{clock(stop.arrivalAt)}</Td>
                  <Td className="whitespace-nowrap">{clock(stop.serviceStartAt)}</Td>
                  <Td className="whitespace-nowrap">{clock(stop.departureAt)}</Td>
                  <Td numeric className="whitespace-nowrap">
                    {Number(stop.legKm) > 0 ? formatDistance(Number(stop.legKm), locale) : '—'}
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {formatPalletEquivalents(
                      Number(stop.loadPalletEqAfter),
                      van?.palletPlaces ?? 0,
                      locale,
                    )}
                    <span className="block text-xs text-ink3">
                      {formatMass(stop.loadKgAfter, locale)}
                    </span>
                  </Td>
                </Tr>
              );
            })}
          </TBody>
        </Table>
      </div>
    </section>
  );
}
