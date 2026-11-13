import type { components } from '@/lib/api/schema';
import gold from './gold-001-plan.json';

type RoutePlan = components['schemas']['RoutePlan'];

/**
 * The rank 1 plan of GOLD-001 for each objective, produced by running the real engine on the
 * fixture of apps/api/tests/golden/fixtures/gold_001.py and mapped like `PlanService.get`
 * (specs/golden/GOLD-001.md: 323.54 EUR, 76.601 l, 199.16 kg CO2, two 45 min breaks, one 660 min rest).
 */
export const goldPlans = gold as unknown as Record<'profit' | 'fastest' | 'fuel', RoutePlan>;
export const goldPlan: RoutePlan = goldPlans.profit;

/** The van of driver D1 in the golden case (10 pallet places, 1 085 kg payload). */
export const goldVan = {
  label: 'BUS-01',
  layoutTemplate: 'EUR_MIXED_6X4',
  palletPlaces: 10,
  payloadKg: 1085,
};
