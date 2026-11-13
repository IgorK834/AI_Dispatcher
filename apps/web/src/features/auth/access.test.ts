import { describe, expect, it } from 'vitest';
import { activeHref, mayOpen, navigationFor } from './access';

describe('role access', () => {
  it('hides the admin screen from dispatcher and demo, and shows it to admin', () => {
    const keys = (role: 'admin' | 'dispatcher' | 'demo') =>
      navigationFor(role).map((item) => item.key);
    expect(keys('admin')).toEqual(['assistant', 'fleet', 'offers', 'optimizer', 'admin']);
    expect(keys('dispatcher')).toEqual(['assistant', 'fleet', 'offers', 'optimizer']);
    expect(keys('demo')).toEqual(['assistant', 'fleet', 'offers', 'optimizer']);
  });

  it('allows /admin only for admins and every other screen for every role', () => {
    expect(mayOpen('admin', '/admin')).toBe(true);
    expect(mayOpen('dispatcher', '/admin')).toBe(false);
    expect(mayOpen('demo', '/admin/anything')).toBe(false);
    expect(mayOpen('demo', '/fleet')).toBe(true);
    expect(mayOpen('dispatcher', '/plans/abc')).toBe(true);
  });

  it('finds the current navigation entry', () => {
    expect(activeHref('/')).toBe('/');
    expect(activeHref('/fleet')).toBe('/fleet');
    expect(activeHref('/fleet/drivers')).toBe('/fleet');
    expect(activeHref('/plans/1')).toBe('');
  });
});
