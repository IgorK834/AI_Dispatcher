import { screen, waitFor } from '@testing-library/react';
import { ESLint } from 'eslint';
import { http, HttpResponse } from 'msw';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { forwardRef, useImperativeHandle } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../messages/en.json';
import pl from '../../messages/pl.json';
import { LoginForm } from '@/features/auth';
import { FleetScreen } from '@/features/fleet';
import { PlanScreen } from '@/features/plans';
import { driver, fiveDrivers } from '@/test/fixtures/fleet';
import { goldPlan, goldPlans } from '@/test/fixtures/gold-001';
import { importedOffer } from '@/test/fixtures/offers';
import { apiUrl } from '@/test/msw/handlers';
import { fleetApi } from '@/test/msw/handlers/fleet';
import { server } from '@/test/msw/server';
import { navigation } from '@/test/navigation';
import { renderSwitchable } from '@/test/render-switchable';
import { signInAs } from '@/test/session';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

// The real widget loads a script from Cloudflare; this one only has to show up on the page.
vi.mock('@marsidev/react-turnstile', () => ({
  Turnstile: forwardRef<{ reset: () => void }, { siteKey: string }>(
    function FakeTurnstile(_props, ref) {
      useImperativeHandle(ref, () => ({ reset: () => undefined }));
      return <div data-testid="captcha" />;
    },
  ),
}));

type Messages = Record<string, unknown>;

function keysOf(value: Messages, prefix = ''): string[] {
  return Object.entries(value).flatMap(([key, child]) =>
    typeof child === 'object' && child !== null
      ? keysOf(child as Messages, `${prefix}${key}.`)
      : [`${prefix}${key}`],
  );
}

function valueAt(messages: Messages, key: string): string {
  return key
    .split('.')
    .reduce<unknown>((node, part) => (node as Messages)[part], messages) as string;
}

describe('[AC-FEAT-005-18] EN/PL parity', () => {
  describe('message files', () => {
    it('have identical key sets in English and Polish', () => {
      const english = new Set(keysOf(en));
      const polish = new Set(keysOf(pl));
      expect([...english].filter((key) => !polish.has(key))).toEqual([]);
      expect([...polish].filter((key) => !english.has(key))).toEqual([]);
    });

    it('have no empty texts and keep the same {placeholders} in both languages', () => {
      const placeholders = (text: string) =>
        [...text.matchAll(/\{(\w+)(?:,|\})/g)].map((match) => match[1]).sort();
      for (const key of keysOf(en)) {
        const english = valueAt(en, key);
        const polish = valueAt(pl, key);
        expect(english.trim(), key).not.toBe('');
        expect(polish.trim(), key).not.toBe('');
        expect(placeholders(polish), `placeholders of ${key}`).toEqual(placeholders(english));
      }
    });

    it('give Polish counts the one / few / many forms (ICU plural rules)', () => {
      const plurals = keysOf(en).filter((key) => /\{\w+, plural,/.test(valueAt(en, key)));
      expect(plurals.length).toBeGreaterThan(0);
      for (const key of plurals) {
        const text = valueAt(pl, key);
        for (const form of ['one', 'few', 'many', 'other']) {
          expect(text, `${key} needs the "${form}" form`).toMatch(new RegExp(`\\b${form} \\{`));
        }
      }
    });
  });

  describe('the lint rule for hard-coded text', () => {
    it('fails on a component fixture with literal text and passes without it', async () => {
      const eslint = new ESLint();
      const fixture = readFileSync(
        path.resolve(import.meta.dirname, '../test/fixtures/hardcoded-literal.fixture'),
        'utf8',
      );
      const where = path.resolve(import.meta.dirname, '../features/fleet/fixture.tsx');
      const [bad] = await eslint.lintText(fixture, { filePath: where });
      const rules = (bad?.messages ?? []).filter(
        (message) => message.ruleId === 'routepilot/no-hardcoded-text',
      );
      expect(rules.length).toBeGreaterThanOrEqual(3); // the heading, the button and the aria-label
      const [good] = await eslint.lintText('export const a = <h2>{t("greeting")}</h2>;', {
        filePath: where,
      });
      expect(good?.messages.map((message) => message.ruleId)).not.toContain(
        'routepilot/no-hardcoded-text',
      );
    });
  });

  /** The names a person sees or hears: headings, controls, labels, table heads and text alternatives. */
  function visibleNames(root: HTMLElement): Set<string> {
    const names = new Set<string>();
    const add = (value: string | null | undefined) => {
      const text = value?.replace(/\s+/g, ' ').trim();
      if (text) names.add(text);
    };
    for (const element of root.querySelectorAll(
      'h1, h2, h3, h4, button, a, th, label, legend, summary, [role="tab"], [role="radio"], [role="status"], [role="alert"]',
    )) {
      add(element.textContent);
    }
    for (const element of root.querySelectorAll('[aria-label]'))
      add(element.getAttribute('aria-label'));
    for (const element of root.querySelectorAll('[placeholder]'))
      add(element.getAttribute('placeholder'));
    return names;
  }

  /** Text that is data or a name in both languages (no letters to translate, brand, codes, people, places). */
  const SAME_IN_BOTH = [
    /^[^\p{L}]*$/u, // numbers, money, punctuation
    /^RoutePilot AI$/,
    /^(PL|DE|CZ|FR|IT|EP|CO₂|CET|CEST)\b/,
    /^[A-Z]{2,}-\d+/, // BUS-01, MOCK-000117
    /^(Paweł Kurek|Ewa Sowa|Marta Lis-Wrona|Jan Bielak|Kamil Dąb)$/,
    /^(Katowice|Wrocław|Poznań|Łódź|Kraków|Opole|Dresden|Leipzig|Praha|Brno)$/,
    /^[\p{L} -]+( → [\p{L} -]+)+$/u, // a route made of place names
    /^(Status|Start)$/, // the same word in Polish
  ];

  const isData = (text: string) => SAME_IN_BOTH.some((pattern) => pattern.test(text));

  async function expectSwitchChangesEveryText(
    render: () => ReturnType<typeof renderSwitchable>,
    ready: () => Promise<unknown>,
  ) {
    const requests: string[] = [];
    const record = ({ request }: { request: Request }) => {
      requests.push(`${request.method} ${new URL(request.url).pathname}`);
    };
    server.events.on('request:start', record);
    try {
      const view = render();
      await ready();
      await new Promise((resolve) => setTimeout(resolve, 50));
      const english = visibleNames(view.container);
      const before = requests.length;
      expect(english.size).toBeGreaterThanOrEqual(3);

      view.switchTo('pl');
      await waitFor(() => expect(visibleNames(view.container)).not.toEqual(english));
      await new Promise((resolve) => setTimeout(resolve, 50));
      const polish = visibleNames(view.container);

      const untranslated = [...english].filter((text) => polish.has(text) && !isData(text));
      expect(untranslated, 'visible texts that stayed English').toEqual([]);
      expect(requests.length, 'a language switch must not reload data').toBe(before);
    } finally {
      server.events.removeListener('request:start', record);
    }
  }

  describe('switching the language', () => {
    beforeEach(() => {
      navigation.reset('/login');
      vi.stubEnv('NEXT_PUBLIC_MAP_STYLE_URL', '');
    });
    afterEach(() => vi.unstubAllEnvs());

    it('changes every visible text of the login screen', async () => {
      signInAs(null);
      server.use(
        http.get(apiUrl('/api/v1/auth/captcha-config'), () =>
          HttpResponse.json({ provider: 'turnstile', siteKey: 'site-key-1' }),
        ),
      );
      await expectSwitchChangesEveryText(
        () => renderSwitchable(<LoginForm showLocalHint={false} />),
        () => screen.findByTestId('captcha'),
      );
    });

    it('changes every visible text of the fleet screen without reloading its data', async () => {
      navigation.reset('/fleet');
      fleetApi({
        drivers: fiveDrivers(),
        vehicles: fiveDrivers().flatMap((d) => (d.vehicle ? [d.vehicle] : [])),
      });
      await expectSwitchChangesEveryText(
        () => renderSwitchable(<FleetScreen />),
        () => screen.findByText('Paweł Kurek'),
      );
    });

    it('changes every visible text of the plan screen without reloading its data', async () => {
      navigation.reset('/plans/x', 'job=job-1');
      const van = { ...driver(1).vehicle!, label: 'BUS-01', palletPlaces: 10, payloadKg: 1085 };
      server.use(
        http.get(apiUrl('/api/v1/route-plans/:id'), () => HttpResponse.json(goldPlan)),
        http.get(apiUrl('/api/v1/drivers/:id'), () =>
          HttpResponse.json({ ...driver(1), vehicle: van }),
        ),
        http.get(apiUrl('/api/v1/freight-offers/:id'), ({ params }) =>
          HttpResponse.json(
            importedOffer({
              id: String(params.id),
              sourceOfferId: `TC-${String(params.id).slice(-2)}`,
            }),
          ),
        ),
        http.get(apiUrl('/api/v1/optimization-jobs/:id/result'), () =>
          HttpResponse.json({
            perDriver: [
              {
                driverId: goldPlan.driverId,
                plans: Object.fromEntries(
                  (['profit', 'fastest', 'fuel'] as const).map((objective) => [
                    objective,
                    [goldPlans[objective]],
                  ]),
                ),
              },
            ],
          }),
        ),
      );
      await expectSwitchChangesEveryText(
        () => renderSwitchable(<PlanScreen planId={goldPlan.id} />),
        () => screen.findByRole('img', { name: /Curtain-sider van/ }),
      );
    });
  });
});
