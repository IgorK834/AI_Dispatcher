type RouteTrackProps = {
  origin: string;
  destination: string;
  /** Progress from 0 (at the origin) to 1 (at the destination). */
  progress: number;
  /** Text for assistive technology, for example "Not started". */
  status: string;
};

export function RouteTrack({ origin, destination, progress, status }: RouteTrackProps) {
  const percent = Math.min(Math.max(progress, 0), 1) * 100;
  return (
    <div className="flex flex-col gap-2" role="group" aria-label={status}>
      <div className="flex justify-between text-sm font-semibold text-ink">
        <span>{origin}</span>
        <span>{destination}</span>
      </div>
      <div className="relative h-1 rounded-round bg-line">
        <div className="h-full rounded-round bg-ink" style={{ width: `${percent}%` }} />
        <span
          aria-hidden="true"
          className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-round bg-red ring-4 ring-red-tint"
          style={{ left: `${percent}%` }}
        />
      </div>
      <span className="text-xs text-ink3">{status}</span>
    </div>
  );
}
