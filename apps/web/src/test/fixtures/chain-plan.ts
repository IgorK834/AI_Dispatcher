import type { components } from '@/lib/api/schema';
import { goldPlan } from './gold-001';

type RoutePlan = components['schemas']['RoutePlan'];

/**
 * A chain of single orders (A to B, then B to C): never more than one order on board and the van
 * less than half full per kilometre. The other figures are those of the GOLD-001 plan.
 */
export const chainPlan: RoutePlan = {
  ...goldPlan,
  id: '00000000-0000-4000-8000-00000000c001',
  loadFactorEp: '0.2300',
  loadFactorKg: '0.4600',
  maxOrdersOnBoard: 1,
};
