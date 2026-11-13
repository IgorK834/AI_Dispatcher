'use client';

import { useLocale, useTranslations } from 'next-intl';
import { Meter } from '@/components/ui/meter';
import { formatDuration } from '@/lib/format';
import type { Driver } from './hooks';
import { drivingBars, workBars, type WorkingTimeBar } from './working-time';

function barLabel(
  t: (key: string, values: Record<string, string>) => string,
  bar: WorkingTimeBar,
): string {
  return t('bar.left', { time: formatDuration(bar.left), limit: formatDuration(bar.limit) });
}

/** A meter for remaining time: the number is always written next to the bar. */
export function TimeLeftMeter({ bar, name }: { bar: WorkingTimeBar; name: string }) {
  const t = useTranslations('fleet');
  return (
    <Meter
      name={name}
      value={bar.left}
      max={bar.limit}
      tone={bar.low ? 'low' : 'normal'}
      label={barLabel(t, bar) + (bar.low ? ` · ${t('bar.low')}` : '')}
    />
  );
}

/** Remaining daily and weekly work for the table (the two bars of FR-13). */
export function WorkBarCell({ driver, which }: { driver: Driver; which: 'day' | 'week' }) {
  const t = useTranslations('fleet');
  if (!driver.state) return <span className="text-xs text-ink3">{t('table.noState')}</span>;
  const bars = workBars(driver.state);
  return (
    <TimeLeftMeter
      bar={bars[which]}
      name={`${which === 'day' ? t('table.workDay') : t('table.workWeek')}: ${driver.name}`}
    />
  );
}

/** The Regulation 561 driving limits shown in the driver's detail row. */
export function DrivingLimits({ driver }: { driver: Driver }) {
  const t = useTranslations('fleet');
  useLocale();
  if (!driver.state) return null;
  const bars = drivingBars(driver.state);
  return (
    <div className="flex flex-col gap-3">
      <h3 className="text-sm font-semibold text-ink">{t('details.title')}</h3>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <TimeLeftMeter bar={bars.sinceBreak} name={`${t('details.sinceBreak')}: ${driver.name}`} />
        <TimeLeftMeter bar={bars.day} name={`${t('details.day')}: ${driver.name}`} />
        <TimeLeftMeter bar={bars.week} name={`${t('details.week')}: ${driver.name}`} />
        <TimeLeftMeter bar={bars.twoWeek} name={`${t('details.twoWeek')}: ${driver.name}`} />
      </div>
    </div>
  );
}
