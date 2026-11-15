import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import en from '../../../messages/en.json';
import pl from '../../../messages/pl.json';
import { chainPlan } from '@/test/fixtures/chain-plan';
import { goldPlans } from '@/test/fixtures/gold-001';
import { renderWithIntl } from '@/test/render';
import { Variants } from './variants';
import type { PlanSummary } from './types';

const v = en.plans.variants;
const names = en.plans.variant;

const summary = (
  plan: (typeof goldPlans)['profit'],
  overrides: Partial<PlanSummary> = {},
): PlanSummary => {
  const {
    stops: _s,
    calculation: _c,
    revenue: _r,
    costTotal: _t,
    geometry: _g,
    disclaimer: _d,
    workMin: _w,
    driveMin: _dm,
    waitMin: _wm,
    ...rest
  } = plan;
  void [_s, _c, _r, _t, _g, _d, _w, _dm, _wm];
  return { ...rest, ...overrides } as PlanSummary;
};

describe('[AC-FEAT-005-11] plan variants', () => {
  it('shows three different variants with figures, estimates, deltas and the legal notice', () => {
    const profit = summary(goldPlans.profit);
    const fastest = summary(goldPlans.fastest);
    const fuel = summary(goldPlans.fuel, {
      id: '00000000-0000-4000-8000-00000000f003',
      offerIds: ['00000000-0000-4000-8000-0000000000b1'],
      fuelL: '20.5',
      co2Kg: '53.3',
      netProfit: { amountMinor: 4000, currency: 'EUR' },
    });
    renderWithIntl(
      <Variants variants={{ profit, fastest, fuel }} currentId={profit.id} jobId="job-1" />,
    );

    const cards = screen.getAllByRole('article');
    expect(cards).toHaveLength(3);
    const first = within(screen.getByRole('article', { name: names.profit }));
    expect(first.getByText('€323.54')).toBeVisible();
    expect(first.getByText(v.shown)).toBeVisible();
    expect(first.getByText('625 km')).toBeVisible();
    expect(first.getByText('76.6 l')).toBeVisible();
    expect(first.getByText('199 kg CO₂')).toBeVisible();
    expect(first.getAllByText(new RegExp(v.estimate))).toHaveLength(2);
    expect(first.queryByText(v.deltaProfit)).toBeNull();

    const second = within(screen.getByRole('article', { name: names.fuel }));
    expect(second.getByText(/Δ profit/)).toHaveTextContent('−€283.54');
    expect(second.getByText(/Δ fuel/)).toHaveTextContent('−56.1 l');
    expect(second.getByRole('link', { name: v.open })).toHaveAttribute(
      'href',
      `/plans/${fuel.id}?job=job-1`,
    );
    expect(screen.getByText(en.legal.notice)).toBeVisible();
  });

  it('says that two variants coincide when they are the same plan', () => {
    const profit = summary(goldPlans.profit);
    const fastest = summary(goldPlans.fastest);
    const fuel = summary(goldPlans.fuel, { id: fastest.id });
    renderWithIntl(
      <Variants variants={{ profit, fastest, fuel }} currentId={profit.id} jobId="job-1" />,
    );
    const card = within(screen.getByRole('article', { name: names.fuel }));
    expect(card.getByText(`Same plan as ${names.fastest}: the variants coincide.`)).toBeVisible();
    expect(
      within(screen.getByRole('article', { name: names.fastest })).queryByText(/coincide/),
    ).toBeNull();
  });
});

describe('[AC-FEAT-010-12] van fill on the variant cards', () => {
  // Polish puts a no-break space before the sign (lib/format); Testing Library reads it as a space.
  const cases = [
    { locale: 'en', bundle: en, gold: ['51%', '48%'], chain: ['23%', '46%'] },
    {
      locale: 'pl',
      bundle: pl,
      gold: ['51 %', '48 %'],
      chain: ['23 %', '46 %'],
    },
  ] as const;

  it.each(cases)(
    '[AC-FEAT-010-12] shows fill and orders on board in $locale; the hint only for the chain',
    ({ locale, bundle, gold, chain }) => {
      const fill = bundle.plans.fill;
      const text = (template: string, values: Record<string, string>) =>
        Object.entries(values).reduce(
          (out, [key, value]) => out.replace(`{${key}}`, value),
          template,
        );
      const profit = summary(goldPlans.profit);
      const fuel = summary(chainPlan);
      renderWithIntl(<Variants variants={{ profit, fuel }} currentId={profit.id} jobId="job-1" />, {
        locale,
      });

      const consolidated = within(
        screen.getByRole('article', { name: bundle.plans.variant.profit }),
      );
      expect(consolidated.getByText(fill.label)).toBeVisible();
      expect(consolidated.getByText(text(fill.value, { ep: gold[0], kg: gold[1] }))).toBeVisible();
      expect(consolidated.getByText(fill.onBoard)).toBeVisible();
      expect(consolidated.getByText(text(fill.upTo, { count: '2' }))).toBeVisible();
      expect(consolidated.queryByText(fill.partEmpty)).toBeNull();

      const single = within(screen.getByRole('article', { name: bundle.plans.variant.fuel }));
      expect(single.getByText(text(fill.value, { ep: chain[0], kg: chain[1] }))).toBeVisible();
      expect(single.getByText(text(fill.upTo, { count: '1' }))).toBeVisible();
      expect(single.getByText(fill.partEmpty)).toBeVisible();
    },
  );

  it('[AC-FEAT-010-12] keeps the hint away from one order on board when the van is half full', () => {
    const fuel = summary(chainPlan, { loadFactorEp: '0.5000' });
    renderWithIntl(<Variants variants={{ fuel }} currentId={fuel.id} jobId="job-1" />);
    expect(screen.queryByText(en.plans.fill.partEmpty)).toBeNull();
  });
});
