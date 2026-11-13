'use client';

import { useTranslations } from 'next-intl';
import { useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Field, Select } from '@/components/ui/field';
import { Segmented } from '@/components/ui/segmented';
import { OBJECTIVES, type JobCreate, type Objective } from './hooks';

type Driver = { id: string; name: string };

type OptimizerFormProps = {
  drivers: Driver[];
  busy: boolean;
  onSubmit: (body: JobCreate) => void;
};

const HORIZONS = [1, 3, 5] as const;
const MAX_OFFERS = [1, 2, 3, 4, 5, 6] as const;

/** Defaults are the API's own (5 days, 6 offers per plan); nothing is tuned silently. */
export function OptimizerForm({ drivers, busy, onSubmit }: OptimizerFormProps) {
  const t = useTranslations('optimizer.form');
  const [scope, setScope] = useState<'fleet' | 'driver'>('fleet');
  const [driverIds, setDriverIds] = useState<string[]>([]);
  const [objectives, setObjectives] = useState<Objective[]>([...OBJECTIVES]);
  const [horizon, setHorizon] = useState<number>(5);
  const [maxOffers, setMaxOffers] = useState<number>(6);
  const [error, setError] = useState<string | null>(null);

  const toggle = <T extends string>(list: T[], value: T, on: boolean) =>
    on ? [...list, value] : list.filter((item) => item !== value);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (objectives.length === 0) return setError(t('objectivesRequired'));
    if (scope === 'driver' && driverIds.length === 0) return setError(t('driversRequired'));
    setError(null);
    onSubmit({
      scope,
      driverIds: scope === 'driver' ? driverIds : [],
      objectives,
      params: { horizonDays: horizon, maxOffersPerPlan: maxOffers, topKPerDriver: 10 },
    });
  }

  return (
    <form
      noValidate
      aria-label={t('label')}
      onSubmit={submit}
      className="flex flex-col gap-5 rounded-card bg-surface p-6 shadow-card"
    >
      <div className="flex flex-col gap-2">
        <span className="text-sm font-semibold text-ink">{t('scope')}</span>
        <Segmented
          label={t('scope')}
          value={scope}
          onValueChange={setScope}
          options={[
            { value: 'fleet', label: t('scopeFleet') },
            { value: 'driver', label: t('scopeDriver') },
          ]}
        />
      </div>

      {scope === 'driver' && (
        <fieldset className="flex flex-col gap-1">
          <legend className="mb-1 text-sm font-semibold text-ink">{t('drivers')}</legend>
          {drivers.map((driver) => (
            <label key={driver.id} className="flex min-h-11 items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                className="size-4 accent-red"
                checked={driverIds.includes(driver.id)}
                onChange={(event) =>
                  setDriverIds(toggle(driverIds, driver.id, event.target.checked))
                }
              />
              {driver.name}
            </label>
          ))}
        </fieldset>
      )}

      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-sm font-semibold text-ink">{t('objectives')}</legend>
        {OBJECTIVES.map((objective) => (
          <label key={objective} className="flex min-h-11 items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              className="size-4 accent-red"
              checked={objectives.includes(objective)}
              onChange={(event) =>
                setObjectives(toggle(objectives, objective, event.target.checked))
              }
            />
            {t(`objective.${objective}`)}
          </label>
        ))}
      </fieldset>

      <div className="flex flex-wrap gap-4">
        <Field id="optimizer-horizon" label={t('horizon')}>
          {(control) => (
            <Select
              {...control}
              value={horizon}
              onChange={(event) => setHorizon(Number(event.target.value))}
            >
              {HORIZONS.map((days) => (
                <option key={days} value={days}>
                  {t('days', { count: days })}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field id="optimizer-max-offers" label={t('maxOffers')}>
          {(control) => (
            <Select
              {...control}
              value={maxOffers}
              onChange={(event) => setMaxOffers(Number(event.target.value))}
            >
              {MAX_OFFERS.map((count) => (
                <option key={count} value={count}>
                  {count}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>

      {error && (
        <p role="alert" className="text-sm font-semibold text-red-hover">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <Button type="submit" variant="primary" loading={busy}>
          {t('start')}
        </Button>
      </div>
    </form>
  );
}
