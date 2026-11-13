import { describe, expect, it } from 'vitest';
import {
  formatCo2,
  formatDateTime,
  formatDistance,
  formatDuration,
  formatFuel,
  formatMass,
  formatMoney,
  formatPalletEquivalents,
} from './index';

const NBSP = ' ';

describe('[AC-FEAT-005-24] formatting through lib/format', () => {
  it('formats 123450 minor EUR in both locales', () => {
    expect(formatMoney(123450, 'EUR', 'en')).toBe('€1,234.50');
    // Polish uses a no-break space as the group separator and before the currency sign.
    expect(formatMoney(123450, 'EUR', 'pl')).toBe(`1${NBSP}234,50${NBSP}€`);
  });

  it('formats distances: whole kilometres in lists, one decimal in details', () => {
    expect(formatDistance(624.81, 'en')).toBe('625 km');
    expect(formatDistance(624.81, 'pl')).toBe('625 km');
    expect(formatDistance(624.81, 'en', 'detail')).toBe('624.8 km');
    expect(formatDistance(624.81, 'pl', 'detail')).toBe('624,8 km');
  });

  it('formats durations as hours and minutes', () => {
    expect(formatDuration(805)).toBe('13 h 25 min');
    expect(formatDuration(625)).toBe('10 h 25 min');
    expect(formatDuration(45)).toBe('45 min');
    expect(formatDuration(120)).toBe('2 h 0 min');
  });

  it('formats a stop time in the stop time zone with the zone abbreviation', () => {
    expect(formatDateTime('2026-11-16T05:00:00Z', 'Europe/Warsaw', 'en')).toBe(
      'Mon 16 Nov, 06:00 CET',
    );
    expect(formatDateTime('2026-11-16T05:00:00Z', 'Europe/Warsaw', 'pl')).toBe(
      'pon. 16 lis, 06:00 CET',
    );
    // Summer time and another zone: the abbreviation follows the zone, not the browser.
    expect(formatDateTime('2026-07-16T04:00:00Z', 'Europe/Warsaw', 'en')).toBe(
      'Thu 16 Jul, 06:00 CEST',
    );
    expect(formatDateTime('2026-11-16T05:00:00Z', 'Europe/London', 'en')).toBe(
      'Mon 16 Nov, 05:00 GMT',
    );
  });

  it('formats mass, pallet equivalents, fuel and CO2 with units', () => {
    expect(formatMass(1085, 'en')).toBe('1,085 kg');
    expect(formatMass(1085, 'pl')).toBe(`1${NBSP}085 kg`);
    expect(formatPalletEquivalents(6, 10, 'en')).toBe('6.0 / 10 EP');
    expect(formatPalletEquivalents(8, 10, 'pl')).toBe('8,0 / 10 EP');
    expect(formatFuel(76.601, 'en')).toBe('76.6 l');
    expect(formatFuel(76.601, 'pl')).toBe('76,6 l');
    expect(formatCo2(199.16, 'en')).toBe('199 kg CO₂');
  });
});
