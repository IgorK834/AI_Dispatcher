'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/field';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import { useSaveProblems } from './form-support';
import type { Driver } from './hooks';
import { stateSchema, type StateFormValues } from './schemas';

const FIELDS = [
  'availableFrom',
  'currentCity',
  'currentLat',
  'currentLon',
  'workTodayMin',
  'driveTodayMin',
  'workSinceBreakMin',
  'driveSinceBreakMin',
  'workWeekMin',
  'driveWeekMin',
  'drivePrevWeekMin',
  'homeBy',
] as const;

const COUNTERS = [
  ['workTodayMin', 'workToday'],
  ['driveTodayMin', 'driveToday'],
  ['workSinceBreakMin', 'workSinceBreak'],
  ['driveSinceBreakMin', 'driveSinceBreak'],
  ['workWeekMin', 'workWeek'],
  ['driveWeekMin', 'driveWeek'],
  ['drivePrevWeekMin', 'drivePrevWeek'],
] as const;

/** `<input type="datetime-local">` value for now, in local time. */
function localNow(): string {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
}

function initialValues(driver: Driver): StateFormValues {
  const state = driver.state;
  return {
    availableFrom: localNow(),
    currentCity: state?.currentCity ?? driver.homeCity,
    currentLat: String(state?.currentLat ?? driver.homeLat),
    currentLon: String(state?.currentLon ?? driver.homeLon),
    workTodayMin: '0',
    driveTodayMin: '0',
    workSinceBreakMin: '0',
    driveSinceBreakMin: '0',
    workWeekMin: String(state?.workWeekMin ?? 0),
    driveWeekMin: String(state?.driveWeekMin ?? 0),
    drivePrevWeekMin: String(state?.drivePrevWeekMin ?? 0),
    homeBy: '',
  };
}

/** "Add driver state": a new state record; the history is kept by the API. */
export function StateForm({ driver, onDone }: { driver: Driver; onDone: () => void }) {
  const t = useTranslations('fleet');
  const common = useTranslations('common');
  const validation = useTranslations('fleet.validation');
  const toast = useToast();
  const queryClient = useQueryClient();
  const schema = useMemo(() => stateSchema((key) => validation(key)), [validation]);
  const form = useForm<StateFormValues>({
    resolver: zodResolver(schema),
    mode: 'onBlur',
    defaultValues: initialValues(driver),
  });
  const { formError, handle } = useSaveProblems({ form, fields: FIELDS });

  async function save(values: StateFormValues) {
    const result = await api.POST('/api/v1/drivers/{driver_id}/state', {
      params: { path: { driver_id: driver.id } },
      body: {
        availableFrom: new Date(values.availableFrom).toISOString(),
        currentCity: values.currentCity || null,
        currentLat: Number(values.currentLat),
        currentLon: Number(values.currentLon),
        workTodayMin: Number(values.workTodayMin),
        driveTodayMin: Number(values.driveTodayMin),
        workSinceBreakMin: Number(values.workSinceBreakMin),
        driveSinceBreakMin: Number(values.driveSinceBreakMin),
        workWeekMin: Number(values.workWeekMin),
        driveWeekMin: Number(values.driveWeekMin),
        drivePrevWeekMin: Number(values.drivePrevWeekMin),
        homeBy: values.homeBy ? new Date(values.homeBy).toISOString() : null,
      },
    });
    if (result.data) {
      toast.show('success', t('toast.stateSaved'));
      await queryClient.invalidateQueries({ queryKey: ['drivers'] });
      onDone();
      return;
    }
    handle(result);
  }

  const errors = form.formState.errors;
  return (
    <form noValidate onSubmit={form.handleSubmit(save)} className="flex flex-col gap-4">
      {formError && <Banner level="error">{formError}</Banner>}
      <Field
        id="state-available"
        label={t('stateForm.availableFrom')}
        error={errors.availableFrom?.message}
      >
        {(control) => (
          <Input {...control} type="datetime-local" {...form.register('availableFrom')} />
        )}
      </Field>
      <Field id="state-city" label={t('stateForm.currentCity')} error={errors.currentCity?.message}>
        {(control) => <Input {...control} {...form.register('currentCity')} />}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field id="state-lat" label={t('stateForm.currentLat')} error={errors.currentLat?.message}>
          {(control) => <Input {...control} inputMode="decimal" {...form.register('currentLat')} />}
        </Field>
        <Field id="state-lon" label={t('stateForm.currentLon')} error={errors.currentLon?.message}>
          {(control) => <Input {...control} inputMode="decimal" {...form.register('currentLon')} />}
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {COUNTERS.map(([field, key]) => (
          <Field
            key={field}
            id={`state-${field}`}
            label={t(`stateForm.${key}`)}
            error={errors[field]?.message}
          >
            {(control) => <Input {...control} inputMode="numeric" {...form.register(field)} />}
          </Field>
        ))}
      </div>
      <Field id="state-home-by" label={t('stateForm.homeBy')} error={errors.homeBy?.message}>
        {(control) => <Input {...control} type="datetime-local" {...form.register('homeBy')} />}
      </Field>
      <div className="flex justify-end">
        <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? common('saving') : common('save')}
        </Button>
      </div>
    </form>
  );
}
