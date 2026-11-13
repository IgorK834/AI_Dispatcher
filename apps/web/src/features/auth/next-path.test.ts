import { describe, expect, it } from 'vitest';
import { loginUrl, safeNextPath } from './next-path';

describe('safeNextPath', () => {
  it('accepts same-site absolute paths', () => {
    expect(safeNextPath('/fleet')).toBe('/fleet');
    expect(safeNextPath('/plans/3?variant=fuel')).toBe('/plans/3?variant=fuel');
  });

  it('falls back to the start page for anything that could leave the site', () => {
    for (const value of [
      null,
      undefined,
      '',
      'fleet',
      '//evil.example',
      '/\\evil.example',
      'https://x',
    ]) {
      expect(safeNextPath(value)).toBe('/');
    }
  });
});

describe('loginUrl', () => {
  it('keeps the target readable and encodes the rest', () => {
    expect(loginUrl('/fleet')).toBe('/login?next=/fleet');
    expect(loginUrl('/offers?source=mock&country=PL')).toBe(
      '/login?next=/offers%3Fsource%3Dmock%26country%3DPL',
    );
    expect(loginUrl('/')).toBe('/login');
  });
});
