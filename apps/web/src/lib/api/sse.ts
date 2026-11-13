import { api } from './client';
import type { components } from './schema';

/** Event names of FEAT-006 section 6.3. The payloads are not part of the OpenAPI document. */
export const RUN_EVENT_TYPES = [
  'run_started',
  'step_started',
  'step_finished',
  'message_delta',
  'approval_required',
  'approval_resolved',
  'final_answer',
  'run_finished',
  'heartbeat',
] as const;

export type RunEventType = (typeof RUN_EVENT_TYPES)[number];

export type RunEvent = {
  /** The stream's own increasing id (not the step `seq`). */
  id: number;
  type: RunEventType;
  data: Record<string, unknown>;
};

export type RunStatus = components['schemas']['Run']['status'];
export type RunConnectionState = 'open' | 'reconnecting' | 'polling' | 'closed';

export type RunEventHandlers = {
  onEvent: (event: RunEvent) => void;
  onState?: (state: RunConnectionState) => void;
  /** Called with every polled run while the stream is unavailable. */
  onPoll?: (run: components['schemas']['Run']) => void;
};

type EventSourceLike = {
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void;
  close(): void;
  onerror: ((event: Event) => void) | null;
  onopen: ((event: Event) => void) | null;
  readyState: number;
};

export type SubscribeOptions = {
  baseUrl?: string;
  createEventSource?: (url: string) => EventSourceLike;
  pollIntervalMs?: number;
  maxFailures?: number;
};

const FINISHED: RunStatus[] = ['succeeded', 'failed', 'cancelled'];
const CLOSED = 2;

/**
 * Streams a run's events. The browser's EventSource reconnects by itself and sends the last
 * event id as `Last-Event-ID`; this helper drops events it has already delivered, counts
 * consecutive failures, and after `maxFailures` closes the stream and polls the run instead.
 */
export function subscribeToRun(
  runId: string,
  handlers: RunEventHandlers,
  options: SubscribeOptions = {},
): () => void {
  const baseUrl =
    options.baseUrl ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';
  const maxFailures = options.maxFailures ?? 3;
  const pollIntervalMs = options.pollIntervalMs ?? 2000;
  const url = `${baseUrl}/api/v1/agent/runs/${encodeURIComponent(runId)}/events`;
  const create =
    options.createEventSource ??
    ((target: string) => new EventSource(target, { withCredentials: true }));

  let lastId = 0;
  let failures = 0;
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let source: EventSourceLike | null = null;

  const setState = (state: RunConnectionState) => handlers.onState?.(state);

  const stop = () => {
    stopped = true;
    source?.close();
    source = null;
    if (timer !== undefined) clearTimeout(timer);
    setState('closed');
  };

  const poll = async () => {
    if (stopped) return;
    const { data } = await api.GET('/api/v1/agent/runs/{run_id}', {
      params: { path: { run_id: runId } },
    });
    if (stopped) return;
    if (data) {
      handlers.onPoll?.(data);
      if (FINISHED.includes(data.status)) {
        stop();
        return;
      }
    }
    timer = setTimeout(() => void poll(), pollIntervalMs);
  };

  const startPolling = () => {
    source?.close();
    source = null;
    setState('polling');
    void poll();
  };

  const deliver = (type: RunEventType, message: MessageEvent<string>) => {
    const id = Number(message.lastEventId);
    if (Number.isFinite(id) && id > 0) {
      if (id <= lastId) return; // replayed after a reconnect: shown once
      lastId = id;
    }
    failures = 0;
    let data: Record<string, unknown> = {};
    try {
      const parsed: unknown = JSON.parse(message.data);
      if (typeof parsed === 'object' && parsed !== null) data = parsed as Record<string, unknown>;
    } catch {
      // A malformed payload is delivered as an empty object rather than breaking the stream.
    }
    handlers.onEvent({ id: lastId, type, data });
    if (type === 'run_finished') stop();
  };

  const connect = () => {
    const next = create(url);
    source = next;
    for (const type of RUN_EVENT_TYPES) {
      next.addEventListener(type, (message) => deliver(type, message));
    }
    next.onopen = () => setState('open');
    next.onerror = () => {
      if (stopped || source !== next) return;
      failures += 1;
      if (failures >= maxFailures) {
        startPolling();
        return;
      }
      setState('reconnecting');
      if (next.readyState === CLOSED) {
        // A closed source never reconnects by itself. A new one has no Last-Event-ID, so the
        // server replays from the start and `deliver` drops what was already shown.
        next.close();
        connect();
      }
    };
  };

  setState('open');
  connect();
  return stop;
}
