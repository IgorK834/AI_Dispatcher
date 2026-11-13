'use client';

import { useLocale, useTranslations } from 'next-intl';
import { IconButton } from '@/components/ui/icon-button';
import { Pill } from '@/components/ui/pill';
import { Table, TBody, Td, Th, THead, Tr } from '@/components/ui/table';
import { VanSide } from '@/components/vehicle/van-side';
import { formatMass } from '@/lib/format';
import type { CostProfile, Vehicle } from './hooks';
import { EditIcon, TrashIcon } from './icons';

type VehicleTableProps = {
  vehicles: Vehicle[];
  costProfiles: CostProfile[];
  onEdit: (vehicle: Vehicle) => void;
  onDelete: (vehicle: Vehicle) => void;
};

export function VehicleTable({ vehicles, costProfiles, onEdit, onDelete }: VehicleTableProps) {
  const t = useTranslations('fleet');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const profiles = new Map(costProfiles.map((profile) => [profile.id, profile.name]));
  return (
    <Table>
      <THead>
        <Tr>
          <Th scope="col">{t('vehicleTable.label')}</Th>
          <Th scope="col">{t('vehicleTable.body')}</Th>
          <Th scope="col" numeric>
            {t('vehicleTable.places')}
          </Th>
          <Th scope="col" numeric>
            {t('vehicleTable.payload')}
          </Th>
          <Th scope="col">{t('vehicleTable.layout')}</Th>
          <Th scope="col">{t('vehicleTable.cost')}</Th>
          <Th scope="col">
            <span className="sr-only">{t('table.actions')}</span>
          </Th>
        </Tr>
      </THead>
      <TBody>
        {vehicles.map((vehicle) => (
          <Tr key={vehicle.id}>
            <Td>
              <div className="flex items-center gap-3">
                <VanSide label={vehicle.label} width={96} />
                <span className="flex flex-col">
                  <span className="font-mono text-xs text-ink">{vehicle.label}</span>
                  <span className="text-xs text-ink3">
                    {vehicle.sleeperCab ? t('sleeperCab') : ''}
                  </span>
                </span>
              </div>
            </Td>
            <Td>{t(`options.${vehicle.bodyType}`)}</Td>
            <Td numeric>{vehicle.palletPlaces}</Td>
            <Td numeric>{formatMass(vehicle.payloadKg, locale)}</Td>
            <Td>{t(`options.${vehicle.layoutTemplate}`)}</Td>
            <Td>
              <span className="flex flex-wrap items-center gap-1">
                {profiles.get(vehicle.costProfileId) ?? '—'}
                {vehicle.isSynthetic && <Pill level="synthetic">{t('status.synthetic')}</Pill>}
              </span>
            </Td>
            <Td>
              <div className="flex justify-end gap-1">
                <IconButton
                  small
                  icon={<EditIcon />}
                  label={t('action.edit', { name: vehicle.label })}
                  onClick={() => onEdit(vehicle)}
                />
                <IconButton
                  small
                  icon={<TrashIcon />}
                  label={t('action.delete', { name: vehicle.label })}
                  onClick={() => onDelete(vehicle)}
                />
              </div>
            </Td>
          </Tr>
        ))}
      </TBody>
    </Table>
  );
}
