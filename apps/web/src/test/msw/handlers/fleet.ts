import { http, HttpResponse } from 'msw';
import type { components } from '@/lib/api/schema';
import { costProfile, type DriverView, type VehicleView } from '../../fixtures/fleet';
import { apiUrl, problem } from '../handlers';
import { server } from '../server';

type DriverCreate = components['schemas']['DriverCreate'];
type DriverUpdate = components['schemas']['DriverUpdate'];
type VehicleCreate = components['schemas']['VehicleCreate'];
type VehicleUpdate = components['schemas']['VehicleUpdate'];

export type FleetApi = {
  drivers: DriverView[];
  vehicles: VehicleView[];
  assignedDriverIds: string[];
  /** Every request the screen sent, as "METHOD path" plus the JSON body when there is one. */
  calls: { method: string; path: string; query: URLSearchParams; body?: unknown }[];
  count(method: string, pathPattern: RegExp): number;
};

/** An in-memory fleet API with versions, so a test can run create, edit and delete end to end. */
export function fleetApi(
  initial: { drivers?: DriverView[]; vehicles?: VehicleView[]; assigned?: string[] } = {},
): FleetApi {
  const api: FleetApi = {
    drivers: [...(initial.drivers ?? [])],
    vehicles: [...(initial.vehicles ?? [])],
    assignedDriverIds: [...(initial.assigned ?? [])],
    calls: [],
    count: (method, pattern) =>
      api.calls.filter((call) => call.method === method && pattern.test(call.path)).length,
  };
  const note = async (request: Request, body?: unknown) => {
    const url = new URL(request.url);
    api.calls.push({ method: request.method, path: url.pathname, query: url.searchParams, body });
  };
  const page = <T>(items: T[]) => HttpResponse.json({ items, nextCursor: null });
  const now = '2026-11-16T05:00:00Z';

  server.use(
    http.get(apiUrl('/api/v1/drivers'), async ({ request }) => {
      await note(request);
      const query = new URL(request.url).searchParams;
      const city = query.get('homeCity');
      return page(
        api.drivers.filter(
          (item) =>
            (!city || item.homeCity === city) &&
            (query.get('hasVehicle') !== 'true' || item.vehicle),
        ),
      );
    }),
    http.get(apiUrl('/api/v1/drivers/:id'), async ({ request, params }) => {
      await note(request);
      const found = api.drivers.find((item) => item.id === params.id);
      return found ? HttpResponse.json(found) : problem(404, 'NOT_FOUND');
    }),
    http.post(apiUrl('/api/v1/drivers'), async ({ request }) => {
      const body = (await request.json()) as DriverCreate;
      await note(request, body);
      const created: DriverView = {
        ...body,
        id: `00000000-0000-4000-8000-00000000ff${String(api.drivers.length).padStart(2, '0')}`,
        phone: body.phone ?? null,
        isSynthetic: false,
        version: 1,
        createdAt: now,
        updatedAt: now,
      };
      api.drivers.push(created);
      return HttpResponse.json(created, { status: 201 });
    }),
    http.patch(apiUrl('/api/v1/drivers/:id'), async ({ request, params }) => {
      const body = (await request.json()) as DriverUpdate;
      await note(request, body);
      const index = api.drivers.findIndex((item) => item.id === params.id);
      const found = api.drivers[index];
      if (!found) return problem(404, 'NOT_FOUND');
      if (body.version !== found.version) return problem(409, 'VERSION_CONFLICT');
      const { version: _sent, ...changes } = body;
      void _sent;
      const updated = { ...found, ...stripNull(changes), version: found.version + 1 } as DriverView;
      api.drivers[index] = updated;
      return HttpResponse.json(updated);
    }),
    http.delete(apiUrl('/api/v1/drivers/:id'), async ({ request, params }) => {
      await note(request);
      if (api.assignedDriverIds.includes(String(params.id))) {
        return problem(409, 'DRIVER_HAS_ACTIVE_ASSIGNMENT');
      }
      api.drivers = api.drivers.filter((item) => item.id !== params.id);
      return new HttpResponse(null, { status: 204 });
    }),
    http.post(apiUrl('/api/v1/drivers/:id/state'), async ({ request }) => {
      await note(request, await request.clone().json());
      return HttpResponse.json({ id: 'state-new' }, { status: 201 });
    }),
    http.get(apiUrl('/api/v1/vehicles'), async ({ request }) => {
      await note(request);
      return page(api.vehicles);
    }),
    http.get(apiUrl('/api/v1/vehicles/:id'), async ({ request, params }) => {
      await note(request);
      const found = api.vehicles.find((item) => item.id === params.id);
      return found ? HttpResponse.json(found) : problem(404, 'NOT_FOUND');
    }),
    http.post(apiUrl('/api/v1/vehicles'), async ({ request }) => {
      const body = (await request.json()) as VehicleCreate;
      await note(request, body);
      const created: VehicleView = {
        ...body,
        fuel: { ...body.fuel, speedCurve: 'VAN_DEFAULT_V1' },
        innerLengthM: body.innerLengthM ?? null,
        innerWidthM: body.innerWidthM ?? null,
        innerHeightM: body.innerHeightM ?? null,
        id: `00000000-0000-4000-8000-00000000ee${String(api.vehicles.length).padStart(2, '0')}`,
        isSynthetic: false,
        version: 1,
        createdAt: now,
        updatedAt: now,
      } as VehicleView;
      api.vehicles.push(created);
      return HttpResponse.json(created, { status: 201 });
    }),
    http.patch(apiUrl('/api/v1/vehicles/:id'), async ({ request, params }) => {
      const body = (await request.json()) as VehicleUpdate;
      await note(request, body);
      const index = api.vehicles.findIndex((item) => item.id === params.id);
      const found = api.vehicles[index];
      if (!found) return problem(404, 'NOT_FOUND');
      if (body.version !== found.version) return problem(409, 'VERSION_CONFLICT');
      const { version: _sent, ...changes } = body;
      void _sent;
      const updated = {
        ...found,
        ...stripNull(changes),
        version: found.version + 1,
      } as VehicleView;
      api.vehicles[index] = updated;
      return HttpResponse.json(updated);
    }),
    http.delete(apiUrl('/api/v1/vehicles/:id'), async ({ request, params }) => {
      await note(request);
      if (api.drivers.some((item) => item.vehicleId === params.id)) {
        return problem(409, 'VEHICLE_ASSIGNED_TO_DRIVER');
      }
      api.vehicles = api.vehicles.filter((item) => item.id !== params.id);
      return new HttpResponse(null, { status: 204 });
    }),
    http.get(apiUrl('/api/v1/cost-profiles'), async ({ request }) => {
      await note(request);
      return page([costProfile]);
    }),
    http.get(apiUrl('/api/v1/assignments'), async ({ request }) => {
      await note(request);
      return page(api.assignedDriverIds.map((driverId) => ({ id: `a-${driverId}`, driverId })));
    }),
  );
  return api;
}

function stripNull<T extends Record<string, unknown>>(value: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(value).filter(([, entry]) => entry !== undefined),
  ) as Partial<T>;
}
