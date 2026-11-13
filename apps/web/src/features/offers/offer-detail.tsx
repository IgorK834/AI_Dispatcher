'use client';

import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Pill } from '@/components/ui/pill';
import { formatDateTime, formatMass, formatMoney } from '@/lib/format';
import { FlagPill, ProvenancePill } from './flags';
import { FALLBACK_ZONE, percent } from './format';
import { isManual, type Offer } from './hooks';

const LIMIT = 160;

/**
 * Text that came from a provider or a user. It is rendered as plain text exactly as written (never
 * as markup), and long text is cut with a "show more" control.
 */
function UntrustedText({ label, text }: { label: string; text: string }) {
  const t = useTranslations('offers.detail');
  const [expanded, setExpanded] = useState(false);
  const long = text.length > LIMIT;
  return (
    <section className="flex flex-col gap-1">
      <h3 className="text-sm font-semibold text-ink">{label}</h3>
      <p className="whitespace-pre-wrap break-words text-sm text-ink2">
        {long && !expanded ? `${text.slice(0, LIMIT)}…` : text}
      </p>
      <span className="text-xs text-ink3">{t('untrusted')}</span>
      {long && (
        <Button small className="self-start" onClick={() => setExpanded(!expanded)}>
          {expanded ? t('showLess') : t('showMore')}
        </Button>
      )}
    </section>
  );
}

export function OfferDetail({ offer }: { offer: Offer }) {
  const t = useTranslations('offers');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const flags = offer.qualityFlags ?? [];
  const missing = offer.missingFields ?? [];
  const provenance = Object.entries(offer.fieldProvenance ?? {});
  const fieldName = (key: string) => (t.has(`field.${key}`) ? t(`field.${key}`) : key);
  const manual = isManual(offer);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center gap-1.5">
        <Pill level={manual ? 'brand' : 'quiet'}>
          {t(manual ? 'source.manual' : 'source.imported')}
        </Pill>
        {offer.isSynthetic && <Pill level="synthetic">{t('synthetic')}</Pill>}
        <Pill level="info">{t(`status.${offer.status}`)}</Pill>
        <span className="text-xs text-ink3">{t('detail.version', { version: offer.version })}</span>
        <span className="text-xs text-ink3">
          {t('detail.completeness', { percent: `${percent(offer.completenessScore)}%` })}
        </span>
      </div>

      {flags.includes('SUSPICIOUS_TEXT') && (
        <Banner level="attention">{t('detail.suspicious')}</Banner>
      )}

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-ink">{t('detail.stops')}</h3>
        <ol className="flex flex-col gap-2">
          {offer.stops.map((stop) => (
            <li
              key={stop.sequence}
              className="flex flex-col rounded-inner border border-line p-3 text-sm"
            >
              <span className="font-semibold text-ink">
                {t(stop.stopType === 'LOADING' ? 'detail.loading' : 'detail.unloading')}:{' '}
                {stop.city} ({stop.countryCode})
              </span>
              <span className="text-ink2">
                {t('detail.window')}:{' '}
                {formatDateTime(stop.windowStart, stop.timezone || FALLBACK_ZONE, locale)} –{' '}
                {formatDateTime(stop.windowEnd, stop.timezone || FALLBACK_ZONE, locale)}
              </span>
              <span className="text-xs text-ink3">
                {t('detail.service', { minutes: stop.serviceMinutes })}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <dl className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-xs text-ink3">{t('field.weightKg')}</dt>
          <dd>{offer.weightKg != null ? formatMass(offer.weightKg, locale) : '—'}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">{t('field.palletCount')}</dt>
          <dd>{offer.palletCount ?? '—'}</dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">{t('field.palletType')}</dt>
          <dd>
            {t.has(`options.${offer.palletType}`)
              ? t(`options.${offer.palletType}`)
              : offer.palletType}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-ink3">{t('field.revenue')}</dt>
          <dd>
            {offer.revenue
              ? formatMoney(offer.revenue.amountMinor, offer.revenue.currency, locale)
              : t('table.noPrice')}
          </dd>
        </div>
      </dl>

      {offer.description && (
        <UntrustedText label={t('detail.description')} text={offer.description} />
      )}
      {offer.publicRemark && <UntrustedText label={t('detail.remark')} text={offer.publicRemark} />}

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-ink">{t('detail.provenance')}</h3>
        <ul className="flex flex-col gap-1.5">
          {provenance.map(([field, value]) => (
            <li key={field} className="flex items-center justify-between gap-3 text-sm">
              <span className="text-ink2">{fieldName(field)}</span>
              <ProvenancePill value={value} />
            </li>
          ))}
        </ul>
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-ink">{t('detail.missing')}</h3>
        {missing.length === 0 ? (
          <p className="text-sm text-ink3">{t('detail.missingNone')}</p>
        ) : (
          <ul className="flex flex-wrap gap-1">
            {missing.map((field) => (
              <li key={field}>
                <Pill level="attention">{fieldName(field)}</Pill>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-ink">{t('detail.flags')}</h3>
        {flags.length === 0 ? (
          <p className="text-sm text-ink3">{t('detail.flagsNone')}</p>
        ) : (
          <ul className="flex flex-wrap gap-1">
            {flags.map((flag) => (
              <li key={flag}>
                <FlagPill code={flag} />
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
