import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { importedOffer, manualOffer, threeOffers } from '@/test/fixtures/offers';
import { apiUrl, problem } from '@/test/msw/handlers';
import { offersApi } from '@/test/msw/handlers/offers';
import { server } from '@/test/msw/server';
import { navigation } from '@/test/navigation';
import { renderApp } from '@/test/render-app';
import { OffersScreen } from './offers-screen';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

beforeEach(() => navigation.reset('/offers'));

const o = en.offers;
const f = o.form;

type User = ReturnType<typeof userEvent.setup>;

/** The datetime-local controls take a value change, not typing, in jsdom. */
const setWindow = (label: string, value: string, index = 0) =>
  fireEvent.change(screen.getAllByLabelText(label)[index] as HTMLElement, { target: { value } });

async function fillValidOffer(user: User) {
  await user.type(screen.getByLabelText(f.description), 'Four pallets of paper');
  await user.type(screen.getByLabelText(f.weightKg), '640');
  await user.type(screen.getByLabelText(f.palletCount), '4');
  await user.type(screen.getByLabelText(f.price), '312,50');
  const [loadingCity, unloadingCity] = screen.getAllByLabelText(f.city);
  await user.type(loadingCity as HTMLElement, 'Opole');
  await user.type(unloadingCity as HTMLElement, 'Brno');
  const [, unloadingCountry] = screen.getAllByLabelText(f.country);
  await user.clear(unloadingCountry as HTMLElement);
  await user.type(unloadingCountry as HTMLElement, 'CZ');
  setWindow(f.windowStart, '2026-11-17T06:00', 0);
  setWindow(f.windowEnd, '2026-11-17T10:00', 0);
  setWindow(f.windowStart, '2026-11-17T13:00', 1);
  setWindow(f.windowEnd, '2026-11-17T17:00', 1);
}

describe('[AC-FEAT-005-10] manual offers: create, edit, delete', () => {
  it('creates a manual offer with two stops and shows it in the list', async () => {
    const user = userEvent.setup();
    const api = offersApi(threeOffers());
    renderApp(<OffersScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: o.addOffer }));
    await screen.findByRole('dialog', { name: f.createTitle });
    await fillValidOffer(user);
    await user.click(screen.getByRole('button', { name: en.common.save }));

    await waitFor(() => expect(api.count('POST', /freight-offers$/)).toBe(1));
    const body = api.last('POST', /freight-offers$/)?.body as Record<string, unknown>;
    expect(body).toMatchObject({
      description: 'Four pallets of paper',
      weightKg: 640,
      palletCount: 4,
      palletType: 'EUR_1200x800',
      requiredBodyTypes: ['CURTAIN_SIDER'],
      revenue: { amountMinor: 31250, currency: 'EUR' },
      publicRemark: null,
    });
    const stops = body.stops as Record<string, unknown>[];
    expect(stops).toHaveLength(2);
    expect(stops[0]).toMatchObject({ stopType: 'LOADING', city: 'Opole', countryCode: 'PL' });
    expect(stops[1]).toMatchObject({ stopType: 'UNLOADING', city: 'Brno', countryCode: 'CZ' });
    expect(stops[0]?.windowStart).toBe(new Date('2026-11-17T06:00').toISOString());

    expect(await screen.findByText(o.toast.saved)).toBeVisible();
    expect(await screen.findByText('MAN-0004')).toBeVisible();
  });

  it('validates before sending: weight 0, window order, missing city', async () => {
    const user = userEvent.setup();
    const api = offersApi(threeOffers());
    renderApp(<OffersScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: o.addOffer }));
    await screen.findByRole('dialog', { name: f.createTitle });
    await user.type(screen.getByLabelText(f.description), 'Paper');
    await user.type(screen.getByLabelText(f.weightKg), '0');
    await user.type(screen.getByLabelText(f.palletCount), '40');
    setWindow(f.windowStart, '2026-11-17T10:00', 0);
    setWindow(f.windowEnd, '2026-11-17T06:00', 0);
    await user.click(screen.getByRole('button', { name: en.common.save }));

    expect(await screen.findByText(o.validation.weightRange)).toBeVisible();
    expect(screen.getByText(o.validation.palletsRange)).toBeVisible();
    expect(screen.getByText(o.validation.windowOrder)).toBeVisible();
    expect(screen.getAllByText(o.validation.cityRequired)).toHaveLength(2);
    expect(screen.getByLabelText(f.weightKg)).toHaveAttribute('aria-invalid', 'true');
    expect(api.count('POST', /freight-offers$/)).toBe(0);
  });

  it('edits a manual offer, sending the version it loaded', async () => {
    const user = userEvent.setup();
    const api = offersApi(threeOffers());
    renderApp(<OffersScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: 'Edit MAN-0001' }));
    const sheet = await screen.findByRole('dialog', { name: f.editTitle });
    const weight = within(sheet).getByLabelText(f.weightKg);
    expect(weight).toHaveValue('400');
    await user.clear(weight);
    await user.type(weight, '450');
    await user.click(within(sheet).getByRole('button', { name: en.common.save }));

    await waitFor(() => expect(api.count('PATCH', /freight-offers\//)).toBe(1));
    expect(api.last('PATCH', /freight-offers\//)?.body).toMatchObject({
      weightKg: 450,
      version: 2,
      revenue: { amountMinor: 25000, currency: 'EUR' },
    });
    expect(api.last('PATCH', /freight-offers\//)?.body).toHaveProperty('stops');
    expect(await screen.findByText(o.toast.saved)).toBeVisible();
    await waitFor(() =>
      expect(api.offers.find((offer) => offer.sourceOfferId === 'MAN-0001')?.version).toBe(3),
    );
  });

  it('keeps the input and offers a reload after a version conflict', async () => {
    const user = userEvent.setup();
    const api = offersApi(threeOffers());
    renderApp(<OffersScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: 'Edit MAN-0001' }));
    const sheet = await screen.findByRole('dialog', { name: f.editTitle });
    // Someone else saved first: the server is now one version ahead.
    api.offers = api.offers.map((offer) =>
      offer.sourceOfferId === 'MAN-0001' ? { ...offer, version: 3 } : offer,
    );
    const weight = within(sheet).getByLabelText(f.weightKg);
    await user.clear(weight);
    await user.type(weight, '450');
    await user.click(within(sheet).getByRole('button', { name: en.common.save }));

    expect(await within(sheet).findByText(o.conflict.title)).toBeVisible();
    expect(weight).toHaveValue('450');
    await user.click(within(sheet).getByRole('button', { name: o.conflict.reload }));
    await waitFor(() => expect(within(sheet).queryByText(o.conflict.title)).toBeNull());
    await user.click(within(sheet).getByRole('button', { name: en.common.save }));
    await waitFor(() =>
      expect(api.last('PATCH', /freight-offers\//)?.body).toMatchObject({ version: 3 }),
    );
  });

  it('names the offer in the delete dialog, sends nothing until confirmed, then removes it', async () => {
    const user = userEvent.setup();
    const api = offersApi(threeOffers());
    renderApp(<OffersScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: 'Delete MAN-0001' }));
    const dialog = await screen.findByRole('alertdialog', { name: 'Delete offer MAN-0001?' });
    expect(api.count('DELETE', /freight-offers\//)).toBe(0);
    await user.click(within(dialog).getByRole('button', { name: o.delete.confirm }));
    await waitFor(() => expect(api.count('DELETE', /freight-offers\//)).toBe(1));
    expect(await screen.findByText(o.toast.deleted)).toBeVisible();
    await waitFor(() => expect(screen.queryByText('MAN-0001')).toBeNull());
  });

  it('explains a refused delete inside the dialog', async () => {
    const user = userEvent.setup();
    offersApi([manualOffer()]);
    server.use(
      http.delete(apiUrl('/api/v1/freight-offers/:id'), () =>
        problem(409, 'PROVIDER_OFFER_READ_ONLY'),
      ),
    );
    renderApp(<OffersScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: 'Delete MAN-0001' }));
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: o.delete.confirm }));
    expect(await within(dialog).findByText(o.delete.blockedTitle)).toBeVisible();
    expect(within(dialog).getByText(en.errors.PROVIDER_OFFER_READ_ONLY)).toBeVisible();
  });

  it('has no edit or delete on an imported offer, only a lock that says why', async () => {
    const user = userEvent.setup();
    offersApi([importedOffer()]);
    renderApp(<OffersScreen />);
    await screen.findByRole('table');
    expect(screen.queryByRole('button', { name: /^Edit / })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Delete / })).toBeNull();
    const lock = screen.getByRole('button', { name: 'Imported offer TC-1001 is read-only' });
    await user.hover(lock);
    expect(await screen.findByRole('tooltip')).toHaveTextContent(o.readOnly);
  });
});
