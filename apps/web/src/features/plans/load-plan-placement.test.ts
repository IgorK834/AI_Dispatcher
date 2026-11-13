import { describe, expect, it } from 'vitest';
import { goldPlan } from '@/test/fixtures/gold-001';
import { lane, loadPlan, placesFor } from './load-plan-placement';

describe('placesFor', () => {
  it('numbers the places from the rear doors, transverse row first', () => {
    expect(placesFor('EUR_MIXED_6X4').map((place) => place.id)).toEqual([
      'T1',
      'T2',
      'T3',
      'T4',
      'T5',
      'T6',
      'L1',
      'L2',
      'L3',
      'L4',
    ]);
    expect(placesFor('EUR_MIXED_5X3').map((place) => place.id)).toEqual([
      'T1',
      'T2',
      'T3',
      'T4',
      'T5',
      'L1',
      'L2',
      'L3',
    ]);
    expect(placesFor('DECLARED_ONLY')).toEqual([]);
  });
});

describe('loadPlan on GOLD-001', () => {
  const plan = loadPlan(goldPlan.stops, 'EUR_MIXED_6X4');
  const taken = (step: number) =>
    plan.steps[step]?.places.filter((entry) => entry.occupant).map((entry) => entry.place.id);

  it('has the start and one step per pickup or delivery', () => {
    expect(plan.steps).toHaveLength(7);
    expect(taken(0)).toEqual([]);
  });

  it('occupies 4, 8, 4, 6, 2 and 0 places after stops 1 to 6', () => {
    expect([1, 2, 3, 4, 5, 6].map((step) => taken(step)?.length)).toEqual([4, 8, 4, 6, 2, 0]);
  });

  it('puts the first offer on T1-T4, the second on T5, T6, L1, L2', () => {
    expect(taken(1)).toEqual(['T1', 'T2', 'T3', 'T4']);
    expect(taken(2)).toEqual(['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'L1', 'L2']);
  });

  it('frees the places of a delivered offer; pallets on board never move', () => {
    // After delivering A: B stays on T5, T6, L1, L2.
    expect(taken(3)).toEqual(['T5', 'T6', 'L1', 'L2']);
  });

  it('places the third offer on the lowest free places, T1-T2 and not L3-L4', () => {
    expect(taken(4)).toEqual(['T1', 'T2', 'T5', 'T6', 'L1', 'L2']);
    const third = plan.steps[4]?.places.filter((entry) => entry.occupant?.tag === 'C');
    expect(third?.map((entry) => entry.place.id)).toEqual(['T1', 'T2']);
  });

  it('divides the kilograms of an offer evenly over its places', () => {
    expect(plan.steps[1]?.places[0]?.occupant?.kg).toBe(95); // 380 kg / 4 places
    expect(plan.steps[2]?.places[4]?.occupant?.kg).toBe(105); // 420 kg / 4 places
    expect(plan.steps[4]?.places[0]?.occupant?.kg).toBe(100); // 200 kg / 2 places
  });

  it('reports the load the plan states after each stop', () => {
    expect(plan.steps.map((step) => step.eq)).toEqual([0, 4, 8, 4, 6, 2, 0]);
    expect(plan.steps.map((step) => step.kg)).toEqual([0, 380, 800, 420, 620, 200, 0]);
  });

  it('tags the offers in pickup order and gives each the next tint', () => {
    expect(plan.offers.map((offer) => [offer.tag, offer.tint])).toEqual([
      ['A', 0],
      ['B', 1],
      ['C', 2],
    ]);
  });

  it('repeats the tints after the fifth offer', () => {
    const stops = Array.from({ length: 6 }, (_, index) => ({
      ...goldPlan.stops[1]!,
      sequence: index,
      offerId: `offer-${index}`,
      loadPalletEqAfter: String(index + 1),
      loadKgAfter: (index + 1) * 10,
    }));
    const six = loadPlan(stops, 'EUR_MIXED_6X4');
    expect(six.offers.map((offer) => offer.tint)).toEqual([0, 1, 2, 3, 4, 0]);
  });

  it('shows no places for DECLARED_ONLY but still follows the load', () => {
    const declared = loadPlan(goldPlan.stops, 'DECLARED_ONLY');
    expect(declared.steps[2]?.places).toEqual([]);
    expect(declared.steps[2]?.eq).toBe(8);
  });
});

describe('lane', () => {
  it('joins consecutive places and lists the others', () => {
    expect(lane(['T1', 'T2', 'T3', 'T4'], 'EUR_MIXED_6X4')).toBe('T1–T4');
    expect(lane(['T5', 'T6', 'L1', 'L2'], 'EUR_MIXED_6X4')).toBe('T5–L2');
    expect(lane(['T1', 'T5'], 'EUR_MIXED_6X4')).toBe('T1, T5');
    expect(lane(['L1'], 'EUR_MIXED_6X4')).toBe('L1');
  });
});
