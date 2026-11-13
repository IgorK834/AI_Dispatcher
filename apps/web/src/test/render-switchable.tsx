import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactElement, ReactNode } from 'react';
import { ToastProvider } from '@/components/ui/toast';
import { TooltipProvider } from '@/components/ui/tooltip';
import { SessionProvider } from '@/features/auth';
import { setCsrfToken } from '@/lib/api/client';
import { bundles, type TestLocale } from './render';

/**
 * Renders a screen in the real providers and lets the test switch the language while the query
 * cache stays: a screen that re-fetches its data on a language switch would show up as a request.
 */
export function renderSwitchable(ui: ReactElement, initial: TestLocale = 'en') {
  setCsrfToken(null);
  let locale: TestLocale = initial;
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
  const view = render(ui, { wrapper: Wrapper });
  return {
    ...view,
    switchTo(next: TestLocale) {
      locale = next;
      view.rerender(ui);
    },
  };
}
