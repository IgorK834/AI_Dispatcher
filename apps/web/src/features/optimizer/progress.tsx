'use client';

import { useTranslations } from 'next-intl';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Meter } from '@/components/ui/meter';
import type { Job } from './hooks';

export function JobProgress({ job, onRunAgain }: { job: Job; onRunAgain: () => void }) {
  const t = useTranslations('optimizer.progress');
  if (job.status === 'failed' || job.status === 'cancelled') {
    return (
      <Banner
        level="error"
        title={t('failed')}
        action={<Button onClick={onRunAgain}>{t('runAgain')}</Button>}
      >
        {job.error ? `${t('code')}: ${job.error.code}` : t(job.status)}
      </Banner>
    );
  }
  if (job.status === 'succeeded') return null;
  const { phase, driversDone, driversTotal } = job.progress;
  return (
    <div className="flex flex-col gap-2 rounded-card bg-surface p-6 shadow-card" role="status">
      <h2>{t('title')}</h2>
      <p className="text-sm text-ink2">{t(`phase.${phase}`)}</p>
      <Meter
        name={t('title')}
        value={driversDone}
        max={Math.max(driversTotal, 1)}
        label={t('drivers', { done: driversDone, total: driversTotal })}
        tone="brand"
      />
    </div>
  );
}
