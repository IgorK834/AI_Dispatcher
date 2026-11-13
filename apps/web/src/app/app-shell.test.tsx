import { screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiUrl } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { dispatcher, renderWithSession, signInAs } from '@/test/session';
import { AppShell } from './app-shell';

const { path } = vi.hoisted(() => ({ path: { current: '/fleet' } }));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
  usePathname: () => path.current,
  useSearchParams: () => new URLSearchParams(),
}));

function drivers(synthetic: boolean) {
  server.use(
    http.get(apiUrl('/api/v1/drivers'), () =>
      HttpResponse.json({ items: [{ id: 'd1', isSynthetic: synthetic }] }),
    ),
  );
}

beforeEach(() => {
  path.current = '/fleet';
});

describe('AppShell', () => {
  it('shows the role-filtered navigation, the active page and the synthetic badge', async () => {
    signInAs(dispatcher);
    drivers(true);
    renderWithSession(
      <AppShell>
        <p>page body</p>
      </AppShell>,
    );
    expect(await screen.findByText('page body')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Fleet' })).toHaveAttribute('aria-current', 'page');
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
    expect(await screen.findByText('SYNTHETIC DATA')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Account' })).toHaveTextContent(dispatcher.email);
  });

  it('shows the Admin link to an admin and no badge without demo data', async () => {
    signInAs({ ...dispatcher, role: 'admin' });
    drivers(false);
    renderWithSession(
      <AppShell>
        <p>page body</p>
      </AppShell>,
    );
    expect(await screen.findByRole('link', { name: 'Admin' })).toBeVisible();
    await waitFor(() => expect(screen.queryByText('SYNTHETIC DATA')).not.toBeInTheDocument());
  });

  it('renders only the page on /login: the sign-in page has its own header', async () => {
    path.current = '/login';
    signInAs(null);
    renderWithSession(
      <AppShell>
        <p>sign-in page</p>
      </AppShell>,
    );
    expect(await screen.findByText('sign-in page')).toBeVisible();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(screen.queryByRole('banner')).not.toBeInTheDocument();
  });
});
