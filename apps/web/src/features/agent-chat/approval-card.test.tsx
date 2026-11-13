import { screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { APPROVAL_ID, RUN_ID, approvalEvent } from '@/test/fixtures/agent';
import { agentApi } from '@/test/msw/handlers/agent';
import { navigation } from '@/test/navigation';
import { renderApp } from '@/test/render-app';
import { ChatScreen } from './chat-screen';
import { ask, emit, mockPlanLookups, installFakeEventSource } from './test-utils';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

installFakeEventSource();

async function openCard(options: Parameters<typeof agentApi>[0] = {}, expiresAt?: string) {
  navigation.reset('/');
  const api = agentApi(options);
  mockPlanLookups();
  renderApp(<ChatScreen />);
  const user = await ask('Assign the best plan');
  emit('approval_required', approvalEvent(expiresAt), 2);
  const card = await screen.findByRole('region', { name: /Approve 1 assignment\?/ });
  return { api, user, card };
}

describe('[AC-FEAT-005-15] the approval card', () => {
  it('shows plans, totals and the legal notice, and sends one approve request', async () => {
    const { api, user, card } = await openCard();
    expect(card).toHaveTextContent('D1');
    expect(card).toHaveTextContent('Paweł Kurek');
    expect(card).toHaveTextContent('€323.54');
    expect(card).toHaveTextContent('Total net');
    expect(card).toHaveTextContent('Fuel est.');
    expect(card).toHaveTextContent('76.6 l');
    expect(card).toHaveTextContent(en.legal.notice);

    const approve = within(card).getByRole('button', { name: 'Approve and assign' });
    const reject = within(card).getByRole('button', { name: 'Reject' });
    await user.click(approve);
    expect(approve).toBeDisabled();
    expect(reject).toBeDisabled();
    await user.click(approve); // a second click sends nothing

    await waitFor(() => expect(api.resumes).toHaveLength(1));
    expect(api.resumes[0]).toEqual({
      runId: RUN_ID,
      body: { approvalId: APPROVAL_ID, decision: 'approve', comment: null },
    });

    emit('approval_resolved', { approvalId: APPROVAL_ID, decision: 'approve', decidedBy: 'u' }, 3);
    expect(await screen.findByText('Approved. The assignments are saved.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See the assignments in the fleet' })).toHaveAttribute(
      'href',
      '/fleet',
    );
    expect(screen.queryByRole('button', { name: 'Approve and assign' })).not.toBeInTheDocument();
    expect(api.resumes).toHaveLength(1);
  });

  it('sends the comment with a rejection', async () => {
    const { api, user, card } = await openCard();
    await user.type(
      within(card).getByRole('textbox', { name: 'Comment' }),
      'Driver D1 is needed elsewhere',
    );
    await user.click(within(card).getByRole('button', { name: 'Reject' }));
    await waitFor(() => expect(api.resumes).toHaveLength(1));
    expect(api.resumes[0]?.body).toEqual({
      approvalId: APPROVAL_ID,
      decision: 'reject',
      comment: 'Driver D1 is needed elsewhere',
    });
    expect(within(card).getByRole('button', { name: 'Approve and assign' })).toBeDisabled();
    emit('approval_resolved', { approvalId: APPROVAL_ID, decision: 'reject', decidedBy: 'u' }, 3);
    expect(await screen.findByText('Rejected. Nothing was assigned.')).toBeInTheDocument();
  });

  it('updates when another tab resolves the request', async () => {
    const { card } = await openCard();
    emit(
      'approval_resolved',
      { approvalId: APPROVAL_ID, decision: 'approve', decidedBy: 'other' },
      3,
    );
    expect(await screen.findByText('Approved. The assignments are saved.')).toBeInTheDocument();
    expect(within(card).queryByRole('button', { name: 'Reject' })).not.toBeInTheDocument();
  });

  it('disables both buttons on an expired request', async () => {
    const { card } = await openCard({}, '2020-01-01T00:00:00Z');
    expect(within(card).getByText('This request expired')).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Approve and assign' })).toBeDisabled();
    expect(within(card).getByRole('button', { name: 'Reject' })).toBeDisabled();
  });

  it('keeps the buttons disabled and explains a 409 APPROVAL_NOT_PENDING', async () => {
    const { user, card } = await openCard({
      resumeProblem: { status: 409, code: 'APPROVAL_NOT_PENDING' },
    });
    await user.click(within(card).getByRole('button', { name: 'Approve and assign' }));
    expect(await screen.findByText(en.errors.APPROVAL_NOT_PENDING)).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Approve and assign' })).toBeDisabled();
  });
});
