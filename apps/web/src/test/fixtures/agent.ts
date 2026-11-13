import type { components } from '@/lib/api/schema';
import { goldPlans } from './gold-001';

export type AgentStatus = components['schemas']['AgentStatus'];
export type FinalAnswer = components['schemas']['FinalAnswer'];

export const THREAD_ID = '00000000-0000-4000-8000-0000000d0001';
export const RUN_ID = '00000000-0000-4000-8000-0000000d0002';
export const APPROVAL_ID = '00000000-0000-4000-8000-0000000d0003';
const STAMP = '2026-11-16T05:00:00Z';

export const aiOn: AgentStatus = {
  aiEnabled: true,
  dailyBudget: { usedTokens: 12340, limitTokens: 500000 },
};
export const aiOff: AgentStatus = {
  aiEnabled: false,
  reason: 'no model key',
  dailyBudget: { usedTokens: 0, limitTokens: 500000 },
};

export const thread = { id: THREAD_ID, title: 'Find the best loads', createdAt: STAMP };

const plan = goldPlans.profit;

/** The proposal of GOLD-001: D1, profit variant, 323.54 EUR net. */
export const proposal = {
  planRef: 'PLAN-1',
  routePlanId: plan.id,
  driverRef: 'D1',
  variant: 'profit' as const,
  netProfit: { amountMinor: plan.netProfit.amountMinor, currency: 'EUR' },
  finishAt: plan.finishAt,
  fuelL: plan.fuelL,
  co2Kg: plan.co2Kg,
};

export const finalAnswer: FinalAnswer = {
  summary: 'I found a plan for 1 of 1 drivers.',
  proposals: [proposal],
  citedFacts: ['netProfit'],
  grounded: true,
  source: 'llm',
  disclaimer: 'planning estimate',
};

export function approvalEvent(expiresAt = '2999-01-01T00:00:00Z') {
  return {
    approvalId: APPROVAL_ID,
    action: 'assign_plan',
    payload: {
      plans: [
        {
          planRef: 'PLAN-1',
          routePlanId: plan.id,
          driverRef: 'D1',
          driverLabel: 'Paweł Kurek',
          offerIds: plan.offerIds,
          variant: 'profit',
          netProfit: { amountMinor: plan.netProfit.amountMinor, currency: 'EUR' },
          finishAt: plan.finishAt,
          homeReached: true,
        },
      ],
      totals: {
        netProfit: { amountMinor: plan.netProfit.amountMinor, currency: 'EUR' },
        fuelL: plan.fuelL,
        co2Kg: plan.co2Kg,
      },
    },
    expiresAt,
  };
}

export const startedEvent = {
  runId: RUN_ID,
  threadId: THREAD_ID,
  modelPolicy: {},
  startedAt: STAMP,
};

export const step = (
  seq: number,
  agent: string,
  type: string,
  toolName: string | undefined,
  outputSummary: string,
  status: 'ok' | 'error' | 'rejected' = 'ok',
) => ({
  started: { seq, agent, type, toolName, inputSummary: 'input' },
  finished: {
    seq,
    agent,
    type,
    toolName,
    status,
    outputSummary,
    durationMs: 120 + seq,
    tokens: { in: 100, out: 20 },
  },
});
