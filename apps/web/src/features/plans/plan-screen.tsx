'use client';

import { useLocale, useTranslations } from 'next-intl';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { ListError, ListSkeleton } from '@/components/ui/list-status';
import { Pill } from '@/components/ui/pill';
import { VanSide } from '@/components/vehicle/van-side';
import { useProblem } from '@/lib/use-problem';
import { AssignDialog } from './assign-dialog';
import { CostBreakdown } from './cost-breakdown';
import { ExplanationPanel } from './explanation';
import { planRef } from './format';
import { useDriverOfPlan, useExplain, useJobVariants, useOfferNames, usePlan } from './hooks';
import { LoadPlanTopView } from './load-plan-top-view';
import { Occupancy } from './occupancy';
import { PlanMap } from './plan-map';
import { RouteProgress } from './route-progress';
import { StopList } from './stop-list';
import { Timeline } from './timeline';
import { isAction, type VanLimits } from './types';
import { VehicleCard } from './vehicle-card';
import { Variants } from './variants';

export function PlanScreen({ planId }: { planId: string }) {
  const t = useTranslations('plans');
  const warnings = useTranslations('warnings');
  const legal = useTranslations('legal');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const toProblem = useProblem();
  const job = useSearchParams().get('job');
  const plan = usePlan(planId);
  const driver = useDriverOfPlan(plan.data?.driverId);
  const variants = useJobVariants(job, plan.data?.driverId);
  const offerNames = useOfferNames(plan.data?.offerIds ?? []);
  const explain = useExplain(planId);
  const [assigning, setAssigning] = useState(false);
  const [assigned, setAssigned] = useState(false);
  const [now] = useState(() => new Date());

  if (plan.isPending) return <ListSkeleton label={t('loading')} />;
  if (plan.isError) {
    return (
      <ListError
        title={t('error.title')}
        problem={toProblem(plan.error)}
        onRetry={() => void plan.refetch()}
      />
    );
  }
  const data = plan.data;
  const vehicle = driver.data?.vehicle ?? undefined;
  const van: VanLimits | undefined = vehicle
    ? {
        label: vehicle.label,
        layoutTemplate: vehicle.layoutTemplate,
        palletPlaces: vehicle.palletPlaces,
        payloadKg: vehicle.payloadKg,
      }
    : undefined;
  const actions = data.stops.filter(isAction);
  const title = `${actions[0]?.label ?? ''} → ${actions.at(-1)?.label ?? ''}`;
  const baseline = data.kind !== 'optimized';
  const profile = t.has(`profile.${data.rulesProfile}`)
    ? t(`profile.${data.rulesProfile}`)
    : data.rulesProfile;

  return (
    <div className="flex flex-col gap-6">
      <nav aria-label={t('breadcrumb.label')} className="text-sm text-ink3">
        <Link href={job ? `/optimizer?job=${job}` : '/optimizer'} className="hover:text-ink">
          {t('breadcrumb.optimizer')}
        </Link>{' '}
        › <span className="font-mono text-ink">{planRef(data.id)}</span>
      </nav>

      <header className="flex flex-wrap items-start justify-between gap-6">
        <div className="flex min-w-72 flex-1 flex-col gap-3">
          <h1>{title}</h1>
          <div className="flex flex-wrap items-center gap-2">
            <Pill level="brand">
              {baseline ? t(`kind.${data.kind}`) : t(`variant.${data.variant}`)}
            </Pill>
            <Pill level="quiet">{profile}</Pill>
            <Pill level={data.homeReached ? 'done' : 'info'}>
              {t(data.homeReached ? 'homeReached' : 'homeNotReached')}
            </Pill>
            {driver.data && (
              <span className="text-sm text-ink2">{t('driver', { name: driver.data.name })}</span>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button loading={explain.isPending} onClick={() => explain.mutate(locale)}>
              {t('actions.explain')}
            </Button>
            {!baseline && !assigned && (
              <Button variant="primary" onClick={() => setAssigning(true)}>
                {t('actions.assign')}
              </Button>
            )}
            {assigned && <Pill level="done">{t('assign.assigned')}</Pill>}
          </div>
        </div>
        {vehicle && <VanSide label={vehicle.label} width={400} />}
      </header>

      {explain.isError && <Banner level="error">{toProblem(explain.error).message}</Banner>}
      {data.warnings.length > 0 && (
        <Banner level="info" title={t('warningsTitle')}>
          <span className="flex flex-col">
            {data.warnings.map((code) => (
              <span key={code}>{warnings.has(code) ? warnings(code) : warnings('UNKNOWN')}</span>
            ))}
          </span>
        </Banner>
      )}

      {job && variants.data ? (
        <Variants variants={variants.data} currentId={data.id} jobId={job} />
      ) : (
        <Banner level="info">{t('variants.noJob')}</Banner>
      )}
      <p className="text-sm text-ink2">{legal('notice')}</p>

      {van && <LoadPlanTopView stops={data.stops} van={van} offerNames={offerNames} />}
      <Timeline stops={data.stops} />
      <StopList stops={data.stops} van={van} offerNames={offerNames} />
      {explain.data && <ExplanationPanel explanation={explain.data} />}
      <CostBreakdown plan={data} />
      <PlanMap plan={data} />
      <RouteProgress stops={data.stops} now={now} />
      {vehicle && <VehicleCard vehicle={vehicle} />}
      {van && <Occupancy stops={data.stops} van={van} />}

      {assigning && (
        <AssignDialog
          plan={data}
          driverName={driver.data?.name}
          offerNames={offerNames}
          onClose={() => setAssigning(false)}
          onAssigned={() => setAssigned(true)}
        />
      )}
    </div>
  );
}
