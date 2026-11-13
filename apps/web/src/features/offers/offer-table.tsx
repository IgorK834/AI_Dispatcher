'use client';

import { useLocale, useTranslations } from 'next-intl';
import { IconButton } from '@/components/ui/icon-button';
import { Meter } from '@/components/ui/meter';
import { Pill } from '@/components/ui/pill';
import { Table, TBody, Td, Th, THead, Tr } from '@/components/ui/table';
import { Tooltip } from '@/components/ui/tooltip';
import { formatDateTime, formatMass, formatMoney } from '@/lib/format';
import { FlagPill } from './flags';
import { destinationOf, FALLBACK_ZONE, originOf, percent } from './format';
import { isManual, type Offer } from './hooks';
import { EditIcon, InfoIcon, LockIcon, TrashIcon } from './icons';

type OfferTableProps = {
  offers: Offer[];
  onDetails: (offer: Offer) => void;
  onEdit: (offer: Offer) => void;
  onDelete: (offer: Offer) => void;
};

const MAX_FLAGS = 3;

export function OfferTable({ offers, onDetails, onEdit, onDelete }: OfferTableProps) {
  const t = useTranslations('offers');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  return (
    <Table>
      <THead>
        <Tr>
          <Th scope="col">{t('table.offer')}</Th>
          <Th scope="col">{t('table.route')}</Th>
          <Th scope="col">{t('table.load')}</Th>
          <Th scope="col">{t('table.price')}</Th>
          <Th scope="col">{t('table.data')}</Th>
          <Th scope="col">{t('table.flags')}</Th>
          <Th scope="col">
            <span className="sr-only">{t('table.actions')}</span>
          </Th>
        </Tr>
      </THead>
      <TBody>
        {offers.map((offer) => {
          const origin = originOf(offer);
          const destination = destinationOf(offer);
          const flags = offer.qualityFlags ?? [];
          const manual = isManual(offer);
          const score = percent(offer.completenessScore);
          return (
            <Tr key={offer.id}>
              <Td>
                <div className="flex flex-col gap-1">
                  <span className="font-mono text-xs text-ink">{offer.sourceOfferId}</span>
                  <span className="flex flex-wrap gap-1">
                    <Pill level={manual ? 'brand' : 'quiet'}>
                      {t(manual ? 'source.manual' : 'source.imported')}
                    </Pill>
                    {offer.isSynthetic && <Pill level="synthetic">{t('synthetic')}</Pill>}
                    {offer.status !== 'open' && (
                      <Pill level="info">{t(`status.${offer.status}`)}</Pill>
                    )}
                  </span>
                </div>
              </Td>
              <Td>
                <div className="flex flex-col">
                  <span className="font-semibold text-ink">
                    {origin?.city} ({origin?.countryCode}) → {destination?.city} (
                    {destination?.countryCode})
                  </span>
                  {origin && (
                    <span className="text-xs text-ink3">
                      {formatDateTime(origin.windowStart, origin.timezone || FALLBACK_ZONE, locale)}
                    </span>
                  )}
                </div>
              </Td>
              <Td className="whitespace-nowrap">
                {offer.weightKg == null && offer.palletCount == null ? (
                  <span className="text-xs text-ink3">{t('table.noLoad')}</span>
                ) : (
                  <div className="flex flex-col">
                    <span>
                      {offer.palletCount != null
                        ? t('capacity', {
                            pallets: offer.palletCount,
                            kg: offer.weightKg != null ? formatMass(offer.weightKg, locale) : '—',
                          })
                        : formatMass(offer.weightKg ?? 0, locale)}
                    </span>
                  </div>
                )}
              </Td>
              <Td className="whitespace-nowrap">
                {offer.revenue ? (
                  <span className="font-semibold">
                    {formatMoney(offer.revenue.amountMinor, offer.revenue.currency, locale)}
                  </span>
                ) : (
                  <span className="text-xs text-ink3">{t('table.noPrice')}</span>
                )}
              </Td>
              <Td className="min-w-32">
                <Meter
                  name={t('table.data')}
                  value={score}
                  max={100}
                  label={t('detail.completeness', { percent: `${score}%` })}
                  tone={score < 60 ? 'low' : 'normal'}
                />
              </Td>
              <Td>
                {flags.length === 0 ? (
                  <span className="text-xs text-ink3">{t('table.noFlags')}</span>
                ) : (
                  <div className="flex flex-wrap gap-1">
                    {flags.slice(0, MAX_FLAGS).map((flag) => (
                      <FlagPill key={flag} code={flag} />
                    ))}
                    {flags.length > MAX_FLAGS && (
                      <Pill level="quiet">+{flags.length - MAX_FLAGS}</Pill>
                    )}
                  </div>
                )}
              </Td>
              <Td>
                <div className="flex justify-end gap-1">
                  <IconButton
                    small
                    icon={<InfoIcon />}
                    label={t('action.details', { id: offer.sourceOfferId })}
                    onClick={() => onDetails(offer)}
                  />
                  {manual ? (
                    <>
                      <IconButton
                        small
                        icon={<EditIcon />}
                        label={t('action.edit', { id: offer.sourceOfferId })}
                        onClick={() => onEdit(offer)}
                      />
                      <IconButton
                        small
                        icon={<TrashIcon />}
                        label={t('action.delete', { id: offer.sourceOfferId })}
                        onClick={() => onDelete(offer)}
                      />
                    </>
                  ) : (
                    <Tooltip content={t('readOnly')}>
                      <button
                        type="button"
                        aria-label={t('action.readOnly', { id: offer.sourceOfferId })}
                        className="inline-flex size-9 items-center justify-center rounded-control border border-line text-ink3"
                      >
                        <LockIcon />
                      </button>
                    </Tooltip>
                  )}
                </div>
              </Td>
            </Tr>
          );
        })}
      </TBody>
    </Table>
  );
}
