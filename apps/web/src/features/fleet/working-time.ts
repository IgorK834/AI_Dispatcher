import type { components } from '@/lib/api/schema';

export type DriverState = components['schemas']['DriverStateView'];

/**
 * Working-time limits in minutes, copied from FEAT-003 FR-2 for DISPLAY only. The API returns
 * used minutes (DriverView.state) but no remaining time, so the bars subtract from these named
 * constants. Nothing is planned or validated here: the engine owns the rules, and every bar sits
 * next to the legal notice ("planning estimate, no certification of compliance").
 */
export const WORKING_TIME_LIMITS = {
  /** Polish profile: `max_daily_work_min`. */
  dailyWorkMin: 720,
  weeklyWorkMin: 3600,
  /** Regulation 561/2006 driving limits. */
  driveSinceBreakMin: 270,
  dailyDriveMin: 540,
  weeklyDriveMin: 3360,
  twoWeekDriveMin: 5400,
} as const;

export type WorkingTimeBar = { used: number; limit: number; left: number; low: boolean };

/** Red when less than a quarter of the limit is left. */
const LOW_SHARE = 0.25;

function bar(used: number, limit: number): WorkingTimeBar {
  const left = Math.max(0, limit - used);
  return { used, limit, left, low: left < limit * LOW_SHARE };
}

export function workBars(state: DriverState): { day: WorkingTimeBar; week: WorkingTimeBar } {
  return {
    day: bar(state.workTodayMin, WORKING_TIME_LIMITS.dailyWorkMin),
    week: bar(state.workWeekMin, WORKING_TIME_LIMITS.weeklyWorkMin),
  };
}

export function drivingBars(state: DriverState) {
  return {
    sinceBreak: bar(state.driveSinceBreakMin, WORKING_TIME_LIMITS.driveSinceBreakMin),
    day: bar(state.driveTodayMin, WORKING_TIME_LIMITS.dailyDriveMin),
    week: bar(state.driveWeekMin, WORKING_TIME_LIMITS.weeklyDriveMin),
    twoWeek: bar(state.driveWeekMin + state.drivePrevWeekMin, WORKING_TIME_LIMITS.twoWeekDriveMin),
  };
}
