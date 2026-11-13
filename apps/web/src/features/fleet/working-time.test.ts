import { describe, expect, it } from 'vitest';
import { drivingBars, workBars, WORKING_TIME_LIMITS, type DriverState } from './working-time';

const state = (overrides: Partial<DriverState>): DriverState => ({
  id: 's1',
  driverId: 'd1',
  validFrom: '2026-11-16T05:00:00Z',
  source: 'user',
  availableFrom: '2026-11-16T05:00:00Z',
  currentLat: 50,
  currentLon: 19,
  workTodayMin: 0,
  driveTodayMin: 0,
  workSinceBreakMin: 0,
  driveSinceBreakMin: 0,
  workWeekMin: 0,
  driveWeekMin: 0,
  drivePrevWeekMin: 0,
  ...overrides,
});

describe('working-time bars (display only)', () => {
  it('subtracts the used minutes from the FEAT-003 limits', () => {
    const { day, week } = workBars(state({ workTodayMin: 480, workWeekMin: 3000 }));
    expect(day).toEqual({ used: 480, limit: 720, left: 240, low: false });
    expect(week).toEqual({ used: 3000, limit: 3600, left: 600, low: true });
  });

  it('never goes below zero and flags a quarter or less as low', () => {
    expect(workBars(state({ workTodayMin: 900 })).day.left).toBe(0);
    expect(workBars(state({ workTodayMin: 540 })).day.low).toBe(false); // exactly 25 % left
    expect(workBars(state({ workTodayMin: 541 })).day.low).toBe(true);
  });

  it('adds the previous week for the two-week driving limit', () => {
    const bars = drivingBars(
      state({
        driveSinceBreakMin: 200,
        driveTodayMin: 300,
        driveWeekMin: 2000,
        drivePrevWeekMin: 1500,
      }),
    );
    expect(bars.sinceBreak.left).toBe(70);
    expect(bars.day.left).toBe(240);
    expect(bars.week.left).toBe(1360);
    expect(bars.twoWeek).toMatchObject({ used: 3500, left: 1900 });
  });

  it('keeps the limits equal to the specification', () => {
    expect(WORKING_TIME_LIMITS).toEqual({
      dailyWorkMin: 720,
      weeklyWorkMin: 3600,
      driveSinceBreakMin: 270,
      dailyDriveMin: 540,
      weeklyDriveMin: 3360,
      twoWeekDriveMin: 5400,
    });
  });
});
