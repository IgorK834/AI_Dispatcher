import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { fiveDrivers } from '@/test/fixtures/fleet';
import { fleetApi } from '@/test/msw/handlers/fleet';
import { navigation } from '@/test/navigation';
import { FleetScreen } from './fleet-screen';
import { renderFleet } from './test-utils';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

beforeEach(() => navigation.reset());

describe('[AC-FEAT-005-07] deleting a driver', () => {
  it('names the driver, sends nothing until the verb button, then toasts and drops the row', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    const table = await screen.findByRole('table');
    await user.click(within(table).getByRole('button', { name: 'Delete Ewa Sowa' }));

    const dialog = await screen.findByRole('alertdialog', { name: 'Delete driver Ewa Sowa?' });
    expect(within(dialog).getByText(en.fleet.delete.driverBody)).toBeVisible();
    expect(api.count('DELETE', /\/drivers\//)).toBe(0);

    await user.click(within(dialog).getByRole('button', { name: en.fleet.delete.driverConfirm }));
    expect(await screen.findByText(en.fleet.toast.driverDeleted)).toBeVisible();
    await waitFor(() =>
      expect(within(screen.getByRole('table')).queryByText('Ewa Sowa')).not.toBeInTheDocument(),
    );
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    expect(api.count('DELETE', /\/drivers\//)).toBe(1);
    expect(api.drivers).toHaveLength(4);
  });

  it('explains DRIVER_HAS_ACTIVE_ASSIGNMENT in the dialog instead of a generic error', async () => {
    const user = userEvent.setup();
    const drivers = fiveDrivers();
    const api = fleetApi({ drivers, assigned: [drivers[1]!.id] });
    renderFleet(<FleetScreen />);
    await user.click(
      within(await screen.findByRole('table')).getByRole('button', { name: 'Delete Ewa Sowa' }),
    );
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: en.fleet.delete.driverConfirm }));
    expect(await within(dialog).findByText(en.errors.DRIVER_HAS_ACTIVE_ASSIGNMENT)).toBeVisible();
    expect(within(dialog).getByText(en.fleet.delete.blockedTitle)).toBeVisible();
    expect(screen.getByRole('alertdialog')).toBeVisible(); // the dialog stays open
    expect(screen.queryByText(en.fleet.toast.driverDeleted)).not.toBeInTheDocument();
    expect(api.drivers).toHaveLength(5);
  });

  it('sends nothing when the dialog is cancelled or closed with Escape', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    const table = await screen.findByRole('table');
    await user.click(within(table).getByRole('button', { name: 'Delete Jan Bielak' }));
    await user.click(
      within(await screen.findByRole('alertdialog')).getByRole('button', {
        name: en.common.cancel,
      }),
    );
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    await user.click(within(table).getByRole('button', { name: 'Delete Jan Bielak' }));
    await screen.findByRole('alertdialog');
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    expect(api.count('DELETE', /\/drivers\//)).toBe(0);
  });
});
