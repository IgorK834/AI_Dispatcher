import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { fiveDrivers } from '@/test/fixtures/fleet';
import { goldPlans } from '@/test/fixtures/gold-001';
import { apiUrl, problem } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { navigation } from '@/test/navigation';
import { renderApp } from '@/test/render-app';
import { OptimizerScreen } from './optimizer-screen';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

const JOB = '00000000-0000-4000-8000-0000000c0001';
const D1 = goldPlans.profit.driverId;
const o = en.optimizer;

beforeEach(() => navigation.reset('/optimizer'));

const job = (
  status: string,
  progress = { phase: 'search', driversDone: 2, driversTotal: 5 },
  error = null,
) => ({
  id: JOB,
  status,
  scope: 'fleet',
  objectives: ['profit'],
  progress,
  stats: null,
  error,
  requestedBy: 'u',
  createdAt: '2026-11-16T05:00:00Z',
});

const money = (amountMinor: number) => ({ amountMinor, currency: 'EUR' });
const solution = (objective: string, profit: number, assign = true) => ({
  objective,
  assignments: assign ? [{ driverId: D1, routePlanId: goldPlans.profit.id }] : [],
  totals: {
    netProfit: money(profit),
    fuelL: '76.601',
    co2Kg: '199.16',
    distanceKm: '624.81',
    driversWithPlan: assign ? 1 : 0,
  },
});

const result = (rejections: unknown[] = []) => ({
  jobId: JOB,
  fleet: {
    profit: solution('profit', 32354),
    fastest: solution('fastest', 5611),
    fuel: solution('fuel', 5611),
  },
  perDriver: [{ driverId: D1, plans: { profit: [goldPlans.profit] } }],
  baselines: {
    baselineGreedy: solution('profit', 5611),
    baselineSingle: solution('profit', 19000),
  },
  rejections,
  warnings: [],
  stats: { nodes: 1, truncated: false, poolTruncated: false, runtimeMs: 10 },
  disclaimer: en.legal.notice,
});

function mockDrivers() {
  server.use(
    http.get(apiUrl('/api/v1/drivers'), () =>
      HttpResponse.json({
        items: fiveDrivers().map((d, i) => (i === 0 ? { ...d, id: D1 } : d)),
        nextCursor: null,
      }),
    ),
  );
}

describe('[AC-FEAT-005-13] optimizer screen', () => {
  it('starts a fleet run with an Idempotency-Key and the chosen parameters, and puts the job in the URL', async () => {
    const user = userEvent.setup();
    mockDrivers();
    const seen: { key: string | null; body: unknown }[] = [];
    server.use(
      http.post(apiUrl('/api/v1/optimization-jobs'), async ({ request }) => {
        seen.push({ key: request.headers.get('Idempotency-Key'), body: await request.json() });
        return HttpResponse.json(job('queued'), { status: 202 });
      }),
    );
    renderApp(<OptimizerScreen />);
    await user.selectOptions(screen.getByLabelText(o.form.horizon), '1');
    await user.selectOptions(screen.getByLabelText(o.form.maxOffers), '2');
    await user.click(screen.getByRole('button', { name: o.form.start }));
    await waitFor(() => expect(seen).toHaveLength(1));
    expect(seen[0]?.key).toMatch(/^[0-9a-f-]{36}$/);
    expect(seen[0]?.body).toEqual({
      scope: 'fleet',
      driverIds: [],
      objectives: ['profit', 'fastest', 'fuel'],
      params: { horizonDays: 1, maxOffersPerPlan: 2, topKPerDriver: 10 },
    });
    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith(`/optimizer?job=${JOB}`));
  });

  it('asks for at least one driver when the scope is "selected drivers"', async () => {
    const user = userEvent.setup();
    mockDrivers();
    renderApp(<OptimizerScreen />);
    await user.click(screen.getByRole('button', { name: o.form.scopeDriver }));
    await user.click(screen.getByRole('button', { name: o.form.start }));
    expect(await screen.findByText(o.form.driversRequired)).toBeVisible();
  });

  it('polls the job, shows progress, and shows the result when it succeeds', async () => {
    navigation.reset('/optimizer', `job=${JOB}`);
    mockDrivers();
    let polls = 0;
    server.use(
      http.get(apiUrl('/api/v1/optimization-jobs/:id'), () => {
        polls += 1;
        return HttpResponse.json(
          polls < 2
            ? job('running')
            : job('succeeded', { phase: 'saving', driversDone: 5, driversTotal: 5 }),
        );
      }),
      http.get(apiUrl('/api/v1/optimization-jobs/:id/result'), () => HttpResponse.json(result())),
    );
    renderApp(<OptimizerScreen />);
    expect(await screen.findByText(o.progress.phase.search)).toBeVisible();
    expect(screen.getByRole('meter', { name: o.progress.title })).toHaveAttribute(
      'aria-valuenow',
      '2',
    );
    expect(
      await screen.findByRole('heading', { name: o.result.title }, { timeout: 4000 }),
    ).toBeVisible();
    expect(polls).toBeGreaterThanOrEqual(2);

    for (const name of [en.plans.variant.profit, en.plans.variant.fastest, en.plans.variant.fuel]) {
      expect(screen.getByRole('region', { name })).toBeVisible();
    }
    const profit = within(screen.getByRole('region', { name: en.plans.variant.profit }));
    expect(profit.getByRole('link', { name: o.result.open })).toHaveAttribute(
      'href',
      `/plans/${goldPlans.profit.id}?job=${JOB}`,
    );
    expect(profit.getAllByText('€323.54').length).toBeGreaterThan(0);
    expect(profit.getByText(en.fleet.table.van ? 'Paweł Kurek' : '')).toBeVisible();
    // Baselines: engine 323.54, greedy 56.11, best single 190.00.
    expect(
      screen.getByRole('img', {
        name: /Engine: €323\.54; Greedy: €56\.11; Best single offer: €190\.00/,
      }),
    ).toBeVisible();
    expect(screen.getByTestId('uplift')).toHaveTextContent('+€267.43');
    expect(screen.getByTestId('uplift')).toHaveTextContent('+€133.54');
    expect(screen.getAllByText(en.legal.notice).length).toBeGreaterThan(0);
  });

  it('shows the error code of a failed job and lets the user run again', async () => {
    const user = userEvent.setup();
    navigation.reset('/optimizer', `job=${JOB}`);
    mockDrivers();
    server.use(
      http.get(apiUrl('/api/v1/optimization-jobs/:id'), () =>
        HttpResponse.json(
          job('failed', { phase: 'search', driversDone: 1, driversTotal: 5 }, {
            code: 'ROUTING_ERROR',
            message: 'x',
          } as never),
        ),
      ),
    );
    renderApp(<OptimizerScreen />);
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(o.progress.failed);
    expect(alert).toHaveTextContent('ROUTING_ERROR');
    await user.click(within(alert).getByRole('button', { name: o.progress.runAgain }));
    expect(navigation.replace).toHaveBeenCalledWith('/optimizer');
  });

  it('groups rejections by reason with a text per code and a generic text for an unknown code', async () => {
    const user = userEvent.setup();
    navigation.reset('/optimizer', `job=${JOB}`);
    mockDrivers();
    const rej = (code: string, offer: string) => ({
      driverId: D1,
      offerId: `00000000-0000-4000-8000-${offer}`,
      stage: 'prefilter',
      code,
      detail: 'd',
    });
    server.use(
      http.get(apiUrl('/api/v1/optimization-jobs/:id'), () => HttpResponse.json(job('succeeded'))),
      http.get(apiUrl('/api/v1/optimization-jobs/:id/result'), () =>
        HttpResponse.json(
          result([
            rej('OVERWEIGHT', '000000000001'),
            rej('OVERWEIGHT', '000000000002'),
            rej('NEW_ENGINE_CODE', '000000000003'),
          ]),
        ),
      ),
    );
    renderApp(<OptimizerScreen />);
    const section = within(await screen.findByRole('region', { name: /Rejected offers/ }));
    const overweight = section
      .getByText(en.rejections.OVERWEIGHT, { exact: false })
      .closest('details') as HTMLElement;
    expect(overweight).toHaveTextContent('OVERWEIGHT');
    expect(overweight).toHaveTextContent('· 2');
    const unknown = section
      .getByText(en.rejections.UNKNOWN, { exact: false })
      .closest('details') as HTMLElement;
    expect(unknown).toHaveTextContent('NEW_ENGINE_CODE');
    await user.click(within(overweight).getByText(en.rejections.OVERWEIGHT, { exact: false }));
    expect(within(overweight).getAllByRole('listitem')).toHaveLength(2);
  });

  it('shows the problem when starting fails', async () => {
    const user = userEvent.setup();
    mockDrivers();
    server.use(
      http.post(apiUrl('/api/v1/optimization-jobs'), () => problem(500, 'INTERNAL_ERROR')),
    );
    renderApp(<OptimizerScreen />);
    await user.click(screen.getByRole('button', { name: o.form.start }));
    expect(await screen.findByText(/req-test-1/)).toBeVisible();
  });
});
