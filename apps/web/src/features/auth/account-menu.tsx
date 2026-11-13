'use client';

import { useTranslations } from 'next-intl';
import { useEffect, useId, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useSession } from './session';

function initials(email: string): string {
  return email.slice(0, 2).toUpperCase();
}

/** The account button: email, role and "Sign out"; Escape or a click outside closes it. */
export function AccountMenu() {
  const t = useTranslations('auth');
  const { state, signOut } = useSession();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const panel = useId();
  const root = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent && event.key !== 'Escape') return;
      if (event instanceof MouseEvent && root.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    document.addEventListener('keydown', close);
    document.addEventListener('mousedown', close);
    return () => {
      document.removeEventListener('keydown', close);
      document.removeEventListener('mousedown', close);
    };
  }, [open]);

  if (state.status !== 'authenticated') return null;
  const { email, role } = state.user;
  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panel}
        aria-label={t('account.label')}
        onClick={() => setOpen((value) => !value)}
        className="flex min-h-11 items-center gap-2 rounded-control border border-line-strong bg-surface px-3 text-sm"
      >
        <span
          aria-hidden="true"
          className="flex size-7 items-center justify-center rounded-round bg-ink text-xs font-semibold text-surface"
        >
          {initials(email)}
        </span>
        <span className="flex flex-col items-start leading-tight">
          <span className="text-xs text-ink3">{t(`roles.${role}`)}</span>
          <span className="font-semibold text-ink">{email}</span>
        </span>
      </button>
      {open && (
        <div
          id={panel}
          className="absolute right-0 top-full z-30 mt-2 flex w-72 flex-col gap-3 rounded-inner bg-surface p-4 shadow-sheet"
        >
          <p className="text-sm text-ink2">{t('account.email', { email })}</p>
          <p className="text-sm text-ink2">{t('account.role', { role: t(`roles.${role}`) })}</p>
          <Button
            loading={busy}
            onClick={async () => {
              setBusy(true);
              await signOut();
            }}
          >
            {busy ? t('account.signingOut') : t('account.signOut')}
          </Button>
        </div>
      )}
    </div>
  );
}
