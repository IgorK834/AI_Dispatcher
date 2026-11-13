'use client';

import { useTranslations } from 'next-intl';
import { LinkButton } from './link-button';

/** Replaces the chat input when AI is off (FR-20): says why and leads to the manual optimizer. */
export function AiOffPanel() {
  const t = useTranslations('chat.aiOff');
  return (
    <section
      aria-labelledby="ai-off-title"
      className="flex max-w-3xl flex-col gap-4 rounded-card bg-surface p-6 shadow-card"
    >
      <h2 id="ai-off-title">{t('title')}</h2>
      <p className="text-ink2">{t('body')}</p>
      <div className="flex flex-wrap gap-3">
        <LinkButton href="/optimizer" primary>
          {t('openOptimizer')}
        </LinkButton>
        <LinkButton href="/fleet">{t('goFleet')}</LinkButton>
      </div>
      <details className="text-sm text-ink2">
        <summary className="cursor-pointer font-semibold text-ink">{t('howTo.title')}</summary>
        <p className="mt-2">
          {t.rich('howTo.body', {
            code: (chunks) => (
              <code className="rounded-segment bg-well px-1 font-mono">{chunks}</code>
            ),
          })}
        </p>
      </details>
    </section>
  );
}
