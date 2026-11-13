'use client';

import { useLocale, useTranslations } from 'next-intl';
import { Fragment, useState } from 'react';
import { IconButton } from '@/components/ui/icon-button';
import { Pill } from '@/components/ui/pill';
import { Table, TBody, Td, Th, THead, Tr } from '@/components/ui/table';
import { Tooltip } from '@/components/ui/tooltip';
import { VanSide } from '@/components/vehicle/van-side';
import { formatDateTime, formatMass } from '@/lib/format';
import type { Driver } from './hooks';
import { ChevronIcon, ClockIcon, EditIcon, InfoIcon, TrashIcon } from './icons';
import { DrivingLimits, WorkBarCell } from './working-time-bars';

/**
 * The API carries no time zone for a driver state; every demo base lies in the CET zone, so the
 * "available from" time is shown in it with the zone abbreviation.
 */
export const FLEET_TIME_ZONE = 'Europe/Warsaw';

type DriverTableProps = {
  drivers: Driver[];
  assignedIds: Set<string>;
  onEdit: (driver: Driver) => void;
  onDelete: (driver: Driver) => void;
  onAddState: (driver: Driver) => void;
};

function initials(name: string): string {
  return name
    .split(/[\s-]+/)
    .map((part) => part.charAt(0))
    .slice(0, 2)
    .join('')
    .toUpperCase();
}

export function DriverTable({
  drivers,
  assignedIds,
  onEdit,
  onDelete,
  onAddState,
}: DriverTableProps) {
  const t = useTranslations('fleet');
  const legal = useTranslations('legal');
  const locale = useLocale() === 'pl' ? 'pl' : 'en';
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Table>
      <THead>
        <Tr>
          <Th scope="col">{t('table.driver')}</Th>
          <Th scope="col">{t('table.van')}</Th>
          <Th scope="col">{t('table.base')}</Th>
          <Th scope="col">{t('table.available')}</Th>
          <Th scope="col">
            <span className="inline-flex items-center gap-1">
              {t('table.workDay')}
              <Tooltip content={legal('notice')}>
                <button type="button" aria-label={t('notice')} className="rounded-round text-ink3">
                  <InfoIcon />
                </button>
              </Tooltip>
            </span>
          </Th>
          <Th scope="col">{t('table.workWeek')}</Th>
          <Th scope="col">{t('table.status')}</Th>
          <Th scope="col">
            <span className="sr-only">{t('table.actions')}</span>
          </Th>
        </Tr>
      </THead>
      <TBody>
        {drivers.map((driver) => {
          const expanded = open === driver.id;
          const assigned = assignedIds.has(driver.id);
          return (
            <Fragment key={driver.id}>
              <Tr>
                <Td>
                  <div className="flex items-center gap-3">
                    <span
                      aria-hidden="true"
                      className="flex size-9 flex-none items-center justify-center rounded-round bg-well text-xs font-medium text-ink2"
                    >
                      {initials(driver.name)}
                    </span>
                    <span className="flex flex-col">
                      <span className="font-semibold text-ink">{driver.name}</span>
                      {driver.phone && <span className="text-xs text-ink3">{driver.phone}</span>}
                    </span>
                  </div>
                </Td>
                <Td>
                  {driver.vehicle ? (
                    <div className="flex items-center gap-3">
                      <VanSide label={driver.vehicle.label} width={96} />
                      <span className="flex flex-col">
                        <span className="font-mono text-xs text-ink">{driver.vehicle.label}</span>
                        <span className="text-xs text-ink3">
                          {t('capacity', {
                            places: driver.vehicle.palletPlaces,
                            kg: formatMass(driver.vehicle.payloadKg, locale).replace(' kg', ''),
                          })}
                          {driver.vehicle.sleeperCab ? ` · ${t('sleeperCab')}` : ''}
                        </span>
                      </span>
                    </div>
                  ) : (
                    <span className="text-xs text-ink3">—</span>
                  )}
                </Td>
                <Td>
                  <div className="flex flex-col">
                    <span>{driver.homeCity}</span>
                    <span className="text-xs text-ink3">
                      {driver.state?.currentCity && driver.state.currentCity !== driver.homeCity
                        ? t('nowIn', { city: driver.state.currentCity })
                        : t('atBase')}
                    </span>
                  </div>
                </Td>
                <Td className="whitespace-nowrap">
                  {driver.state
                    ? formatDateTime(driver.state.availableFrom, FLEET_TIME_ZONE, locale)
                    : '—'}
                </Td>
                <Td className="min-w-40">
                  <WorkBarCell driver={driver} which="day" />
                </Td>
                <Td className="min-w-44">
                  <WorkBarCell driver={driver} which="week" />
                </Td>
                <Td>
                  <div className="flex flex-wrap gap-1">
                    <Pill level={assigned ? 'done' : 'quiet'}>
                      {assigned ? t('status.assigned') : t('status.free')}
                    </Pill>
                    {driver.isSynthetic && <Pill level="synthetic">{t('status.synthetic')}</Pill>}
                  </div>
                </Td>
                <Td>
                  <div className="flex justify-end gap-1">
                    {driver.state && (
                      <IconButton
                        small
                        icon={<ChevronIcon open={expanded} />}
                        label={t(expanded ? 'details.hide' : 'details.show', { name: driver.name })}
                        aria-expanded={expanded}
                        onClick={() => setOpen(expanded ? null : driver.id)}
                      />
                    )}
                    <IconButton
                      small
                      icon={<ClockIcon />}
                      label={t('action.addState', { name: driver.name })}
                      onClick={() => onAddState(driver)}
                    />
                    <IconButton
                      small
                      icon={<EditIcon />}
                      label={t('action.edit', { name: driver.name })}
                      onClick={() => onEdit(driver)}
                    />
                    <IconButton
                      small
                      icon={<TrashIcon />}
                      label={t('action.delete', { name: driver.name })}
                      onClick={() => onDelete(driver)}
                    />
                  </div>
                </Td>
              </Tr>
              {expanded && (
                <Tr>
                  <Td colSpan={8} className="bg-well">
                    <DrivingLimits driver={driver} />
                  </Td>
                </Tr>
              )}
            </Fragment>
          );
        })}
      </TBody>
    </Table>
  );
}
