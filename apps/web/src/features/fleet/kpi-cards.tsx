'use client';

import { useLocale, useTranslations } from 'next-intl';
import { formatDateTime, formatDuration } from '@/lib/format';
import { FLEET_TIME_ZONE } from './driver-table';
import type { Driver } from './hooks';
import { workBars } from './working-time';

type KpiCardsProps = { drivers: Driver[]; assignedIds: Set<string> };

function Card({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-card bg-surface p-6 shadow-card">
      <span className="text-xs text-ink3">{label}</span>
      <span className="font-display text-3xl font-medium text-ink">{value}</span>
      <span className="text-xs text-ink3">{note}</span>
    </div>
  );
}

/** Four numbers above the table: counts and the tightest limits, all from the loaded drivers. */
export function KpiCards({ drivers, assignedIds }: KpiCardsProps) {
  const t = useTranslations('fleet');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const vehicles = drivers.flatMap((driver) => (driver.vehicle ? [driver.vehicle] : []));
  const assigned = drivers.filter((driver) => assignedIds.has(driver.id)).length;
  const weekly = drivers
    .flatMap((driver) => (driver.state ? [{ driver, left: workBars(driver.state).week.left }] : []))
    .sort((a, b) => a.left - b.left)[0];
  const homeBy = drivers
    .flatMap((driver) => (driver.state?.homeBy ? [driver.state.homeBy] : []))
    .sort()[0];
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Card
        label={t('kpi.drivers')}
        value={String(drivers.length)}
        note={t('kpi.driversNote', {
          vans: vehicles.length,
          places: vehicles.reduce((sum, vehicle) => sum + vehicle.palletPlaces, 0),
        })}
      />
      <Card
        label={t('kpi.free')}
        value={String(drivers.length - assigned)}
        note={t('kpi.freeNote', { assigned })}
      />
      <Card
        label={t('kpi.lowestWeek')}
        value={weekly ? formatDuration(weekly.left) : t('kpi.none')}
        note={weekly?.driver.name ?? t('kpi.none')}
      />
      <Card
        label={t('kpi.homeBy')}
        value={homeBy ? formatDateTime(homeBy, FLEET_TIME_ZONE, locale) : t('kpi.none')}
        note={t('kpi.homeByNote')}
      />
    </div>
  );
}
