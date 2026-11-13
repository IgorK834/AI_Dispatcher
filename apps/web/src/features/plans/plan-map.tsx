'use client';

import { useTranslations } from 'next-intl';
import { useEffect, useState, type ComponentType } from 'react';
import { Segmented } from '@/components/ui/segmented';
import { isAction, type PlanStop, type RoutePlan } from './types';

export type MapStop = { number: number; label: string; lat: number; lon: number };

type CanvasProps = {
  styleUrl: string;
  stops: MapStop[];
  line: [number, number][];
  approximate: boolean;
  onError: () => void;
};

function routeLine(
  plan: RoutePlan,
  stops: PlanStop[],
): { line: [number, number][]; approximate: boolean } {
  const geometry = plan.geometry as
    { type?: string; coordinates?: [number, number][] } | null | undefined;
  if (
    geometry?.type === 'LineString' &&
    Array.isArray(geometry.coordinates) &&
    geometry.coordinates.length > 1
  ) {
    return {
      line: geometry.coordinates,
      approximate: plan.warnings.includes('GEOMETRY_APPROXIMATE'),
    };
  }
  return { line: stops.map((stop) => [stop.lon, stop.lat]), approximate: true };
}

/** The ordered stop list, used when there is no map style or the map cannot start. */
function StopOrder({ stops }: { stops: MapStop[] }) {
  return (
    <ol className="flex flex-col gap-2 p-4 text-sm" data-testid="map-fallback">
      {stops.map((stop) => (
        <li key={stop.number} className="flex items-center gap-3">
          <span className="flex size-7 flex-none items-center justify-center rounded-round bg-red text-xs font-semibold text-surface">
            {stop.number}
          </span>
          <span>{stop.label}</span>
        </li>
      ))}
    </ol>
  );
}

export function PlanMap({ plan }: { plan: RoutePlan }) {
  const t = useTranslations('plans.map');
  const styleUrl = process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? '';
  const attribution = process.env.NEXT_PUBLIC_MAP_ATTRIBUTION || t('attribution');
  const [Canvas, setCanvas] = useState<ComponentType<CanvasProps> | null>(null);
  const [failed, setFailed] = useState(false);
  const [view, setView] = useState<'map' | 'list'>('map');
  const actions = plan.stops.filter(isAction);
  const stops: MapStop[] = actions.map((stop, index) => ({
    number: index + 1,
    label: stop.label,
    lat: stop.lat,
    lon: stop.lon,
  }));
  const { line, approximate } = routeLine(plan, actions);
  const mapAvailable = styleUrl !== '' && !failed && stops.length > 0;

  useEffect(() => {
    if (styleUrl === '') return;
    let active = true;
    import('./map-canvas')
      .then((module) => {
        if (active) setCanvas(() => module.MapCanvas);
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => {
      active = false;
    };
  }, [styleUrl]);

  return (
    <section className="flex flex-col gap-3" aria-label={t('title')}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2>{t('title')}</h2>
        {mapAvailable && (
          <Segmented
            label={t('view')}
            value={view}
            onValueChange={setView}
            options={[
              { value: 'map', label: t('map') },
              { value: 'list', label: t('list') },
            ]}
          />
        )}
      </div>
      <div className="relative overflow-hidden rounded-card bg-well shadow-card">
        {mapAvailable && view === 'map' ? (
          <div className="relative h-96" data-testid="map" data-approximate={approximate}>
            {Canvas && (
              <Canvas
                styleUrl={styleUrl}
                stops={stops}
                line={line}
                approximate={approximate}
                onError={() => setFailed(true)}
              />
            )}
            <span className="absolute bottom-1 left-2 rounded-segment bg-surface px-1.5 text-xs text-ink2">
              {attribution}
            </span>
          </div>
        ) : (
          <>
            {!mapAvailable && <p className="px-4 pt-4 text-sm text-ink2">{t('unavailable')}</p>}
            <StopOrder stops={stops} />
          </>
        )}
      </div>
      {approximate && <p className="text-xs text-ink3">{t('approximate')}</p>}
    </section>
  );
}
