import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { renderWithIntl } from '@/test/render';
import { TopBar } from './top-bar';

vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh: vi.fn() }) }));

const items = [
  { href: '/', label: 'AI Dispatcher' },
  { href: '/fleet', label: 'Fleet' },
];

describe('TopBar', () => {
  it('shows the navigation with the active page marked, the badge and the language switch', () => {
    renderWithIntl(
      <TopBar
        items={items}
        activeHref="/fleet"
        navLabel="Main navigation"
        appName="RoutePilot AI"
        syntheticLabel="SYNTHETIC DATA"
        account={<button type="button">dispatcher@example.test</button>}
      />,
    );
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Fleet' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'AI Dispatcher' })).not.toHaveAttribute('aria-current');
    expect(screen.getByText('SYNTHETIC DATA')).toBeVisible();
    expect(screen.getByRole('group', { name: 'Language' })).toBeVisible();
    expect(screen.getByRole('button', { name: 'dispatcher@example.test' })).toBeVisible();
  });

  it('has no navigation and no badge on the sign-in page', () => {
    renderWithIntl(
      <TopBar items={[]} activeHref="/login" navLabel="Main navigation" appName="RoutePilot AI" />,
    );
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(screen.queryByText('SYNTHETIC DATA')).not.toBeInTheDocument();
    expect(screen.getByRole('group', { name: 'Language' })).toBeVisible();
  });
});
