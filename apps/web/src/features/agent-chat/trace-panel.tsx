'use client';

import { useLocale, useTranslations } from 'next-intl';
import { Pill, type PillLevel } from '@/components/ui/pill';
import { formatStepDuration, formatTokens } from './format';
import type { Step, StepStatus } from './run-state';

const LEVEL: Record<StepStatus, PillLevel> = {
  running: 'info',
  ok: 'quiet',
  error: 'error',
  rejected: 'attention',
};

const KNOWN_TYPES = ['llm', 'tool', 'guard', 'interrupt'];

type TracePanelProps = {
  steps: Step[];
  tokens: number;
};

/**
 * The steps of the active run as they arrive (FR-22). Only the one-line summaries the API
 * sends are shown; free text from offers never reaches this panel.
 */
export function TracePanel({ steps, tokens }: TracePanelProps) {
  const t = useTranslations('chat.trace');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  return (
    <section aria-labelledby="trace-title" className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h2 id="trace-title">{t('title')}</h2>
        {steps.length > 0 && (
          <p className="text-sm text-ink2">
            {t('summary', { steps: steps.length, tokens: formatTokens(tokens, locale) })}
          </p>
        )}
      </div>
      {steps.length === 0 ? (
        <p className="text-sm text-ink3">{t('empty')}</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {steps.map((step) => (
            <li
              key={step.seq}
              className="flex flex-col gap-1 rounded-inner border border-line bg-surface p-3 text-sm"
              data-status={step.status}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-ink">{step.agent}</span>
                <Pill level={LEVEL[step.status]}>{t(`status.${step.status}`)}</Pill>
              </div>
              <span className="text-ink2">
                {KNOWN_TYPES.includes(step.type) ? t(`type.${step.type}`) : step.type}
                {step.toolName && (
                  <>
                    {' · '}
                    <span className="font-mono">{step.toolName}</span>
                  </>
                )}
              </span>
              {step.summary !== '' && step.status !== 'running' && (
                <span className="break-words text-ink">{step.summary}</span>
              )}
              {step.durationMs !== undefined && (
                <span className="text-xs text-ink3">
                  {formatStepDuration(step.durationMs, locale)}
                  {step.tokens &&
                    ` · ${t('tokens', {
                      input: formatTokens(step.tokens.in, locale),
                      output: formatTokens(step.tokens.out, locale),
                    })}`}
                </span>
              )}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
