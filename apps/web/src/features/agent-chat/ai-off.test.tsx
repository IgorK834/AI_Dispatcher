import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { aiOff } from '@/test/fixtures/agent';
import { agentApi } from '@/test/msw/handlers/agent';
import { navigation } from '@/test/navigation';
import { renderApp } from '@/test/render-app';
import { ChatScreen } from './chat-screen';
import { installFakeEventSource } from './test-utils';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

installFakeEventSource();

async function expectAiOffPanel() {
  expect(await screen.findByRole('heading', { name: en.chat.aiOff.title })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Open the manual optimizer' })).toHaveAttribute(
    'href',
    '/optimizer',
  );
  expect(screen.queryByRole('textbox', { name: 'Message' })).not.toBeInTheDocument();
}

describe('[AC-FEAT-005-16] the AI is off panel', () => {
  it('replaces the input when GET /agent/status says aiEnabled = false', async () => {
    navigation.reset('/');
    agentApi({ status: aiOff });
    renderApp(<ChatScreen />);
    await expectAiOffPanel();
  });

  it('shows the same panel when the status call answers 503 AI_UNAVAILABLE', async () => {
    navigation.reset('/');
    agentApi({ status: 'unavailable' });
    renderApp(<ChatScreen />);
    await expectAiOffPanel();
  });

  it('switches to the panel when sending answers 503 AI_UNAVAILABLE', async () => {
    navigation.reset('/');
    agentApi({ messageProblem: { status: 503, code: 'AI_UNAVAILABLE' } });
    renderApp(<ChatScreen />);
    const user = userEvent.setup();
    await user.type(await screen.findByRole('textbox', { name: 'Message' }), 'Plan');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await expectAiOffPanel();
  });

  it.each([
    [429, 'AI_BUDGET_EXCEEDED', en.errors.AI_BUDGET_EXCEEDED],
    [409, 'RUN_IN_PROGRESS', en.errors.RUN_IN_PROGRESS],
  ])('answers %s %s with its own message and keeps the input', async (status, code, text) => {
    navigation.reset('/');
    agentApi({ messageProblem: { status, code } });
    renderApp(<ChatScreen />);
    const user = userEvent.setup();
    await user.type(await screen.findByRole('textbox', { name: 'Message' }), 'Plan');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    expect(await screen.findByText(text)).toBeInTheDocument();
    expect(screen.getByRole('textbox', { name: 'Message' })).toBeEnabled();
  });
});
