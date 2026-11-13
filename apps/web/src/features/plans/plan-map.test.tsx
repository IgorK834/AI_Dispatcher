import { screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { goldPlan } from '@/test/fixtures/gold-001';
import { renderWithIntl } from '@/test/render';
import { PlanMap } from './plan-map';

const behaviour = vi.hoisted(() => ({ failInit: false }));

vi.mock('maplibre-gl/dist/maplibre-gl.css', () => ({}));
vi.mock('react-map-gl/maplibre', async () => {
  const React = await import('react');
  return {
    Map: ({ children, onError }: { children: ReactNode; onError: () => void }) => {
      React.useEffect(() => {
        if (behaviour.failInit) onError();
      }, [onError]);
      return <div data-testid="maplibre">{children}</div>;
    },
    Marker: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    NavigationControl: () => null,
    Source: ({ data, children }: { data: unknown; children: ReactNode }) => (
      <div data-testid="source" data-line={JSON.stringify(data)}>
        {children}
      </div>
    ),
    Layer: ({ paint }: { paint: Record<string, unknown> }) => (
      <div data-testid="layer" data-dashed={String('line-dasharray' in paint)} />
    ),
  };
});

afterEach(() => {
  vi.unstubAllEnvs();
  behaviour.failInit = false;
});

const withGeometry = (approximate: boolean) => ({
  ...goldPlan,
  warnings: approximate ? ['GEOMETRY_APPROXIMATE'] : [],
  geometry: {
    type: 'LineString',
    coordinates: [
      [19.02, 50.26],
      [17.03, 51.1],
      [13.74, 51.05],
    ],
  },
});

describe('[AC-FEAT-005-23] plan map', () => {
  it('shows numbered markers in plan order, the route and the attribution', async () => {
    vi.stubEnv('NEXT_PUBLIC_MAP_STYLE_URL', 'https://tiles.example.test/style.json');
    renderWithIntl(<PlanMap plan={withGeometry(false)} />);
    await waitFor(() => expect(screen.getAllByTestId('map-marker')).toHaveLength(6));
    expect(screen.getAllByTestId('map-marker').map((marker) => marker.textContent)).toEqual([
      '1',
      '2',
      '3',
      '4',
      '5',
      '6',
    ]);
    expect(
      JSON.parse(screen.getByTestId('source').getAttribute('data-line') ?? '{}').geometry
        .coordinates,
    ).toHaveLength(3);
    expect(screen.getByTestId('layer')).toHaveAttribute('data-dashed', 'false');
    expect(screen.getByText(en.plans.map.attribution)).toBeVisible();
  });

  it('draws the route dashed when it is approximate', async () => {
    vi.stubEnv('NEXT_PUBLIC_MAP_STYLE_URL', 'https://tiles.example.test/style.json');
    renderWithIntl(<PlanMap plan={withGeometry(true)} />);
    expect(await screen.findByTestId('layer')).toHaveAttribute('data-dashed', 'true');
    expect(screen.getByText(en.plans.map.approximate)).toBeVisible();
  });

  it('shows the ordered stop list when the map fails to initialise, without an error boundary', async () => {
    vi.stubEnv('NEXT_PUBLIC_MAP_STYLE_URL', 'https://tiles.example.test/style.json');
    behaviour.failInit = true;
    renderWithIntl(<PlanMap plan={withGeometry(false)} />);
    const list = await screen.findByTestId('map-fallback');
    expect(list.querySelectorAll('li')).toHaveLength(6);
    expect(list.querySelectorAll('li')[0]).toHaveTextContent('Katowice');
    expect(screen.getByText(en.plans.map.unavailable)).toBeVisible();
    expect(screen.queryByTestId('maplibre')).toBeNull();
  });

  it('shows the list when no style URL is configured', () => {
    vi.stubEnv('NEXT_PUBLIC_MAP_STYLE_URL', '');
    renderWithIntl(<PlanMap plan={withGeometry(false)} />);
    expect(screen.getByTestId('map-fallback')).toBeVisible();
    expect(screen.queryByTestId('maplibre')).toBeNull();
  });
});
