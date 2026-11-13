import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactElement, ReactNode } from 'react';
import { ToastProvider } from '@/components/ui/toast';
import { TooltipProvider } from '@/components/ui/tooltip';
import { bundles, type TestLocale } from './render';

/** The providers a screen needs (messages, fresh query cache, toasts, tooltips), without a session. */
export function renderApp(ui: ReactElement, locale: TestLocale = 'en') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <NextIntlClientProvider locale={locale} messages={bundles[locale]} timeZone="UTC">
        <QueryClientProvider client={client}>
          <ToastProvider dismissLabel={bundles[locale].common.dismiss}>
            <TooltipProvider>{children}</TooltipProvider>
          </ToastProvider>
        </QueryClientProvider>
      </NextIntlClientProvider>
    );
  }
  return { client, ...render(ui, { wrapper: Wrapper }) };
}
