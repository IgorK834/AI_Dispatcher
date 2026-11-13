import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cn } from './cn';

export type IconButtonProps = Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'aria-label'> & {
  /** Required accessible name: an icon alone is not a label. */
  label: string;
  icon: ReactNode;
  small?: boolean;
  /** Optional red count badge, for example the number of pending approvals. */
  count?: number;
};

export function IconButton({
  label,
  icon,
  small = false,
  count,
  className,
  type = 'button',
  ...rest
}: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      className={cn(
        'relative inline-flex items-center justify-center rounded-control border border-line-strong bg-surface text-ink hover:bg-well disabled:cursor-not-allowed disabled:bg-well disabled:text-ink3',
        small ? 'size-9' : 'size-11',
        className,
      )}
      {...rest}
    >
      <span aria-hidden="true">{icon}</span>
      {count !== undefined && count > 0 && (
        <span className="absolute -right-1 -top-1 min-w-5 rounded-round bg-red px-1 text-center text-xs font-semibold text-surface">
          {count}
        </span>
      )}
    </button>
  );
}
