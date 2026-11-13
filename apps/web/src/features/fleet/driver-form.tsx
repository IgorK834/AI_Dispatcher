'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { ChoiceCard } from '@/components/ui/choice-card';
import { Field, Input, Select } from '@/components/ui/field';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import { unwrap } from '@/lib/api/unwrap';
import { useSaveProblems } from './form-support';
import type { Driver, Vehicle } from './hooks';
import { driverSchema, type DriverFormValues } from './schemas';

const FIELDS = [
  'name',
  'phone',
  'homeCity',
  'homeCountry',
  'homeLat',
  'homeLon',
  'defaultRulesProfile',
  'vehicleId',
] as const;

function initialValues(driver?: Driver): DriverFormValues {
  return {
    name: driver?.name ?? '',
    phone: driver?.phone ?? '',
    homeCity: driver?.homeCity ?? '',
    homeCountry: driver?.homeCountry ?? 'PL',
    homeLat: driver ? String(driver.homeLat) : '',
    homeLon: driver ? String(driver.homeLon) : '',
    defaultRulesProfile: driver?.defaultRulesProfile ?? 'pl_domestic_employee_v1',
    vehicleId: driver?.vehicleId ?? '',
  };
}

type DriverFormProps = {
  driver?: Driver;
  vehicles: Vehicle[];
  onDone: () => void;
};

/** Create or edit a driver in the side sheet; edits carry the `version` that was loaded. */
export function DriverForm({ driver, vehicles, onDone }: DriverFormProps) {
  const t = useTranslations('fleet');
  const common = useTranslations('common');
  const validation = useTranslations('fleet.validation');
  const toast = useToast();
  const queryClient = useQueryClient();
  const [version, setVersion] = useState(driver?.version ?? 1);
  const [conflict, setConflict] = useState(false);
  const schema = useMemo(() => driverSchema((key) => validation(key)), [validation]);
  const form = useForm<DriverFormValues>({
    resolver: zodResolver(schema),
    mode: 'onBlur',
    defaultValues: initialValues(driver),
  });
  const { formError, handle } = useSaveProblems({
    form,
    fields: FIELDS,
    onConflict: () => setConflict(true),
  });

  async function save(values: DriverFormValues) {
    const body = {
      name: values.name,
      phone: values.phone || null,
      homeCity: values.homeCity,
      homeCountry: values.homeCountry,
      homeLat: Number(values.homeLat),
      homeLon: Number(values.homeLon),
      defaultRulesProfile: values.defaultRulesProfile,
      vehicleId: values.vehicleId || null,
    };
    const result = driver
      ? await api.PATCH('/api/v1/drivers/{driver_id}', {
          params: { path: { driver_id: driver.id } },
          body: { ...body, version },
        })
      : await api.POST('/api/v1/drivers', { body });
    if (result.data) {
      toast.show('success', t('toast.driverSaved'));
      await queryClient.invalidateQueries({ queryKey: ['drivers'] });
      onDone();
      return;
    }
    handle(result);
  }

  async function reload() {
    if (!driver) return;
    const fresh = unwrap(
      await api.GET('/api/v1/drivers/{driver_id}', { params: { path: { driver_id: driver.id } } }),
    );
    // The typed values stay; only the version moves on so the next save is not stale again.
    setVersion(fresh.version);
    setConflict(false);
    await queryClient.invalidateQueries({ queryKey: ['drivers'] });
  }

  const errors = form.formState.errors;
  return (
    <form noValidate onSubmit={form.handleSubmit(save)} className="flex flex-col gap-4">
      {conflict && (
        <Banner
          level="attention"
          title={t('conflict.title')}
          action={
            <Button small onClick={() => void reload()}>
              {t('conflict.reload')}
            </Button>
          }
        >
          {t('conflict.body')}
        </Banner>
      )}
      {formError && <Banner level="error">{formError}</Banner>}

      <Field id="driver-name" label={t('driverForm.name')} error={errors.name?.message}>
        {(control) => <Input {...control} autoComplete="off" {...form.register('name')} />}
      </Field>
      <Field id="driver-phone" label={t('driverForm.phone')} error={errors.phone?.message}>
        {(control) => <Input {...control} type="tel" {...form.register('phone')} />}
      </Field>
      <Field id="driver-city" label={t('driverForm.homeCity')} error={errors.homeCity?.message}>
        {(control) => <Input {...control} {...form.register('homeCity')} />}
      </Field>
      <Field
        id="driver-country"
        label={t('driverForm.homeCountry')}
        hint={t('driverForm.homeCountryHint')}
        error={errors.homeCountry?.message}
      >
        {(control) => <Input {...control} maxLength={2} {...form.register('homeCountry')} />}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field id="driver-lat" label={t('driverForm.homeLat')} error={errors.homeLat?.message}>
          {(control) => <Input {...control} inputMode="decimal" {...form.register('homeLat')} />}
        </Field>
        <Field id="driver-lon" label={t('driverForm.homeLon')} error={errors.homeLon?.message}>
          {(control) => <Input {...control} inputMode="decimal" {...form.register('homeLon')} />}
        </Field>
      </div>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-semibold text-ink">{t('driverForm.profile')}</legend>
        <ChoiceCard
          value="pl_domestic_employee_v1"
          title={t('driverForm.profilePl')}
          description={t('driverForm.profilePlNote')}
          {...form.register('defaultRulesProfile')}
        />
        <ChoiceCard
          value="eu561_van_international_v1"
          title={t('driverForm.profile561')}
          description={t('driverForm.profile561Note')}
          {...form.register('defaultRulesProfile')}
        />
      </fieldset>

      <Field id="driver-vehicle" label={t('driverForm.vehicle')} error={errors.vehicleId?.message}>
        {(control) => (
          <Select {...control} {...form.register('vehicleId')}>
            <option value="">{t('driverForm.noVehicle')}</option>
            {vehicles.map((vehicle) => (
              <option key={vehicle.id} value={vehicle.id}>
                {vehicle.label}
              </option>
            ))}
          </Select>
        )}
      </Field>

      <div className="flex justify-end">
        <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? common('saving') : common('save')}
        </Button>
      </div>
    </form>
  );
}
