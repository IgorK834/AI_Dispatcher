import type { Offer, OfferStop } from './hooks';

/** The zone used when a stop carries none (every demo stop lies in Poland or a neighbour). */
export const FALLBACK_ZONE = 'Europe/Warsaw';

export const originOf = (offer: Offer): OfferStop | undefined =>
  offer.stops.find((stop) => stop.stopType === 'LOADING') ?? offer.stops[0];

export const destinationOf = (offer: Offer): OfferStop | undefined =>
  [...offer.stops].reverse().find((stop) => stop.stopType === 'UNLOADING') ?? offer.stops.at(-1);

export const percent = (score: number) => Math.round(score * 100);

/** `<input type="datetime-local">` value for an ISO instant, in the browser's zone. */
export function toLocalInput(iso: string): string {
  const date = new Date(iso);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** "250.00" or "250,5" in euro to integer cents. */
export function toMinor(price: string): number {
  return Math.round(Number(price.replace(',', '.')) * 100);
}
