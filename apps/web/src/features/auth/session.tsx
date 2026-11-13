'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api, onUnauthorized, setCsrfToken } from '@/lib/api/client';
import type { components } from '@/lib/api/schema';
import { loginUrl } from './next-path';

export type SessionUser = components['schemas']['UserView'];

export type SessionState =
  | { status: 'loading' }
  | { status: 'anonymous' }
  | { status: 'unreachable' }
  | { status: 'authenticated'; user: SessionUser };

type SessionApi = {
  state: SessionState;
  /** Called by the login form after a successful sign-in. */
  signedIn: (user: SessionUser, csrfToken: string) => void;
  signOut: () => Promise<void>;
  /** Asks the API again, for example after "Cannot reach the API". */
  reload: () => void;
};

const SessionContext = createContext<SessionApi | null>(null);

export function useSession(): SessionApi {
  const context = useContext(SessionContext);
  if (!context) throw new Error('useSession needs a SessionProvider');
  return context;
}

/**
 * Holds the session of the signed-in user (FR-5): `/auth/me` runs on every full page load, the
 * CSRF token stays in memory, and any 401 clears the state and goes to /login?next=...
 */
export function SessionProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const search = useSearchParams();
  const [state, setState] = useState<SessionState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  const here = `${pathname}${search.size > 0 ? `?${search.toString()}` : ''}`;

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data, response } = await api.GET('/api/v1/auth/me', {});
        if (cancelled) return;
        if (data) {
          setCsrfToken(data.csrfToken);
          setState({ status: 'authenticated', user: data.user });
        } else if (response.status === 401) {
          setCsrfToken(null);
          setState({ status: 'anonymous' });
        } else {
          setState({ status: 'unreachable' });
        }
      } catch {
        // No response at all: the API is down or the browser blocked it (CORS), section 8.
        if (!cancelled) setState({ status: 'unreachable' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  useEffect(
    () =>
      onUnauthorized(() => {
        setCsrfToken(null);
        setState({ status: 'anonymous' });
        router.replace(loginUrl(here));
      }),
    [router, here],
  );

  const signedIn = useCallback((user: SessionUser, csrfToken: string) => {
    setCsrfToken(csrfToken);
    setState({ status: 'authenticated', user });
  }, []);

  const signOut = useCallback(async () => {
    await api.POST('/api/v1/auth/logout', {});
    setCsrfToken(null);
    setState({ status: 'anonymous' });
    router.replace('/login');
  }, [router]);

  const reload = useCallback(() => {
    setState({ status: 'loading' });
    setAttempt((count) => count + 1);
  }, []);

  const value = useMemo(
    () => ({ state, signedIn, signOut, reload }),
    [state, signedIn, signOut, reload],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
