import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ESLint } from 'eslint';
import { http, HttpResponse } from 'msw';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../messages/en.json';
import { ChatScreen } from '@/features/agent-chat';
import { FleetScreen } from '@/features/fleet';
import { OptimizerScreen } from '@/features/optimizer';
import { PlanScreen } from '@/features/plans';
import { FakeEventSource } from './fake-event-source';
import { finalAnswer, startedEvent } from './fixtures/agent';
import { driver, fiveDrivers } from './fixtures/fleet';
import { goldPlan, goldPlans } from './fixtures/gold-001';
import { importedOffer } from './fixtures/offers';
import { apiUrl } from './msw/handlers';
import { agentApi } from './msw/handlers/agent';
import { fleetApi } from './msw/handlers/fleet';
import { server } from './msw/server';
import { navigation } from './navigation';
import { renderApp } from './render-app';
import { act } from '@testing-library/react';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

const root = path.resolve(import.meta.dirname, '../../../..');
const src = path.resolve(import.meta.dirname, '..');

describe('[AC-FEAT-005-27] design conformance', () => {
  describe('design tokens in the source', () => {
    it('fails the lint rule on a component with a raw colour and a font-family', async () => {
      const eslint = new ESLint();
      const fixture = readFileSync(path.join(src, 'test/fixtures/raw-color.fixture'), 'utf8');
      const [result] = await eslint.lintText(fixture, {
        filePath: path.join(src, 'components/fixture.tsx'),
      });
      const hits = (result?.messages ?? []).filter(
        (message) => message.ruleId === 'routepilot/no-raw-colors',
      );
      // the hex colour, the font-family, the arbitrary Tailwind colour and the rgb() string
      expect(hits.length).toBeGreaterThanOrEqual(4);
    });

    it('passes the lint rule on the whole real source', { timeout: 120_000 }, async () => {
      const eslint = new ESLint();
      const results = await eslint.lintFiles(['src/**/*.{ts,tsx}']);
      const offenders = results.flatMap((result) =>
        result.messages
          .filter((message) => message.ruleId === 'routepilot/no-raw-colors')
          .map(
            (message) =>
              `${path.relative(src, result.filePath)}:${message.line} ${message.message}`,
          ),
      );
      expect(offenders).toEqual([]);
    });
  });

  type Tokens = {
    color: Record<string, { value: string }>;
    status: Record<string, { bg: string; fg: string }>;
  };
  const tokens = JSON.parse(
    readFileSync(path.join(root, 'docs/design/tokens.json'), 'utf8'),
  ) as Tokens;

  function luminance(hex: string): number {
    const channels = [1, 3, 5].map((start) => parseInt(hex.slice(start, start + 2), 16) / 255);
    const [r = 0, g = 0, b = 0] = channels.map((c) =>
      c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4,
    );
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  /** WCAG 2.x contrast ratio of two opaque colours. */
  function contrast(a: string, b: string): number {
    const [light = 0, dark = 0] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (light + 0.05) / (dark + 0.05);
  }

  /** The colour of each Tailwind colour utility (`text-ink2`, `bg-red-tint`) as tokens.json defines it. */
  const palette: Record<string, string> = {
    ground: tokens.color.ground!.value,
    surface: tokens.color.surface!.value,
    well: tokens.color.well!.value,
    ink: tokens.color.ink!.value,
    ink2: tokens.color.ink2!.value,
    ink3: tokens.color.ink3!.value,
    red: tokens.color.red!.value,
    'red-hover': tokens.color.redHover!.value,
    'red-tint': tokens.color.redTint!.value,
    'done-bg': tokens.status.done!.bg,
    'done-fg': tokens.status.done!.fg,
    'info-bg': tokens.status.info!.bg,
    'info-fg': tokens.status.info!.fg,
    'quiet-bg': tokens.status.quiet!.bg,
    'quiet-fg': tokens.status.quiet!.fg,
  };
  const PAGE_BACKGROUNDS = ['ground', 'surface', 'well'];

  function sourceFiles(directory: string): string[] {
    return readdirSync(directory).flatMap((entry) => {
      const full = path.join(directory, entry);
      if (statSync(full).isDirectory()) return entry === 'test' ? [] : sourceFiles(full);
      return /\.tsx$/.test(entry) && !/\.test\.tsx$/.test(entry) ? [full] : [];
    });
  }

  /** Every (text colour, background colour) pair a class string in the source puts together. */
  function pairsInSource(): { text: string; background: string; where: string }[] {
    const found: { text: string; background: string; where: string }[] = [];
    for (const file of sourceFiles(src)) {
      const code = readFileSync(file, 'utf8');
      for (const literal of code.matchAll(/(["'`])((?:\\[\s\S]|(?!\1)[^\\])*)\1/g)) {
        const classes = (literal[2] ?? '').split(/\s+/);
        const split = (prefix: 'text' | 'bg') =>
          classes.flatMap((name) => {
            const at = name.lastIndexOf(':');
            const variant = at === -1 ? '' : name.slice(0, at);
            const base = name.slice(at + 1);
            return base.startsWith(`${prefix}-`) && base.slice(prefix.length + 1) in palette
              ? [{ variant, color: base.slice(prefix.length + 1) }]
              : [];
          });
        const texts = split('text');
        const backgrounds = split('bg');
        for (const text of texts) {
          const same = backgrounds.filter((bg) => bg.variant === text.variant);
          const plain = backgrounds.filter((bg) => bg.variant === '');
          const against = same.length > 0 ? same : plain;
          const where = path.relative(src, file);
          if (against.length > 0) {
            for (const bg of against) found.push({ text: text.color, background: bg.color, where });
          } else if (text.color !== 'surface') {
            // no background of its own: it sits on the page, a card or an inner panel
            for (const bg of PAGE_BACKGROUNDS)
              found.push({ text: text.color, background: bg, where });
          }
        }
      }
    }
    return found;
  }

  describe('contrast', () => {
    it('reaches 4.5:1 for the text and status pairs of tokens.json', () => {
      const pairs: [string, string, string][] = [];
      for (const text of ['ink', 'ink2', 'ink3', 'red-hover']) {
        for (const background of PAGE_BACKGROUNDS) pairs.push([text, background, 'text on page']);
      }
      pairs.push(['surface', 'red', 'primary button']);
      pairs.push(['red-hover', 'red-tint', 'attention']);
      for (const [name, level] of Object.entries(tokens.status)) {
        pairs.push([level.fg, level.bg, `status ${name}`]);
      }
      const failures = pairs
        .map(([text, background, what]) => ({
          what: `${what}: ${text} on ${background}`,
          ratio: contrast(palette[text] ?? text, palette[background] ?? background),
        }))
        .filter((pair) => pair.ratio < 4.5);
      expect(failures).toEqual([]);
    });

    it('reaches 4.5:1 for every text/background combination the components use', () => {
      const used = pairsInSource();
      expect(used.length).toBeGreaterThan(50);
      const failures = new Map<string, number>();
      for (const { text, background, where } of used) {
        const ratio = contrast(palette[text]!, palette[background]!);
        if (ratio < 4.5)
          failures.set(`${text} on ${background} = ${ratio.toFixed(2)} (${where})`, ratio);
      }
      expect([...failures.keys()]).toEqual([]);
    });
  });

  const VAN = 'Curtain-sider van up to 3.5 t, BUS-01';

  describe('the van illustration', () => {
    const van = () => ({
      ...driver(1).vehicle!,
      label: 'BUS-01',
      palletPlaces: 10,
      payloadKg: 1085,
    });

    beforeEach(() => {
      vi.stubEnv('NEXT_PUBLIC_MAP_STYLE_URL', '');
      FakeEventSource.reset();
      vi.stubGlobal('EventSource', FakeEventSource);
    });
    afterEach(() => {
      vi.unstubAllEnvs();
      vi.unstubAllGlobals();
    });

    it('renders in the plan header at 400 px', async () => {
      navigation.reset('/plans/x');
      server.use(
        http.get(apiUrl('/api/v1/route-plans/:id'), () => HttpResponse.json(goldPlan)),
        http.get(apiUrl('/api/v1/drivers/:id'), () =>
          HttpResponse.json({ ...driver(1), vehicle: van() }),
        ),
        http.get(apiUrl('/api/v1/freight-offers/:id'), ({ params }) =>
          HttpResponse.json(importedOffer({ id: String(params.id) })),
        ),
      );
      renderApp(<PlanScreen planId={goldPlan.id} />);
      const header = await screen.findByRole('img', { name: VAN });
      expect(header).toHaveAttribute('width', '400');
    });

    it('renders in a Dispatcher proposal card at 120 px', async () => {
      navigation.reset('/');
      agentApi();
      server.use(
        http.get(apiUrl('/api/v1/route-plans/:id'), () => HttpResponse.json(goldPlan)),
        http.get(apiUrl('/api/v1/drivers/:id'), () =>
          HttpResponse.json({ ...driver(1), vehicle: van() }),
        ),
      );
      renderApp(<ChatScreen />);
      const user = userEvent.setup();
      const input = await screen.findByRole('textbox', { name: en.chat.composer.label });
      await waitFor(() => expect(input).toBeEnabled());
      await user.type(input, 'Plan');
      await user.click(screen.getByRole('button', { name: en.chat.composer.send }));
      await waitFor(() => expect(FakeEventSource.instances.length).toBeGreaterThan(0));
      act(() => FakeEventSource.latest.emit('run_started', startedEvent, 1));
      act(() => FakeEventSource.latest.emit('final_answer', finalAnswer, 2));
      const card = await screen.findByRole('article', { name: /D1/ });
      expect(await within(card).findByRole('img', { name: VAN })).toHaveAttribute('width', '120');
    });

    it('renders in a fleet table row at 96 px', async () => {
      navigation.reset('/fleet');
      fleetApi({
        drivers: fiveDrivers(),
        vehicles: fiveDrivers().flatMap((d) => (d.vehicle ? [d.vehicle] : [])),
      });
      renderApp(<FleetScreen />);
      const row = (await screen.findByText('Paweł Kurek')).closest('tr') as HTMLElement;
      expect(within(row).getByRole('img', { name: VAN })).toHaveAttribute('width', '96');
    });

    it('renders in an optimizer result row at 88 px', async () => {
      const job = '00000000-0000-4000-8000-0000000c0001';
      const d1 = goldPlans.profit.driverId;
      navigation.reset('/optimizer', `job=${job}`);
      const money = (amountMinor: number) => ({ amountMinor, currency: 'EUR' });
      const solution = (objective: string) => ({
        objective,
        assignments: [{ driverId: d1, routePlanId: goldPlans.profit.id }],
        totals: {
          netProfit: money(32354),
          fuelL: '76.601',
          co2Kg: '199.16',
          distanceKm: '624.81',
          driversWithPlan: 1,
        },
      });
      server.use(
        http.get(apiUrl('/api/v1/drivers'), () =>
          HttpResponse.json({
            items: fiveDrivers().map((d, i) => (i === 0 ? { ...d, id: d1 } : d)),
            nextCursor: null,
          }),
        ),
        http.get(apiUrl('/api/v1/optimization-jobs/:id'), () =>
          HttpResponse.json({
            id: job,
            status: 'succeeded',
            scope: 'fleet',
            objectives: ['profit'],
            progress: { phase: 'saving', driversDone: 5, driversTotal: 5 },
            stats: null,
            error: null,
            requestedBy: 'u',
            createdAt: '2026-11-16T05:00:00Z',
          }),
        ),
        http.get(apiUrl('/api/v1/optimization-jobs/:id/result'), () =>
          HttpResponse.json({
            jobId: job,
            fleet: {
              profit: solution('profit'),
              fastest: solution('fastest'),
              fuel: solution('fuel'),
            },
            perDriver: [{ driverId: d1, plans: { profit: [goldPlans.profit] } }],
            baselines: { baselineGreedy: solution('profit'), baselineSingle: solution('profit') },
            rejections: [],
            warnings: [],
            stats: { nodes: 1, truncated: false, poolTruncated: false, runtimeMs: 10 },
            disclaimer: en.legal.notice,
          }),
        ),
      );
      renderApp(<OptimizerScreen />);
      const region = await screen.findByRole(
        'region',
        { name: 'Most profitable' },
        { timeout: 4000 },
      );
      const images = await within(region).findAllByRole('img', { name: VAN });
      expect(images[0]).toHaveAttribute('width', '88');
    });
  });
});
