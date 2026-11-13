import { cn } from './cn';

type MeterProps = {
  value: number;
  max: number;
  /** Visible text next to the bar: a meter is never the only carrier of the number. */
  label: string;
  /** Accessible name of the meter itself. */
  name: string;
  /** Red when little is left, or when the meter is a brand meter (for example mass loaded). */
  tone?: 'normal' | 'low' | 'brand';
  className?: string;
};

export function Meter({ value, max, label, name, tone = 'normal', className }: MeterProps) {
  const clamped = Math.min(Math.max(value, 0), max);
  const percent = max > 0 ? (clamped / max) * 100 : 0;
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <div
        role="meter"
        aria-label={name}
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={clamped}
        aria-valuetext={label}
        className="h-1.5 w-full overflow-hidden rounded-round bg-line"
      >
        <div
          className={cn('h-full rounded-round', tone === 'normal' ? 'bg-ink' : 'bg-red')}
          style={{ width: `${percent}%` }}
        />
      </div>
      <span className="text-xs text-ink2">{label}</span>
    </div>
  );
}
