'use client';

import * as AlertDialog from '@radix-ui/react-alert-dialog';
import * as Dialog from '@radix-ui/react-dialog';
import type { ReactNode } from 'react';
import { Button } from './button';
import { cn } from './cn';
import { useReturnFocus } from './use-return-focus';

const overlay = 'fixed inset-0 z-40 bg-scrim';
const panel =
  'fixed left-1/2 top-1/2 z-50 w-[min(92vw,480px)] -translate-x-1/2 -translate-y-1/2 rounded-card bg-surface p-6 shadow-sheet';

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
};

/** A modal dialog: focus is trapped, Escape closes it and focus returns to the trigger. */
export function ModalDialog({ open, onOpenChange, title, description, children }: DialogProps) {
  const returnFocus = useReturnFocus(open);
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className={overlay} />
        <Dialog.Content
          className={panel}
          onCloseAutoFocus={returnFocus}
          {...(description ? {} : { 'aria-describedby': undefined })}
        >
          <Dialog.Title className="font-display text-lg font-semibold text-ink">
            {title}
          </Dialog.Title>
          {description ? (
            <Dialog.Description className="mt-1 text-sm text-ink2">
              {description}
            </Dialog.Description>
          ) : null}
          <div className="mt-4">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

type ConfirmDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  /** The verb on the confirm button ("Delete driver"), never "OK". */
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  destructive?: boolean;
  loading?: boolean;
  /** An explanation shown in place of the description when the action is blocked. */
  children?: ReactNode;
};

/** An alert dialog that names the item and asks before anything is sent. */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel,
  onConfirm,
  destructive = false,
  loading = false,
  children,
}: ConfirmDialogProps) {
  const returnFocus = useReturnFocus(open);
  return (
    <AlertDialog.Root open={open} onOpenChange={onOpenChange}>
      <AlertDialog.Portal>
        <AlertDialog.Overlay className={overlay} />
        <AlertDialog.Content className={panel} onCloseAutoFocus={returnFocus}>
          <AlertDialog.Title className="font-display text-lg font-semibold text-ink">
            {title}
          </AlertDialog.Title>
          <AlertDialog.Description className="mt-1 text-sm text-ink2">
            {description}
          </AlertDialog.Description>
          {children && <div className="mt-3">{children}</div>}
          <div className={cn('mt-6 flex justify-end gap-2')}>
            <AlertDialog.Cancel asChild>
              <Button>{cancelLabel}</Button>
            </AlertDialog.Cancel>
            <Button
              variant={destructive ? 'danger' : 'primary'}
              loading={loading}
              onClick={(event) => {
                event.preventDefault();
                onConfirm();
              }}
            >
              {confirmLabel}
            </Button>
          </div>
        </AlertDialog.Content>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
}
