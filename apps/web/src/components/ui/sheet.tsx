'use client';

import * as Dialog from '@radix-ui/react-dialog';
import type { ReactNode } from 'react';
import { useReturnFocus } from './use-return-focus';

type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  closeLabel: string;
  children: ReactNode;
};

/** A side sheet for create and edit forms; the list stays visible behind the scrim. */
export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  closeLabel,
  children,
}: SheetProps) {
  const returnFocus = useReturnFocus(open);
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-scrim" />
        <Dialog.Content
          className="fixed bottom-0 right-0 top-0 z-50 flex w-[min(100vw,480px)] flex-col gap-4 overflow-y-auto rounded-l-card bg-surface p-6 shadow-sheet"
          onCloseAutoFocus={returnFocus}
          {...(description ? {} : { 'aria-describedby': undefined })}
        >
          <div className="flex items-start justify-between gap-4">
            <Dialog.Title className="font-display text-lg font-semibold text-ink">
              {title}
            </Dialog.Title>
            <Dialog.Close className="min-h-9 rounded-control border border-line-strong px-3 text-sm font-semibold">
              {closeLabel}
            </Dialog.Close>
          </div>
          {description && (
            <Dialog.Description className="text-sm text-ink2">{description}</Dialog.Description>
          )}
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
