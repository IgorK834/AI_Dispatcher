'use client';

import 'maplibre-gl/dist/maplibre-gl.css';
import { Layer, Map, Marker, NavigationControl, Source } from 'react-map-gl/maplibre';
import type { MapStop } from './plan-map';

type MapCanvasProps = {
  styleUrl: string;
  stops: MapStop[];
  line: [number, number][];
  approximate: boolean;
  onError: () => void;
};

/** The MapLibre part, loaded on demand: it needs a browser and WebGL. */
export function MapCanvas({ styleUrl, stops, line, approximate, onError }: MapCanvasProps) {
  const lons = stops.map((stop) => stop.lon);
  const lats = stops.map((stop) => stop.lat);
  const bounds: [number, number, number, number] = [
    Math.min(...lons),
    Math.min(...lats),
    Math.max(...lons),
    Math.max(...lats),
  ];
  // MapLibre paints with WebGL and cannot resolve a CSS variable: read the token's value.
  const red = getComputedStyle(document.documentElement).getPropertyValue('--red').trim() || 'red';
  return (
    <Map
      mapStyle={styleUrl}
      attributionControl={false}
      initialViewState={{ bounds, fitBoundsOptions: { padding: 48 } }}
      style={{ width: '100%', height: '100%' }}
      onError={onError}
    >
      <NavigationControl position="bottom-right" />
      <Source
        id="route"
        type="geojson"
        data={{
          type: 'Feature',
          properties: {},
          geometry: { type: 'LineString', coordinates: line },
        }}
      >
        <Layer
          id="route-line"
          type="line"
          layout={{ 'line-cap': 'round', 'line-join': 'round' }}
          paint={{
            'line-color': red,
            'line-width': 3,
            ...(approximate ? { 'line-dasharray': [2, 2] } : {}),
          }}
        />
      </Source>
      {stops.map((stop) => (
        <Marker key={stop.number} longitude={stop.lon} latitude={stop.lat}>
          <span
            data-testid="map-marker"
            className="flex size-7 items-center justify-center rounded-round bg-red text-xs font-semibold text-surface ring-2 ring-surface"
          >
            {stop.number}
          </span>
        </Marker>
      ))}
    </Map>
  );
}
