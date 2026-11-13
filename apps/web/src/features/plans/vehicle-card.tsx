'use client';

import { useLocale, useTranslations } from 'next-intl';
import { formatMass } from '@/lib/format';
import type { components } from '@/lib/api/schema';

type Vehicle = components['schemas']['VehicleView'];

export function VehicleCard({ vehicle }: { vehicle: Vehicle }) {
  const t = useTranslations('plans.vehicle');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const dims = [vehicle.innerLengthM, vehicle.innerWidthM, vehicle.innerHeightM];
  const interior = dims.every((value) => value != null)
    ? `${dims.join(' × ')} m`
    : t('interiorUnknown');
  const rows: [string, string][] = [
    [t('type'), vehicle.vehicleType],
    [
      t('body'),
      t.has(`bodyType.${vehicle.bodyType}`) ? t(`bodyType.${vehicle.bodyType}`) : vehicle.bodyType,
    ],
    [
      t('places'),
      t('placesValue', { places: vehicle.palletPlaces, layout: vehicle.layoutTemplate }),
    ],
    [t('payload'), formatMass(vehicle.payloadKg, locale)],
    [t('interior'), interior],
    [t('sleeper'), t(vehicle.sleeperCab ? 'yes' : 'no')],
    [
      t('fuel'),
      t('fuelValue', {
        empty: String(vehicle.fuel.lPer100kmEmptyAt90),
        full: String(vehicle.fuel.lPer100kmFullAt90),
        basis: vehicle.fuel.provenance,
      }),
    ],
  ];
  return (
    <section
      className="flex flex-col gap-3 rounded-card bg-surface p-6 shadow-card"
      aria-label={t('title')}
    >
      <h2>{t('title')}</h2>
      <p className="font-mono text-sm text-ink">{vehicle.label}</p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        {rows.map(([name, value]) => (
          <div key={name} className="contents">
            <dt className="text-ink3">{name}</dt>
            <dd className="text-ink">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
