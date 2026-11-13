import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { apiUrl } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { subscribeToRun, type RunConnectionState, type RunEvent } from './sse';

type Listener = (event: MessageEvent<string>) => void;

/**
 * A scripted EventSource. Like a browser it reconnects by itself after a drop and then sends the
 * id of the last event it delivered as `Last-Event-ID`; the test controls what the server replays.
 */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  readyState = 0;
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  lastDelivered = 0;
  /** Last-Event-ID header of each (re)connection, in order; undefined for the first one. */
  readonly connections: (string | undefined)[] = [undefined];
  private listeners = new Map<string, Listener[]>();
  closed = false;

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: Listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {
    this.closed = true;
    this.readyState = 2;
  }

  emit(id: number, type: string, data: object = {}) {
    this.lastDelivered = id;
    const event = new MessageEvent<string>(type, {
      data: JSON.stringify(data),
      lastEventId: String(id),
    });
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }

  /** The connection drops: the browser retries and sends Last-Event-ID. */
  drop() {
    this.connections.push(String(this.lastDelivered));
    this.onerror?.(new Event('error'));
  }
}

const factory = (url: string) => new FakeEventSource(url);

function setup(handlers: Parameters<typeof subscribeToRun>[1] extends infer H ? H : never) {
  FakeEventSource.instances = [];
  return subscribeToRun('run-1', handlers, {
    baseUrl: 'http://localhost:8000',
    createEventSource: factory,
    pollIntervalMs: 5,
  });
}

describe('[AC-FEAT-005-21] run event stream', () => {
  it('reconnects with Last-Event-ID 4 and shows no step twice', () => {
    const seen: RunEvent[] = [];
    const states: RunConnectionState[] = [];
    const stop = setup({ onEvent: (e) => seen.push(e), onState: (s) => states.push(s) });
    const source = FakeEventSource.instances[0]!;
    expect(source.url).toBe('http://localhost:8000/api/v1/agent/runs/run-1/events');

    source.emit(1, 'run_started');
    source.emit(2, 'step_started', { seq: 1 });
    source.emit(3, 'step_finished', { seq: 1 });
    source.emit(4, 'step_started', { seq: 2 });
    source.drop();
    expect(source.connections.at(-1)).toBe('4'); // what a browser would send
    expect(states.at(-1)).toBe('reconnecting');
    expect(source.closed).toBe(false); // the same source reconnects by itself

    // The server replays from id 5; a duplicate of 4 and 3 arrives as well (proxy replay).
    source.emit(3, 'step_finished', { seq: 1 });
    source.emit(4, 'step_started', { seq: 2 });
    source.emit(5, 'step_finished', { seq: 2 });
    source.emit(6, 'final_answer', { text: 'done' });
    expect(seen.map((event) => event.id)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(seen.filter((event) => event.type === 'step_started')).toHaveLength(2);
    stop();
  });

  it('closes the stream after run_finished', () => {
    const states: RunConnectionState[] = [];
    setup({ onEvent: () => undefined, onState: (s) => states.push(s) });
    const source = FakeEventSource.instances[0]!;
    source.emit(1, 'run_started');
    source.emit(2, 'run_finished', { status: 'succeeded' });
    expect(source.closed).toBe(true);
    expect(states.at(-1)).toBe('closed');
  });

  it('polls the run every interval after three failed reconnects until it finishes', async () => {
    let polls = 0;
    server.use(
      http.get(apiUrl('/api/v1/agent/runs/run-1'), () => {
        polls += 1;
        return HttpResponse.json({
          id: 'run-1',
          threadId: 't-1',
          status: polls < 3 ? 'running' : 'succeeded',
          startedAt: '2026-11-16T05:00:00Z',
          tokensIn: 0,
          tokensOut: 0,
          modelPolicy: {},
        });
      }),
    );
    const states: RunConnectionState[] = [];
    const polled: string[] = [];
    setup({
      onEvent: () => undefined,
      onState: (s) => states.push(s),
      onPoll: (run) => polled.push(run.status),
    });
    const source = FakeEventSource.instances[0]!;
    source.emit(1, 'run_started');
    source.drop();
    source.drop();
    expect(states.at(-1)).toBe('reconnecting');
    source.drop(); // the third failure in a row
    expect(states).toContain('polling');
    expect(source.closed).toBe(true);
    await vi.waitFor(() => expect(states.at(-1)).toBe('closed'));
    expect(polled).toEqual(['running', 'running', 'succeeded']);
  });

  it('counts only consecutive failures: a delivered event resets the counter', () => {
    const states: RunConnectionState[] = [];
    setup({ onEvent: () => undefined, onState: (s) => states.push(s) });
    const source = FakeEventSource.instances[0]!;
    source.drop();
    source.drop();
    source.emit(1, 'run_started');
    source.drop();
    source.drop();
    expect(states).not.toContain('polling');
  });

  it('opens a new source when the browser gave up (closed) and drops replayed events', () => {
    const seen: number[] = [];
    setup({ onEvent: (e) => seen.push(e.id) });
    const first = FakeEventSource.instances[0]!;
    first.emit(1, 'run_started');
    first.readyState = 2;
    first.onerror?.(new Event('error'));
    expect(FakeEventSource.instances).toHaveLength(2);
    const second = FakeEventSource.instances[1]!;
    second.emit(1, 'run_started'); // replay from the start
    second.emit(2, 'step_started', { seq: 1 });
    expect(seen).toEqual([1, 2]);
  });

  it('stops delivering after unsubscribe', () => {
    const seen: number[] = [];
    const stop = setup({ onEvent: (e) => seen.push(e.id) });
    const source = FakeEventSource.instances[0]!;
    source.emit(1, 'run_started');
    stop();
    expect(source.closed).toBe(true);
    source.drop();
    expect(seen).toEqual([1]);
  });
});
