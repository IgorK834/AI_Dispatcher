import { vi } from 'vitest';

/** A controllable stand-in for next/navigation; tests mock the module with `navigationModule`. */
export const navigation = {
  replace: vi.fn(),
  refresh: vi.fn(),
  pathname: '/fleet',
  search: new URLSearchParams(),
  reset(pathname = '/fleet', search = '') {
    this.replace.mockClear();
    this.refresh.mockClear();
    this.pathname = pathname;
    this.search = new URLSearchParams(search);
  },
};

export const navigationModule = {
  useRouter: () => ({ replace: navigation.replace, refresh: navigation.refresh }),
  usePathname: () => navigation.pathname,
  useSearchParams: () => navigation.search,
};
