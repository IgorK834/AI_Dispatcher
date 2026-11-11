import { ESLint } from 'eslint';
import { expect, it } from 'vitest';

it('[AC-FEAT-000-11] enforces feature entry points and the HTTP boundary', async () => {
  const eslint = new ESLint();
  const cases = [
    ["export {value} from '@/features/offers/internal';", 'src/features/fleet/fixture.ts', true],
    ["export {value} from '@/features/offers';", 'src/features/fleet/fixture.ts', false],
    ["export const load = () => fetch('/health');", 'src/features/fleet/fixture.ts', true],
    ["export const load = () => fetch('/health');", 'src/lib/api/fixture.ts', false],
  ] as const;
  for (const [code, filePath, forbidden] of cases) {
    const results = await eslint.lintText(code, { filePath });
    const violations = results
      .flatMap((result) => result.messages)
      .filter((message) => message.ruleId === 'routepilot/imports');
    expect(violations.length > 0).toBe(forbidden);
  }
});
