import { http, HttpResponse } from 'msw';
import type { components } from '@/lib/api/schema';
import type { OfferView } from '../../fixtures/offers';
import { apiUrl, problem } from '../handlers';
import { server } from '../server';

type OfferCreate = components['schemas']['FreightOfferCreate'];
type OfferUpdate = components['schemas']['FreightOfferUpdate'];

export type OffersApi = {
  offers: OfferView[];
  /** Every request the screen sent, with its query and JSON body. */
  calls: { method: string; path: string; query: URLSearchParams; body?: unknown }[];
  count(method: string, pathPattern: RegExp): number;
  last(method: string, pathPattern: RegExp): { query: URLSearchParams; body?: unknown } | undefined;
};

/** An in-memory freight-offers API: filters, versions and the provider read-only rule. */
export function offersApi(initial: OfferView[] = []): OffersApi {
  const api: OffersApi = {
    offers: [...initial],
    calls: [],
    count: (method, pattern) =>
      api.calls.filter((call) => call.method === method && pattern.test(call.path)).length,
    last: (method, pattern) =>
      api.calls.filter((call) => call.method === method && pattern.test(call.path)).at(-1),
  };
  const note = (request: Request, body?: unknown) => {
    const url = new URL(request.url);
    api.calls.push({ method: request.method, path: url.pathname, query: url.searchParams, body });
  };
  const now = '2026-11-16T05:00:00Z';

  server.use(
    http.get(apiUrl('/api/v1/freight-offers'), ({ request }) => {
      note(request);
      const query = new URL(request.url).searchParams;
      const source = query.get('source');
      const maxWeight = query.get('maxWeightKg');
      return HttpResponse.json({
        items: api.offers.filter(
          (offer) =>
            (!source || offer.source === source) &&
            (query.get('hasPrice') !== 'true' || offer.revenue) &&
            (!maxWeight || (offer.weightKg ?? 0) <= Number(maxWeight)),
        ),
        nextCursor: null,
      });
    }),
    http.get(apiUrl('/api/v1/freight-offers/:id'), ({ request, params }) => {
      note(request);
      const found = api.offers.find((offer) => offer.id === params.id);
      return found ? HttpResponse.json(found) : problem(404, 'NOT_FOUND');
    }),
    http.post(apiUrl('/api/v1/freight-offers'), async ({ request }) => {
      const body = (await request.json()) as OfferCreate;
      note(request, body);
      const created: OfferView = {
        ...body,
        id: `00000000-0000-4000-8000-0000000b${String(api.offers.length).padStart(4, '0')}`,
        sourceOfferId: `MAN-${String(api.offers.length + 1).padStart(4, '0')}`,
        source: 'manual',
        status: 'open',
        description: body.description,
        loadingLengthM: body.loadingLengthM == null ? null : String(body.loadingLengthM),
        stops: body.stops.map((stop, sequence) => ({
          ...stop,
          sequence,
          serviceMinutes: stop.serviceMinutes ?? 30,
          timezone: 'Europe/Warsaw',
          provenance: {},
        })),
        completenessScore: 1,
        fieldProvenance: {},
        missingFields: [],
        qualityFlags: [],
        isSynthetic: false,
        version: 1,
        createdAt: now,
        updatedAt: now,
      };
      api.offers.push(created);
      return HttpResponse.json(created, { status: 201 });
    }),
    http.patch(apiUrl('/api/v1/freight-offers/:id'), async ({ request, params }) => {
      const body = (await request.json()) as OfferUpdate;
      note(request, body);
      const index = api.offers.findIndex((offer) => offer.id === params.id);
      const found = api.offers[index];
      if (!found) return problem(404, 'NOT_FOUND');
      if (found.source !== 'manual') return problem(409, 'PROVIDER_OFFER_READ_ONLY');
      if (body.version !== found.version) return problem(409, 'VERSION_CONFLICT');
      const { version: _sent, stops, ...changes } = body;
      void _sent;
      const updated = {
        ...found,
        ...Object.fromEntries(Object.entries(changes).filter(([, value]) => value !== undefined)),
        stops: stops
          ? stops.map((stop, sequence) => ({
              ...stop,
              sequence,
              serviceMinutes: stop.serviceMinutes ?? 30,
              timezone: 'Europe/Warsaw',
              provenance: {},
            }))
          : found.stops,
        version: found.version + 1,
      } as OfferView;
      api.offers[index] = updated;
      return HttpResponse.json(updated);
    }),
    http.delete(apiUrl('/api/v1/freight-offers/:id'), ({ request, params }) => {
      note(request);
      const found = api.offers.find((offer) => offer.id === params.id);
      if (!found) return problem(404, 'NOT_FOUND');
      if (found.source !== 'manual') return problem(409, 'PROVIDER_OFFER_READ_ONLY');
      api.offers = api.offers.filter((offer) => offer.id !== params.id);
      return new HttpResponse(null, { status: 204 });
    }),
  );
  return api;
}
