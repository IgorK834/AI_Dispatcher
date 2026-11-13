import type { SessionUser } from './session';

export type Role = SessionUser['role'];

export type NavTarget = {
  href: string;
  key: 'assistant' | 'fleet' | 'offers' | 'optimizer' | 'admin';
};

const ALL_ROLES: Role[] = ['admin', 'dispatcher', 'demo'];

/** Screens of FEAT-005 section 4.1 with the roles that may open them. */
const SCREENS: (NavTarget & { roles: Role[] })[] = [
  { href: '/', key: 'assistant', roles: ALL_ROLES },
  { href: '/fleet', key: 'fleet', roles: ALL_ROLES },
  { href: '/offers', key: 'offers', roles: ALL_ROLES },
  { href: '/optimizer', key: 'optimizer', roles: ALL_ROLES },
  { href: '/admin', key: 'admin', roles: ['admin'] },
];

/** Navigation for a role: screens it may not use are absent, not disabled (FR-11). */
export function navigationFor(role: Role): NavTarget[] {
  return SCREENS.filter((screen) => screen.roles.includes(role)).map(({ href, key }) => ({
    href,
    key,
  }));
}

/** Whether a role may open a path; unknown paths are open (the page itself decides). */
export function mayOpen(role: Role, path: string): boolean {
  const screen = SCREENS.find(
    (candidate) =>
      candidate.href !== '/' && (path === candidate.href || path.startsWith(`${candidate.href}/`)),
  );
  return screen ? screen.roles.includes(role) : true;
}

/** The nav entry that is "current" for a path (the longest matching screen). */
export function activeHref(path: string): string {
  const match = SCREENS.filter(
    (screen) => screen.href !== '/' && (path === screen.href || path.startsWith(`${screen.href}/`)),
  ).sort((a, b) => b.href.length - a.href.length)[0];
  return match?.href ?? (path === '/' ? '/' : '');
}
