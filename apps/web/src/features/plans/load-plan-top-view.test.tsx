import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import en from '../../../messages/en.json';
import { goldPlan, goldVan } from '@/test/fixtures/gold-001';
import { renderWithIntl } from '@/test/render';
import { LoadPlanTopView } from './load-plan-top-view';

const t = en.plans.topView;

describe('[AC-FEAT-005-26] top-view load plan', () => {
  it('occupies 4, 8, 4, 6, 2 and 0 places after stops 1 to 6, each with place id, offer and kg', async () => {
    const user = userEvent.setup();
    const { container } = renderWithIntl(<LoadPlanTopView stops={goldPlan.stops} van={goldVan} />);
    const group = screen.getByRole('group', { name: t.selector });
    const counts: number[] = [];
    const loads: [string, string][] = [
      ['380 kg of 1,085 kg', '4.0 / 10 EP'],
      ['800 kg of 1,085 kg', '8.0 / 10 EP'],
      ['420 kg of 1,085 kg', '4.0 / 10 EP'],
      ['620 kg of 1,085 kg', '6.0 / 10 EP'],
      ['200 kg of 1,085 kg', '2.0 / 10 EP'],
      ['0 kg of 1,085 kg', '0.0 / 10 EP'],
    ];
    for (const [index, [kg, eq]] of loads.entries()) {
      await user.click(within(group).getByRole('button', { name: String(index + 1) }));
      expect(within(group).getByRole('button', { name: String(index + 1) })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
      const occupied = container.querySelectorAll('[data-place][data-occupied="true"]');
      counts.push(occupied.length);
      for (const cell of occupied) {
        expect(cell.textContent).toMatch(/^[TL]\d/);
        expect(cell.textContent).toMatch(/\d+ kg/);
        expect(cell.textContent).toMatch(/Offer [ABC]/);
      }
      const free = container.querySelectorAll('[data-place][data-occupied="false"]');
      expect(free).toHaveLength(10 - occupied.length);
      for (const cell of free) expect(cell).toHaveTextContent(t.free);
      expect(screen.getByText(kg)).toBeVisible();
      expect(screen.getAllByText(eq).length).toBeGreaterThan(0);
    }
    expect(counts).toEqual([4, 8, 4, 6, 2, 0]);
  });

  it('shows the notice, the drawing alternative and a keyboard-operable selector', async () => {
    const user = userEvent.setup();
    renderWithIntl(<LoadPlanTopView stops={goldPlan.stops} van={goldVan} />);
    expect(screen.getByText(t.illustrative)).toBeVisible();
    const drawing = screen.getByRole('img', { name: /Van floor from above/ });
    expect(drawing).toHaveAccessibleName(/8 of 10 pallet places used, 800 kg of 1,085 kg/);
    // Peak first: the selected button is stop 2 (8 EP), and Start shows an empty van.
    expect(screen.getByRole('button', { name: '2' })).toHaveAttribute('aria-pressed', 'true');
    screen.getByRole('button', { name: t.start }).focus();
    await user.keyboard('{Enter}');
    expect(screen.getByRole('button', { name: t.start })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '2' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('puts the third offer on T1 and T2', async () => {
    const user = userEvent.setup();
    const { container } = renderWithIntl(<LoadPlanTopView stops={goldPlan.stops} van={goldVan} />);
    await user.click(screen.getByRole('button', { name: '5' }));
    const third = [...container.querySelectorAll('[data-place][data-occupied="true"]')]
      .filter((cell) => cell.textContent?.includes('Offer C'))
      .map((cell) => cell.getAttribute('data-place'));
    expect(third).toEqual(['T1', 'T2']);
  });

  it('draws no floor for DECLARED_ONLY and shows only the counter', () => {
    const { container } = renderWithIntl(
      <LoadPlanTopView
        stops={goldPlan.stops}
        van={{ ...goldVan, layoutTemplate: 'DECLARED_ONLY', palletPlaces: 9 }}
      />,
    );
    expect(screen.queryByRole('img', { name: /Van floor/ })).toBeNull();
    expect(container.querySelector('[data-place]')).toBeNull();
    expect(screen.getByText('8.0 / 9 EP')).toBeVisible();
    expect(screen.getByText(t.declaredOnly)).toBeVisible();
  });
});
