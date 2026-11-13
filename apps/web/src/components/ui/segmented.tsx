import { cn } from './cn';

export type SegmentedOption<T extends string> = { value: T; label: string };

type SegmentedProps<T extends string> = {
  options: SegmentedOption<T>[];
  value: T;
  onValueChange: (value: T) => void;
  /** Accessible name of the whole group. */
  label: string;
  className?: string;
};

/** A group of toggle buttons: the selected one has aria-pressed="true" and is the only red one. */
export function Segmented<T extends string>({
  options,
  value,
  onValueChange,
  label,
  className,
}: SegmentedProps<T>) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cn('inline-flex gap-1 rounded-control bg-well p-1', className)}
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={selected}
            onClick={() => onValueChange(option.value)}
            className={cn(
              'min-h-9 min-w-9 rounded-segment px-3 text-sm font-semibold',
              selected ? 'bg-surface text-red shadow-segment-on' : 'text-ink2 hover:text-ink',
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
