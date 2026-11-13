import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { mayOpen, navigationFor } from '@/features/auth';
import { aiOn } from '@/test/fixtures/agent';
import { adminApi } from '@/test/msw/handlers/admin';
import { agentApi } from '@/test/msw/handlers/agent';
import { renderApp } from '@/test/render-app';
import { AdminScreen } from './admin-screen';

function setup() {
  const api = adminApi();
  agentApi({ status: aiOn });
  renderApp(<AdminScreen />);
  return { api, user: userEvent.setup() };
}

describe('[AC-FEAT-005-17] the admin screen', () => {
  it('generates with a seed and shows the returned counts', async () => {
    const { api, user } = setup();
    const generate = screen.getByRole('region', { name: 'Generate demo data' });
    await user.type(within(generate).getByLabelText('Seed'), '42');
    await user.type(within(generate).getByLabelText('Reference date'), '2026-11-16');
    await user.click(within(generate).getByRole('button', { name: 'Generate' }));

    const result = await within(generate).findByText('Last run');
    expect(api.generates).toEqual([
      { drivers: 5, offers: 150, seed: 42, referenceDate: '2026-11-16' },
    ]);
    const counts = result.closest('[role="status"]') as HTMLElement;
    expect(counts).toHaveTextContent('Imported147');
    expect(counts).toHaveTextContent('Failed3');
    expect(counts).toHaveTextContent('5 drivers · 5 vans');
    expect(await screen.findByText('Demo data generated.')).toBeInTheDocument();
  });

  it('asks for a valid offer count before anything is sent', async () => {
    const { api, user } = setup();
    const generate = screen.getByRole('region', { name: 'Generate demo data' });
    const offers = within(generate).getByLabelText('Offers');
    await user.clear(offers);
    await user.type(offers, '900');
    await user.click(within(generate).getByRole('button', { name: 'Generate' }));
    expect(
      await within(generate).findByText('Enter a whole number from 1 to 500.'),
    ).toBeInTheDocument();
    expect(api.generates).toHaveLength(0);
  });

  it('sends nothing for Reset until the confirmation word is typed', async () => {
    const { api, user } = setup();
    const reset = screen.getByRole('region', { name: 'Reset demo data' });
    const button = within(reset).getByRole('button', { name: 'Reset demo data' });
    const word = within(reset).getByLabelText('Type RESET to confirm');

    expect(button).toBeDisabled();
    await user.click(button);
    await user.type(word, 'reset{Enter}'); // wrong case, and Enter submits the form
    expect(button).toBeDisabled();
    expect(api.resets).toBe(0);

    await user.clear(word);
    await user.type(word, 'RESET');
    expect(button).toBeEnabled();
    await user.click(button);

    await waitFor(() => expect(api.resets).toBe(1));
    expect(
      await screen.findByText('Demo data reset to the first-start state.'),
    ).toBeInTheDocument();
    expect(await within(reset).findByText('Last run')).toBeInTheDocument();
    expect(word).toHaveValue('');
    expect(button).toBeDisabled();
  });

  it('shows the cost profile read-only with its basis and the AI status', async () => {
    setup();
    const cost = await screen.findByRole('region', { name: /Cost profile DEMO-DEFAULT/ });
    expect(within(cost).getByText('Read-only')).toBeInTheDocument();
    expect(within(cost).queryByRole('button')).not.toBeInTheDocument();
    const fuel = within(cost).getByText('Fuel price per litre').closest('tr') as HTMLElement;
    expect(fuel).toHaveTextContent('€1.81');
    expect(fuel).toHaveTextContent('source');
    const driverCost = within(cost).getByText('Driver cost per hour').closest('tr') as HTMLElement;
    expect(driverCost).toHaveTextContent('assumption');
    const ai = await screen.findByRole('region', { name: 'AI status' });
    expect(await within(ai).findByText('On')).toBeInTheDocument();
    expect(ai).toHaveTextContent('12,340 of 500,000');
  });

  it('is open to administrators only: other roles have no route and no menu entry', () => {
    expect(mayOpen('admin', '/admin')).toBe(true);
    for (const role of ['dispatcher', 'demo'] as const) {
      expect(mayOpen(role, '/admin')).toBe(false);
      expect(navigationFor(role).map((entry) => entry.href)).not.toContain('/admin');
    }
  });
});
