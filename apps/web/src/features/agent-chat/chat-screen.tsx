'use client';

import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ListError, ListSkeleton } from '@/components/ui/list-status';
import { LiveRegion } from '@/components/ui/live-region';
import { Sheet } from '@/components/ui/sheet';
import { PlanMap, usePlan } from '@/features/plans';
import { useProblem } from '@/lib/use-problem';
import { Banner } from '@/components/ui/banner';
import { AiOffPanel } from './ai-off-panel';
import { Composer } from './composer';
import { isAiUnavailable, useAgentStatus, useChat } from './hooks';
import { MessageList } from './message-list';
import { TracePanel } from './trace-panel';
import { useChatLayout } from './use-layout';

function MapOfPlan({ planId }: { planId: string }) {
  const t = useTranslations('chat.map');
  const plan = usePlan(planId);
  if (!plan.data) return <p className="text-sm text-ink3">{t('loading')}</p>;
  return <PlanMap plan={plan.data} />;
}

function SelectedMap({ planId }: { planId: string | null }) {
  const t = useTranslations('chat.map');
  if (planId === null) return <p className="text-sm text-ink3">{t('empty')}</p>;
  return <MapOfPlan planId={planId} />;
}

export function ChatScreen() {
  const t = useTranslations('chat');
  const toProblem = useProblem();
  const status = useAgentStatus();
  const chat = useChat();
  const layout = useChatLayout();
  const [picked, setPicked] = useState<string | null>(null);
  const [traceOpen, setTraceOpen] = useState(false);

  const active = chat.active;
  const selectedPlanId =
    picked ??
    active?.run.answer?.proposals[0]?.routePlanId ??
    active?.run.approval?.plans[0]?.routePlanId ??
    null;
  const aiOff = chat.aiOff || status.data?.aiEnabled === false || isAiUnavailable(status.error);

  const runStatus = active ? t(`status.${active.run.status}`) : '';
  const connection =
    chat.connection === 'reconnecting' || chat.connection === 'polling'
      ? t(`connection.${chat.connection}`)
      : '';

  const header = (
    <header className="flex flex-col gap-1">
      <h1>{t('title')}</h1>
      <p className="text-ink2">{t('subtitle')}</p>
    </header>
  );

  if (status.isPending) {
    return (
      <div className="flex flex-col gap-4">
        {header}
        <ListSkeleton label={t('loading')} />
      </div>
    );
  }
  if (aiOff) {
    return (
      <div className="flex flex-col gap-4">
        {header}
        <AiOffPanel />
      </div>
    );
  }
  if (status.isError) {
    return (
      <div className="flex flex-col gap-4">
        {header}
        <ListError
          title={t('loadFailed')}
          problem={toProblem(status.error)}
          onRetry={() => void status.refetch()}
        />
      </div>
    );
  }

  const trace = (
    <TracePanel
      steps={active?.run.steps ?? []}
      tokens={(active?.run.tokensIn ?? 0) + (active?.run.tokensOut ?? 0)}
    />
  );
  const map = (
    <section aria-labelledby="chat-map-title" className="flex flex-col gap-3">
      <h2 id="chat-map-title" className="sr-only">
        {t('map.title')}
      </h2>
      <SelectedMap planId={selectedPlanId} />
    </section>
  );

  const conversation = (
    <section aria-label={t('conversation')} className="flex min-w-0 flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <LiveRegion>
          <span className="text-sm font-semibold text-ink2">
            {[runStatus, connection].filter(Boolean).join(' · ')}
          </span>
        </LiveRegion>
        <div className="flex flex-wrap gap-2">
          {layout === 'drawer' && (
            <Button small onClick={() => setTraceOpen(true)}>
              {t('trace.title')}
            </Button>
          )}
          <Button small onClick={chat.reset} disabled={chat.busy}>
            {t('newConversation')}
          </Button>
        </div>
      </div>
      {chat.turns.length === 0 ? (
        <div className="flex flex-col gap-2 rounded-card bg-surface p-6 shadow-card">
          <h2>{t('empty.title')}</h2>
          <p className="text-ink2">{t('empty.body')}</p>
          <p className="break-words rounded-inner bg-well p-3 text-sm text-ink2">
            {t('empty.example')}
          </p>
        </div>
      ) : (
        <MessageList
          turns={chat.turns}
          selectedPlanId={selectedPlanId}
          onSelectPlan={setPicked}
          onDecide={(turn, decision, comment) => {
            const approval = turn.run.approval;
            if (approval) void chat.resume(turn.runId, approval.approvalId, decision, comment);
          }}
        />
      )}
      {chat.notice && <Banner level="error">{chat.notice.text}</Banner>}
      <Composer busy={chat.busy} onSend={(content) => void chat.send(content)} />
    </section>
  );

  return (
    <div className="flex min-w-0 flex-col gap-4" data-layout={layout}>
      {header}
      {layout === 'three-column' && (
        <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_minmax(0,22rem)_minmax(0,24rem)] items-start gap-6">
          {conversation}
          {trace}
          {map}
        </div>
      )}
      {layout === 'drawer' && (
        <>
          <div className="grid min-w-0 grid-cols-1 gap-6">
            {conversation}
            {map}
          </div>
          <Sheet
            open={traceOpen}
            onOpenChange={setTraceOpen}
            title={t('trace.title')}
            closeLabel={t('trace.close')}
          >
            {trace}
          </Sheet>
        </>
      )}
      {layout === 'stacked' && (
        <div className="flex min-w-0 flex-col gap-4">
          <div className="rounded-card bg-surface p-4 shadow-card">{conversation}</div>
          <div className="rounded-card bg-surface p-4 shadow-card">{trace}</div>
          <div className="rounded-card bg-surface p-4 shadow-card">{map}</div>
        </div>
      )}
    </div>
  );
}
