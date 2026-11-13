import type { components } from '@/lib/api/schema';

export type DriverView = components['schemas']['DriverView'];
export type VehicleView = components['schemas']['VehicleView'];
export type CostProfileView = components['schemas']['CostProfileView'];
export type DriverStateView = components['schemas']['DriverStateView'];

const STAMP = '2026-11-16T05:00:00Z';

export const costProfile: CostProfileView = {
  id: '99999999-9999-4999-8999-999999999999',
  name: 'DEMO-DEFAULT',
  currency: 'EUR',
  fuelPriceMinorPerL: 181,
  driverCostMinorPerHour: 1400,
  vehicleCostMinorPerKm: 12,
  accommodationMinor: 5500,
  perDiem: {},
  tolls: { annualVignettes: [], perKm: {} },
  fxRates: {},
  minProfitMinor: 0,
  minMarginPct: '0',
  provenance: {},
  isSynthetic: true,
  version: 1,
  createdAt: STAMP,
  updatedAt: STAMP,
};

export function vehicle(index: number, overrides: Partial<VehicleView> = {}): VehicleView {
  return {
    id: `00000000-0000-4000-8000-0000000001${String(index).padStart(2, '0')}`,
    label: `BUS-0${index}`,
    vehicleType: 'VEHICLE_UP_TO_3_5_T',
    bodyType: 'CURTAIN_SIDER',
    palletPlaces: 10,
    layoutTemplate: 'EUR_MIXED_6X4',
    sideAccess: 'BOTH',
    payloadKg: 1085,
    gvwKg: 3500,
    sleeperCab: index === 2,
    fuel: {
      lPer100kmEmptyAt90: '11',
      lPer100kmFullAt90: '13',
      provenance: 'assumption',
      speedCurve: 'VAN_DEFAULT_V1',
    },
    costProfileId: costProfile.id,
    isSynthetic: true,
    version: 1,
    createdAt: STAMP,
    updatedAt: STAMP,
    ...overrides,
  };
}

export function state(driverId: string, overrides: Partial<DriverStateView> = {}): DriverStateView {
  return {
    id: `state-${driverId}`,
    driverId,
    validFrom: STAMP,
    source: 'user',
    availableFrom: STAMP,
    currentCity: null,
    currentLat: 50.26,
    currentLon: 19.02,
    workTodayMin: 0,
    driveTodayMin: 0,
    workSinceBreakMin: 0,
    driveSinceBreakMin: 0,
    workWeekMin: 0,
    driveWeekMin: 0,
    drivePrevWeekMin: 0,
    ...overrides,
  };
}

const BASES = ['Katowice', 'Wrocław', 'Poznań', 'Łódź', 'Kraków'];
const NAMES = ['Paweł Kurek', 'Ewa Sowa', 'Marta Lis-Wrona', 'Jan Bielak', 'Kamil Dąb'];

/** Five synthetic drivers; D3 has the least weekly time left. */
export function driver(index: number, overrides: Partial<DriverView> = {}): DriverView {
  const id = `00000000-0000-4000-8000-0000000000${String(index).padStart(2, '0')}`;
  const van = vehicle(index);
  const weekly = [0, 1260, 2070, 720, 1815][index - 1] ?? 0;
  return {
    id,
    name: NAMES[index - 1] ?? `Driver ${index}`,
    phone: `+48 000 000 10${index}`,
    homeCity: BASES[index - 1] ?? 'Katowice',
    homeCountry: 'PL',
    homeLat: 50.26,
    homeLon: 19.02,
    defaultRulesProfile: 'pl_domestic_employee_v1',
    vehicleId: van.id,
    vehicle: van,
    state: state(id, { workTodayMin: 0, workWeekMin: weekly, driveWeekMin: weekly - 400 }),
    isSynthetic: true,
    version: 3,
    createdAt: STAMP,
    updatedAt: STAMP,
    ...overrides,
  };
}

export const fiveDrivers = () => [1, 2, 3, 4, 5].map((index) => driver(index));
