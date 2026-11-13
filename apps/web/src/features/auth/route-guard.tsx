'use client';

import Link from 'next/link';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useEffect, type ReactNode } from 'react';
import { ApiUnreachable } from '@/components/app-shell/api-unreachable';
import { mayOpen } from './access';
import { loginUrl } from './next-path';
import { useSession } from './session';

/** FR-2: no session redirects to /login?next=..., and a role without access sees a notice. */
export function RouteGuard({ children }: { children: ReactNode }) {
  const t = useTranslations('auth');
  const { state, reload } = useSession();
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const here = `${pathname}${search.size > 0 ? `?${search.toString()}` : ''}`;

  useEffect(() => {
    if (state.status === 'anonymous') router.replace(loginUrl(here));
  }, [state.status, router, here]);

  if (state.status === 'unreachable') return <ApiUnreachable onRetry={reload} />;
  if (state.status !== 'authenticated') {
    return (
      <p role="status" className="p-10 text-ink2">
        {t('checkingSession')}
      </p>
    );
  }
  if (!mayOpen(state.user.role, pathname)) {
    return (
      <section aria-labelledby="no-access" className="mx-auto max-w-lg p-10">
        <h1 id="no-access" className="font-display text-2xl font-medium text-ink">
          {t('noAccess.title')}
        </h1>
        <p className="mt-2 text-ink2">{t('noAccess.body')}</p>
        <Link href="/" className="mt-4 inline-block font-semibold text-red">
          {t('noAccess.back')}
        </Link>
      </section>
    );
  }
  return <>{children}</>;
}
