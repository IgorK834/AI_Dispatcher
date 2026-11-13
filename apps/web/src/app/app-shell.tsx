'use client';

import { useQuery } from '@tanstack/react-query';
import { useTranslations } from 'next-intl';
import { usePathname } from 'next/navigation';
import { Suspense, type ReactNode } from 'react';
import { TopBar } from '@/components/app-shell/top-bar';
import { AccountMenu, RouteGuard, activeHref, navigationFor, useSession } from '@/features/auth';
import { api } from '@/lib/api/client';

/** Whether demo data is present: any listed driver is synthetic (the badge is permanent then). */
function useSyntheticData(enabled: boolean): boolean {
  const { data } = useQuery({
    queryKey: ['synthetic-data'],
    enabled,
    staleTime: 60_000,
    queryFn: async () => {
      const { data: page } = await api.GET('/api/v1/drivers', { params: { query: { limit: 1 } } });
      return page?.items.some((driver) => driver.isSynthetic) ?? false;
    },
  });
  return data ?? false;
}

export function AppShell({ children }: { children: ReactNode }) {
  const t = useTranslations('common');
  const pathname = usePathname();
  const { state } = useSession();
  const onLogin = pathname === '/login';
  const user = state.status === 'authenticated' ? state.user : null;
  const synthetic = useSyntheticData(user !== null);
  const items = user
    ? navigationFor(user.role).map((item) => ({ href: item.href, label: t(`nav.${item.key}`) }))
    : [];

  if (onLogin) return <>{children}</>;
  return (
    <>
      <TopBar
        items={items}
        activeHref={activeHref(pathname)}
        navLabel={t('nav.label')}
        appName={t('appTitle')}
        syntheticLabel={synthetic ? t('syntheticData') : undefined}
        account={<AccountMenu />}
      />
      <main className="mx-auto w-full max-w-[1440px] px-10 py-6">
        <Suspense>
          <RouteGuard>{children}</RouteGuard>
        </Suspense>
      </main>
    </>
  );
}
