import { describe, expect, it } from 'vitest';
import { APPROVAL_ID, RUN_ID, approvalEvent, finalAnswer } from '@/test/fixtures/agent';
import type { RunEvent } from '@/lib/api/sse';
import { newRun, reduceRun, type Run } from './run-state';

const event = (type: RunEvent['type'], data: Record<string, unknown>): RunAction => ({
  type: 'event',
  event: { id: 1, type, data },
});
type RunAction = Parameters<typeof reduceRun>[1];

describe('run state', () => {
  it('keeps one row per step: the finish replaces the start', () => {
    let state = newRun(RUN_ID);
    state = reduceRun(
      state,
      event('step_started', {
        seq: 1,
        agent: 'a',
        type: 'tool',
        toolName: 't',
        inputSummary: 'in',
      }),
    );
    expect(state.steps).toMatchObject([{ seq: 1, status: 'running', summary: 'in' }]);
    state = reduceRun(
      state,
      event('step_finished', {
        seq: 1,
        agent: 'a',
        type: 'tool',
        toolName: 't',
        status: 'rejected',
        outputSummary: 'out',
        durationMs: 40,
        tokens: { in: 3, out: 4 },
      }),
    );
    expect(state.steps).toEqual([
      {
        seq: 1,
        agent: 'a',
        type: 'tool',
        toolName: 't',
        summary: 'out',
        status: 'rejected',
        durationMs: 40,
        tokens: { in: 3, out: 4 },
      },
    ]);
  });

  it('accumulates the draft and clears it when the final answer arrives', () => {
    let state = reduceRun(newRun(RUN_ID), event('message_delta', { text: 'Hel' }));
    state = reduceRun(state, event('message_delta', { text: 'lo' }));
    expect(state.draft).toBe('Hello');
    state = reduceRun(state, event('final_answer', finalAnswer));
    expect(state).toMatchObject({ draft: '', answer: finalAnswer });
  });

  it('ignores a payload that is not an answer or an approval', () => {
    const state = newRun(RUN_ID);
    expect(reduceRun(state, event('final_answer', { nonsense: true }))).toBe(state);
    expect(reduceRun(state, event('approval_required', {}))).toBe(state);
    expect(reduceRun(state, event('heartbeat', {}))).toBe(state);
  });

  it('tracks an approval from request to resolution', () => {
    let state = reduceRun(newRun(RUN_ID), event('approval_required', approvalEvent()));
    expect(state.status).toBe('waiting_approval');
    expect(state.approval?.approvalId).toBe(APPROVAL_ID);
    state = reduceRun(state, { type: 'submitted', decision: 'approve' });
    expect(state.approval?.submitted).toBe('approve');
    state = reduceRun(state, { type: 'submit-failed' });
    expect(state.approval?.submitted).toBeUndefined();
    state = reduceRun(
      state,
      event('approval_resolved', { approvalId: APPROVAL_ID, decision: 'reject' }),
    );
    expect(state.approval?.resolved).toBe('reject');
  });

  it('ends the run with its status, tokens and error', () => {
    const state = reduceRun(
      newRun(RUN_ID),
      event('run_finished', {
        status: 'failed',
        tokensIn: 5,
        tokensOut: 6,
        error: { code: 'TOOL_ERROR', message: 'boom' },
      }),
    );
    expect(state).toMatchObject({
      finished: true,
      status: 'failed',
      tokensIn: 5,
      tokensOut: 6,
      error: { code: 'TOOL_ERROR' },
    });
  });

  it('takes the answer and a pending approval from a polled run', () => {
    const run: Run = {
      id: RUN_ID,
      threadId: 't',
      status: 'waiting_approval',
      modelPolicy: {},
      tokensIn: 1,
      tokensOut: 2,
      pendingApproval: {
        approvalId: APPROVAL_ID,
        action: 'assign_plan',
        payload: approvalEvent().payload as never,
        expiresAt: '2999-01-01T00:00:00Z',
      },
      finalAnswer: finalAnswer,
    };
    const state = reduceRun(newRun(RUN_ID), { type: 'poll', run });
    expect(state).toMatchObject({
      status: 'waiting_approval',
      finished: false,
      answer: finalAnswer,
    });
    expect(state.approval?.approvalId).toBe(APPROVAL_ID);
    const done = reduceRun(state, { type: 'poll', run: { ...run, status: 'succeeded' } });
    expect(done.finished).toBe(true);
  });
});
