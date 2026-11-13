import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Banner } from './banner';
import { Meter } from './meter';
import { RouteTrack } from './route-track';
import { Table, TBody, Td, Th, THead, Tr } from './table';

describe('Table', () => {
  it('renders heads and right-aligned numeric cells', () => {
    render(
      <Table>
        <THead>
          <Tr>
            <Th>Driver</Th>
            <Th numeric>Km</Th>
          </Tr>
        </THead>
        <TBody>
          <Tr>
            <Td>D1</Td>
            <Td numeric>625</Td>
          </Tr>
        </TBody>
      </Table>,
    );
    expect(screen.getByRole('columnheader', { name: 'Km' }).className).toContain('text-right');
    expect(screen.getByRole('cell', { name: '625' }).className).toContain('text-right');
    expect(screen.getByRole('cell', { name: 'D1' }).className).not.toContain('text-right');
  });
});

describe('Meter', () => {
  it('exposes its value to assistive technology and always shows the number', () => {
    render(<Meter name="Work today" value={480} max={720} label="240 min left" />);
    const meter = screen.getByRole('meter', { name: 'Work today' });
    expect(meter).toHaveAttribute('aria-valuenow', '480');
    expect(meter).toHaveAttribute('aria-valuemax', '720');
    expect(meter).toHaveAttribute('aria-valuetext', '240 min left');
    expect(screen.getByText('240 min left')).toBeVisible();
  });

  it('clamps values and turns red for a low or brand meter', () => {
    const { rerender } = render(<Meter name="m" value={900} max={720} label="full" />);
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '720');
    expect(screen.getByRole('meter').firstElementChild?.className).toContain('bg-ink');
    rerender(<Meter name="m" value={-5} max={720} label="empty" tone="low" />);
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '0');
    expect(screen.getByRole('meter').firstElementChild?.className).toContain('bg-red');
  });
});

describe('RouteTrack', () => {
  it('names origin, destination and status', () => {
    render(
      <RouteTrack origin="Katowice" destination="Leipzig" progress={0} status="Not started" />,
    );
    expect(screen.getByRole('group', { name: 'Not started' })).toBeInTheDocument();
    expect(screen.getByText('Katowice')).toBeVisible();
    expect(screen.getByText('Leipzig')).toBeVisible();
  });
});

describe('Banner', () => {
  it('uses an alert role for attention and error and a status role for information', () => {
    render(
      <>
        <Banner level="error" title="Conflict">
          Changed elsewhere
        </Banner>
        <Banner level="attention">Assumption</Banner>
        <Banner level="info">FYI</Banner>
      </>,
    );
    expect(screen.getAllByRole('alert')).toHaveLength(2);
    expect(screen.getByRole('status')).toHaveTextContent('FYI');
    expect(screen.getByText('Conflict')).toBeVisible();
  });
});
