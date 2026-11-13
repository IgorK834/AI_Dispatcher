'use client';

import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { Pill } from '@/components/ui/pill';
import { Table, TBody, Td, Th, THead, Tr } from '@/components/ui/table';
import { VanSide } from '@/components/vehicle/van-side';
import { formatCo2, formatDateTime, formatFuel, formatMoney } from '@/lib/format';
import { OBJECTIVES, type FleetSolution, type JobResult, type PlanSummary } from './hooks';

type DriverInfo = { id: string; name: string; vehicleLabel?: string };

const ZONE = 'Europe/Warsaw';

function plansById(result: JobResult): Map<string, PlanSummary> {
  const map = new Map<string, PlanSummary>();
  for (const entry of result.perDriver) {
    for (const list of Object.values(entry.plans)) for (const plan of list) map.set(plan.id, plan);
  }
  return map;
}

function FleetTable({
  jobId,
  objective,
  solution,
  plans,
  drivers,
}: {
  jobId: string;
  objective: string;
  solution: FleetSolution;
  plans: Map<string, PlanSummary>;
  drivers: Map<string, DriverInfo>;
}) {
  const t = useTranslations('optimizer.result');
  const names = useTranslations('plans.variant');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const total = solution.totals;
  return (
    <section className="flex flex-col gap-3" aria-label={names(objective)}>
      <h3>{names(objective)}</h3>
      <div className="rounded-card bg-surface shadow-card">
        <Table>
          <THead>
            <Tr>
              <Th scope="col">{t('driver')}</Th>
              <Th scope="col">{t('plan')}</Th>
              <Th scope="col" numeric>
                {t('profit')}
              </Th>
              <Th scope="col">{t('finish')}</Th>
              <Th scope="col" numeric>
                {t('fuel')}
              </Th>
              <Th scope="col" numeric>
                {t('co2')}
              </Th>
              <Th scope="col">{t('home')}</Th>
            </Tr>
          </THead>
          <TBody>
            {solution.assignments.map((assignment) => {
              const plan = plans.get(assignment.routePlanId);
              const driver = drivers.get(assignment.driverId);
              return (
                <Tr key={assignment.driverId} data-driver={assignment.driverId}>
                  <Td>
                    <div className="flex items-center gap-3">
                      {driver?.vehicleLabel && <VanSide label={driver.vehicleLabel} width={88} />}
                      <span className="font-semibold text-ink">
                        {driver?.name ?? assignment.driverId.slice(0, 8)}
                      </span>
                    </div>
                  </Td>
                  <Td>
                    <Link
                      href={`/plans/${assignment.routePlanId}?job=${jobId}`}
                      className="font-semibold text-red hover:text-red-hover"
                    >
                      {t('open')}
                    </Link>
                  </Td>
                  <Td numeric className="tabular-nums">
                    {plan
                      ? formatMoney(plan.netProfit.amountMinor, plan.netProfit.currency, locale)
                      : '—'}
                  </Td>
                  <Td className="whitespace-nowrap">
                    {plan ? formatDateTime(plan.finishAt, ZONE, locale) : '—'}
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {plan ? formatFuel(Number(plan.fuelL), locale) : '—'}
                  </Td>
                  <Td numeric className="whitespace-nowrap">
                    {plan ? formatCo2(Number(plan.co2Kg), locale) : '—'}
                  </Td>
                  <Td>
                    {plan && (
                      <Pill level={plan.homeReached ? 'done' : 'info'}>
                        {t(plan.homeReached ? 'homeYes' : 'homeNo')}
                      </Pill>
                    )}
                  </Td>
                </Tr>
              );
            })}
            <Tr>
              <Td className="font-semibold">{t('total')}</Td>
              <Td />
              <Td numeric className="font-semibold tabular-nums">
                {formatMoney(total.netProfit.amountMinor, total.netProfit.currency, locale)}
              </Td>
              <Td />
              <Td numeric className="whitespace-nowrap">
                {formatFuel(Number(total.fuelL), locale)}
              </Td>
              <Td numeric className="whitespace-nowrap">
                {formatCo2(Number(total.co2Kg), locale)}
              </Td>
              <Td />
            </Tr>
          </TBody>
        </Table>
      </div>
    </section>
  );
}

const BAR_HEIGHT = 120;

function Baselines({ result }: { result: JobResult }) {
  const t = useTranslations('optimizer.baselines');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const engine = result.fleet.profit;
  if (!engine) return null;
  const bars = [
    { key: 'engine', minor: engine.totals.netProfit.amountMinor, accent: true },
    {
      key: 'greedy',
      minor: result.baselines.baselineGreedy.totals.netProfit.amountMinor,
      accent: false,
    },
    {
      key: 'single',
      minor: result.baselines.baselineSingle.totals.netProfit.amountMinor,
      accent: false,
    },
  ];
  const max = Math.max(1, ...bars.map((bar) => bar.minor));
  const money = (minor: number) => formatMoney(minor, 'EUR', locale);
  const uplift = (base: number) => {
    const diff = engine.totals.netProfit.amountMinor - base;
    return `${diff >= 0 ? '+' : '−'}${money(Math.abs(diff))}`;
  };
  const alt = bars.map((bar) => `${t(bar.key)}: ${money(bar.minor)}`).join('; ');
  return (
    <section
      className="flex flex-col gap-3 rounded-card bg-surface p-6 shadow-card"
      aria-label={t('title')}
    >
      <h2>{t('title')}</h2>
      <div role="img" aria-label={alt} className="flex items-end gap-8">
        {bars.map((bar) => (
          <div
            key={bar.key}
            className="flex flex-col items-center gap-1 text-sm text-ink2"
            aria-hidden="true"
          >
            <span className="tabular-nums">{money(bar.minor)}</span>
            <div
              className={`w-14 rounded-inner ${bar.accent ? 'bg-red' : 'bg-neutral-data'}`}
              style={{ height: `${Math.max(4, (Math.max(bar.minor, 0) / max) * BAR_HEIGHT)}px` }}
            />
            <span>{t(bar.key)}</span>
          </div>
        ))}
      </div>
      <ul className="rounded-inner bg-well p-3 text-sm text-ink2" data-testid="uplift">
        <li>
          {t('upliftGreedy')} {uplift(bars[1]?.minor ?? 0)}
        </li>
        <li>
          {t('upliftSingle')} {uplift(bars[2]?.minor ?? 0)}
        </li>
      </ul>
    </section>
  );
}

function Rejections({ result, drivers }: { result: JobResult; drivers: Map<string, DriverInfo> }) {
  const t = useTranslations('rejections');
  const o = useTranslations('optimizer.rejections');
  const groups = new Map<string, JobResult['rejections']>();
  for (const rejection of result.rejections) {
    groups.set(rejection.code, [...(groups.get(rejection.code) ?? []), rejection]);
  }
  return (
    <section
      className="flex flex-col gap-3 rounded-card bg-surface p-6 shadow-card"
      aria-label={o('title', { count: result.rejections.length })}
    >
      <h2>{o('title', { count: result.rejections.length })}</h2>
      {groups.size === 0 && <p className="text-sm text-ink3">{o('none')}</p>}
      {[...groups.entries()].map(([code, items]) => (
        <details key={code} className="rounded-inner border border-line p-3">
          <summary className="cursor-pointer text-sm font-semibold text-ink">
            {t.has(code) ? t(code) : t('UNKNOWN')}{' '}
            <span className="font-mono text-xs text-ink3">{code}</span> · {items.length}
          </summary>
          <ul className="mt-2 flex flex-col gap-1 text-xs text-ink2">
            {items.map((item) => (
              <li key={`${item.driverId}-${item.offerId}`}>
                {drivers.get(item.driverId)?.name ?? item.driverId.slice(0, 8)} ·{' '}
                <span className="font-mono">{item.offerId.slice(0, 8)}</span>
              </li>
            ))}
          </ul>
        </details>
      ))}
    </section>
  );
}

export function OptimizerResult({
  jobId,
  result,
  drivers,
}: {
  jobId: string;
  result: JobResult;
  drivers: DriverInfo[];
}) {
  const t = useTranslations('optimizer.result');
  const legal = useTranslations('legal');
  const plans = plansById(result);
  const directory = new Map(drivers.map((driver) => [driver.id, driver]));
  return (
    <div className="flex flex-col gap-6">
      <h2>{t('title')}</h2>
      {OBJECTIVES.filter((objective) => result.fleet[objective]).map((objective) => (
        <FleetTable
          key={objective}
          jobId={jobId}
          objective={objective}
          solution={result.fleet[objective] as FleetSolution}
          plans={plans}
          drivers={directory}
        />
      ))}
      <Baselines result={result} />
      <p className="text-sm text-ink2">{legal('notice')}</p>
      <Rejections result={result} drivers={directory} />
    </div>
  );
}
