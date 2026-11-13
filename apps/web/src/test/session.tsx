import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactElement, ReactNode } from 'react';
import { ToastProvider } from '@/components/ui/toast';
import { TooltipProvider } from '@/components/ui/tooltip';
import { SessionProvider } from '@/features/auth';
import { setCsrfToken } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { bundles, type TestLocale } from './render';
import { apiUrl } from './msw/handlers';
import { server } from './msw/server';

export type TestUser = components['schemas']['UserView'];

export const dispatcher: TestUser = {
  id: '11111111-1111-4111-8111-111111111111',
  email: 'dispatcher@example.test',
  role: 'dispatcher',
  locale: 'en',
};

/** `/auth/me` answers with this user (or 401 for null) and a CSRF token. */
export function signInAs(user: TestUser | null) {
  server.use(
    http.get(apiUrl('/api/v1/auth/me'), () =>
      user
        ? HttpResponse.json({ user, csrfToken: 'csrf-test-token' })
        : HttpResponse.json({ code: 'UNAUTHENTICATED' }, { status: 401 }),
    ),
  );
}

/** Renders inside the real providers a page gets: messages, query cache and the session. */
export function renderWithSession(
  ui: ReactElement,
  { locale = 'en', ...options }: RenderOptions & { locale?: TestLocale } = {},
) {
  setCsrfToken(null);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <NextIntlClientProvider locale={locale} messages={bundles[locale]} timeZone="UTC">
        <QueryClientProvider client={client}>
          <ToastProvider dismissLabel={bundles[locale].common.dismiss}>
            <TooltipProvider>
              <SessionProvider>{children}</SessionProvider>
            </TooltipProvider>
          </ToastProvider>
        </QueryClientProvider>
      </NextIntlClientProvider>
    );
  }
  return render(ui, { wrapper: Wrapper, ...options });
}
