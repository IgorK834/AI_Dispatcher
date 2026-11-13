'use client';

import Link from 'next/link';
import type { ReactNode } from 'react';
import { LanguageSwitch } from '@/components/language-switch';
import { cn } from '@/components/ui/cn';
import { Pill } from '@/components/ui/pill';

export type NavItem = { href: string; label: string };

type TopBarProps = {
  /** Only the screens the role may use; hidden, not disabled (FR-11). */
  items: NavItem[];
  activeHref: string;
  navLabel: string;
  appName: string;
  /** Shown while demo data is present (FR-1). */
  syntheticLabel?: string;
  /** The account button or menu; absent on the sign-in page. */
  account?: ReactNode;
};

/** The shared top bar: logo, role-filtered navigation, badge, language switch, account. */
export function TopBar({
  items,
  activeHref,
  navLabel,
  appName,
  syntheticLabel,
  account,
}: TopBarProps) {
  return (
    <header className="flex min-h-20 items-center gap-6 border-b border-line bg-surface px-10">
      <Link
        href="/"
        className="flex items-center gap-2 font-display text-lg font-semibold text-ink"
      >
        <span
          aria-hidden="true"
          className="flex h-7 w-9 items-stretch overflow-hidden rounded-segment"
        >
          <span className="w-6 bg-red" />
          <span className="w-3 bg-ink" />
        </span>
        {appName}
      </Link>
      {items.length > 0 && (
        <nav aria-label={navLabel} className="flex flex-1 justify-center gap-1">
          {items.map((item) => {
            const active = item.href === activeHref;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'inline-flex min-h-11 items-center rounded-control px-4 text-sm font-semibold',
                  active ? 'bg-red-tint text-red' : 'text-ink2 hover:bg-well',
                )}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
      )}
      <div className="ml-auto flex items-center gap-3">
        {syntheticLabel && <Pill level="synthetic">{syntheticLabel}</Pill>}
        <LanguageSwitch />
        {account}
      </div>
    </header>
  );
}
