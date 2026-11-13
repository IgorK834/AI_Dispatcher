import type { components } from '@/lib/api/schema';

export type RoutePlan = components['schemas']['RoutePlan'];
export type PlanStop = components['schemas']['PlanStop'];
export type PlanSummary = components['schemas']['PlanSummary'];
export type Objective = 'profit' | 'fastest' | 'fuel';
export const OBJECTIVES: Objective[] = ['profit', 'fastest', 'fuel'];

/** What the load plan and the occupancy chart need to know about the van. */
export type VanLimits = {
  label: string;
  layoutTemplate: string;
  palletPlaces: number;
  payloadKg: number;
};

/** Plan stops carry no time zone; every demo route lies in the CET zone, as on the fleet screen. */
export const PLAN_TIME_ZONE = 'Europe/Warsaw';

export const isAction = (stop: PlanStop) => stop.kind === 'PICKUP' || stop.kind === 'DELIVERY';
