'use client';

import { useTranslations } from 'next-intl';
import { RouteTrack } from '@/components/ui/route-track';
import { isAction, type PlanStop } from './types';

/** Before departure the position is the origin ("Not started"); after the finish it is the end. */
export function RouteProgress({ stops, now }: { stops: PlanStop[]; now: Date }) {
  const t = useTranslations('plans.progress');
  const actions = stops.filter(isAction);
  const origin = actions[0]?.label ?? stops[0]?.label ?? '';
  const destination = actions.at(-1)?.label ?? stops.at(-1)?.label ?? '';
  const start = new Date(stops[0]?.departureAt ?? now).getTime();
  const end = new Date(stops.at(-1)?.departureAt ?? now).getTime();
  const at = now.getTime();
  const fraction = at <= start ? 0 : at >= end ? 1 : (at - start) / (end - start);
  const status =
    fraction === 0
      ? t('notStarted')
      : fraction === 1
        ? t('finished')
        : t('underway', { percent: Math.round(fraction * 100) });
  return (
    <div className="flex flex-col gap-2">
      <h3>{t('title')}</h3>
      <RouteTrack origin={origin} destination={destination} progress={fraction} status={status} />
    </div>
  );
}
