import { isAction, type PlanStop } from './types';

/**
 * Illustrative pallet positions (docs/design/README.md section 7.2). The engine checks pallet
 * places and mass, not positions, so the browser derives them from the load deltas of the stops.
 */

export type Place = { id: string; row: 'T' | 'L' };

const LAYOUTS: Record<string, { transverse: number; longitudinal: number }> = {
  EUR_MIXED_6X4: { transverse: 6, longitudinal: 4 },
  EUR_MIXED_5X3: { transverse: 5, longitudinal: 3 },
};

/** Places from the rear doors towards the cab, the transverse row first. */
export function placesFor(layout: string): Place[] {
  const shape = LAYOUTS[layout];
  if (!shape) return [];
  return [
    ...Array.from({ length: shape.transverse }, (_, index): Place => ({
      id: `T${index + 1}`,
      row: 'T',
    })),
    ...Array.from({ length: shape.longitudinal }, (_, index): Place => ({
      id: `L${index + 1}`,
      row: 'L',
    })),
  ];
}

export type Occupant = { offerId: string; tag: string; tint: number; kg: number };

export type LoadStep = {
  /** 0 is the start; k is the state after the k-th pickup or delivery. */
  step: number;
  stop: PlanStop | null;
  /** One entry per place of the layout, in place order; null is a free place. */
  places: { place: Place; occupant: Occupant | null }[];
  /** Pallet equivalents and kilograms on board, as the plan states them after this stop. */
  eq: number;
  kg: number;
};

export type LoadPlan = {
  steps: LoadStep[];
  /** Offers in pickup order with their tag ("A", "B", ...) and cargo tint index. */
  offers: { offerId: string; tag: string; tint: number }[];
};

const tagFor = (index: number) => (index < 26 ? String.fromCharCode(65 + index) : `A${index - 25}`);

export function loadPlan(stops: PlanStop[], layout: string): LoadPlan {
  const places = placesFor(layout);
  const board: (Occupant | null)[] = places.map(() => null);
  const offers: LoadPlan['offers'] = [];
  const snapshot = (step: number, stop: PlanStop | null, eq: number, kg: number): LoadStep => ({
    step,
    stop,
    places: places.map((place, index) => ({ place, occupant: board[index] ?? null })),
    eq,
    kg,
  });

  const steps: LoadStep[] = [snapshot(0, null, 0, 0)];
  stops.forEach((stop, index) => {
    if (!isAction(stop)) return;
    const before = stops[index - 1];
    const eqBefore = before ? Number(before.loadPalletEqAfter) : 0;
    const kgBefore = before ? before.loadKgAfter : 0;
    if (stop.kind === 'PICKUP' && stop.offerId) {
      let entry = offers.find((offer) => offer.offerId === stop.offerId);
      if (!entry) {
        entry = { offerId: stop.offerId, tag: tagFor(offers.length), tint: offers.length % 5 };
        offers.push(entry);
      }
      const eq = Number(stop.loadPalletEqAfter) - eqBefore;
      const count = Math.ceil(eq - 1e-9);
      if (count > 0) {
        const kgPerPlace = Math.round((stop.loadKgAfter - kgBefore) / count);
        let taken = 0;
        for (let slot = 0; slot < board.length && taken < count; slot += 1) {
          if (board[slot] === null) {
            board[slot] = {
              offerId: stop.offerId,
              tag: entry.tag,
              tint: entry.tint,
              kg: kgPerPlace,
            };
            taken += 1;
          }
        }
      }
    } else if (stop.kind === 'DELIVERY') {
      board.forEach((occupant, slot) => {
        if (occupant?.offerId === stop.offerId) board[slot] = null;
      });
    }
    steps.push(snapshot(steps.length, stop, Number(stop.loadPalletEqAfter), stop.loadKgAfter));
  });
  return { steps, offers };
}

/** "T1–T4" for consecutive places of the layout, otherwise the ids joined by commas. */
export function lane(ids: string[], layout: string): string {
  const order = placesFor(layout).map((place) => place.id);
  const sorted = [...ids].sort((left, right) => order.indexOf(left) - order.indexOf(right));
  if (sorted.length === 0) return '';
  const consecutive = sorted.every(
    (id, index) => index === 0 || order.indexOf(id) === order.indexOf(sorted[index - 1] ?? '') + 1,
  );
  const first = sorted[0] ?? '';
  const last = sorted.at(-1) ?? '';
  return consecutive && sorted.length > 1 ? `${first}–${last}` : sorted.join(', ');
}
