import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { flaggedOffer, threeOffers } from '@/test/fixtures/offers';
import { apiUrl, problem } from '@/test/msw/handlers';
import { offersApi } from '@/test/msw/handlers/offers';
import { server } from '@/test/msw/server';
import { navigation } from '@/test/navigation';
import { renderApp } from '@/test/render-app';
import { OffersScreen } from './offers-screen';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

beforeEach(() => navigation.reset('/offers'));

const o = en.offers;

describe('[AC-FEAT-005-09] offers list', () => {
  it('shows the three list states: skeleton, empty with a way out, and the error with a retry', async () => {
    const user = userEvent.setup();
    offersApi([]);
    server.use(
      http.get(apiUrl('/api/v1/freight-offers'), () => new Promise<never>(() => undefined)),
    );
    const first = renderApp(<OffersScreen />);
    expect(await screen.findByText(o.loading)).toBeInTheDocument();
    expect(screen.getAllByTestId('skeleton-row')).toHaveLength(5);
    first.unmount();

    offersApi([]);
    const second = renderApp(<OffersScreen />);
    expect(await screen.findByRole('heading', { name: o.empty.title })).toBeVisible();
    second.unmount();

    let healthy = false;
    const api = offersApi(threeOffers());
    server.use(
      http.get(apiUrl('/api/v1/freight-offers'), () =>
        healthy
          ? HttpResponse.json({ items: api.offers, nextCursor: null })
          : problem(500, 'INTERNAL_ERROR'),
      ),
    );
    renderApp(<OffersScreen />);
    expect(await screen.findByText(o.error.title)).toBeVisible();
    expect(screen.getByText(/req-test-1/)).toBeVisible();
    healthy = true;
    await user.click(screen.getByRole('button', { name: en.common.tryAgain }));
    expect(await screen.findByRole('table')).toBeVisible();
  });

  it('shows the source, the synthetic badge, the price or "No price", completeness and flags per row', async () => {
    offersApi(threeOffers());
    renderApp(<OffersScreen />);
    const table = await screen.findByRole('table');

    const imported = within(screen.getByText('TC-1001').closest('tr') as HTMLElement);
    expect(imported.getByText(o.source.imported)).toBeVisible();
    expect(imported.getByText(o.synthetic)).toBeVisible();
    expect(imported.getByText('Katowice (PL) → Berlin (DE)')).toBeVisible();
    expect(imported.getByText(/€480\.00/)).toBeVisible();
    expect(imported.getByRole('meter', { name: o.table.data })).toHaveAttribute(
      'aria-valuenow',
      '95',
    );

    const flagged = within(screen.getByText('TC-1002').closest('tr') as HTMLElement);
    expect(flagged.getByText(o.table.noPrice)).toBeVisible();
    expect(flagged.getByText(o.flag.MISSING_REVENUE)).toBeVisible();
    expect(flagged.getByText(o.flag.SUSPICIOUS_TEXT)).toBeVisible();
    // A code the screen has no text for falls back to the generic label, not to the raw code.
    expect(flagged.getByText(o.flag.UNKNOWN)).toBeVisible();
    expect(flagged.queryByText('BRAND_NEW_FLAG')).toBeNull();

    const manual = within(screen.getByText('MAN-0001').closest('tr') as HTMLElement);
    expect(manual.getByText(o.source.manual)).toBeVisible();
    expect(manual.queryByText(o.synthetic)).toBeNull();
    expect(table).toBeVisible();
  });

  it('sends the filters from the URL to the API unchanged', async () => {
    navigation.reset(
      '/offers',
      'source=mock_timocom_v3&originCountry=PL&destinationCity=Berlin&maxWeightKg=1000&maxPallets=8&minCompleteness=0.8&hasPrice=true',
    );
    const api = offersApi(threeOffers());
    renderApp(<OffersScreen />);
    await screen.findByRole('table');
    const query = api.last('GET', /freight-offers$/)?.query;
    expect(query?.get('source')).toBe('mock_timocom_v3');
    expect(query?.get('originCountry')).toBe('PL');
    expect(query?.get('destinationCity')).toBe('Berlin');
    expect(query?.get('maxWeightKg')).toBe('1000');
    expect(query?.get('maxPallets')).toBe('8');
    expect(query?.get('minCompleteness')).toBe('0.8');
    expect(query?.get('hasPrice')).toBe('true');
    // The controls show what the URL says; completeness is a percentage for people.
    expect(screen.getByLabelText(o.filters.minCompleteness)).toHaveValue(80);
    expect(screen.getByLabelText(o.filters.hasPrice)).toBeChecked();
  });

  it('writes a changed filter to the URL and can clear them all', async () => {
    const user = userEvent.setup();
    offersApi(threeOffers());
    renderApp(<OffersScreen />);
    await screen.findByRole('table');

    await user.selectOptions(screen.getByLabelText(o.filters.source), 'manual');
    expect(navigation.replace).toHaveBeenLastCalledWith('/offers?source=manual');

    const completeness = screen.getByLabelText(o.filters.minCompleteness);
    await user.type(completeness, '80');
    fireEvent.blur(completeness);
    expect(navigation.replace).toHaveBeenLastCalledWith('/offers?minCompleteness=0.8');

    await user.click(screen.getByLabelText(o.filters.hasPrice));
    expect(navigation.replace).toHaveBeenLastCalledWith('/offers?hasPrice=true');

    navigation.reset('/offers', 'source=manual');
    renderApp(<OffersScreen />);
    const clear = await screen.findByRole('button', { name: o.filters.clear });
    await user.click(clear);
    expect(navigation.replace).toHaveBeenLastCalledWith('/offers');
  });

  it('opens the details with provenance, missing data and flags; text stays text', async () => {
    const user = userEvent.setup();
    offersApi([flaggedOffer()]);
    const { container } = renderApp(<OffersScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: `Details of TC-1002` }));

    const sheet = await screen.findByRole('dialog', { name: 'Offer TC-1002' });
    const detail = within(sheet);
    expect(detail.getByText(o.detail.suspicious)).toBeVisible();

    // Provenance pills name where each value comes from.
    const provenance = within(
      detail.getByRole('heading', { name: o.detail.provenance }).parentElement as HTMLElement,
    );
    expect(provenance.getByText(o.provenance.inferred)).toHaveAttribute('data-level', 'info');
    expect(provenance.getByText(o.provenance.default)).toHaveAttribute('data-level', 'attention');

    const missing = within(
      detail.getByRole('heading', { name: o.detail.missing }).parentElement as HTMLElement,
    );
    expect(missing.getByText(o.field.revenue)).toBeVisible();
    expect(missing.getByText(o.field.weightKg)).toBeVisible();
    expect(detail.getAllByText(o.flag.MISSING_REVENUE).length).toBeGreaterThan(0);

    // The description is shown exactly as written and never becomes markup.
    expect(detail.getByText(/<script>alert\("x"\)<\/script>/)).toBeVisible();
    expect(container.ownerDocument.querySelector('script[src], script:not([type])')).toBeNull();

    // A long remark is cut, and "Show more" reveals the end.
    expect(detail.queryByText(/END-OF-REMARK/)).toBeNull();
    await user.click(detail.getByRole('button', { name: o.detail.showMore }));
    expect(detail.getByText(/END-OF-REMARK/)).toBeVisible();
    await waitFor(() =>
      expect(detail.getByRole('button', { name: o.detail.showLess })).toBeVisible(),
    );
  });
});
