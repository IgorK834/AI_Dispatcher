'use client';

import { useLocale, useTranslations } from 'next-intl';
import { Pill } from '@/components/ui/pill';
import { numberFormat } from '@/lib/format/locale';
import { useAiStatus } from './hooks';

/** Whether the model is on and how much of today's token budget is used (read-only). */
export function AiStatus() {
  const t = useTranslations('admin.ai');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const status = useAiStatus();
  const fmt = numberFormat(locale, { maximumFractionDigits: 0 });
  return (
    <section
      aria-labelledby="admin-ai-title"
      className="flex flex-col gap-3 rounded-card bg-surface p-6 shadow-card"
    >
      <h2 id="admin-ai-title">{t('title')}</h2>
      {status.isPending && <p className="text-sm text-ink3">{t('loading')}</p>}
      {status.isError && <p className="text-sm text-ink2">{t('unavailable')}</p>}
      {status.data && (
        <>
          <div className="flex items-center gap-2">
            <Pill level={status.data.aiEnabled ? 'done' : 'quiet'}>
              {status.data.aiEnabled ? t('on') : t('off')}
            </Pill>
          </div>
          <p className="text-sm text-ink2">
            {t.rich('models', {
              code: (chunks) => (
                <code className="rounded-segment bg-well px-1 font-mono">{chunks}</code>
              ),
            })}
          </p>
          <dl className="text-sm">
            <dt className="text-xs text-ink3">{t('budget')}</dt>
            <dd className="font-semibold tabular-nums text-ink">
              {t('budgetValue', {
                used: fmt.format(status.data.dailyBudget.usedTokens),
                limit: fmt.format(status.data.dailyBudget.limitTokens),
              })}
            </dd>
          </dl>
        </>
      )}
    </section>
  );
}
