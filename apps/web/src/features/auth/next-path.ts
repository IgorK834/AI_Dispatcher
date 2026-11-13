/** Only same-site absolute paths are accepted as a post-login target (no open redirect). */
export function safeNextPath(value: string | null | undefined): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) {
    return '/';
  }
  return value;
}

export function loginUrl(path: string): string {
  if (path === '/' || path === '') return '/login';
  // Slashes stay readable: /login?next=/fleet; everything else in the path is encoded.
  return `/login?next=${encodeURIComponent(path).replaceAll('%2F', '/')}`;
}
