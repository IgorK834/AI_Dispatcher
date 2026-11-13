import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { api } from '@/lib/api/client';
import { apiUrl } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { dispatcher, renderWithSession, signInAs } from '@/test/session';
import { RouteGuard } from './route-guard';

const { replace, path, search } = vi.hoisted(() => ({
  replace: vi.fn(),
  path: { current: '/fleet' },
  search: { current: new URLSearchParams() },
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  usePathname: () => path.current,
  useSearchParams: () => search.current,
}));

function Protected() {
  return <p>fleet screen</p>;
}

beforeEach(() => {
  replace.mockClear();
  path.current = '/fleet';
  search.current = new URLSearchParams();
});

describe('[AC-FEAT-005-03] route protection', () => {
  it('redirects to /login?next=/fleet when there is no session', async () => {
    signInAs(null);
    renderWithSession(
      <RouteGuard>
        <Protected />
      </RouteGuard>,
    );
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login?next=/fleet'));
    expect(screen.queryByText('fleet screen')).not.toBeInTheDocument();
  });

  it('keeps the query string of the page in the redirect target', async () => {
    signInAs(null);
    path.current = '/offers';
    search.current = new URLSearchParams({ source: 'mock', country: 'PL' });
    renderWithSession(
      <RouteGuard>
        <Protected />
      </RouteGuard>,
    );
    await waitFor(() =>
      expect(replace).toHaveBeenCalledWith('/login?next=/offers%3Fsource%3Dmock%26country%3DPL'),
    );
  });

  it('redirects the same way after a 401 on a data request and clears the session', async () => {
    signInAs(dispatcher);
    server.use(http.get(apiUrl('/api/v1/drivers'), () => HttpResponse.json({}, { status: 401 })));
    renderWithSession(
      <RouteGuard>
        <Protected />
      </RouteGuard>,
    );
    expect(await screen.findByText('fleet screen')).toBeVisible();
    expect(replace).not.toHaveBeenCalled();
    await api.GET('/api/v1/drivers', {});
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login?next=/fleet'));
    // The session is cleared: the protected screen is gone while the redirect happens.
    await waitFor(() => expect(screen.queryByText('fleet screen')).not.toBeInTheDocument());
  });

  it('shows a "no access" page to a dispatcher who opens /admin', async () => {
    signInAs(dispatcher);
    path.current = '/admin';
    renderWithSession(
      <RouteGuard>
        <p>admin screen</p>
      </RouteGuard>,
    );
    expect(await screen.findByRole('heading', { name: en.auth.noAccess.title })).toBeVisible();
    expect(screen.getByText(en.auth.noAccess.body)).toBeVisible();
    expect(screen.queryByText('admin screen')).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it('lets an admin open /admin', async () => {
    signInAs({ ...dispatcher, role: 'admin' });
    path.current = '/admin';
    renderWithSession(
      <RouteGuard>
        <p>admin screen</p>
      </RouteGuard>,
    );
    expect(await screen.findByText('admin screen')).toBeVisible();
  });

  it('shows a loading message while the session is being checked', () => {
    server.use(http.get(apiUrl('/api/v1/auth/me'), () => new Promise<never>(() => undefined)));
    renderWithSession(
      <RouteGuard>
        <Protected />
      </RouteGuard>,
    );
    expect(screen.getByText(en.auth.checkingSession)).toBeVisible();
  });

  it('shows the full-page "Cannot reach the API" state and retries on request', async () => {
    const user = userEvent.setup();
    server.use(http.get(apiUrl('/api/v1/auth/me'), () => HttpResponse.error()));
    renderWithSession(
      <RouteGuard>
        <Protected />
      </RouteGuard>,
    );
    const title = await screen.findByRole('heading', { name: /Cannot reach the API at/ });
    expect(title).toHaveTextContent('http://localhost:8000');
    expect(screen.getByText(/CORS_ALLOWED_ORIGINS/)).toBeVisible();
    signInAs(dispatcher);
    await user.click(screen.getByRole('button', { name: en.common.apiUnreachable.retry }));
    expect(await screen.findByText('fleet screen')).toBeVisible();
  });
});
