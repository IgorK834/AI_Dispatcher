'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Field, Input, Select } from '@/components/ui/field';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import { unwrap } from '@/lib/api/unwrap';
import { useSaveProblems } from './form-support';
import type { CostProfile, Vehicle } from './hooks';
import { vehicleSchema, type VehicleFormValues } from './schemas';

const FIELDS = [
  'label',
  'bodyType',
  'palletPlaces',
  'layoutTemplate',
  'sideAccess',
  'payloadKg',
  'gvwKg',
  'sleeperCab',
  'fuelEmpty',
  'fuelFull',
  'costProfileId',
  'innerLengthM',
  'innerWidthM',
  'innerHeightM',
] as const;

const BODY_TYPES = ['CURTAIN_SIDER', 'TAUTLINER', 'BOX'] as const;
const LAYOUTS = ['EUR_MIXED_6X4', 'EUR_MIXED_5X3', 'DECLARED_ONLY'] as const;
const SIDES = ['LEFT', 'RIGHT', 'BOTH', 'NONE'] as const;

const text = (value: number | string | null | undefined) => (value == null ? '' : String(value));

function initialValues(
  vehicle: Vehicle | undefined,
  costProfiles: CostProfile[],
): VehicleFormValues {
  return {
    label: vehicle?.label ?? '',
    bodyType: vehicle?.bodyType ?? 'CURTAIN_SIDER',
    palletPlaces: text(vehicle?.palletPlaces ?? 10),
    layoutTemplate: vehicle?.layoutTemplate ?? 'EUR_MIXED_6X4',
    sideAccess: vehicle?.sideAccess ?? 'BOTH',
    payloadKg: text(vehicle?.payloadKg ?? 1085),
    gvwKg: text(vehicle?.gvwKg ?? 3500),
    sleeperCab: vehicle?.sleeperCab ?? false,
    fuelEmpty: text(vehicle?.fuel.lPer100kmEmptyAt90 ?? 11),
    fuelFull: text(vehicle?.fuel.lPer100kmFullAt90 ?? 13),
    costProfileId: vehicle?.costProfileId ?? costProfiles[0]?.id ?? '',
    innerLengthM: text(vehicle?.innerLengthM),
    innerWidthM: text(vehicle?.innerWidthM),
    innerHeightM: text(vehicle?.innerHeightM),
  };
}

const optionalNumber = (value: string) => (value === '' ? null : Number(value));

type VehicleFormProps = { vehicle?: Vehicle; costProfiles: CostProfile[]; onDone: () => void };

/** Create or edit a vehicle: the same form, conflict and toast behaviour as the driver form. */
export function VehicleForm({ vehicle, costProfiles, onDone }: VehicleFormProps) {
  const t = useTranslations('fleet');
  const common = useTranslations('common');
  const validation = useTranslations('fleet.validation');
  const toast = useToast();
  const queryClient = useQueryClient();
  const [version, setVersion] = useState(vehicle?.version ?? 1);
  const [conflict, setConflict] = useState(false);
  const schema = useMemo(() => vehicleSchema((key) => validation(key)), [validation]);
  const form = useForm<VehicleFormValues>({
    resolver: zodResolver(schema),
    mode: 'onBlur',
    defaultValues: initialValues(vehicle, costProfiles),
  });
  const { formError, handle } = useSaveProblems({
    form,
    fields: FIELDS,
    onConflict: () => setConflict(true),
    fieldForCode: { DUPLICATE_RESOURCE: 'label' },
  });

  async function save(values: VehicleFormValues) {
    const body = {
      label: values.label,
      vehicleType: 'VEHICLE_UP_TO_3_5_T' as const,
      bodyType: values.bodyType,
      palletPlaces: Number(values.palletPlaces),
      layoutTemplate: values.layoutTemplate,
      sideAccess: values.sideAccess,
      payloadKg: Number(values.payloadKg),
      gvwKg: Number(values.gvwKg),
      sleeperCab: values.sleeperCab,
      fuel: {
        lPer100kmEmptyAt90: Number(values.fuelEmpty),
        lPer100kmFullAt90: Number(values.fuelFull),
        speedCurve: 'VAN_DEFAULT_V1' as const,
      },
      costProfileId: values.costProfileId,
      innerLengthM: optionalNumber(values.innerLengthM),
      innerWidthM: optionalNumber(values.innerWidthM),
      innerHeightM: optionalNumber(values.innerHeightM),
    };
    const result = vehicle
      ? await api.PATCH('/api/v1/vehicles/{vehicle_id}', {
          params: { path: { vehicle_id: vehicle.id } },
          body: { ...body, version },
        })
      : await api.POST('/api/v1/vehicles', { body });
    if (result.data) {
      toast.show('success', t('toast.vehicleSaved'));
      await queryClient.invalidateQueries({ queryKey: ['vehicles'] });
      await queryClient.invalidateQueries({ queryKey: ['drivers'] });
      onDone();
      return;
    }
    handle(result);
  }

  async function reload() {
    if (!vehicle) return;
    const fresh = unwrap(
      await api.GET('/api/v1/vehicles/{vehicle_id}', {
        params: { path: { vehicle_id: vehicle.id } },
      }),
    );
    setVersion(fresh.version);
    setConflict(false);
    await queryClient.invalidateQueries({ queryKey: ['vehicles'] });
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

      <Field id="vehicle-label" label={t('vehicleForm.label')} error={errors.label?.message}>
        {(control) => <Input {...control} autoComplete="off" {...form.register('label')} />}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field id="vehicle-body" label={t('vehicleForm.bodyType')} error={errors.bodyType?.message}>
          {(control) => (
            <Select {...control} {...form.register('bodyType')}>
              {BODY_TYPES.map((value) => (
                <option key={value} value={value}>
                  {t(`options.${value}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          id="vehicle-places"
          label={t('vehicleForm.palletPlaces')}
          error={errors.palletPlaces?.message}
        >
          {(control) => (
            <Input {...control} inputMode="numeric" {...form.register('palletPlaces')} />
          )}
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field
          id="vehicle-layout"
          label={t('vehicleForm.layout')}
          error={errors.layoutTemplate?.message}
        >
          {(control) => (
            <Select {...control} {...form.register('layoutTemplate')}>
              {LAYOUTS.map((value) => (
                <option key={value} value={value}>
                  {t(`options.${value}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field
          id="vehicle-side"
          label={t('vehicleForm.sideAccess')}
          error={errors.sideAccess?.message}
        >
          {(control) => (
            <Select {...control} {...form.register('sideAccess')}>
              {SIDES.map((value) => (
                <option key={value} value={value}>
                  {t(`options.${value}`)}
                </option>
              ))}
            </Select>
          )}
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field
          id="vehicle-payload"
          label={t('vehicleForm.payload')}
          error={errors.payloadKg?.message}
        >
          {(control) => <Input {...control} inputMode="numeric" {...form.register('payloadKg')} />}
        </Field>
        <Field id="vehicle-gvw" label={t('vehicleForm.gvw')} error={errors.gvwKg?.message}>
          {(control) => <Input {...control} inputMode="numeric" {...form.register('gvwKg')} />}
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field
          id="vehicle-fuel-empty"
          label={t('vehicleForm.fuelEmpty')}
          error={errors.fuelEmpty?.message}
        >
          {(control) => <Input {...control} inputMode="decimal" {...form.register('fuelEmpty')} />}
        </Field>
        <Field
          id="vehicle-fuel-full"
          label={t('vehicleForm.fuelFull')}
          error={errors.fuelFull?.message}
        >
          {(control) => <Input {...control} inputMode="decimal" {...form.register('fuelFull')} />}
        </Field>
      </div>
      <Field
        id="vehicle-cost"
        label={t('vehicleForm.costProfile')}
        error={errors.costProfileId?.message}
      >
        {(control) => (
          <Select {...control} {...form.register('costProfileId')}>
            {costProfiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <div className="grid grid-cols-3 gap-3">
        <Field
          id="vehicle-length"
          label={t('vehicleForm.innerLength')}
          error={errors.innerLengthM?.message}
        >
          {(control) => (
            <Input {...control} inputMode="decimal" {...form.register('innerLengthM')} />
          )}
        </Field>
        <Field
          id="vehicle-width"
          label={t('vehicleForm.innerWidth')}
          error={errors.innerWidthM?.message}
        >
          {(control) => (
            <Input {...control} inputMode="decimal" {...form.register('innerWidthM')} />
          )}
        </Field>
        <Field
          id="vehicle-height"
          label={t('vehicleForm.innerHeight')}
          error={errors.innerHeightM?.message}
        >
          {(control) => (
            <Input {...control} inputMode="decimal" {...form.register('innerHeightM')} />
          )}
        </Field>
      </div>
      <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
        <input type="checkbox" className="size-4 accent-red" {...form.register('sleeperCab')} />
        {t('vehicleForm.sleeperCab')}
      </label>

      <div className="flex justify-end">
        <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? common('saving') : common('save')}
        </Button>
      </div>
    </form>
  );
}
