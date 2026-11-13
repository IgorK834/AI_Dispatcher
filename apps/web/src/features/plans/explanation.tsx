'use client';

import { useTranslations } from 'next-intl';
import { Banner } from '@/components/ui/banner';
import { Pill } from '@/components/ui/pill';
import type { components } from '@/lib/api/schema';

type Explanation = components['schemas']['RouteExplanation'];

export function ExplanationPanel({ explanation }: { explanation: Explanation }) {
  const t = useTranslations('plans.explanation');
  const { output } = explanation;
  return (
    <section
      className="flex flex-col gap-3 rounded-card bg-surface p-6 shadow-card"
      aria-label={t('title')}
    >
      <div className="flex items-center justify-between gap-3">
        <h2>{t('title')}</h2>
        <Pill level={explanation.source === 'llm' ? 'brand' : 'quiet'}>
          {t(explanation.source === 'llm' ? 'ai' : 'template')}
        </Pill>
      </div>
      <p className="font-semibold text-ink">{output.headline}</p>
      {output.reasons.length > 0 && (
        <div>
          <h3>{t('reasons')}</h3>
          <ul className="ml-5 list-disc text-sm text-ink2">
            {output.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        </div>
      )}
      {output.tradeoffs.length > 0 && (
        <div>
          <h3>{t('tradeoffs')}</h3>
          <ul className="ml-5 list-disc text-sm text-ink2">
            {output.tradeoffs.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {!explanation.groundingOk && <Banner level="attention">{t('ungrounded')}</Banner>}
      <p className="text-xs text-ink3">{explanation.disclaimer}</p>
    </section>
  );
}
