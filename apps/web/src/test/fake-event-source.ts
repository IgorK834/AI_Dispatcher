import type { RunEventType } from '@/lib/api/sse';

type Listener = (event: MessageEvent<string>) => void;

/** A stand-in for the browser's EventSource: a test pushes events and failures by hand. */
export class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static readonly CLOSED = 2;

  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  readyState = 1;
  closed = false;
  private listeners = new Map<string, Listener[]>();

  constructor(readonly url: string) {
    FakeEventSource.instances.push(this);
  }

  static get latest(): FakeEventSource {
    const found = FakeEventSource.instances.at(-1);
    if (!found) throw new Error('no EventSource was opened');
    return found;
  }

  static reset() {
    FakeEventSource.instances = [];
  }

  addEventListener(type: string, listener: Listener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  close() {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }

  emit(type: RunEventType, data: unknown, id: number) {
    const message = { data: JSON.stringify(data), lastEventId: String(id) } as MessageEvent<string>;
    for (const listener of this.listeners.get(type) ?? []) listener(message);
  }

  fail() {
    this.onerror?.(new Event('error'));
  }
}
