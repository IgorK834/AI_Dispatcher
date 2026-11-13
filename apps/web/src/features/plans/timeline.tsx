'use client';

import { useLocale, useTranslations } from 'next-intl';
import { formatDuration } from '@/lib/format';
import { formatClock, minutesBetween } from './format';
import { isAction, type PlanStop } from './types';

type Kind = 'drive' | 'service' | 'wait' | 'break' | 'rest';
export type Segment = { kind: Kind; start: string; end: string; minutes: number };

/**
 * The schedule as segments: the gap before a stop is driving, a pickup or delivery is service,
 * a rest or break stop is that rest, and a wait is the time between arrival and service start.
 */
export function timelineSegments(stops: PlanStop[]): Segment[] {
  const segments: Segment[] = [];
  const first = stops[0];
  if (!first) return segments;
  let cursor = first.departureAt;
  const push = (kind: Kind, start: string, end: string) => {
    const minutes = minutesBetween(start, end);
    if (minutes > 0) segments.push({ kind, start, end, minutes });
  };
  for (const stop of stops.slice(1)) {
    push('drive', cursor, stop.arrivalAt);
    push('wait', stop.arrivalAt, stop.serviceStartAt);
    if (isAction(stop)) push('service', stop.serviceStartAt, stop.departureAt);
    else if (stop.kind === 'BREAK') push('break', stop.serviceStartAt, stop.departureAt);
    else if (stop.kind === 'DAILY_REST' || stop.kind === 'WEEKLY_REST')
      push('rest', stop.serviceStartAt, stop.departureAt);
    cursor = stop.departureAt;
  }
  return segments;
}

const FILL: Record<Kind, string> = {
  drive: 'bg-red',
  service: 'bg-red-soft',
  wait: 'border border-line-strong bg-surface',
  break: 'bg-neutral-data',
  rest: '',
};

export function Timeline({ stops }: { stops: PlanStop[] }) {
  const t = useTranslations('plans.timeline');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const segments = timelineSegments(stops);
  const first = segments[0];
  const last = segments.at(-1);
  if (!first || !last) return null;
  const total = minutesBetween(first.start, last.end);
  const sum = (kind: Kind) =>
    segments
      .filter((segment) => segment.kind === kind)
      .reduce((value, segment) => value + segment.minutes, 0);
  const count = (kind: Kind) => segments.filter((segment) => segment.kind === kind).length;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((fraction) => ({
    fraction,
    label: formatClock(
      new Date(new Date(first.start).getTime() + total * fraction * 60000).toISOString(),
      locale,
    ),
  }));
  const label = (segment: Segment) =>
    t('segment', {
      kind: t(`kind.${segment.kind}`),
      minutes: formatDuration(segment.minutes),
      from: formatClock(segment.start, locale),
      to: formatClock(segment.end, locale),
    });
  const legend: { kind: Kind; swatch: string }[] = [
    { kind: 'drive', swatch: FILL.drive },
    { kind: 'service', swatch: FILL.service },
    { kind: 'wait', swatch: FILL.wait },
    { kind: 'break', swatch: FILL.break },
    { kind: 'rest', swatch: '' },
  ];

  return (
    <section
      className="flex flex-col gap-3 rounded-card bg-surface p-6 shadow-card"
      aria-label={t('title')}
    >
      <h2>{t('title')}</h2>
      <div
        className="flex h-9 items-stretch gap-[3px] overflow-hidden rounded-inner border border-line bg-well p-1"
        data-testid="timeline-track"
      >
        {segments.map((segment) => (
          <div
            key={`${segment.kind}-${segment.start}`}
            role="img"
            aria-label={label(segment)}
            title={label(segment)}
            data-kind={segment.kind}
            className={`min-w-0.5 rounded-segment ${FILL[segment.kind]}`}
            style={{
              flexGrow: segment.minutes,
              flexBasis: 0,
              ...(segment.kind === 'rest' ? { backgroundImage: 'var(--timeline-rest)' } : {}),
            }}
          />
        ))}
      </div>
      <div className="flex justify-between text-xs text-ink3" aria-hidden="true">
        {ticks.map((tick) => (
          <span key={tick.fraction}>{tick.label}</span>
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink2">
        {legend.map(({ kind, swatch }) => (
          <li key={kind} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className={`size-3 rounded-segment ${swatch}`}
              style={kind === 'rest' ? { backgroundImage: 'var(--timeline-rest)' } : undefined}
            />
            <span>
              {t(`kind.${kind}`)}: {formatDuration(sum(kind))}
              {(kind === 'break' || kind === 'rest') && ` (${count(kind)})`}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-ink3">{t('estimate')}</p>
    </section>
  );
}
