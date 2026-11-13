import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
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

describe('[AC-FEAT-005-04] fleet list states', () => {
  it('shows skeleton rows while the drivers request is pending', async () => {
    fleetApi({ drivers: [] });
    server.use(http.get(apiUrl('/api/v1/drivers'), () => new Promise<never>(() => undefined)));
    renderFleet(<FleetScreen />);
    const label = await screen.findByText(en.fleet.loading);
    expect(label.closest('[aria-busy="true"]')).toHaveAttribute('role', 'status');
    expect(screen.getAllByTestId('skeleton-row')).toHaveLength(5);
  });

  it('shows the empty state with an "Add driver" action for an empty list', async () => {
    fleetApi({ drivers: [] });
    renderFleet(<FleetScreen />);
    const title = await screen.findByRole('heading', { name: en.fleet.empty.driversTitle });
    expect(screen.getByText(en.fleet.empty.driversBody)).toBeVisible();
    const action = within(title.parentElement as HTMLElement).getByRole('button', {
      name: en.fleet.addDriver,
    });
    await userEvent.click(action);
    expect(
      await screen.findByRole('dialog', { name: en.fleet.driverForm.createTitle }),
    ).toBeVisible();
  });

  it('shows the error by problem code with "Try again" and the request id, and retries', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    let healthy = false;
    server.use(
      http.get(apiUrl('/api/v1/drivers'), () =>
        healthy
          ? HttpResponse.json({ items: api.drivers, nextCursor: null })
          : problem(500, 'INTERNAL_ERROR'),
      ),
    );
    renderFleet(<FleetScreen />);
    expect(await screen.findByText(en.fleet.error.drivers)).toBeVisible();
    expect(screen.getByText(en.errors.INTERNAL_ERROR)).toBeVisible();
    expect(screen.getByText('Request ID: req-test-1')).toBeVisible();
    healthy = true;
    await user.click(screen.getByRole('button', { name: en.common.tryAgain }));
    expect(await screen.findByText('Paweł Kurek')).toBeVisible();
  });

  it('shows the table with working-time bars for five drivers', async () => {
    fleetApi({ drivers: fiveDrivers(), assigned: [fiveDrivers()[0]!.id] });
    renderFleet(<FleetScreen />);
    const table = await screen.findByRole('table');
    for (const name of ['Paweł Kurek', 'Ewa Sowa', 'Marta Lis-Wrona', 'Jan Bielak', 'Kamil Dąb']) {
      expect(within(table).getByText(name)).toBeVisible();
    }
    // Two bars per driver, each with its number written next to it.
    expect(screen.getAllByRole('meter')).toHaveLength(10);
    const day = screen.getByRole('meter', { name: `${en.fleet.table.workDay}: Paweł Kurek` });
    expect(day).toHaveAttribute('aria-valuetext', '12 h 0 min left of 12 h 0 min');
    const week = screen.getByRole('meter', { name: `${en.fleet.table.workWeek}: Marta Lis-Wrona` });
    expect(week).toHaveAttribute(
      'aria-valuetext',
      expect.stringContaining('25 h 30 min left of 60 h 0 min'),
    );
    expect(screen.getAllByText(en.fleet.status.assigned)).toHaveLength(1);
    expect(screen.getAllByText(en.fleet.status.free)).toHaveLength(4);
    expect(screen.getAllByText(en.fleet.status.synthetic)).toHaveLength(5);
    expect(
      screen.getAllByRole('img', { name: /Curtain-sider van up to 3.5 t, BUS-0\d/ }),
    ).toHaveLength(5);
  });
});

describe('fleet list behaviour', () => {
  it('shows the KPI cards from the loaded drivers and the legal notice', async () => {
    const drivers = fiveDrivers();
    fleetApi({ drivers, assigned: [drivers[0]!.id] });
    renderFleet(<FleetScreen />);
    await screen.findByText('Paweł Kurek');
    const cards = screen.getByText(en.fleet.kpi.drivers).parentElement as HTMLElement;
    expect(within(cards).getByText('5')).toBeVisible();
    expect(within(cards).getByText('5 vans · 50 pallet places')).toBeVisible();
    expect(screen.getByText('4')).toBeVisible(); // free today
    expect(screen.getByText('1 assigned')).toBeVisible();
    expect(screen.getByText('25 h 30 min')).toBeVisible();
    expect(screen.getAllByText('Marta Lis-Wrona').length).toBeGreaterThanOrEqual(2);
  });

  it('puts the filters in the URL and sends them to the API', async () => {
    const user = userEvent.setup();
    const api = fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    await screen.findByText('Paweł Kurek');
    await user.click(screen.getByRole('checkbox', { name: en.fleet.filters.hasVehicle }));
    expect(navigation.replace).toHaveBeenLastCalledWith('/fleet?hasVehicle=true');
    await user.type(screen.getByLabelText(en.fleet.filters.base), 'Katowice');
    await user.tab();
    expect(navigation.replace).toHaveBeenLastCalledWith('/fleet?homeCity=Katowice');
    expect(api.calls.some((call) => call.query.get('limit') === '20')).toBe(true);
  });

  it('reads the filters from the URL', async () => {
    navigation.reset('/fleet', 'homeCity=Katowice&hasVehicle=true');
    const api = fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    const table = await screen.findByRole('table');
    expect(within(table).getByText('Paweł Kurek')).toBeVisible();
    expect(screen.queryByText('Ewa Sowa')).not.toBeInTheDocument();
    const request = api.calls.find((call) => call.path === '/api/v1/drivers');
    expect(request?.query.get('homeCity')).toBe('Katowice');
    expect(request?.query.get('hasVehicle')).toBe('true');
    expect(screen.getByRole('checkbox', { name: en.fleet.filters.hasVehicle })).toBeChecked();
  });

  it('loads the next page with "Load more"', async () => {
    const user = userEvent.setup();
    const all = fiveDrivers();
    fleetApi({ drivers: [] });
    server.use(
      http.get(apiUrl('/api/v1/drivers'), ({ request }) => {
        const cursor = new URL(request.url).searchParams.get('cursor');
        return cursor
          ? HttpResponse.json({ items: all.slice(2), nextCursor: null })
          : HttpResponse.json({ items: all.slice(0, 2), nextCursor: 'page-2' });
      }),
      http.get(apiUrl('/api/v1/assignments'), () =>
        HttpResponse.json({ items: [], nextCursor: null }),
      ),
    );
    renderFleet(<FleetScreen />);
    await screen.findByText('Paweł Kurek');
    expect(screen.queryByText('Marta Lis-Wrona')).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: en.fleet.loadMore }));
    expect(
      await within(await screen.findByRole('table')).findByText('Marta Lis-Wrona'),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: en.fleet.allLoaded })).toBeDisabled();
  });

  it('opens the 561 driving limits of a driver and shows the working-time notice', async () => {
    const user = userEvent.setup();
    fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    await screen.findByText('Paweł Kurek');
    const toggle = screen.getByRole('button', { name: 'Show 561 driving limits for Paweł Kurek' });
    await user.click(toggle);
    expect(screen.getByRole('heading', { name: en.fleet.details.title })).toBeVisible();
    expect(screen.getAllByRole('meter')).toHaveLength(14);
    await user.tab();
    await user.hover(screen.getByRole('button', { name: en.fleet.notice }));
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'does not certify legal compliance',
    );
  });

  it('switches to the vehicles tab and keeps the choice in the URL', async () => {
    const user = userEvent.setup();
    fleetApi({ drivers: fiveDrivers(), vehicles: fiveDrivers().map((item) => item.vehicle!) });
    renderFleet(<FleetScreen />);
    await screen.findByText('Paweł Kurek');
    await user.click(screen.getByRole('tab', { name: /Vehicles/ }));
    expect(navigation.replace).toHaveBeenLastCalledWith('/fleet?view=vehicles');
    await waitFor(() => expect(navigation.search.get('view')).toBe(null));
  });
});
