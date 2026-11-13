'use client';

import { useQuery } from '@tanstack/react-query';
import { useLocale } from 'next-intl';
import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { api } from '@/lib/api/client';
import { subscribeToRun, type RunConnectionState } from '@/lib/api/sse';
import { ApiError, unwrap } from '@/lib/api/unwrap';
import { useProblem } from '@/lib/use-problem';
import { newRun, reduceRun, type RunAction, type RunState } from './run-state';

export function useAgentStatus() {
  return useQuery({
    queryKey: ['agent-status'],
    staleTime: 30_000,
    retry: false,
    queryFn: async () => unwrap(await api.GET('/api/v1/agent/status')),
  });
}

/** `503 AI_UNAVAILABLE` means the same as `aiEnabled = false` (FR-20). */
export function isAiUnavailable(error: unknown): boolean {
  if (!(error instanceof ApiError) || error.status !== 503) return false;
  const body = error.body as { code?: unknown } | null;
  return body?.code === 'AI_UNAVAILABLE';
}

/** One question and the run that answers it. */
export type Turn = { runId: string; question: string; run: RunState };

type ChatAction =
  | { type: 'add'; runId: string; question: string }
  | { type: 'run'; runId: string; action: RunAction }
  | { type: 'clear' };

function reduceChat(turns: Turn[], action: ChatAction): Turn[] {
  switch (action.type) {
    case 'add':
      return [
        ...turns,
        { runId: action.runId, question: action.question, run: newRun(action.runId) },
      ];
    case 'run':
      return turns.map((turn) =>
        turn.runId === action.runId ? { ...turn, run: reduceRun(turn.run, action.action) } : turn,
      );
    case 'clear':
      return [];
  }
}

export type ChatNotice = { kind: 'error'; text: string } | null;

/**
 * Owns one conversation: creates the thread on the first message, posts messages with an
 * `Idempotency-Key`, follows the active run through the event stream (FR-21, FR-25) and
 * sends the approval decision (FR-24).
 */
export function useChat() {
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const toProblem = useProblem();
  const [turns, dispatch] = useReducer(reduceChat, []);
  const [connection, setConnection] = useState<RunConnectionState>('closed');
  const [sending, setSending] = useState(false);
  const [aiOff, setAiOff] = useState(false);
  const [notice, setNotice] = useState<ChatNotice>(null);
  const threadId = useRef<string | null>(null);

  const active = turns.at(-1);
  const activeRunId = active && !active.run.finished ? active.runId : null;

  useEffect(() => {
    if (activeRunId === null) return;
    return subscribeToRun(activeRunId, {
      onEvent: (event) =>
        dispatch({ type: 'run', runId: activeRunId, action: { type: 'event', event } }),
      onPoll: (run) => dispatch({ type: 'run', runId: activeRunId, action: { type: 'poll', run } }),
      onState: setConnection,
    });
  }, [activeRunId]);

  const fail = useCallback(
    (error: unknown) => {
      if (isAiUnavailable(error)) {
        setAiOff(true);
        return;
      }
      setNotice({ kind: 'error', text: toProblem(error).message });
    },
    [toProblem],
  );

  const send = useCallback(
    async (content: string) => {
      setSending(true);
      setNotice(null);
      try {
        if (threadId.current === null) {
          const created = unwrap(await api.POST('/api/v1/agent/threads', { body: {} }));
          threadId.current = created.id;
        }
        const accepted = unwrap(
          await api.POST('/api/v1/agent/threads/{thread_id}/messages', {
            params: {
              path: { thread_id: threadId.current },
              header: { 'idempotency-key': crypto.randomUUID() },
            },
            body: { content, locale },
          }),
        );
        dispatch({ type: 'add', runId: accepted.runId, question: content });
      } catch (error) {
        fail(error);
      } finally {
        setSending(false);
      }
    },
    [fail, locale],
  );

  const resume = useCallback(
    async (runId: string, approvalId: string, decision: 'approve' | 'reject', comment: string) => {
      dispatch({ type: 'run', runId, action: { type: 'submitted', decision } });
      setNotice(null);
      try {
        unwrap(
          await api.POST('/api/v1/agent/runs/{run_id}/resume', {
            params: { path: { run_id: runId } },
            body: {
              approvalId,
              decision,
              comment: decision === 'reject' && comment.trim() !== '' ? comment.trim() : null,
            },
          }),
        );
      } catch (error) {
        // A 409 means the request is no longer pending: the buttons stay disabled.
        if (!(error instanceof ApiError && error.status === 409)) {
          dispatch({ type: 'run', runId, action: { type: 'submit-failed' } });
        }
        fail(error);
      }
    },
    [fail],
  );

  const reset = useCallback(() => {
    threadId.current = null;
    setNotice(null);
    dispatch({ type: 'clear' });
  }, []);

  return {
    turns,
    active,
    connection,
    sending,
    busy: sending || activeRunId !== null,
    aiOff,
    notice,
    send,
    resume,
    reset,
  };
}
