'use client';

import { useTranslations } from 'next-intl';
import { useState } from 'react';
import type { FieldValues, Path, UseFormReturn } from 'react-hook-form';
import { useToast } from '@/components/ui/toast';
import { useProblemFromBody } from './problems';

type Outcome = { error?: unknown; response: Response };

type Options<T extends FieldValues> = {
  form: UseFormReturn<T>;
  /** Form fields by name; a server field that is not listed goes to the form-level alert. */
  fields: readonly Path<T>[];
  onConflict?: () => void;
  /** A problem code that belongs to one field, for example DUPLICATE_RESOURCE -> label. */
  fieldForCode?: Partial<Record<string, Path<T>>>;
};

/**
 * Maps a failed save to the form (FR-7, FR-8): `422` messages go under their fields, unknown
 * fields to a form-level alert, `409 VERSION_CONFLICT` to the conflict banner, `403` to a
 * "no permission" toast and anything else to an error toast with the request id.
 */
export function useSaveProblems<T extends FieldValues>({
  form,
  fields,
  onConflict,
  fieldForCode,
}: Options<T>) {
  const t = useTranslations('fleet');
  const toast = useToast();
  const toProblem = useProblemFromBody();
  const [formError, setFormError] = useState<string | null>(null);

  function handle({ error, response }: Outcome) {
    setFormError(null);
    const problem = toProblem(error);
    if (response.status === 409 && problem.code === 'VERSION_CONFLICT') {
      onConflict?.();
      return;
    }
    if (response.status === 403) {
      toast.show('error', t('toast.noPermission'));
      return;
    }
    const owner = fieldForCode?.[problem.code];
    if (owner) {
      form.setError(owner, { type: 'server', message: problem.message });
      return;
    }
    const entries = Object.entries(problem.fieldErrors);
    if (entries.length > 0) {
      const unknown: string[] = [];
      for (const [field, message] of entries) {
        if ((fields as readonly string[]).includes(field)) {
          form.setError(field as Path<T>, { type: 'server', message });
        } else {
          unknown.push(field);
        }
      }
      if (unknown.length > 0) setFormError(t('formError', { fields: unknown.join(', ') }));
      return;
    }
    toast.show(
      'error',
      problem.requestId ? `${problem.message} (${problem.requestId})` : problem.message,
    );
  }

  return { formError, handle, clearFormError: () => setFormError(null) };
}
