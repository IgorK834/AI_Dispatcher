'use client';

import { useLocale, useTranslations } from 'next-intl';
import { Pill } from '@/components/ui/pill';
import { Table, TBody, Td, Th, THead, Tr } from '@/components/ui/table';
import { formatMoney, type AppLocale } from '@/lib/format';
import { useCostProfiles, type CostProfile } from './hooks';

type Row = { id: string; value: string; provenance: string[] };

/** "assumption" if any of the keys is an assumption, "source" if all are sourced, else unknown. */
function basisOf(profile: CostProfile, keys: string[]): 'source' | 'assumption' | 'unknown' {
  const found = keys.map((key) => profile.provenance[key]);
  if (found.some((entry) => entry === 'assumption')) return 'assumption';
  return found.length > 0 && found.every((entry) => entry === 'source') ? 'source' : 'unknown';
}

function rowsOf(profile: CostProfile, locale: AppLocale): (Row & { basis: string })[] {
  const money = (minor: number) => formatMoney(minor, profile.currency, locale);
  const rate = (record: Record<string, number>) =>
    Object.entries(record)
      .map(([code, minor]) => `${code} ${money(minor)}`)
      .join(', ') || '—';
  const tollKeys = Object.keys(profile.tolls.perKm).map((code) => `tolls.${code}`);
  const rows: Row[] = [
    {
      id: 'fuelPrice',
      value: money(profile.fuelPriceMinorPerL),
      provenance: ['fuel_price_minor_per_l'],
    },
    {
      id: 'driverCost',
      value: money(profile.driverCostMinorPerHour),
      provenance: ['driver_cost_minor_per_hour'],
    },
    {
      id: 'vehicleCost',
      value: money(profile.vehicleCostMinorPerKm),
      provenance: ['vehicle_cost_minor_per_km'],
    },
    {
      id: 'accommodation',
      value: money(profile.accommodationMinor),
      provenance: ['accommodation_minor'],
    },
    { id: 'perDiem', value: rate(profile.perDiem), provenance: ['per_diem'] },
    { id: 'tolls', value: rate(profile.tolls.perKm), provenance: tollKeys },
    {
      id: 'vignettes',
      value: profile.tolls.annualVignettes.join(', ') || '—',
      provenance: ['tolls.annual_vignettes'],
    },
    {
      id: 'fx',
      value:
        Object.entries(profile.fxRates)
          .map(([code, value]) => `EUR/${code} ${value}`)
          .join(', ') || '—',
      provenance: ['fx_rates'],
    },
    { id: 'minProfit', value: money(profile.minProfitMinor), provenance: ['min_profit_minor'] },
    { id: 'minMargin', value: `${profile.minMarginPct} %`, provenance: ['min_margin_pct'] },
  ];
  return rows.map((row) => ({ ...row, basis: basisOf(profile, row.provenance) }));
}

/** The cost profile as values with their basis; editing is deliberately not offered (OQ-005-05). */
export function CostProfileView() {
  const t = useTranslations('admin.cost');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const profiles = useCostProfiles();
  const profile = profiles.data?.[0];
  return (
    <section
      aria-labelledby="admin-cost-title"
      className="flex flex-col gap-3 rounded-card bg-surface p-6 shadow-card"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h2 id="admin-cost-title">
          {profile ? t('title', { name: profile.name }) : t('titleEmpty')}
        </h2>
        <Pill level="quiet">{t('readOnly')}</Pill>
      </div>
      {profiles.isPending && <p className="text-sm text-ink3">{t('loading')}</p>}
      {profiles.isError && <p className="text-sm text-ink2">{t('unavailable')}</p>}
      {profiles.data && !profile && <p className="text-sm text-ink2">{t('none')}</p>}
      {profile && (
        <>
          <div className="overflow-x-auto">
            <Table>
              <THead>
                <Tr>
                  <Th scope="col">{t('parameter')}</Th>
                  <Th scope="col">{t('value')}</Th>
                  <Th scope="col">{t('basis')}</Th>
                </Tr>
              </THead>
              <TBody>
                {rowsOf(profile, locale).map((row) => (
                  <Tr key={row.id}>
                    <Td>{t(`rows.${row.id}`)}</Td>
                    <Td>{row.value}</Td>
                    <Td>
                      <Pill level={row.basis === 'assumption' ? 'attention' : 'quiet'}>
                        {t(`basisValue.${row.basis}`)}
                      </Pill>
                    </Td>
                  </Tr>
                ))}
              </TBody>
            </Table>
          </div>
          <p className="text-xs text-ink3">{t('note')}</p>
        </>
      )}
    </section>
  );
}
