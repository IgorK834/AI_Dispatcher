'use client';

import { useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { Banner } from '@/components/ui/banner';
import { ConfirmDialog } from '@/components/ui/dialog';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import type { ProblemInfo } from '@/lib/api/errors';
import { useProblemFromBody } from './problems';
import type { Driver, Vehicle } from './hooks';

export type DeleteTarget = { kind: 'driver'; item: Driver } | { kind: 'vehicle'; item: Vehicle };

/** Codes that explain why an item cannot be deleted (FR-9); shown instead of a generic error. */
const BLOCKING = new Set([
  'DRIVER_HAS_ACTIVE_ASSIGNMENT',
  'VEHICLE_ASSIGNED_TO_DRIVER',
  'COST_PROFILE_IN_USE',
]);

type DeleteDialogProps = { target: DeleteTarget; onClose: () => void };

/** Names the item, sends nothing until the verb button is pressed, explains conflicts. */
export function DeleteDialog({ target, onClose }: DeleteDialogProps) {
  const t = useTranslations('fleet');
  const common = useTranslations('common');
  const toast = useToast();
  const queryClient = useQueryClient();
  const toProblem = useProblemFromBody();
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<ProblemInfo | null>(null);
  const name = target.kind === 'driver' ? target.item.name : target.item.label;

  async function confirm() {
    setBusy(true);
    setBlocked(null);
    try {
      const outcome =
        target.kind === 'driver'
          ? await api.DELETE('/api/v1/drivers/{driver_id}', {
              params: { path: { driver_id: target.item.id } },
            })
          : await api.DELETE('/api/v1/vehicles/{vehicle_id}', {
              params: { path: { vehicle_id: target.item.id } },
            });
      if (outcome.response.ok) {
        toast.show(
          'success',
          t(target.kind === 'driver' ? 'toast.driverDeleted' : 'toast.vehicleDeleted'),
        );
        await queryClient.invalidateQueries({
          queryKey: [target.kind === 'driver' ? 'drivers' : 'vehicles'],
        });
        onClose();
        return;
      }
      const problem = toProblem(outcome.error);
      if (outcome.response.status === 403) {
        toast.show('error', t('toast.noPermission'));
      } else if (BLOCKING.has(problem.code)) {
        setBlocked(problem);
      } else {
        toast.show(
          'error',
          problem.requestId ? `${problem.message} (${problem.requestId})` : problem.message,
        );
      }
    } finally {
      setBusy(false);
    }
  }

  const driver = target.kind === 'driver';
  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={t(driver ? 'delete.driverTitle' : 'delete.vehicleTitle', { name })}
      description={t(driver ? 'delete.driverBody' : 'delete.vehicleBody')}
      confirmLabel={t(driver ? 'delete.driverConfirm' : 'delete.vehicleConfirm')}
      cancelLabel={common('cancel')}
      destructive
      loading={busy}
      onConfirm={() => void confirm()}
    >
      {blocked && (
        <Banner level="attention" title={t('delete.blockedTitle')}>
          {blocked.message}
        </Banner>
      )}
    </ConfirmDialog>
  );
}
