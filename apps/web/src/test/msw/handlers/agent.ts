import { http, HttpResponse } from 'msw';
import type { components } from '@/lib/api/schema';
import { aiOn, RUN_ID, thread, type AgentStatus } from '../../fixtures/agent';
import { apiUrl, problem } from '../handlers';
import { server } from '../server';

type ResumeInput = components['schemas']['ResumeInput'];
type MessageCreate = components['schemas']['MessageCreate'];

export type AgentApi = {
  /** Every message the screen posted, with the Idempotency-Key it sent. */
  messages: { threadId: string; body: MessageCreate; idempotencyKey: string | null }[];
  resumes: { runId: string; body: ResumeInput }[];
  threadsCreated: number;
};

type Options = {
  status?: AgentStatus | 'unavailable';
  /** When set, posting a message fails with this problem. */
  messageProblem?: { status: number; code: string };
  /** When set, resuming fails with this problem. */
  resumeProblem?: { status: number; code: string };
};

/** The agent endpoints of FEAT-006 section 6.1 that the AI Dispatcher screen calls. */
export function agentApi(options: Options = {}): AgentApi {
  const api: AgentApi = { messages: [], resumes: [], threadsCreated: 0 };
  server.use(
    http.get(apiUrl('/api/v1/agent/status'), () =>
      options.status === 'unavailable'
        ? problem(503, 'AI_UNAVAILABLE')
        : HttpResponse.json(options.status ?? aiOn),
    ),
    http.post(apiUrl('/api/v1/agent/threads'), () => {
      api.threadsCreated += 1;
      return HttpResponse.json(thread, { status: 201 });
    }),
    http.post(apiUrl('/api/v1/agent/threads/:id/messages'), async ({ request, params }) => {
      const body = (await request.json()) as MessageCreate;
      api.messages.push({
        threadId: String(params.id),
        body,
        idempotencyKey: request.headers.get('Idempotency-Key'),
      });
      if (options.messageProblem) {
        return problem(options.messageProblem.status, options.messageProblem.code);
      }
      return HttpResponse.json({ runId: RUN_ID }, { status: 202 });
    }),
    http.post(apiUrl('/api/v1/agent/runs/:id/resume'), async ({ request, params }) => {
      const body = (await request.json()) as ResumeInput;
      api.resumes.push({ runId: String(params.id), body });
      if (options.resumeProblem) {
        return problem(options.resumeProblem.status, options.resumeProblem.code);
      }
      return HttpResponse.json(
        {
          id: params.id,
          threadId: thread.id,
          status: 'running',
          modelPolicy: {},
          tokensIn: 0,
          tokensOut: 0,
        },
        { status: 202 },
      );
    }),
  );
  return api;
}
