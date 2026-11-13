import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { ESLint } from 'eslint';
import { describe, expect, it } from 'vitest';

const eslint = new ESLint();
const fixtures = path.resolve(import.meta.dirname, 'test/fixtures');

async function ruleIds(code: string, filePath: string) {
  const [result] = await eslint.lintText(code, { filePath });
  return (result?.messages ?? []).map((message) => message.ruleId);
}

describe('[AC-FEAT-005-27] design-token lint rule', () => {
  const componentFile = path.resolve(import.meta.dirname, 'components/ui/fixture.tsx');

  it.each([
    ["export const a = '#D42A22';", 'a hex colour'],
    ["export const a = 'rgba(0, 0, 0, 0.5)';", 'an rgb function'],
    ["export const a = 'oklch(60% 0.2 30)';", 'a modern colour function'],
    ['export const a = <svg fill="white" />;', 'a named colour in a colour attribute'],
    ["export const a = { color: 'red' };", 'a named colour in a style property'],
    ["export const a = { fontFamily: 'Arial' };", 'font-family in a style object'],
    ["export const a = 'font-family: Arial';", 'font-family in a string'],
    ['export const a = `bg-[#fff]`;', 'an arbitrary Tailwind colour'],
  ])('rejects %s (%s)', async (code) => {
    expect(await ruleIds(code, componentFile)).toContain('routepilot/no-raw-colors');
  });

  it.each([
    ['export const a = <svg fill="var(--red)" />;'],
    ["export const a = 'bg-red-tint text-ink';"],
    ["export const a = { accent: 'red' };"], // a word, not a colour property
    ["export const a = 'transparent';"],
  ])('accepts %s', async (code) => {
    expect(await ruleIds(code, componentFile)).not.toContain('routepilot/no-raw-colors');
  });

  it('accepts raw values inside styles/tokens.css only (the file the rule exempts)', async () => {
    const tokens = path.resolve(import.meta.dirname, 'styles/tokens.ts');
    expect(await ruleIds("export const a = '#D42A22';", tokens)).toContain(
      'routepilot/no-raw-colors',
    );
  });

  it('fails on the bad component fixture and passes on the good one', async () => {
    const bad = readFileSync(path.join(fixtures, 'bad-component.fixture'), 'utf8');
    const good = readFileSync(path.join(fixtures, 'good-component.fixture'), 'utf8');
    const where = path.resolve(import.meta.dirname, 'components/fixture.tsx');
    const badIds = await ruleIds(bad, where);
    expect(badIds.filter((id) => id === 'routepilot/no-raw-colors').length).toBeGreaterThanOrEqual(
      4,
    );
    const goodIds = await ruleIds(good, where);
    expect(goodIds).not.toContain('routepilot/no-raw-colors');
    expect(goodIds).not.toContain('routepilot/no-hardcoded-text');
  });

  it('keeps raw colours out of every stylesheet except tokens.css', () => {
    const offenders: string[] = [];
    const walk = (directory: string) => {
      for (const entry of readdirSync(directory)) {
        const full = path.join(directory, entry);
        if (statSync(full).isDirectory()) walk(full);
        else if (
          entry.endsWith('.css') &&
          !full.endsWith(`${path.sep}styles${path.sep}tokens.css`)
        ) {
          const text = readFileSync(full, 'utf8');
          if (/#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(/.test(text)) offenders.push(full);
          if (/font-family\s*:/.test(text)) offenders.push(`${full} (font-family)`);
        }
      }
    };
    walk(path.resolve(import.meta.dirname));
    expect(offenders).toEqual([]);
  });
});

describe('[AC-FEAT-005-18] hard-coded text lint rule', () => {
  const where = path.resolve(import.meta.dirname, 'features/fleet/fixture.tsx');

  it('fails on text and on user-visible attributes written in the component', async () => {
    expect(await ruleIds('export const a = <p>Save the driver</p>;', where)).toContain(
      'routepilot/no-hardcoded-text',
    );
    expect(await ruleIds('export const a = <input placeholder="Search" />;', where)).toContain(
      'routepilot/no-hardcoded-text',
    );
    expect(await ruleIds('export const a = <button aria-label="Close" />;', where)).toContain(
      'routepilot/no-hardcoded-text',
    );
  });

  it('allows translated text, punctuation and numbers', async () => {
    const ids = await ruleIds('export const a = <p>{t("save")} / 12 — <b>{count}</b></p>;', where);
    expect(ids).not.toContain('routepilot/no-hardcoded-text');
  });

  it('is not applied to tests', async () => {
    const testFile = path.resolve(import.meta.dirname, 'features/fleet/fixture.test.tsx');
    expect(await ruleIds('export const a = <p>Save the driver</p>;', testFile)).not.toContain(
      'routepilot/no-hardcoded-text',
    );
  });
});
