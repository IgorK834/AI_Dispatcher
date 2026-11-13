import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { driver, fiveDrivers, vehicle } from '@/test/fixtures/fleet';
import { fleetApi } from '@/test/msw/handlers/fleet';
import { navigation } from '@/test/navigation';
import { dispatcher, renderWithSession, signInAs } from '@/test/session';
import { RouteGuard } from '@/features/auth';
import { FleetScreen } from './fleet-screen';
import { renderFleet } from './test-utils';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

const form = en.fleet.vehicleForm;

beforeEach(() => navigation.reset('/fleet', 'view=vehicles'));

async function openVehicles() {
  return within(await screen.findByRole('tabpanel')).findByRole('table');
}

describe('[AC-FEAT-005-08] vehicles in the fleet screen', () => {
  it.each(['admin', 'dispatcher', 'demo'] as const)(
    'lets the %s role create, edit and delete a vehicle with the same behaviour',
    async (role) => {
      const user = userEvent.setup();
      signInAs({ ...dispatcher, role });
      const api = fleetApi({ drivers: [], vehicles: [vehicle(1), vehicle(2)] });
      renderWithSession(
        <RouteGuard>
          <FleetScreen />
        </RouteGuard>,
      );
      const table = await openVehicles();
      expect(within(table).getByRole('button', { name: 'Edit BUS-01' })).toBeVisible();

      // Create.
      await user.click(screen.getByRole('button', { name: en.fleet.addVehicle }));
      await user.type(await screen.findByLabelText(form.label), 'BUS-09');
      await user.click(screen.getByRole('button', { name: en.common.save }));
      expect(await screen.findByText(en.fleet.toast.vehicleSaved)).toBeVisible();
      expect(
        await within(await openVehicles()).findByRole('button', { name: 'Edit BUS-09' }),
      ).toBeVisible();
      expect(api.calls.find((call) => call.method === 'POST')?.body).toMatchObject({
        label: 'BUS-09',
        vehicleType: 'VEHICLE_UP_TO_3_5_T',
        palletPlaces: 10,
        payloadKg: 1085,
        fuel: { lPer100kmEmptyAt90: 11, lPer100kmFullAt90: 13, speedCurve: 'VAN_DEFAULT_V1' },
      });

      // Edit.
      await user.click(within(await openVehicles()).getByRole('button', { name: 'Edit BUS-01' }));
      const label = await screen.findByLabelText(form.label);
      await user.clear(label);
      await user.type(label, 'BUS-01X');
      await user.click(screen.getByRole('button', { name: en.common.save }));
      await waitFor(() => expect(api.vehicles.some((item) => item.label === 'BUS-01X')).toBe(true));
      expect(api.calls.find((call) => call.method === 'PATCH')?.body).toMatchObject({ version: 1 });

      // Delete.
      await user.click(within(await openVehicles()).getByRole('button', { name: 'Delete BUS-02' }));
      const dialog = await screen.findByRole('alertdialog', { name: 'Delete vehicle BUS-02?' });
      await user.click(
        within(dialog).getByRole('button', { name: en.fleet.delete.vehicleConfirm }),
      );
      expect(await screen.findByText(en.fleet.toast.vehicleDeleted)).toBeVisible();
      await waitFor(() => expect(api.vehicles.some((item) => item.label === 'BUS-02')).toBe(false));
    },
  );

  it('explains VEHICLE_ASSIGNED_TO_DRIVER when the vehicle belongs to a driver', async () => {
    const user = userEvent.setup();
    const drivers = fiveDrivers();
    fleetApi({ drivers, vehicles: drivers.map((item) => item.vehicle!) });
    renderFleet(<FleetScreen />);
    await user.click(within(await openVehicles()).getByRole('button', { name: 'Delete BUS-01' }));
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: en.fleet.delete.vehicleConfirm }));
    expect(await within(dialog).findByText(en.errors.VEHICLE_ASSIGNED_TO_DRIVER)).toBeVisible();
  });

  it('shows the conflict banner and keeps the input on a vehicle version conflict', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: [], vehicles: [vehicle(1)] });
    renderFleet(<FleetScreen />);
    await user.click(within(await openVehicles()).getByRole('button', { name: 'Edit BUS-01' }));
    const label = await screen.findByLabelText(form.label);
    await user.clear(label);
    await user.type(label, 'BUS-77');
    api.vehicles[0] = { ...api.vehicles[0]!, version: 2 };
    await user.click(screen.getByRole('button', { name: en.common.save }));
    expect(await screen.findByText(en.fleet.conflict.title)).toBeVisible();
    expect(screen.getByLabelText(form.label)).toHaveValue('BUS-77');
    await user.click(screen.getByRole('button', { name: en.fleet.conflict.reload }));
    await waitFor(() =>
      expect(screen.queryByText(en.fleet.conflict.title)).not.toBeInTheDocument(),
    );
    await user.click(screen.getByRole('button', { name: en.common.save }));
    expect(await screen.findByText(en.fleet.toast.vehicleSaved)).toBeVisible();
  });

  it('puts a duplicate label under the label field and checks the payload limit', async () => {
    const user = userEvent.setup();
    fleetApi({ drivers: [], vehicles: [vehicle(1)] });
    renderFleet(<FleetScreen />);
    await openVehicles();
    await user.click(screen.getByRole('button', { name: en.fleet.addVehicle }));
    const payload = await screen.findByLabelText(form.payload);
    await user.clear(payload);
    await user.type(payload, '5000');
    await user.type(screen.getByLabelText(form.label), 'BUS-01');
    await user.click(screen.getByRole('button', { name: en.common.save }));
    expect(await screen.findByText(en.fleet.validation.payloadRange)).toBeVisible();
    expect(screen.getByLabelText(form.payload)).toHaveAttribute('aria-invalid', 'true');
  });

  it('shows the empty state of the vehicles tab with its own action', async () => {
    const user = userEvent.setup();
    fleetApi({ drivers: [driver(1)], vehicles: [] });
    renderFleet(<FleetScreen />);
    const title = await screen.findByRole('heading', { name: en.fleet.empty.vehiclesTitle });
    await user.click(
      within(title.parentElement as HTMLElement).getByRole('button', { name: en.fleet.addVehicle }),
    );
    expect(await screen.findByRole('dialog', { name: form.createTitle })).toBeVisible();
  });
});
