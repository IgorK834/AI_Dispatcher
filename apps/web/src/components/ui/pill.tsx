import type { ReactNode } from 'react';
import { cn } from './cn';

/** Status levels of docs/design/README.md section 2.2. The level is always written as text. */
export type PillLevel = 'done' | 'attention' | 'error' | 'info' | 'quiet' | 'brand' | 'synthetic';

const levels: Record<PillLevel, string> = {
  done: 'bg-done-bg text-done-fg',
  attention: 'bg-red-tint text-red-hover',
  error: 'bg-red text-surface',
  info: 'bg-info-bg text-info-fg',
  quiet: 'bg-quiet-bg text-quiet-fg',
  brand: 'bg-red-tint text-red',
  synthetic: 'border border-line-strong bg-surface text-ink2',
};

export function Pill({
  level = 'info',
  children,
  className,
}: {
  level?: PillLevel;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      data-level={level}
      className={cn(
        'inline-flex items-center rounded-pill px-2 py-0.5 text-xs font-semibold',
        levels[level],
        className,
      )}
    >
      {children}
    </span>
  );
}
