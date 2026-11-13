'use client';

import { useTranslations } from 'next-intl';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/field';
import { Sheet } from '@/components/ui/sheet';
import { Tabs } from '@/components/ui/tabs';
import { DeleteDialog, type DeleteTarget } from './delete-dialog';
import { DriverForm } from './driver-form';
import { DriverTable } from './driver-table';
import {
  useAssignedDriverIds,
  useCostProfiles,
  useDrivers,
  useVehicles,
  type Driver,
  type DriverFilters,
  type Vehicle,
} from './hooks';
import { PlusIcon } from './icons';
import { KpiCards } from './kpi-cards';
import { EmptyState, ListError, ListSkeleton } from './list-status';
import { useProblem } from './problems';
import { StateForm } from './state-form';
import { VehicleForm } from './vehicle-form';
import { VehicleTable } from './vehicle-table';

type SheetTarget =
  | { kind: 'driver'; driver?: Driver }
  | { kind: 'vehicle'; vehicle?: Vehicle }
  | { kind: 'state'; driver: Driver };

type View = 'drivers' | 'vehicles';

/** Filters and the active tab live in the URL so that a view can be shared (FR-6). */
function useUrlState() {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const filters: DriverFilters = {
    homeCity: search.get('homeCity') ?? undefined,
    availableBefore: search.get('availableBefore') ?? undefined,
    hasVehicle: search.get('hasVehicle') === 'true' ? true : undefined,
  };
  const view: View = search.get('view') === 'vehicles' ? 'vehicles' : 'drivers';
  function update(changes: Record<string, string | undefined>) {
    const next = new URLSearchParams(search.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }
  return { filters, view, update };
}

export function FleetScreen() {
  const t = useTranslations('fleet');
  const common = useTranslations('common');
  const toProblem = useProblem();
  const { filters, view, update } = useUrlState();
  const drivers = useDrivers(filters);
  const vehicles = useVehicles();
  const costProfiles = useCostProfiles();
  const assigned = useAssignedDriverIds();
  const [sheet, setSheet] = useState<SheetTarget | null>(null);
  const [deleting, setDeleting] = useState<DeleteTarget | null>(null);

  const driverItems = drivers.data?.pages.flatMap((page) => page.items) ?? [];
  const vehicleItems = vehicles.data?.pages.flatMap((page) => page.items) ?? [];
  const assignedIds = assigned.data ?? new Set<string>();
  const closeSheet = () => setSheet(null);

  const driversBody = drivers.isPending ? (
    <ListSkeleton label={t('loading')} />
  ) : drivers.isError ? (
    <ListError
      title={t('error.drivers')}
      problem={toProblem(drivers.error)}
      onRetry={() => void drivers.refetch()}
    />
  ) : driverItems.length === 0 ? (
    <EmptyState
      title={t('empty.driversTitle')}
      body={t('empty.driversBody')}
      action={
        <Button variant="primary" onClick={() => setSheet({ kind: 'driver' })}>
          <PlusIcon />
          {t('addDriver')}
        </Button>
      }
    />
  ) : (
    <>
      <DriverTable
        drivers={driverItems}
        assignedIds={assignedIds}
        onEdit={(driver) => setSheet({ kind: 'driver', driver })}
        onDelete={(driver) => setDeleting({ kind: 'driver', item: driver })}
        onAddState={(driver) => setSheet({ kind: 'state', driver })}
      />
      <div className="flex justify-end p-4">
        {drivers.hasNextPage ? (
          <Button
            small
            loading={drivers.isFetchingNextPage}
            onClick={() => void drivers.fetchNextPage()}
          >
            {t('loadMore')}
          </Button>
        ) : (
          <Button small disabled>
            {t('allLoaded')}
          </Button>
        )}
      </div>
    </>
  );

  const vehiclesBody = vehicles.isPending ? (
    <ListSkeleton label={t('loading')} />
  ) : vehicles.isError ? (
    <ListError
      title={t('error.vehicles')}
      problem={toProblem(vehicles.error)}
      onRetry={() => void vehicles.refetch()}
    />
  ) : vehicleItems.length === 0 ? (
    <EmptyState
      title={t('empty.vehiclesTitle')}
      body={t('empty.vehiclesBody')}
      action={
        <Button variant="primary" onClick={() => setSheet({ kind: 'vehicle' })}>
          <PlusIcon />
          {t('addVehicle')}
        </Button>
      }
    />
  ) : (
    <>
      <VehicleTable
        vehicles={vehicleItems}
        costProfiles={costProfiles.data ?? []}
        onEdit={(vehicle) => setSheet({ kind: 'vehicle', vehicle })}
        onDelete={(vehicle) => setDeleting({ kind: 'vehicle', item: vehicle })}
      />
      <div className="flex justify-end p-4">
        {vehicles.hasNextPage ? (
          <Button
            small
            loading={vehicles.isFetchingNextPage}
            onClick={() => void vehicles.fetchNextPage()}
          >
            {t('loadMore')}
          </Button>
        ) : (
          <Button small disabled>
            {t('allLoaded')}
          </Button>
        )}
      </div>
    </>
  );

  const filtersForm = (
    <form
      aria-label={t('filters.label')}
      className="flex flex-wrap items-center gap-3 px-6 pb-4"
      onSubmit={(event) => event.preventDefault()}
    >
      <label className="flex flex-col gap-1 text-xs text-ink3">
        {t('filters.base')}
        <Input
          className="w-44"
          defaultValue={filters.homeCity ?? ''}
          onBlur={(event) => update({ homeCity: event.target.value.trim() || undefined })}
        />
      </label>
      <label className="flex flex-col gap-1 text-xs text-ink3">
        {t('filters.availableBefore')}
        <Input
          type="datetime-local"
          className="w-56"
          defaultValue={filters.availableBefore?.slice(0, 16) ?? ''}
          onChange={(event) =>
            update({
              availableBefore: event.target.value
                ? new Date(event.target.value).toISOString()
                : undefined,
            })
          }
        />
      </label>
      <label className="flex min-h-11 items-center gap-2 pt-4 text-sm text-ink">
        <input
          type="checkbox"
          className="size-4 accent-red"
          checked={filters.hasVehicle === true}
          onChange={(event) => update({ hasVehicle: event.target.checked ? 'true' : undefined })}
        />
        {t('filters.hasVehicle')}
      </label>
    </form>
  );

  const sheetTitle =
    sheet?.kind === 'driver'
      ? t(sheet.driver ? 'driverForm.editTitle' : 'driverForm.createTitle')
      : sheet?.kind === 'vehicle'
        ? t(sheet.vehicle ? 'vehicleForm.editTitle' : 'vehicleForm.createTitle')
        : t('stateForm.title');

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1>{t('title')}</h1>
          <p className="text-ink2">{t('subtitle')}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => setSheet({ kind: 'vehicle' })}>{t('addVehicle')}</Button>
          <Button variant="primary" onClick={() => setSheet({ kind: 'driver' })}>
            <PlusIcon />
            {t('addDriver')}
          </Button>
        </div>
      </div>

      <KpiCards drivers={driverItems} assignedIds={assignedIds} />

      <section className="rounded-card bg-surface shadow-card">
        <div className="min-w-0 px-6 pb-3 pt-5">
          <Tabs
            label={t('tabs.label')}
            value={view}
            onValueChange={(next) => update({ view: next === 'vehicles' ? 'vehicles' : undefined })}
            items={[
              {
                value: 'drivers',
                label: t('tabs.drivers', { count: driverItems.length }),
                content: (
                  <>
                    {filtersForm}
                    {driversBody}
                  </>
                ),
              },
              {
                value: 'vehicles',
                label: t('tabs.vehicles', { count: vehicleItems.length }),
                content: vehiclesBody,
              },
            ]}
          />
        </div>
      </section>

      <Sheet
        open={sheet !== null}
        onOpenChange={(open) => {
          if (!open) closeSheet();
        }}
        title={sheetTitle}
        description={
          sheet?.kind === 'state'
            ? t('stateForm.description', { name: sheet.driver.name })
            : undefined
        }
        closeLabel={common('close')}
      >
        {sheet?.kind === 'driver' && (
          <DriverForm
            key={sheet.driver?.id ?? 'new'}
            driver={sheet.driver}
            vehicles={vehicleItems}
            onDone={closeSheet}
          />
        )}
        {sheet?.kind === 'vehicle' && (
          <VehicleForm
            key={sheet.vehicle?.id ?? 'new'}
            vehicle={sheet.vehicle}
            costProfiles={costProfiles.data ?? []}
            onDone={closeSheet}
          />
        )}
        {sheet?.kind === 'state' && (
          <StateForm key={sheet.driver.id} driver={sheet.driver} onDone={closeSheet} />
        )}
      </Sheet>

      {deleting && (
        <DeleteDialog key={deleting.item.id} target={deleting} onClose={() => setDeleting(null)} />
      )}
    </div>
  );
}
