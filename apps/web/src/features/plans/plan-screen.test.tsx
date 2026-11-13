import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { driver } from '@/test/fixtures/fleet';
import { goldPlan, goldPlans } from '@/test/fixtures/gold-001';
import { importedOffer } from '@/test/fixtures/offers';
import { apiUrl, problem } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { navigation } from '@/test/navigation';
import { renderApp } from '@/test/render-app';
import { PlanScreen } from './plan-screen';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

beforeEach(() => {
  navigation.reset('/plans/x', 'job=job-1');
  vi.stubEnv('NEXT_PUBLIC_MAP_STYLE_URL', '');
});

const posted: { assignments: unknown[]; explanations: unknown[] } = {
  assignments: [],
  explanations: [],
};

function mockApi(plan = goldPlan) {
  posted.assignments = [];
  posted.explanations = [];
  const van = { ...driver(1).vehicle!, label: 'BUS-01', palletPlaces: 10, payloadKg: 1085 };
  server.use(
    http.get(apiUrl('/api/v1/route-plans/:id'), () => HttpResponse.json(plan)),
    http.get(apiUrl('/api/v1/drivers/:id'), () =>
      HttpResponse.json({ ...driver(1), vehicle: van }),
    ),
    http.get(apiUrl('/api/v1/freight-offers/:id'), ({ params }) =>
      HttpResponse.json(
        importedOffer({
          id: String(params.id),
          sourceOfferId: `TC-${String(params.id).slice(-2)}`,
        }),
      ),
    ),
    http.get(apiUrl('/api/v1/optimization-jobs/:id/result'), () =>
      HttpResponse.json({
        perDriver: [
          {
            driverId: plan.driverId,
            plans: Object.fromEntries(
              (['profit', 'fastest', 'fuel'] as const).map((objective) => [
                objective,
                [goldPlans[objective]],
              ]),
            ),
          },
        ],
      }),
    ),
    http.post(apiUrl('/api/v1/route-plans/:id/explanations'), async ({ request }) => {
      posted.explanations.push(await request.json());
      return HttpResponse.json(
        {
          id: 'e1',
          routePlanId: plan.id,
          source: 'template',
          groundingOk: true,
          disclaimer: en.legal.notice,
          output: {
            headline: 'Three offers on one van',
            reasons: ['Highest profit'],
            tradeoffs: ['Longest finish'],
            warnings: [],
          },
        },
        { status: 201 },
      );
    }),
  );
}

describe('plan screen', () => {
  it('renders the plan with variants from the job, the top view and the vehicle card', async () => {
    mockApi();
    renderApp(<PlanScreen planId={goldPlan.id} />);
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Katowice → Leipzig' }),
    ).toBeVisible();
    expect(await screen.findByRole('article', { name: en.plans.variant.profit })).toBeVisible();
    expect(await screen.findByRole('img', { name: /Van floor from above/ })).toBeVisible();
    expect(
      screen.getByRole('img', { name: /Curtain-sider van up to 3.5 t, BUS-01/ }),
    ).toBeVisible();
    expect(screen.getByText(en.plans.progress.notStarted)).toBeVisible();
    expect(await screen.findAllByText('TC-a1')).not.toHaveLength(0);
  });

  it('explains the plan with the Template label', async () => {
    const user = userEvent.setup();
    mockApi();
    renderApp(<PlanScreen planId={goldPlan.id} />);
    await user.click(await screen.findByRole('button', { name: en.plans.actions.explain }));
    expect(await screen.findByText('Three offers on one van')).toBeVisible();
    expect(screen.getByText(en.plans.explanation.template)).toBeVisible();
    expect(posted.explanations).toEqual([{ locale: 'en' }]);
  });

  it('asks for confirmation before assigning and sends the plan id', async () => {
    const user = userEvent.setup();
    mockApi();
    server.use(
      http.post(apiUrl('/api/v1/assignments'), async ({ request }) => {
        posted.assignments.push(await request.json());
        return HttpResponse.json({ id: 'a1' }, { status: 201 });
      }),
    );
    renderApp(<PlanScreen planId={goldPlan.id} />);
    await user.click(await screen.findByRole('button', { name: en.plans.actions.assign }));
    const dialog = await screen.findByRole('alertdialog', { name: en.plans.assign.title });
    expect(dialog).toHaveTextContent('€323.54');
    expect(posted.assignments).toHaveLength(0);
    await user.click(within(dialog).getByRole('button', { name: en.plans.assign.confirm }));
    await waitFor(() => expect(posted.assignments).toEqual([{ routePlanId: goldPlan.id }]));
    expect(await screen.findByText(en.plans.assign.assigned)).toBeVisible();
  });

  it('explains a stale plan on 409 and links to a new run', async () => {
    const user = userEvent.setup();
    mockApi();
    server.use(
      http.post(apiUrl('/api/v1/assignments'), () =>
        problem(409, 'PLAN_NOT_ASSIGNABLE', {
          errors: [{ field: 'offerIds', code: 'OFFER_CHANGED', message: 'x' }],
        }),
      ),
    );
    renderApp(<PlanScreen planId={goldPlan.id} />);
    await user.click(await screen.findByRole('button', { name: en.plans.actions.assign }));
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: en.plans.assign.confirm }));
    expect(await within(dialog).findByText(en.plans.assign.reason.OFFER_CHANGED)).toBeVisible();
    expect(within(dialog).getByRole('link', { name: en.plans.assign.rerun })).toHaveAttribute(
      'href',
      '/optimizer',
    );
  });

  it('has no assign button on a baseline plan', async () => {
    mockApi({ ...goldPlan, kind: 'baseline_greedy' });
    renderApp(<PlanScreen planId={goldPlan.id} />);
    await screen.findByRole('heading', { level: 1 });
    expect(screen.queryByRole('button', { name: en.plans.actions.assign })).toBeNull();
    expect(screen.getByText(en.plans.kind.baseline_greedy)).toBeVisible();
  });
});
