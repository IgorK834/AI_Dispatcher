'use client';

import { useTranslations } from 'next-intl';
import { Pill } from '@/components/ui/pill';
import { ApprovalCard } from './approval-card';
import { ProposalCard } from './proposal-card';
import type { Turn } from './hooks';

type MessageListProps = {
  turns: Turn[];
  selectedPlanId: string | null;
  onSelectPlan: (planId: string) => void;
  onDecide: (turn: Turn, decision: 'approve' | 'reject', comment: string) => void;
};

const KNOWN_ERRORS = [
  'BUDGET_EXCEEDED',
  'AI_PROVIDER_ERROR',
  'TOOL_ERROR',
  'APPROVAL_EXPIRED',
  'INTERNAL_ERROR',
];

/** The conversation: each question, the greyed draft, then the verified answer with its cards. */
export function MessageList({ turns, selectedPlanId, onSelectPlan, onDecide }: MessageListProps) {
  const t = useTranslations('chat');
  const legal = useTranslations('legal');
  return (
    <ol className="flex flex-col gap-6" aria-label={t('conversation')}>
      {turns.map((turn) => {
        const { run } = turn;
        const answer = run.answer;
        return (
          <li key={turn.runId} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-xs font-semibold text-ink3">{t('roles.user')}</span>
              <p className="max-w-full self-start break-words rounded-card bg-well p-3 text-ink">
                {turn.question}
              </p>
            </div>
            <div className="flex flex-col gap-3">
              <span className="text-xs font-semibold text-ink3">{t('roles.assistant')}</span>
              {answer === null && run.draft !== '' && (
                <p className="break-words rounded-card border border-dashed border-line-strong p-3 text-ink3">
                  <span className="mr-2 text-xs font-semibold">{t('draft')}</span>
                  {run.draft}
                </p>
              )}
              {answer && (
                <div className="flex flex-col gap-3 rounded-card bg-surface p-4 shadow-card">
                  <div className="flex flex-wrap items-center gap-2">
                    {answer.grounded && <Pill level="done">{t('answer.verified')}</Pill>}
                    {answer.source === 'template' && (
                      <Pill level="quiet">{t('answer.template')}</Pill>
                    )}
                    {!answer.grounded && answer.source !== 'template' && (
                      <Pill level="attention">{t('answer.unverified')}</Pill>
                    )}
                  </div>
                  <p className="break-words text-ink">{answer.summary}</p>
                  <div className="flex flex-col gap-3">
                    {answer.proposals.map((proposal) => (
                      <ProposalCard
                        key={proposal.planRef}
                        proposal={proposal}
                        selected={selectedPlanId === proposal.routePlanId}
                        onSelect={() => onSelectPlan(proposal.routePlanId)}
                      />
                    ))}
                  </div>
                  {answer.proposals.length > 0 && (
                    <p className="text-xs text-ink3">{legal('notice')}</p>
                  )}
                </div>
              )}
              {run.approval && (
                <ApprovalCard
                  approval={run.approval}
                  onDecide={(decision, comment) => onDecide(turn, decision, comment)}
                />
              )}
              {run.error && (
                <p role="alert" className="rounded-inner bg-red-tint p-3 text-sm text-red-hover">
                  {KNOWN_ERRORS.includes(run.error.code)
                    ? t(`runErrors.${run.error.code}`)
                    : t('runErrors.UNKNOWN', { code: run.error.code })}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
