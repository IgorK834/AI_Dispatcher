import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithIntl } from '@/test/render';
import { VanSide } from './van-side';

describe('VanSide', () => {
  it('has the accessible name "Curtain-sider van up to 3.5 t, <label>" and draws the label', () => {
    renderWithIntl(<VanSide label="BUS-01" />);
    const drawing = screen.getByRole('img', { name: 'Curtain-sider van up to 3.5 t, BUS-01' });
    expect(drawing).toHaveTextContent('BUS-01');
  });

  it('translates the name for the Polish locale', () => {
    renderWithIntl(<VanSide label="BUS-01" />, { locale: 'pl' });
    expect(screen.getByRole('img', { name: 'Furgon z plandeką do 3,5 t, BUS-01' })).toBeVisible();
  });

  it('takes its width and accent as props', () => {
    const { container, rerender } = renderWithIntl(<VanSide label="BUS-02" width={96} />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('width', '96');
    expect(container.innerHTML).toContain('var(--red)');
    rerender(<VanSide label="BUS-02" width={96} accent="ink" />);
    expect(container.innerHTML).not.toContain('var(--red)');
  });

  it('is hidden from assistive technology when decorative', () => {
    const { container } = renderWithIntl(<VanSide label="BUS-01" decorative />);
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });
});
