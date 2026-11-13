import type { ReactNode } from 'react';
import { cn } from './cn';

type BannerProps = {
  level?: 'attention' | 'error' | 'info';
  title?: string;
  children?: ReactNode;
  /** An action such as "Reload" or "Try again". */
  action?: ReactNode;
  className?: string;
};

export function Banner({ level = 'info', title, children, action, className }: BannerProps) {
  return (
    <div
      role={level === 'info' ? 'status' : 'alert'}
      data-level={level}
      className={cn(
        'flex flex-wrap items-center gap-3 rounded-inner p-3 text-sm',
        level === 'info' ? 'bg-info-bg text-info-fg' : 'bg-red-tint text-red-hover',
        level === 'error' && 'border border-red',
        className,
      )}
    >
      <div className="flex min-w-0 flex-1 flex-col">
        {title && <strong className="font-semibold">{title}</strong>}
        {children && <span>{children}</span>}
      </div>
      {action}
    </div>
  );
}
