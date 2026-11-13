import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import en from '../../../messages/en.json';
import { goldPlan, goldVan } from '@/test/fixtures/gold-001';
import { renderWithIntl } from '@/test/render';
import { CostBreakdown } from './cost-breakdown';
import { Occupancy } from './occupancy';
import { StopList } from './stop-list';
import { Timeline, timelineSegments } from './timeline';

describe('[AC-FEAT-005-12] GOLD-001 plan detail', () => {
  it('lists the 6 pickup and delivery stops in order', () => {
    const { container } = renderWithIntl(
      <StopList stops={goldPlan.stops} van={goldVan} offerNames={{}} />,
    );
    const rows = [...container.querySelectorAll('tr[data-kind]')];
    const actions = rows.filter((row) =>
      ['PICKUP', 'DELIVERY'].includes(row.getAttribute('data-kind') ?? ''),
    );
    expect(actions.map((row) => row.getAttribute('data-kind'))).toEqual([
      'PICKUP',
      'PICKUP',
      'DELIVERY',
      'PICKUP',
      'DELIVERY',
      'DELIVERY',
    ]);
    expect(
      actions.map((row) => within(row as HTMLElement).getAllByRole('cell')[0]?.textContent),
    ).toEqual(['1', '2', '3', '4', '5', '6']);
    // A rest reason code is shown in words.
    expect(screen.getAllByText(en.plans.reason.BREAK_LIMIT_REACHED)).toHaveLength(2);
    expect(screen.getByText(en.plans.reason.DAILY_LIMIT_REACHED)).toBeVisible();
  });

  it('has two break segments and one rest segment with text labels, and 625 min of driving', () => {
    const { container } = renderWithIntl(<Timeline stops={goldPlan.stops} />);
    const breaks = container.querySelectorAll('[data-kind="break"]');
    const rests = container.querySelectorAll('[data-kind="rest"]');
    expect(breaks).toHaveLength(2);
    expect(rests).toHaveLength(1);
    expect(breaks[0]).toHaveAccessibleName(/^Break, 45 min/);
    expect(rests[0]).toHaveAccessibleName(/^Daily rest, 11 h 0 min/);
    expect(screen.getByText('Break: 1 h 30 min (2)')).toBeVisible();
    expect(screen.getByText('Daily rest: 11 h 0 min (1)')).toBeVisible();
    const driving = timelineSegments(goldPlan.stops)
      .filter((segment) => segment.kind === 'drive')
      .reduce((sum, segment) => sum + segment.minutes, 0);
    expect(driving).toBe(goldPlan.driveMin);
  });

  it('peaks at 8.0 / 10 EP and 800 / 1 085 kg', () => {
    renderWithIntl(<Occupancy stops={goldPlan.stops} van={goldVan} />);
    expect(screen.getByTestId('occupancy-peak')).toHaveTextContent(
      'Peak: 8.0 / 10 EP and 800 kg of 1,085 kg',
    );
    expect(screen.getByRole('img', { name: /stop 2: 8.0 \/ 10 EP, 800 kg/ })).toBeVisible();
  });

  it('shows the cost breakdown and marks assumption-based parameters', () => {
    const { container } = renderWithIntl(<CostBreakdown plan={goldPlan} />);
    expect(screen.getByText('€780.00')).toBeVisible(); // revenue
    expect(screen.getByText(/€323\.54 · margin 41\.48 %/)).toBeVisible();
    const rows = [...container.querySelectorAll('tr[data-provenance]')];
    const assumption = rows.filter((row) => row.getAttribute('data-provenance') === 'assumption');
    expect(assumption.length).toBeGreaterThan(0);
    for (const row of assumption) {
      expect(within(row as HTMLElement).getByText(en.plans.costs.basis.assumption)).toBeVisible();
    }
    const fuelPrice = rows.find((row) =>
      row.textContent?.includes(en.plans.costs.param.fuel_price_minor_per_l),
    );
    expect(within(fuelPrice as HTMLElement).getByText(en.plans.costs.basis.source)).toBeVisible();
    expect(screen.getAllByText(en.plans.costs.estimate).length).toBeGreaterThan(0);
  });
});
