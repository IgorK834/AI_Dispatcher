'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';
import { useForm, type UseFormReturn } from 'react-hook-form';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Field, Input, Select, Textarea } from '@/components/ui/field';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { unwrap } from '@/lib/api/unwrap';
import { useSaveProblems } from '@/lib/use-save-problems';
import { destinationOf, originOf, toLocalInput, toMinor } from './format';
import type { Offer, OfferStop } from './hooks';
import { offerSchema, type OfferFormValues } from './schemas';

type StopCreate = components['schemas']['StopCreate'];

const FIELDS = [
  'description',
  'weightKg',
  'palletType',
  'palletCount',
  'loadingLengthM',
  'requiredBodyTypes',
  'publicRemark',
] as const;
const BODY_TYPES = ['CURTAIN_SIDER', 'TAUTLINER', 'BOX'] as const;
const PALLET_TYPES = ['EUR_1200x800', 'IND_1200x1000', 'HALF_800x600', 'UNKNOWN'] as const;

type StopValues = OfferFormValues['loading'];

function stopValues(stop?: OfferStop): StopValues {
  return {
    city: stop?.city ?? '',
    countryCode: stop?.countryCode ?? 'PL',
    lat: stop?.lat != null ? String(stop.lat) : '',
    lon: stop?.lon != null ? String(stop.lon) : '',
    windowStart: stop ? toLocalInput(stop.windowStart) : '',
    windowEnd: stop ? toLocalInput(stop.windowEnd) : '',
    serviceMinutes: stop ? String(stop.serviceMinutes) : '',
  };
}

function initialValues(offer?: Offer): OfferFormValues {
  return {
    description: offer?.description ?? '',
    weightKg: offer?.weightKg != null ? String(offer.weightKg) : '',
    palletType: (offer?.palletType as OfferFormValues['palletType']) ?? 'EUR_1200x800',
    palletCount: offer?.palletCount != null ? String(offer.palletCount) : '',
    loadingLengthM: offer?.loadingLengthM ?? '',
    requiredBodyTypes: offer?.requiredBodyTypes ?? ['CURTAIN_SIDER'],
    price: offer?.revenue ? (offer.revenue.amountMinor / 100).toFixed(2) : '',
    publicRemark: offer?.publicRemark ?? '',
    loading: stopValues(offer && originOf(offer)),
    unloading: stopValues(offer && destinationOf(offer)),
  };
}

function stopBody(stopType: StopCreate['stopType'], values: StopValues): StopCreate {
  return {
    stopType,
    city: values.city,
    countryCode: values.countryCode,
    lat: values.lat === '' ? null : Number(values.lat),
    lon: values.lon === '' ? null : Number(values.lon),
    serviceMinutes: values.serviceMinutes === '' ? null : Number(values.serviceMinutes),
    windowStart: new Date(values.windowStart).toISOString(),
    windowEnd: new Date(values.windowEnd).toISOString(),
  };
}

type StopFieldsProps = {
  form: UseFormReturn<OfferFormValues>;
  prefix: 'loading' | 'unloading';
};

function StopFields({ form, prefix }: StopFieldsProps) {
  const t = useTranslations('offers.form');
  const errors = form.formState.errors[prefix];
  return (
    <fieldset className="flex flex-col gap-3 rounded-inner border border-line p-3">
      <legend className="px-1 text-sm font-semibold text-ink">
        {t(prefix === 'loading' ? 'loadingStop' : 'unloadingStop')}
      </legend>
      <div className="grid grid-cols-[1fr_6rem] gap-3">
        <Field id={`${prefix}-city`} label={t('city')} error={errors?.city?.message}>
          {(control) => <Input {...control} {...form.register(`${prefix}.city`)} />}
        </Field>
        <Field id={`${prefix}-country`} label={t('country')} error={errors?.countryCode?.message}>
          {(control) => (
            <Input {...control} maxLength={2} {...form.register(`${prefix}.countryCode`)} />
          )}
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field id={`${prefix}-lat`} label={t('lat')} error={errors?.lat?.message}>
          {(control) => (
            <Input {...control} inputMode="decimal" {...form.register(`${prefix}.lat`)} />
          )}
        </Field>
        <Field id={`${prefix}-lon`} label={t('lon')} error={errors?.lon?.message}>
          {(control) => (
            <Input {...control} inputMode="decimal" {...form.register(`${prefix}.lon`)} />
          )}
        </Field>
      </div>
      <Field id={`${prefix}-start`} label={t('windowStart')} error={errors?.windowStart?.message}>
        {(control) => (
          <Input {...control} type="datetime-local" {...form.register(`${prefix}.windowStart`)} />
        )}
      </Field>
      <Field id={`${prefix}-end`} label={t('windowEnd')} error={errors?.windowEnd?.message}>
        {(control) => (
          <Input {...control} type="datetime-local" {...form.register(`${prefix}.windowEnd`)} />
        )}
      </Field>
      <Field
        id={`${prefix}-service`}
        label={t('service')}
        hint={t('serviceHint')}
        error={errors?.serviceMinutes?.message}
      >
        {(control) => (
          <Input {...control} inputMode="numeric" {...form.register(`${prefix}.serviceMinutes`)} />
        )}
      </Field>
    </fieldset>
  );
}

type OfferFormProps = { offer?: Offer; onDone: () => void };

/** Create or edit a manual offer; an edit carries the `version` that was loaded. */
export function OfferForm({ offer, onDone }: OfferFormProps) {
  const t = useTranslations('offers');
  if (offer && offer.stops.length !== 2) {
    return <Banner level="attention">{t('form.multiStop', { count: offer.stops.length })}</Banner>;
  }
  return <OfferFormFields offer={offer} onDone={onDone} />;
}

function OfferFormFields({ offer, onDone }: OfferFormProps) {
  const t = useTranslations('offers');
  const common = useTranslations('common');
  const validation = useTranslations('offers.validation');
  const toast = useToast();
  const queryClient = useQueryClient();
  const [version, setVersion] = useState(offer?.version ?? 1);
  const [conflict, setConflict] = useState(false);
  const schema = useMemo(() => offerSchema((key) => validation(key)), [validation]);
  const form = useForm<OfferFormValues>({
    resolver: zodResolver(schema),
    mode: 'onBlur',
    defaultValues: initialValues(offer),
  });
  const { formError, handle } = useSaveProblems({
    form,
    fields: FIELDS,
    texts: {
      noPermission: t('toast.noPermission'),
      unknownFields: (fields) => t('formError', { fields }),
    },
    onConflict: () => setConflict(true),
  });

  async function save(values: OfferFormValues) {
    const body = {
      description: values.description,
      weightKg: Number(values.weightKg),
      palletType: values.palletType,
      palletCount: Number(values.palletCount),
      loadingLengthM: values.loadingLengthM === '' ? null : Number(values.loadingLengthM),
      requiredBodyTypes: values.requiredBodyTypes,
      revenue: values.price === '' ? null : { amountMinor: toMinor(values.price), currency: 'EUR' },
      publicRemark: values.publicRemark || null,
      stops: [stopBody('LOADING', values.loading), stopBody('UNLOADING', values.unloading)],
    };
    const result = offer
      ? await api.PATCH('/api/v1/freight-offers/{offer_id}', {
          params: { path: { offer_id: offer.id } },
          body: { ...body, version },
        })
      : await api.POST('/api/v1/freight-offers', { body });
    if (result.data) {
      toast.show('success', t('toast.saved'));
      await queryClient.invalidateQueries({ queryKey: ['offers'] });
      onDone();
      return;
    }
    handle(result);
  }

  async function reload() {
    if (!offer) return;
    const fresh = unwrap(
      await api.GET('/api/v1/freight-offers/{offer_id}', {
        params: { path: { offer_id: offer.id } },
      }),
    );
    // The typed values stay; only the version moves on so the next save is not stale again.
    setVersion(fresh.version);
    setConflict(false);
    await queryClient.invalidateQueries({ queryKey: ['offers'] });
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

      <Field
        id="offer-description"
        label={t('form.description')}
        error={errors.description?.message}
      >
        {(control) => <Textarea {...control} {...form.register('description')} />}
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field id="offer-weight" label={t('form.weightKg')} error={errors.weightKg?.message}>
          {(control) => <Input {...control} inputMode="decimal" {...form.register('weightKg')} />}
        </Field>
        <Field id="offer-pallets" label={t('form.palletCount')} error={errors.palletCount?.message}>
          {(control) => (
            <Input {...control} inputMode="numeric" {...form.register('palletCount')} />
          )}
        </Field>
      </div>
      <Field id="offer-pallet-type" label={t('form.palletType')} error={errors.palletType?.message}>
        {(control) => (
          <Select {...control} {...form.register('palletType')}>
            {PALLET_TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`options.${type}`)}
              </option>
            ))}
          </Select>
        )}
      </Field>
      <Field
        id="offer-length"
        label={t('form.loadingLength')}
        error={errors.loadingLengthM?.message}
      >
        {(control) => (
          <Input {...control} inputMode="decimal" {...form.register('loadingLengthM')} />
        )}
      </Field>

      <fieldset className="flex flex-col gap-2">
        <legend className="mb-1 text-sm font-semibold text-ink">{t('form.bodyTypes')}</legend>
        {BODY_TYPES.map((type) => (
          <label key={type} className="flex min-h-11 items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              className="size-4 accent-red"
              value={type}
              {...form.register('requiredBodyTypes')}
            />
            {t(`options.${type}`)}
          </label>
        ))}
        {errors.requiredBodyTypes?.message && (
          <p role="alert" className="text-xs font-semibold text-red-hover">
            {errors.requiredBodyTypes.message}
          </p>
        )}
      </fieldset>

      <Field id="offer-price" label={t('form.price')} error={errors.price?.message}>
        {(control) => <Input {...control} inputMode="decimal" {...form.register('price')} />}
      </Field>

      <StopFields form={form} prefix="loading" />
      <StopFields form={form} prefix="unloading" />
      <p className="text-xs text-ink3">
        {t('form.coordinatesHint')} {t('form.zoneNote')}
      </p>

      <Field id="offer-remark" label={t('form.remark')} error={errors.publicRemark?.message}>
        {(control) => <Textarea {...control} {...form.register('publicRemark')} />}
      </Field>

      <div className="flex justify-end">
        <Button type="submit" variant="primary" loading={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? common('saving') : common('save')}
        </Button>
      </div>
    </form>
  );
}
