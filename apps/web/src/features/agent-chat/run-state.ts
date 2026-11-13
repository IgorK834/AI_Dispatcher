import type { RunEvent } from '@/lib/api/sse';
import type { components } from '@/lib/api/schema';

export type Run = components['schemas']['Run'];
export type FinalAnswer = components['schemas']['FinalAnswer'];
export type Proposal = components['schemas']['Proposal'];
export type ApprovalPlan = components['schemas']['ApprovalPlan'];
export type ApprovalTotals = components['schemas']['ApprovalTotals'];
export type RunStatus = Run['status'];

export type StepStatus = 'running' | 'ok' | 'error' | 'rejected';

/** One agent or tool step of a run, as the trace panel shows it (FR-22). */
export type Step = {
  seq: number;
  agent: string;
  type: string;
  toolName?: string;
  summary: string;
  status: StepStatus;
  durationMs?: number;
  tokens?: { in: number; out: number };
};

export type Approval = {
  approvalId: string;
  plans: ApprovalPlan[];
  totals: ApprovalTotals;
  expiresAt: string;
  /** The decision this tab sent; the buttons stay disabled after the first click. */
  submitted?: 'approve' | 'reject';
  /** The decision that `approval_resolved` reported (possibly from another tab). */
  resolved?: string;
};

export type RunState = {
  runId: string;
  status: RunStatus | 'queued';
  steps: Step[];
  /** Provisional text of the answer; replaced by `final_answer`. */
  draft: string;
  answer: FinalAnswer | null;
  approval: Approval | null;
  tokensIn: number;
  tokensOut: number;
  error: { code: string; message?: string } | null;
  finished: boolean;
};

export type RunAction =
  | { type: 'event'; event: RunEvent }
  | { type: 'poll'; run: Run }
  | { type: 'submitted'; decision: 'approve' | 'reject' }
  | { type: 'submit-failed' };

const FINISHED: RunStatus[] = ['succeeded', 'failed', 'cancelled'];

export const isFinished = (status: string): boolean => FINISHED.includes(status as RunStatus);

export function newRun(runId: string): RunState {
  return {
    runId,
    status: 'queued',
    steps: [],
    draft: '',
    answer: null,
    approval: null,
    tokensIn: 0,
    tokensOut: 0,
    error: null,
    finished: false,
  };
}

const text = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;
const count = (value: unknown): number => (typeof value === 'number' ? value : 0);

function stepStatus(value: unknown): StepStatus {
  return value === 'error' || value === 'rejected' ? value : 'ok';
}

function withStep(steps: Step[], next: Step): Step[] {
  const index = steps.findIndex((step) => step.seq === next.seq);
  if (index === -1) return [...steps, next].sort((a, b) => a.seq - b.seq);
  return steps.map((step, position) => (position === index ? { ...step, ...next } : step));
}

function approvalFrom(data: Record<string, unknown>): Approval | null {
  const payload = data.payload as { plans?: unknown; totals?: unknown } | undefined;
  if (typeof data.approvalId !== 'string' || !payload || !Array.isArray(payload.plans)) return null;
  return {
    approvalId: data.approvalId,
    plans: payload.plans as ApprovalPlan[],
    totals: payload.totals as ApprovalTotals,
    expiresAt: text(data.expiresAt),
  };
}

function isFinalAnswer(value: unknown): value is FinalAnswer {
  const candidate = value as Partial<FinalAnswer> | null;
  return (
    typeof candidate === 'object' &&
    candidate !== null &&
    typeof candidate.summary === 'string' &&
    Array.isArray(candidate.proposals)
  );
}

function applyEvent(state: RunState, event: RunEvent): RunState {
  const { data } = event;
  switch (event.type) {
    case 'run_started':
      return { ...state, status: 'running' };
    case 'step_started':
      return {
        ...state,
        steps: withStep(state.steps, {
          seq: count(data.seq),
          agent: text(data.agent),
          type: text(data.type),
          toolName: typeof data.toolName === 'string' ? data.toolName : undefined,
          summary: text(data.inputSummary),
          status: 'running',
        }),
      };
    case 'step_finished': {
      const tokens = data.tokens as { in?: unknown; out?: unknown } | undefined;
      return {
        ...state,
        steps: withStep(state.steps, {
          seq: count(data.seq),
          agent: text(data.agent),
          type: text(data.type),
          toolName: typeof data.toolName === 'string' ? data.toolName : undefined,
          summary: text(data.outputSummary),
          status: stepStatus(data.status),
          durationMs: count(data.durationMs),
          tokens: tokens ? { in: count(tokens.in), out: count(tokens.out) } : undefined,
        }),
      };
    }
    case 'message_delta':
      return { ...state, draft: state.draft + text(data.text) };
    case 'approval_required': {
      const approval = approvalFrom(data);
      return approval ? { ...state, status: 'waiting_approval', approval } : state;
    }
    case 'approval_resolved':
      if (!state.approval) return state;
      return {
        ...state,
        status: 'running',
        approval: { ...state.approval, resolved: text(data.decision, 'resolved') },
      };
    case 'final_answer':
      return isFinalAnswer(data) ? { ...state, draft: '', answer: data } : state;
    case 'run_finished': {
      const error = data.error as { code?: unknown; message?: unknown } | undefined;
      const status = isFinished(text(data.status)) ? (data.status as RunStatus) : 'succeeded';
      return {
        ...state,
        status,
        finished: true,
        tokensIn: count(data.tokensIn),
        tokensOut: count(data.tokensOut),
        error: error?.code ? { code: text(error.code), message: text(error.message) } : null,
      };
    }
    default:
      return state; // heartbeat
  }
}

/** A polled run has no steps, but carries the status, the answer and a pending approval. */
function applyRun(state: RunState, run: Run): RunState {
  const pending = run.pendingApproval;
  const approval: Approval | null =
    state.approval ??
    (pending
      ? {
          approvalId: pending.approvalId,
          plans: pending.payload.plans,
          totals: pending.payload.totals,
          expiresAt: pending.expiresAt,
        }
      : null);
  return {
    ...state,
    status: run.status,
    finished: isFinished(run.status),
    tokensIn: run.tokensIn,
    tokensOut: run.tokensOut,
    answer: run.finalAnswer ?? state.answer,
    draft: run.finalAnswer ? '' : state.draft,
    approval,
    error: run.error ? { code: run.error.code, message: run.error.message } : state.error,
  };
}

export function reduceRun(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case 'event':
      return applyEvent(state, action.event);
    case 'poll':
      return applyRun(state, action.run);
    case 'submitted':
      return state.approval
        ? { ...state, approval: { ...state.approval, submitted: action.decision } }
        : state;
    case 'submit-failed':
      return state.approval
        ? { ...state, approval: { ...state.approval, submitted: undefined } }
        : state;
  }
}
