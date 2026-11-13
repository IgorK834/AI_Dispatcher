import Link from 'next/link';
import type { ReactNode } from 'react';
import { cn } from '@/components/ui/cn';

/** A link that looks like a button of the design system (primary or secondary). */
export function LinkButton({
  href,
  children,
  primary = false,
}: {
  href: string;
  children: ReactNode;
  primary?: boolean;
}) {
  return (
    <Link
      href={href}
      className={cn(
        'inline-flex min-h-11 items-center justify-center rounded-control border px-4 text-sm font-semibold transition-colors',
        primary
          ? 'border-red bg-red text-surface hover:border-red-hover hover:bg-red-hover'
          : 'border-line-strong bg-surface text-ink hover:bg-well',
      )}
    >
      {children}
    </Link>
  );
}
