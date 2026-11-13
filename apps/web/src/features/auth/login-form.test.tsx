import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { forwardRef, useImperativeHandle } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import pl from '../../../messages/pl.json';
import { apiUrl, problem } from '@/test/msw/handlers';
import { server } from '@/test/msw/server';
import { renderWithSession, signInAs } from '@/test/session';
import { LoginForm } from './login-form';

const { replace, reset, search } = vi.hoisted(() => ({
  replace: vi.fn(),
  reset: vi.fn(),
  search: { current: new URLSearchParams() },
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
  useSearchParams: () => search.current,
  usePathname: () => '/login',
}));

// The real widget loads a script from Cloudflare; this one hands out a token on a click.
vi.mock('@marsidev/react-turnstile', () => ({
  Turnstile: forwardRef<
    { reset: () => void },
    { siteKey: string; onSuccess?: (token: string) => void }
  >(function FakeTurnstile({ siteKey, onSuccess }, ref) {
    useImperativeHandle(ref, () => ({ reset }));
    return (
      <button type="button" data-site-key={siteKey} onClick={() => onSuccess?.('captcha-token')}>
        solve captcha
      </button>
    );
  }),
}));

type LoginRequest = { email: string; password: string; captchaToken: string };

function stubServer(login: () => Response | Promise<Response>) {
  const requests: LoginRequest[] = [];
  signInAs(null);
  server.use(
    http.get(apiUrl('/api/v1/auth/captcha-config'), () =>
      HttpResponse.json({ provider: 'turnstile', siteKey: 'site-key-1' }),
    ),
    http.post(apiUrl('/api/v1/auth/login'), async ({ request }) => {
      requests.push((await request.json()) as LoginRequest);
      return login();
    }),
  );
  return requests;
}

async function fillAndSubmit(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Email'), 'dispatcher@example.test');
  await user.type(screen.getByLabelText('Password'), 'wrong-password');
  await user.click(await screen.findByRole('button', { name: 'solve captcha' }));
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
}

beforeEach(() => {
  replace.mockClear();
  reset.mockClear();
  search.current = new URLSearchParams();
});

describe('[AC-FEAT-005-02] login failures', () => {
  it('shows a distinct translated message for each failure, clears the password, keeps the email', async () => {
    const user = userEvent.setup();
    const messages: string[] = [];
    const cases = [
      {
        response: () => problem(401, 'INVALID_CREDENTIALS'),
        expected: en.errors.INVALID_CREDENTIALS,
      },
      { response: () => problem(400, 'CAPTCHA_FAILED'), expected: en.errors.CAPTCHA_FAILED },
      {
        response: () => problem(429, 'RATE_LIMITED', { headers: { 'Retry-After': '30' } }),
        expected: 'Too many attempts. Wait 30 seconds and try again.',
      },
    ];
    for (const { response, expected } of cases) {
      stubServer(response);
      const { unmount } = renderWithSession(<LoginForm showLocalHint={false} />);
      await fillAndSubmit(user);
      const alert = await screen.findByText(expected);
      messages.push(alert.textContent ?? '');
      expect(screen.getByLabelText('Password')).toHaveValue('');
      expect(screen.getByLabelText('Email')).toHaveValue('dispatcher@example.test');
      unmount();
    }
    expect(new Set(messages).size).toBe(3);
  });

  it('resets the captcha after CAPTCHA_FAILED only, and asks for a new token', async () => {
    const user = userEvent.setup();
    stubServer(() => problem(400, 'CAPTCHA_FAILED'));
    renderWithSession(<LoginForm showLocalHint={false} />);
    await fillAndSubmit(user);
    await screen.findByText(en.errors.CAPTCHA_FAILED);
    await waitFor(() => expect(reset).toHaveBeenCalledTimes(1));
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled();
  });

  it('does not reset the captcha after wrong credentials', async () => {
    const user = userEvent.setup();
    stubServer(() => problem(401, 'INVALID_CREDENTIALS'));
    renderWithSession(<LoginForm showLocalHint={false} />);
    await fillAndSubmit(user);
    await screen.findByText(en.errors.INVALID_CREDENTIALS);
    expect(reset).not.toHaveBeenCalled();
  });

  it('shows the messages in Polish when the locale is pl', async () => {
    const user = userEvent.setup();
    stubServer(() => problem(401, 'INVALID_CREDENTIALS'));
    renderWithSession(<LoginForm showLocalHint={false} />, { locale: 'pl' });
    await user.type(screen.getByLabelText('E-mail'), 'a@example.test');
    await user.type(screen.getByLabelText('Hasło'), 'x');
    await user.click(await screen.findByRole('button', { name: 'solve captcha' }));
    await user.click(screen.getByRole('button', { name: 'Zaloguj się' }));
    expect(await screen.findByText(pl.errors.INVALID_CREDENTIALS)).toBeVisible();
  });
});

describe('login form behaviour', () => {
  it('keeps submit disabled until the captcha gives a token, then sends it with the form', async () => {
    const user = userEvent.setup();
    const requests = stubServer(() =>
      HttpResponse.json({
        user: { id: 'u1', email: 'dispatcher@example.test', role: 'dispatcher', locale: 'en' },
        csrfToken: 'csrf-1',
      }),
    );
    renderWithSession(<LoginForm showLocalHint={false} />);
    await user.type(screen.getByLabelText('Email'), 'dispatcher@example.test');
    await user.type(screen.getByLabelText('Password'), 'secret');
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled();
    const widget = await screen.findByRole('button', { name: 'solve captcha' });
    expect(widget).toHaveAttribute('data-site-key', 'site-key-1');
    await user.click(widget);
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/'));
    expect(requests).toEqual([
      { email: 'dispatcher@example.test', password: 'secret', captchaToken: 'captcha-token' },
    ]);
  });

  it('goes to the next page after sign-in, but never to another site', async () => {
    const user = userEvent.setup();
    const ok = () =>
      HttpResponse.json({
        user: { id: 'u1', email: 'a@example.test', role: 'demo', locale: 'en' },
        csrfToken: 'csrf-1',
      });
    for (const [next, target] of [
      ['/fleet', '/fleet'],
      ['//evil.example', '/'],
    ] as const) {
      replace.mockClear();
      search.current = new URLSearchParams({ next });
      stubServer(ok);
      const { unmount } = renderWithSession(<LoginForm showLocalHint={false} />);
      await fillAndSubmit(user);
      await waitFor(() => expect(replace).toHaveBeenCalledWith(target));
      unmount();
    }
  });

  it('explains invalid input under the fields and sends nothing', async () => {
    const user = userEvent.setup();
    const requests = stubServer(() => problem(401, 'INVALID_CREDENTIALS'));
    renderWithSession(<LoginForm showLocalHint={false} />);
    await user.type(screen.getByLabelText('Email'), 'not-an-email');
    await user.click(await screen.findByRole('button', { name: 'solve captcha' }));
    await user.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByText(en.auth.validation.emailInvalid)).toBeVisible();
    expect(screen.getByText(en.auth.validation.passwordRequired)).toBeVisible();
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true');
    expect(requests).toHaveLength(0);
  });

  it('shows the local demo hint only when asked to, with names and no passwords', async () => {
    stubServer(() => problem(401, 'INVALID_CREDENTIALS'));
    const { unmount } = renderWithSession(<LoginForm showLocalHint />);
    const hint = await screen.findByText(/demo@example.invalid/);
    expect(hint.textContent).toContain('admin@example.invalid');
    expect(hint.textContent).not.toMatch(/password:/i);
    unmount();
    renderWithSession(<LoginForm showLocalHint={false} />);
    expect(screen.queryByText(/demo@example.invalid/)).not.toBeInTheDocument();
  });

  it('reports a captcha configuration that cannot be loaded', async () => {
    signInAs(null);
    server.use(
      http.get(apiUrl('/api/v1/auth/captcha-config'), () => problem(500, 'INTERNAL_ERROR')),
    );
    renderWithSession(<LoginForm showLocalHint={false} />);
    expect(await screen.findByText(en.auth.form.captchaUnavailable)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeDisabled();
  });
});
