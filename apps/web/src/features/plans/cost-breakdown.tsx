'use client';

import { useLocale, useTranslations } from 'next-intl';
import { Pill } from '@/components/ui/pill';
import { Table, TBody, Td, Th, THead, Tr } from '@/components/ui/table';
import { formatMoney } from '@/lib/format';
import type { RoutePlan } from './types';

const LINES = ['fuel', 'toll', 'driver', 'perDiem', 'accommodation', 'vehicle'] as const;

type Locale = 'en' | 'pl';

/** Parameter values in words and units; an unknown parameter shows its raw value. */
function parameterValue(
  name: string,
  value: string,
  locale: Locale,
  perHour: string,
  perKm: string,
  perL: string,
) {
  const money = (minor: string) => formatMoney(Number(minor), 'EUR', locale);
  switch (name) {
    case 'fuel_price_minor_per_l':
      return `${money(value)} ${perL}`;
    case 'driver_cost_minor_per_hour':
      return `${money(value)} ${perHour}`;
    case 'vehicle_cost_minor_per_km':
      return `${money(value)} ${perKm}`;
    case 'accommodation_minor':
      return money(value);
    case 'co2_factor_kg_per_l':
      return `${value} kg/l`;
    case 'fuel_consumption':
      return `${value.replace('/', ' / ')} l/100 km`;
    default:
      return value;
  }
}

export function CostBreakdown({ plan }: { plan: RoutePlan }) {
  const t = useTranslations('plans.costs');
  const locale: Locale = useLocale() === 'pl' ? 'pl' : 'en';
  const money = (minor: number) => formatMoney(minor, plan.revenue.currency, locale);
  const parameters = Object.entries(plan.calculation.parameters ?? {});
  return (
    <section
      className="flex flex-col gap-3 rounded-card bg-surface p-6 shadow-card"
      aria-label={t('title')}
    >
      <h2>{t('title')}</h2>
      <Table>
        <TBody>
          <Tr>
            <Td>{t('revenue')}</Td>
            <Td numeric className="tabular-nums">
              {money(plan.revenue.amountMinor)}
            </Td>
          </Tr>
          {LINES.map((line) => (
            <Tr key={line}>
              <Td>
                {t(`line.${line}`)}
                {line === 'fuel' && <span className="ml-2 text-xs text-ink3">{t('estimate')}</span>}
                {line === 'toll' && <span className="ml-2 text-xs text-ink3">{t('estimate')}</span>}
              </Td>
              <Td numeric className="tabular-nums">
                {money(plan.calculation[line].amountMinor)}
              </Td>
            </Tr>
          ))}
          <Tr>
            <Td className="font-semibold">{t('total')}</Td>
            <Td numeric className="font-semibold tabular-nums">
              {money(plan.costTotal.amountMinor)}
            </Td>
          </Tr>
          <Tr>
            <Td className="font-semibold">{t('net')}</Td>
            <Td numeric className="font-semibold tabular-nums">
              {money(plan.netProfit.amountMinor)} · {t('margin', { percent: plan.marginPct })}
            </Td>
          </Tr>
        </TBody>
      </Table>
      <h3>{t('parameters')}</h3>
      <Table>
        <THead>
          <Tr>
            <Th scope="col">{t('parameter')}</Th>
            <Th scope="col">{t('value')}</Th>
            <Th scope="col">{t('basisColumn')}</Th>
          </Tr>
        </THead>
        <TBody>
          {parameters.map(([name, entry]) => (
            <Tr key={name} data-provenance={entry.provenance}>
              <Td>{t.has(`param.${name}`) ? t(`param.${name}`) : name}</Td>
              <Td className="tabular-nums">
                {parameterValue(
                  name,
                  entry.value ?? '',
                  locale,
                  t('perHour'),
                  t('perKm'),
                  t('perL'),
                )}
              </Td>
              <Td>
                <Pill level={entry.provenance === 'assumption' ? 'attention' : 'quiet'}>
                  {t.has(`basis.${entry.provenance}`)
                    ? t(`basis.${entry.provenance}`)
                    : entry.provenance}
                </Pill>
              </Td>
            </Tr>
          ))}
        </TBody>
      </Table>
    </section>
  );
}
