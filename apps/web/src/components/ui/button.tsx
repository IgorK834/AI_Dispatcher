import type { ButtonHTMLAttributes } from 'react';
import { cn } from './cn';

export type ButtonVariant = 'primary' | 'secondary' | 'danger';

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  small?: boolean;
  /** Shows a spinner inside the button and disables it (the only place a spinner is used). */
  loading?: boolean;
};

const variants: Record<ButtonVariant, string> = {
  primary: 'border-red bg-red text-surface hover:border-red-hover hover:bg-red-hover',
  secondary: 'border-line-strong bg-surface text-ink hover:bg-well',
  // Destructive actions are outlined so they never look like the primary action.
  danger: 'border-red bg-surface text-red-hover hover:bg-red-tint',
};

export function Button({
  variant = 'secondary',
  small = false,
  loading = false,
  disabled,
  className,
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-control border px-4 text-sm font-semibold transition-colors',
        small ? 'min-h-9' : 'min-h-11',
        variants[variant],
        'disabled:cursor-not-allowed disabled:border-line disabled:bg-well disabled:text-ink3',
        className,
      )}
      {...rest}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="inline-block size-4 rounded-round border-2 border-current border-t-transparent"
          style={{ animation: 'rp-spin 0.8s linear infinite' }}
        />
      )}
      {children}
    </button>
  );
}
