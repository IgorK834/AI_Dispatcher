'use client';

import { useQueryClient } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { Banner } from '@/components/ui/banner';
import { ConfirmDialog } from '@/components/ui/dialog';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api/client';
import type { ProblemInfo } from '@/lib/api/errors';
import { useProblemFromBody } from '@/lib/use-problem';
import type { Offer } from './hooks';

type DeleteDialogProps = { offer: Offer; onClose: () => void };

/** Names the offer, sends nothing until the verb button is pressed, explains a refusal. */
export function DeleteDialog({ offer, onClose }: DeleteDialogProps) {
  const t = useTranslations('offers');
  const common = useTranslations('common');
  const toast = useToast();
  const queryClient = useQueryClient();
  const toProblem = useProblemFromBody();
  const [busy, setBusy] = useState(false);
  const [blocked, setBlocked] = useState<ProblemInfo | null>(null);

  async function confirm() {
    setBusy(true);
    setBlocked(null);
    try {
      const outcome = await api.DELETE('/api/v1/freight-offers/{offer_id}', {
        params: { path: { offer_id: offer.id } },
      });
      if (outcome.response.ok) {
        toast.show('success', t('toast.deleted'));
        await queryClient.invalidateQueries({ queryKey: ['offers'] });
        onClose();
        return;
      }
      const problem = toProblem(outcome.error);
      if (outcome.response.status === 403) {
        toast.show('error', t('toast.noPermission'));
      } else if (outcome.response.status === 409) {
        // PROVIDER_OFFER_READ_ONLY and an offer that is already assigned: say why, in the dialog.
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

  return (
    <ConfirmDialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={t('delete.title', { id: offer.sourceOfferId })}
      description={t('delete.body')}
      confirmLabel={t('delete.confirm')}
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
