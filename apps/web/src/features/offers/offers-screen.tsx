'use client';

import { useTranslations } from 'next-intl';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';
import { EmptyState, ListError, ListSkeleton } from '@/components/ui/list-status';
import { Button } from '@/components/ui/button';
import { Input, Select } from '@/components/ui/field';
import { Sheet } from '@/components/ui/sheet';
import { useProblem } from '@/lib/use-problem';
import { DeleteDialog } from './delete-dialog';
import { filtersFromSearch, hasActiveFilters } from './filters';
import { IMPORTED_SOURCE, MANUAL_SOURCE, useOffers, type Offer } from './hooks';
import { PlusIcon } from './icons';
import { OfferDetail } from './offer-detail';
import { OfferForm } from './offer-form';
import { OfferTable } from './offer-table';

type SheetTarget = { kind: 'detail'; offer: Offer } | { kind: 'form'; offer?: Offer };

/** Filters live in the URL so that a view can be shared (FR-6). */
function useUrlState() {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const filters = filtersFromSearch(search);
  function update(changes: Record<string, string | undefined>) {
    const next = new URLSearchParams(search.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname);
  }
  function clear() {
    router.replace(pathname);
  }
  return { filters, update, clear };
}

export function OffersScreen() {
  const t = useTranslations('offers');
  const common = useTranslations('common');
  const toProblem = useProblem();
  const { filters, update, clear } = useUrlState();
  const offers = useOffers(filters);
  const [sheet, setSheet] = useState<SheetTarget | null>(null);
  const [deleting, setDeleting] = useState<Offer | null>(null);
  const [resetKey, setResetKey] = useState(0);

  const items = offers.data?.pages.flatMap((page) => page.items) ?? [];
  const closeSheet = () => setSheet(null);
  const clearFilters = () => {
    setResetKey((key) => key + 1);
    clear();
  };

  const textFilter = (key: string, label: string, maxLength?: number) => (
    <label className="flex flex-col gap-1 text-xs text-ink3">
      {label}
      <Input
        className={maxLength ? 'w-24' : 'w-40'}
        maxLength={maxLength}
        defaultValue={(filters[key as keyof typeof filters] as string | undefined) ?? ''}
        onBlur={(event) =>
          update({
            [key]:
              (maxLength ? event.target.value.trim().toUpperCase() : event.target.value.trim()) ||
              undefined,
          })
        }
      />
    </label>
  );

  const numberFilter = (
    key: string,
    label: string,
    shown: number | undefined,
    toUrl: (n: number) => string,
  ) => (
    <label className="flex flex-col gap-1 text-xs text-ink3">
      {label}
      <Input
        type="number"
        min={0}
        className="w-28"
        defaultValue={shown ?? ''}
        onBlur={(event) => {
          const value = event.target.value.trim();
          update({
            [key]: value && Number.isFinite(Number(value)) ? toUrl(Number(value)) : undefined,
          });
        }}
      />
    </label>
  );

  const dateFilter = (key: 'pickupFrom' | 'pickupTo', label: string) => (
    <label className="flex flex-col gap-1 text-xs text-ink3">
      {label}
      <Input
        type="datetime-local"
        className="w-56"
        defaultValue={filters[key]?.slice(0, 16) ?? ''}
        onChange={(event) =>
          update({
            [key]: event.target.value ? new Date(event.target.value).toISOString() : undefined,
          })
        }
      />
    </label>
  );

  const filtersForm = (
    <form
      key={resetKey}
      aria-label={t('filters.label')}
      className="flex flex-wrap items-end gap-3 px-6 pb-4"
      onSubmit={(event) => event.preventDefault()}
    >
      <label className="flex flex-col gap-1 text-xs text-ink3">
        {t('filters.source')}
        <Select
          className="w-48"
          value={filters.source ?? ''}
          onChange={(event) => update({ source: event.target.value || undefined })}
        >
          <option value="">{t('filters.sourceAll')}</option>
          <option value={IMPORTED_SOURCE}>{t('filters.sourceImported')}</option>
          <option value={MANUAL_SOURCE}>{t('filters.sourceManual')}</option>
        </Select>
      </label>
      {textFilter('originCountry', t('filters.originCountry'), 2)}
      {textFilter('originCity', t('filters.originCity'))}
      {textFilter('destinationCountry', t('filters.destinationCountry'), 2)}
      {textFilter('destinationCity', t('filters.destinationCity'))}
      {dateFilter('pickupFrom', t('filters.pickupFrom'))}
      {dateFilter('pickupTo', t('filters.pickupTo'))}
      {numberFilter('maxWeightKg', t('filters.maxWeight'), filters.maxWeightKg, String)}
      {numberFilter('maxPallets', t('filters.maxPallets'), filters.maxPallets, String)}
      {numberFilter(
        'minCompleteness',
        t('filters.minCompleteness'),
        filters.minCompleteness === undefined
          ? undefined
          : Math.round(filters.minCompleteness * 100),
        (percent) => String(Math.min(percent, 100) / 100),
      )}
      <label className="flex min-h-11 items-center gap-2 text-sm text-ink">
        <input
          type="checkbox"
          className="size-4 accent-red"
          checked={filters.hasPrice === true}
          onChange={(event) => update({ hasPrice: event.target.checked ? 'true' : undefined })}
        />
        {t('filters.hasPrice')}
      </label>
      {hasActiveFilters(filters) && (
        <Button small onClick={clearFilters}>
          {t('filters.clear')}
        </Button>
      )}
    </form>
  );

  const body = offers.isPending ? (
    <ListSkeleton label={t('loading')} />
  ) : offers.isError ? (
    <ListError
      title={t('error.title')}
      problem={toProblem(offers.error)}
      onRetry={() => void offers.refetch()}
    />
  ) : items.length === 0 ? (
    <EmptyState
      title={t('empty.title')}
      body={t('empty.body')}
      action={
        hasActiveFilters(filters) ? (
          <Button variant="primary" onClick={clearFilters}>
            {t('empty.action')}
          </Button>
        ) : (
          <Button variant="primary" onClick={() => setSheet({ kind: 'form' })}>
            <PlusIcon />
            {t('addOffer')}
          </Button>
        )
      }
    />
  ) : (
    <>
      <OfferTable
        offers={items}
        onDetails={(offer) => setSheet({ kind: 'detail', offer })}
        onEdit={(offer) => setSheet({ kind: 'form', offer })}
        onDelete={setDeleting}
      />
      <div className="flex justify-end p-4">
        {offers.hasNextPage ? (
          <Button
            small
            loading={offers.isFetchingNextPage}
            onClick={() => void offers.fetchNextPage()}
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

  const sheetTitle =
    sheet?.kind === 'detail'
      ? t('detail.title', { id: sheet.offer.sourceOfferId })
      : t(sheet?.offer ? 'form.editTitle' : 'form.createTitle');

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1>{t('title')}</h1>
          <p className="text-ink2">{t('subtitle')}</p>
        </div>
        <Button variant="primary" onClick={() => setSheet({ kind: 'form' })}>
          <PlusIcon />
          {t('addOffer')}
        </Button>
      </div>

      <section className="rounded-card bg-surface pt-5 shadow-card">
        {filtersForm}
        {body}
      </section>

      <Sheet
        open={sheet !== null}
        onOpenChange={(open) => {
          if (!open) closeSheet();
        }}
        title={sheetTitle}
        closeLabel={common('close')}
      >
        {sheet?.kind === 'detail' && <OfferDetail offer={sheet.offer} />}
        {sheet?.kind === 'form' && (
          <OfferForm key={sheet.offer?.id ?? 'new'} offer={sheet.offer} onDone={closeSheet} />
        )}
      </Sheet>

      {deleting && (
        <DeleteDialog key={deleting.id} offer={deleting} onClose={() => setDeleting(null)} />
      )}
    </div>
  );
}
