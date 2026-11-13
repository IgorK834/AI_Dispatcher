'use client';

import { useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useState, type FormEvent } from 'react';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/field';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import { useProblemFromBody } from '@/lib/use-problem';
import { CountsView } from './counts-view';

/** The word that has to be typed; it stays "RESET" in every language (the label is translated). */
export const CONFIRMATION_WORD = 'RESET';

const DELETED = ['generated', 'manual', 'jobs', 'agent'] as const;
const KEPT = ['accounts', 'audit'] as const;

/** Restores the first-start state; nothing is sent until the confirmation word is typed (FR-30). */
export function ResetSection() {
  const t = useTranslations('admin.reset');
  const toast = useToast();
  const queryClient = useQueryClient();
  const toProblem = useProblemFromBody();
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<unknown>(null);
  const confirmed = typed === CONFIRMATION_WORD;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!confirmed || busy) return;
    setBusy(true);
    try {
      const outcome = await api.POST('/api/v1/admin/demo-data/reset');
      if (outcome.data) {
        setResult(outcome.data);
        setTyped('');
        toast.show('success', t('done'));
        await queryClient.invalidateQueries();
        return;
      }
      const problem = toProblem(outcome.error);
      toast.show(
        'error',
        problem.requestId ? `${problem.message} (${problem.requestId})` : problem.message,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="admin-reset-title"
      className="flex flex-col gap-4 rounded-card bg-surface p-6 shadow-card"
    >
      <div className="flex flex-col gap-1">
        <h2 id="admin-reset-title">{t('title')}</h2>
        <p className="text-sm text-ink2">{t('body')}</p>
      </div>
      <div className="grid gap-4 text-sm sm:grid-cols-2">
        <div>
          <h3 className="text-sm font-semibold text-ink">{t('deletedTitle')}</h3>
          <ul className="mt-1 list-disc pl-5 text-ink2">
            {DELETED.map((key) => (
              <li key={key}>{t(`deleted.${key}`)}</li>
            ))}
          </ul>
        </div>
        <div>
          <h3 className="text-sm font-semibold text-ink">{t('keptTitle')}</h3>
          <ul className="mt-1 list-disc pl-5 text-ink2">
            {KEPT.map((key) => (
              <li key={key}>{t(`kept.${key}`)}</li>
            ))}
          </ul>
        </div>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <Field id="admin-reset-word" label={t('confirmLabel')} hint={t('confirmHint')}>
          {(control) => (
            <Input
              {...control}
              autoComplete="off"
              value={typed}
              onChange={(event) => setTyped(event.target.value)}
            />
          )}
        </Field>
        <div>
          <Button type="submit" variant="danger" disabled={!confirmed} loading={busy}>
            {t('submit')}
          </Button>
        </div>
      </form>
      {result !== null && <CountsView result={result} />}
    </section>
  );
}
