import { http, HttpResponse } from 'msw';
import type { components } from '@/lib/api/schema';
import { costProfile } from '../../fixtures/fleet';
import { apiUrl } from '../handlers';
import { server } from '../server';

type GenerateInput = components['schemas']['GenerateInput'];

export type AdminApi = {
  generates: GenerateInput[];
  resets: number;
};

const counts = {
  importBatchId: '00000000-0000-4000-8000-0000000b0001',
  drivers: 5,
  vehicles: 5,
  offers: { imported: 147, updated: 0, unchanged: 0, failed: 3 },
};

/** The admin endpoints of FEAT-002 section 6.7 and the cost profile list the admin screen reads. */
export function adminApi(): AdminApi {
  const api: AdminApi = { generates: [], resets: 0 };
  server.use(
    http.post(apiUrl('/api/v1/admin/demo-data/generate'), async ({ request }) => {
      api.generates.push((await request.json()) as GenerateInput);
      return HttpResponse.json(counts);
    }),
    http.post(apiUrl('/api/v1/admin/demo-data/reset'), () => {
      api.resets += 1;
      return HttpResponse.json(counts);
    }),
    http.get(apiUrl('/api/v1/cost-profiles'), () =>
      HttpResponse.json({
        items: [
          {
            ...costProfile,
            perDiem: { PL: 1059 },
            tolls: { annualVignettes: ['AT', 'CZ'], perKm: { PL: 0, FR: 12 } },
            fxRates: { PLN: '4.25' },
            provenance: {
              fuel_price_minor_per_l: 'source',
              driver_cost_minor_per_hour: 'assumption',
              vehicle_cost_minor_per_km: 'assumption',
              accommodation_minor: 'assumption',
              per_diem: 'source',
              'tolls.PL': 'source',
              'tolls.FR': 'assumption',
              'tolls.annual_vignettes': 'assumption',
              fx_rates: 'assumption',
              min_profit_minor: 'assumption',
              min_margin_pct: 'assumption',
            },
          },
        ],
        nextCursor: null,
      }),
    ),
  );
  return api;
}
