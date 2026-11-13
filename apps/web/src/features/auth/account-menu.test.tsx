import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';
import { getCsrfToken } from '@/lib/api/client';
import { apiUrl } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { dispatcher, renderWithSession, signInAs } from '@/test/session';
import { AccountMenu } from './account-menu';

const { replace } = vi.hoisted(() => ({ replace: vi.fn() }));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

describe('AccountMenu', () => {
  it('shows email and role, keeps the CSRF token in memory and signs out with it', async () => {
    const user = userEvent.setup();
    signInAs(dispatcher);
    let header: string | null = null;
    server.use(
      http.post(apiUrl('/api/v1/auth/logout'), ({ request }) => {
        header = request.headers.get('X-CSRF-Token');
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithSession(<AccountMenu />);
    const button = await screen.findByRole('button', { name: 'Account' });
    expect(button).toHaveTextContent('dispatcher@example.test');
    expect(button).toHaveTextContent('Dispatcher');
    expect(getCsrfToken()).toBe('csrf-test-token');
    await user.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    await user.click(screen.getByRole('button', { name: 'Sign out' }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/login'));
    expect(header).toBe('csrf-test-token');
    expect(getCsrfToken()).toBeNull();
  });

  it('closes with Escape', async () => {
    const user = userEvent.setup();
    signInAs(dispatcher);
    renderWithSession(<AccountMenu />);
    const button = await screen.findByRole('button', { name: 'Account' });
    await user.click(button);
    await user.keyboard('{Escape}');
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  it('renders no account button without a session', async () => {
    signInAs(null);
    renderWithSession(<AccountMenu />);
    await waitFor(() => expect(replace).not.toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: 'Account' })).not.toBeInTheDocument();
  });
});
