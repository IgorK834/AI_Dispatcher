import { screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { finalAnswer, step } from '@/test/fixtures/agent';
import { agentApi } from '@/test/msw/handlers/agent';
import { navigation } from '@/test/navigation';
import { renderApp } from '@/test/render-app';
import { ChatScreen } from './chat-screen';
import { ask, emit, mockPlanLookups, installFakeEventSource } from './test-utils';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

installFakeEventSource();

describe('[AC-FEAT-005-14] a run in the AI Dispatcher', () => {
  it('disables the input, shows each step in the trace, replaces the draft and enables the input again', async () => {
    navigation.reset('/');
    const api = agentApi();
    mockPlanLookups();
    renderApp(<ChatScreen />);

    await ask('Find the best loads for all vans for tomorrow');
    expect(api.threadsCreated).toBe(1);
    expect(api.messages).toHaveLength(1);
    expect(api.messages[0]?.body).toEqual({
      content: 'Find the best loads for all vans for tomorrow',
      locale: 'en',
    });
    expect(api.messages[0]?.idempotencyKey).toMatch(/^[0-9a-f-]{36}$/);

    // The input is locked while the run lasts.
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
    expect(screen.getByText('Working on it')).toBeInTheDocument();

    // Steps of three agents.
    const dispatcher = step(1, 'dispatcher', 'llm', undefined, 'Plan the request');
    const fleet = step(2, 'fleet_compliance', 'tool', 'get_driver_states', '5 drivers read');
    const planner = step(3, 'route_planner', 'tool', 'optimize_fleet', '1 plan found');
    let id = 2;
    for (const entry of [dispatcher, fleet, planner]) {
      emit('step_started', entry.started, id++);
      emit('step_finished', entry.finished, id++);
    }

    const trace = screen.getByRole('region', { name: 'Agent trace' });
    for (const [agent, tool, summary] of [
      ['dispatcher', 'Model', 'Plan the request'],
      ['fleet_compliance', 'get_driver_states', '5 drivers read'],
      ['route_planner', 'optimize_fleet', '1 plan found'],
    ] as const) {
      const row = within(trace).getByText(agent).closest('li') as HTMLElement;
      expect(row).toHaveTextContent(tool);
      expect(row).toHaveTextContent(summary);
      expect(within(row).getByText('ok')).toBeInTheDocument();
      expect(row).toHaveTextContent(/\d+ ms/);
    }
    expect(trace).toHaveTextContent('3 steps');

    // The draft is greyed and provisional; the final answer replaces it.
    emit('message_delta', { text: 'I found a plan for' }, id++);
    expect(screen.getByText(/I found a plan for/)).toBeInTheDocument();
    expect(screen.getByText('Draft')).toBeInTheDocument();

    emit('final_answer', finalAnswer, id++);
    expect(screen.queryByText('Draft')).not.toBeInTheDocument();
    expect(screen.getByText(finalAnswer.summary)).toBeInTheDocument();
    expect(screen.getByText('Verified numbers')).toBeInTheDocument();

    // A proposal card with the van, the profit and a link to the plan.
    const card = await screen.findByRole('article', { name: /D1 · Paweł Kurek/ });
    expect(
      await within(card).findByRole('img', { name: /Curtain-sider van.*BUS-01/ }),
    ).toBeInTheDocument();
    expect(card).toHaveTextContent('€323.54');
    expect(within(card).getByRole('link', { name: 'Open plan' })).toHaveAttribute(
      'href',
      `/plans/${finalAnswer.proposals[0]?.routePlanId}`,
    );

    emit('run_finished', { status: 'succeeded', tokensIn: 300, tokensOut: 60 }, id++);
    expect(await screen.findByRole('textbox', { name: 'Message' })).toBeEnabled();
    expect(screen.getByText('Done')).toBeInTheDocument();
  });

  it('marks a rejected step and a failed run in plain text', async () => {
    navigation.reset('/');
    agentApi();
    renderApp(<ChatScreen />);
    await ask('Plan');
    const rejected = step(1, 'guard', 'guard', undefined, 'Offer excluded', 'rejected');
    emit('step_started', rejected.started, 2);
    emit('step_finished', rejected.finished, 3);
    const row = screen.getByText('guard', { selector: 'span' }).closest('li') as HTMLElement;
    expect(within(row).getByText('rejected')).toBeInTheDocument();
    emit(
      'run_finished',
      { status: 'failed', tokensIn: 0, tokensOut: 0, error: { code: 'TOOL_ERROR', message: 'x' } },
      4,
    );
    expect(await screen.findByRole('alert')).toHaveTextContent('A data step failed');
  });

  it('labels a template answer', async () => {
    navigation.reset('/');
    agentApi();
    renderApp(<ChatScreen />);
    await ask('Plan');
    emit('final_answer', { ...finalAnswer, source: 'template', grounded: true }, 2);
    expect(screen.getByText('Template answer')).toBeInTheDocument();
  });
});
