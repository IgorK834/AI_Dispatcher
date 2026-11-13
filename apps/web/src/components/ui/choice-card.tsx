import type { InputHTMLAttributes, ReactNode } from 'react';
import { cn } from './cn';

type ChoiceCardProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'children'> & {
  type?: 'radio' | 'checkbox';
  title: string;
  description?: ReactNode;
};

/** A radio or checkbox drawn as a card; the selected card has a red border on a red tint. */
export function ChoiceCard({
  type = 'radio',
  title,
  description,
  className,
  ...rest
}: ChoiceCardProps) {
  return (
    <label
      className={cn(
        'flex cursor-pointer items-start gap-3 rounded-inner border border-line-strong bg-surface p-3 has-[:checked]:border-red has-[:checked]:bg-red-tint',
        className,
      )}
    >
      <input type={type} className="mt-1 accent-red" {...rest} />
      <span className="flex flex-col">
        <span className="text-sm font-semibold text-ink">{title}</span>
        {description && <span className="text-xs text-ink2">{description}</span>}
      </span>
    </label>
  );
}
