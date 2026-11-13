import { act, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, beforeEach, expect, vi } from 'vitest';
import { driver } from '@/test/fixtures/fleet';
import { goldPlan } from '@/test/fixtures/gold-001';
import { FakeEventSource } from '@/test/fake-event-source';
import { apiUrl } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import type { RunEventType } from '@/lib/api/sse';
import { startedEvent } from '@/test/fixtures/agent';

/** The plan and driver lookups a proposal card makes (GOLD-001, driver D1 with van BUS-01). */
export function mockPlanLookups() {
  const van = { ...driver(1).vehicle!, label: 'BUS-01', palletPlaces: 10, payloadKg: 1085 };
  server.use(
    http.get(apiUrl('/api/v1/route-plans/:id'), () => HttpResponse.json(goldPlan)),
    http.get(apiUrl('/api/v1/drivers/:id'), () =>
      HttpResponse.json({ ...driver(1), vehicle: van }),
    ),
  );
}

/** Replaces the browser's EventSource with the fake one and clears the map style (no tiles). */
export function installFakeEventSource() {
  beforeEach(() => {
    FakeEventSource.reset();
    vi.stubGlobal('EventSource', FakeEventSource);
    vi.stubEnv('NEXT_PUBLIC_MAP_STYLE_URL', '');
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });
}

/** Pushes one event into the open stream, as the server would. */
export function emit(type: RunEventType, data: unknown, id: number) {
  act(() => FakeEventSource.latest.emit(type, data, id));
}

/** Types a question, sends it and waits until the run's stream is open. */
export async function ask(question: string) {
  const user = userEvent.setup();
  const input = await screen.findByRole('textbox', { name: 'Message' });
  await waitFor(() => expect(input).toBeEnabled());
  await user.type(input, question);
  await user.click(screen.getByRole('button', { name: 'Send' }));
  await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0));
  emit('run_started', startedEvent, 1);
  return user;
}
