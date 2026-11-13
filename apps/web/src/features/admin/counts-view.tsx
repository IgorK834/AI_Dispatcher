'use client';

import { useLocale, useTranslations } from 'next-intl';
import { numberFormat } from '@/lib/format/locale';
import { parseCounts } from './schemas';

/** The counts a generate or reset call returned, or a plain note when the answer has another shape. */
export function CountsView({ result }: { result: unknown }) {
  const t = useTranslations('admin.counts');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const counts = parseCounts(result);
  const fmt = numberFormat(locale, { maximumFractionDigits: 0 });
  if (!counts) return <p className="text-sm text-ink2">{t('unknown')}</p>;
  const offers: [string, number][] = [
    [t('imported'), counts.offers.imported],
    [t('updated'), counts.offers.updated],
    [t('unchanged'), counts.offers.unchanged],
    [t('failed'), counts.offers.failed],
  ];
  return (
    <div className="flex flex-col gap-2 rounded-inner bg-well p-3" role="status">
      <p className="text-sm font-semibold text-ink">{t('title')}</p>
      <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
        {offers.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs text-ink3">{label}</dt>
            <dd className="font-semibold tabular-nums text-ink">{fmt.format(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="text-sm text-ink2">
        {t('fleet', { drivers: counts.drivers, vehicles: counts.vehicles })}
      </p>
    </div>
  );
}
