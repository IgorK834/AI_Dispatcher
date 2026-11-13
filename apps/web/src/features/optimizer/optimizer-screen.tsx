'use client';

import { useTranslations } from 'next-intl';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { ListError } from '@/components/ui/list-status';
import { useToast } from '@/components/ui/toast';
import { useProblem } from '@/lib/use-problem';
import { useDriverDirectory, useJob, useJobResult, useStartJob, type JobCreate } from './hooks';
import { OptimizerForm } from './optimizer-form';
import { JobProgress } from './progress';
import { OptimizerResult } from './result';

/** The run lives in `?job=`, so opening a plan and coming back shows the same result. */
export function OptimizerScreen() {
  const t = useTranslations('optimizer');
  const router = useRouter();
  const pathname = usePathname();
  const jobId = useSearchParams().get('job');
  const toast = useToast();
  const toProblem = useProblem();
  const drivers = useDriverDirectory();
  const start = useStartJob();
  const job = useJob(jobId);
  const result = useJobResult(jobId, job.data?.status === 'succeeded');
  const running =
    start.isPending || job.data?.status === 'queued' || job.data?.status === 'running';

  const driverList = (drivers.data ?? []).map((driver) => ({
    id: driver.id,
    name: driver.name,
    vehicleLabel: driver.vehicle?.label,
  }));

  function run(body: JobCreate) {
    start.mutate(body, {
      onSuccess: (created) => router.replace(`${pathname}?job=${created.id}`),
      onError: (error) => {
        const problem = toProblem(error);
        toast.show(
          'error',
          problem.requestId ? `${problem.message} (${problem.requestId})` : problem.message,
        );
      },
    });
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1>{t('title')}</h1>
        <p className="text-ink2">{t('subtitle')}</p>
      </div>
      <OptimizerForm drivers={driverList} busy={running} onSubmit={run} />
      {job.isError && (
        <ListError
          title={t('error.job')}
          problem={toProblem(job.error)}
          onRetry={() => void job.refetch()}
        />
      )}
      {job.data && <JobProgress job={job.data} onRunAgain={() => router.replace(pathname)} />}
      {result.isError && (
        <ListError
          title={t('error.result')}
          problem={toProblem(result.error)}
          onRetry={() => void result.refetch()}
        />
      )}
      {jobId && result.data && (
        <OptimizerResult jobId={jobId} result={result.data} drivers={driverList} />
      )}
    </div>
  );
}
