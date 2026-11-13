'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { Suspense, useState, type ReactNode } from 'react';
import { ToastProvider } from '@/components/ui/toast';
import { TooltipProvider } from '@/components/ui/tooltip';
import { SessionProvider } from '@/features/auth';

/** Query cache, toasts, tooltips and the session for the whole app. */
export function Providers({ children }: { children: ReactNode }) {
  const t = useTranslations('common');
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { refetchOnWindowFocus: false, retry: 1 } },
      }),
  );
  return (
    <QueryClientProvider client={client}>
      <ToastProvider dismissLabel={t('dismiss')}>
        <TooltipProvider>
          <Suspense>
            <SessionProvider>{children}</SessionProvider>
          </Suspense>
        </TooltipProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}
