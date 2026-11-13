import { readFileSync } from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const root = path.resolve(import.meta.dirname, '../../../..');
const tokens = JSON.parse(readFileSync(path.join(root, 'docs/design/tokens.json'), 'utf8')) as {
  color: Record<string, { value: string }>;
  status: Record<string, { bg: string; fg: string }>;
  radius: Record<string, number>;
};
const css = readFileSync(path.resolve(import.meta.dirname, 'tokens.css'), 'utf8').toLowerCase();
const theme = readFileSync(path.resolve(import.meta.dirname, '../app/globals.css'), 'utf8');

describe('design tokens in code (FR-31)', () => {
  it('maps every colour of tokens.json to a CSS variable', () => {
    for (const [name, token] of Object.entries(tokens.color)) {
      expect(css, name).toContain(token.value.toLowerCase());
    }
  });

  it('maps every status level colour and every radius', () => {
    for (const [name, level] of Object.entries(tokens.status)) {
      if (name === 'attention' || name === 'error' || name === 'synthetic') continue; // use core tokens
      expect(css, `${name} bg`).toContain(level.bg.toLowerCase());
      expect(css, `${name} fg`).toContain(level.fg.toLowerCase());
    }
    for (const [name, px] of Object.entries(tokens.radius)) {
      expect(css, `radius ${name}`).toMatch(new RegExp(`--radius-${name}:\\s*${px}px`));
    }
  });

  it('exposes the core colours to Tailwind and drops its default palette', () => {
    expect(theme).toContain('--color-*: initial;');
    for (const name of ['ground', 'surface', 'ink', 'ink2', 'ink3', 'red', 'red-tint', 'line']) {
      expect(theme, name).toContain(`--color-${name}:`);
    }
  });
});
