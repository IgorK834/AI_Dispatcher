import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { fiveDrivers } from '@/test/fixtures/fleet';
import { apiUrl, problem } from '@/test/msw/handlers';
import { fleetApi } from '@/test/msw/handlers/fleet';
import { server } from '@/test/msw/server';
import { navigation } from '@/test/navigation';
import { FleetScreen } from './fleet-screen';
import { renderFleet } from './test-utils';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

beforeEach(() => navigation.reset());

const form = en.fleet.driverForm;

async function openCreateSheet(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByRole('table');
  await user.click(screen.getByRole('button', { name: en.fleet.addDriver }));
  return screen.findByRole('dialog', { name: form.createTitle });
}

async function fillValid(
  user: ReturnType<typeof userEvent.setup>,
  overrides: Partial<Record<'name' | 'lat' | 'lon', string>> = {},
) {
  await user.type(screen.getByLabelText(form.name), overrides.name ?? 'Nowa Kierowca');
  await user.type(screen.getByLabelText(form.homeCity), 'Opole');
  await user.clear(screen.getByLabelText(form.homeCountry));
  await user.type(screen.getByLabelText(form.homeCountry), 'PL');
  await user.type(screen.getByLabelText(form.homeLat), overrides.lat ?? '50.67');
  await user.type(screen.getByLabelText(form.homeLon), overrides.lon ?? '17.92');
}

describe('[AC-FEAT-005-05] driver form validation', () => {
  it('shows messages under an empty name and latitude 123 and sends no request', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    await openCreateSheet(user);
    await user.type(screen.getByLabelText(form.homeCity), 'Opole');
    await user.type(screen.getByLabelText(form.homeLat), '123');
    await user.type(screen.getByLabelText(form.homeLon), '17.92');
    await user.click(screen.getByRole('button', { name: en.common.save }));

    const name = screen.getByLabelText(form.name);
    const latitude = screen.getByLabelText(form.homeLat);
    expect(await screen.findByText(en.fleet.validation.nameRequired)).toBeVisible();
    expect(screen.getByText(en.fleet.validation.latitudeRange)).toBeVisible();
    expect(name).toHaveAttribute('aria-invalid', 'true');
    expect(name).toHaveAccessibleDescription(en.fleet.validation.nameRequired);
    expect(latitude).toHaveAccessibleDescription(en.fleet.validation.latitudeRange);
    expect(api.count('POST', /\/drivers$/)).toBe(0);
  });

  it('shows the server message under the field named by errors[].field', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    server.use(
      http.post(apiUrl('/api/v1/drivers'), () =>
        problem(422, 'VALIDATION_ERROR', {
          errors: [
            { field: 'homeLon', code: 'RANGE', message: 'Longitude is outside the service area' },
          ],
        }),
      ),
    );
    renderFleet(<FleetScreen />);
    await openCreateSheet(user);
    await fillValid(user);
    await user.click(screen.getByRole('button', { name: en.common.save }));
    const message = await screen.findByText('Longitude is outside the service area');
    expect(message).toBeVisible();
    expect(screen.getByLabelText(form.homeLon)).toHaveAccessibleDescription(
      'Longitude is outside the service area',
    );
    expect(screen.getByLabelText(form.homeLon)).toHaveAttribute('aria-invalid', 'true');
    expect(api.drivers).toHaveLength(5);
  });

  it('sends unknown server fields to a form-level alert', async () => {
    const user = userEvent.setup();
    fleetApi({ drivers: fiveDrivers() });
    server.use(
      http.post(apiUrl('/api/v1/drivers'), () =>
        problem(422, 'VALIDATION_ERROR', {
          errors: [{ field: 'secretField', message: 'unexpected' }],
        }),
      ),
    );
    renderFleet(<FleetScreen />);
    await openCreateSheet(user);
    await fillValid(user);
    await user.click(screen.getByRole('button', { name: en.common.save }));
    const alert = await screen.findByText(
      'Some fields could not be matched to the form: secretField',
    );
    expect(alert.closest('[role="alert"]')).toBeInTheDocument();
  });

  it('creates a driver, confirms with a toast, closes the sheet and refreshes the list', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    await openCreateSheet(user);
    await fillValid(user);
    await user.click(screen.getByRole('button', { name: en.common.save }));
    expect(await screen.findByText(en.fleet.toast.driverSaved)).toBeVisible();
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: form.createTitle })).not.toBeInTheDocument(),
    );
    expect(await within(screen.getByRole('table')).findByText('Nowa Kierowca')).toBeVisible();
    expect(api.calls.find((call) => call.method === 'POST')?.body).toMatchObject({
      name: 'Nowa Kierowca',
      homeCity: 'Opole',
      homeCountry: 'PL',
      homeLat: 50.67,
      homeLon: 17.92,
      phone: null,
      vehicleId: null,
    });
  });

  it('shows a "no permission" toast for a 403 that still happens', async () => {
    const user = userEvent.setup();
    fleetApi({ drivers: fiveDrivers() });
    server.use(http.post(apiUrl('/api/v1/drivers'), () => problem(403, 'FORBIDDEN')));
    renderFleet(<FleetScreen />);
    await openCreateSheet(user);
    await fillValid(user);
    await user.click(screen.getByRole('button', { name: en.common.save }));
    expect(await screen.findByText(en.fleet.toast.noPermission)).toBeVisible();
  });
});

describe('[AC-FEAT-005-06] version conflict', () => {
  it('keeps the sheet and the typed values, offers Reload, and Reload refetches the driver', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: 'Edit Paweł Kurek' }));
    const dialog = await screen.findByRole('dialog', { name: form.editTitle });
    const name = within(dialog).getByLabelText(form.name);
    expect(name).toHaveValue('Paweł Kurek');
    await user.clear(name);
    await user.type(name, 'Paweł Kurek-Nowy');

    // Somebody else saved in the meantime: the server is at version 4, the form loaded version 3.
    api.drivers[0] = { ...api.drivers[0]!, version: 4 };
    await user.click(within(dialog).getByRole('button', { name: en.common.save }));

    expect(await screen.findByText(en.fleet.conflict.title)).toBeVisible();
    expect(api.calls.find((call) => call.method === 'PATCH')?.body).toMatchObject({ version: 3 });
    expect(screen.getByRole('dialog', { name: form.editTitle })).toBeVisible();
    expect(screen.getByLabelText(form.name)).toHaveValue('Paweł Kurek-Nowy');

    const before = api.count('GET', /\/drivers\/[^/]+$/);
    await user.click(screen.getByRole('button', { name: en.fleet.conflict.reload }));
    await waitFor(() => expect(api.count('GET', /\/drivers\/[^/]+$/)).toBe(before + 1));
    await waitFor(() =>
      expect(screen.queryByText(en.fleet.conflict.title)).not.toBeInTheDocument(),
    );
    expect(screen.getByLabelText(form.name)).toHaveValue('Paweł Kurek-Nowy');

    // After the reload the next save carries the fresh version and succeeds.
    await user.click(screen.getByRole('button', { name: en.common.save }));
    expect(await screen.findByText(en.fleet.toast.driverSaved)).toBeVisible();
    const patches = api.calls.filter((call) => call.method === 'PATCH');
    expect(patches.map((call) => (call.body as { version: number }).version)).toEqual([3, 4]);
    expect(api.drivers[0]).toMatchObject({ name: 'Paweł Kurek-Nowy', version: 5 });
  });
});

describe('driver state form', () => {
  it('adds a driver state with the counters in minutes', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: 'Add state for Ewa Sowa' }));
    const dialog = await screen.findByRole('dialog', { name: en.fleet.stateForm.title });
    const work = within(dialog).getByLabelText(en.fleet.stateForm.workToday);
    await user.clear(work);
    await user.type(work, '120');
    await user.click(within(dialog).getByRole('button', { name: en.common.save }));
    expect(await screen.findByText(en.fleet.toast.stateSaved)).toBeVisible();
    const post = api.calls.find((call) => call.method === 'POST' && /state$/.test(call.path));
    expect(post?.body).toMatchObject({ workTodayMin: 120, driveTodayMin: 0 });
  });

  it('refuses a negative counter under its field', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: 'Add state for Ewa Sowa' }));
    const dialog = await screen.findByRole('dialog', { name: en.fleet.stateForm.title });
    const work = within(dialog).getByLabelText(en.fleet.stateForm.workToday);
    await user.clear(work);
    await user.type(work, '-5');
    await user.click(within(dialog).getByRole('button', { name: en.common.save }));
    expect(await screen.findByText(en.fleet.validation.minutesRange)).toBeVisible();
    expect(api.count('POST', /state$/)).toBe(0);
  });
});
