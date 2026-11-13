'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Banner } from '@/components/ui/banner';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/field';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import { useSaveProblems } from '@/lib/use-save-problems';
import { CountsView } from './counts-view';
import { generateSchema, type GenerateValues } from './schemas';

const FIELDS = ['seed', 'referenceDate', 'offers'] as const;

/** Re-runs the fleet and offer generators with a seed and a reference date (FR-30). */
export function GenerateForm() {
  const t = useTranslations('admin.generate');
  const validation = useTranslations('admin.validation');
  const toast = useToast();
  const queryClient = useQueryClient();
  const [result, setResult] = useState<unknown>(null);
  const schema = useMemo(() => generateSchema((key) => validation(key)), [validation]);
  const form = useForm<GenerateValues>({
    resolver: zodResolver(schema),
    defaultValues: { seed: '', referenceDate: '', offers: '150' },
  });
  const { formError, handle } = useSaveProblems({
    form,
    fields: FIELDS,
    texts: {
      noPermission: t('noPermission'),
      unknownFields: (fields) => t('unknownFields', { fields }),
    },
  });
  const { errors, isSubmitting } = form.formState;

  async function submit(values: GenerateValues) {
    const outcome = await api.POST('/api/v1/admin/demo-data/generate', {
      body: {
        drivers: 5,
        offers: Number(values.offers),
        seed: values.seed === '' ? null : Number(values.seed),
        referenceDate: values.referenceDate === '' ? null : values.referenceDate,
      },
    });
    if (outcome.data) {
      setResult(outcome.data);
      toast.show('success', t('done'));
      await queryClient.invalidateQueries();
      return;
    }
    handle(outcome);
  }

  return (
    <section
      aria-labelledby="admin-generate-title"
      className="flex flex-col gap-4 rounded-card bg-surface p-6 shadow-card"
    >
      <div className="flex flex-col gap-1">
        <h2 id="admin-generate-title">{t('title')}</h2>
        <p className="text-sm text-ink2">{t('body')}</p>
      </div>
      <form onSubmit={form.handleSubmit(submit)} noValidate className="flex flex-col gap-4">
        {formError && <Banner level="error">{formError}</Banner>}
        <div className="grid gap-4 sm:grid-cols-3">
          <Field
            id="admin-seed"
            label={t('seed')}
            hint={t('seedHint')}
            error={errors.seed?.message}
          >
            {(control) => <Input inputMode="numeric" {...control} {...form.register('seed')} />}
          </Field>
          <Field
            id="admin-reference-date"
            label={t('referenceDate')}
            hint={t('referenceDateHint')}
            error={errors.referenceDate?.message}
          >
            {(control) => <Input type="date" {...control} {...form.register('referenceDate')} />}
          </Field>
          <Field
            id="admin-offers"
            label={t('offers')}
            hint={t('offersHint')}
            error={errors.offers?.message}
          >
            {(control) => <Input inputMode="numeric" {...control} {...form.register('offers')} />}
          </Field>
        </div>
        <div>
          <Button type="submit" variant="primary" loading={isSubmitting}>
            {t('submit')}
          </Button>
        </div>
      </form>
      {result !== null && <CountsView result={result} />}
    </section>
  );
}
