import { execFileSync, spawnSync } from 'node:child_process';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const web = path.resolve(import.meta.dirname, '../../..');
const generator = path.join(web, 'node_modules/.bin/openapi-typescript');

describe('[AC-FEAT-005-20] contract drift and the HTTP boundary', () => {
  it('regenerating schema.d.ts from contracts/openapi.json changes nothing', () => {
    const out = path.join(mkdtempSync(path.join(tmpdir(), 'schema-')), 'schema.d.ts');
    execFileSync(generator, [path.join(web, '../../contracts/openapi.json'), '-o', out], {
      cwd: web,
      stdio: 'pipe',
    });
    const committed = readFileSync(path.join(web, 'src/lib/api/schema.d.ts'), 'utf8');
    expect(readFileSync(out, 'utf8') === committed).toBe(true);
  });

  it('finds no fetch( outside src/lib/api in the real source', () => {
    const result = spawnSync('node', [path.join(web, 'scripts/check-fetch-usage.mjs')], {
      encoding: 'utf8',
    });
    expect(result.stderr).toBe('');
    expect(result.status).toBe(0);
  });

  it('fails on a fetch( call outside lib/api and accepts one inside', () => {
    const root = mkdtempSync(path.join(tmpdir(), 'src-'));
    mkdirSync(path.join(root, 'lib/api'), { recursive: true });
    mkdirSync(path.join(root, 'features/fleet'), { recursive: true });
    writeFileSync(path.join(root, 'lib/api/client.ts'), "export const a = () => fetch('/x');\n");
    writeFileSync(path.join(root, 'features/fleet/ok.test.ts'), "const a = fetch('/x');\n");
    const clean = spawnSync('node', [path.join(web, 'scripts/check-fetch-usage.mjs'), root]);
    expect(clean.status).toBe(0);
    writeFileSync(
      path.join(root, 'features/fleet/bad.ts'),
      "export const b = () => fetch('/y');\n",
    );
    writeFileSync(path.join(root, 'features/fleet/bad2.ts'), 'export const c = window.fetch(1);\n');
    const dirty = spawnSync('node', [path.join(web, 'scripts/check-fetch-usage.mjs'), root], {
      encoding: 'utf8',
    });
    expect(dirty.status).toBe(1);
    expect(dirty.stderr).toContain('features/fleet/bad.ts:1');
    expect(dirty.stderr).toContain('features/fleet/bad2.ts:1');
  });

  it('keeps English and Polish message keys identical, and notices a difference', () => {
    const real = spawnSync('node', [path.join(web, 'scripts/check-messages.mjs')], {
      encoding: 'utf8',
    });
    expect(real.stderr).toBe('');
    expect(real.status).toBe(0);
    const directory = mkdtempSync(path.join(tmpdir(), 'messages-'));
    writeFileSync(path.join(directory, 'en.json'), JSON.stringify({ a: { b: 'x', c: 'y' } }));
    writeFileSync(path.join(directory, 'pl.json'), JSON.stringify({ a: { b: 'x' }, d: 'z' }));
    const broken = spawnSync('node', [path.join(web, 'scripts/check-messages.mjs'), directory], {
      encoding: 'utf8',
    });
    expect(broken.status).toBe(1);
    expect(broken.stderr).toContain('missing in pl.json: a.c');
    expect(broken.stderr).toContain('missing in en.json: d');
  });
});
