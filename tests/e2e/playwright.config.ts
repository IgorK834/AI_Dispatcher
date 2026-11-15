import os from 'node:os';
import path from 'node:path';
import { defineConfig } from '@playwright/test';
import { accounts } from './fixtures';

const root = path.resolve(__dirname, '../..');
// A throw-away stack on its own ports and database: the e2e run never touches local data.
const work = path.join(os.tmpdir(), 'routepilot-e2e');
const apiPort = 8010;
const webPort = 3010;
const apiUrl = `http://localhost:${apiPort}`;
const webUrl = `http://localhost:${webPort}`;

export default defineConfig({
  testDir: __dirname,
  outputDir: path.join(work, 'results'),
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  // A CI runner shares a few CPUs between Chromium, `next dev` and the API: requests that take
  // milliseconds locally have taken seconds there, so assertions wait longer in CI.
  expect: { timeout: process.env.CI ? 30_000 : 5_000 },
  use: { baseURL: webUrl, locale: 'en-US', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: [
    {
      // Fresh database, migrations, then the API with the local demo accounts and no provider keys.
      command: [
        `rm -rf "${work}/data" && mkdir -p "${work}/data"`,
        `cd "${root}/apps/api"`,
        'uv run alembic upgrade head',
        `uv run uvicorn routepilot.main:app --port ${apiPort}`,
      ].join(' && '),
      // The API's request log (method, path, status, duration) goes into the test output, so a slow or
      // stuck request of a CI run can be read from it.
      stdout: 'pipe',
      url: `${apiUrl}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        APP_ENV: 'local',
        DATABASE_URL: `sqlite:///${work}/data/routepilot.db`,
        AGENTS_DB_PATH: `${work}/data/agents.db`,
        CORS_ALLOWED_ORIGINS: webUrl,
        SECRET_KEY: '',
        TURNSTILE_SITE_KEY: '1x00000000000000000000AA',
        TURNSTILE_SECRET_KEY: '1x0000000000000000000000000000000AA',
        ADMIN_EMAIL: accounts.admin.email,
        ADMIN_PASSWORD: accounts.admin.password,
        DEMO_EMAIL: accounts.demo.email,
        DEMO_PASSWORD: accounts.demo.password,
        GOOGLE_API_KEY: '',
        ANTHROPIC_API_KEY: '',
        OPENAI_API_KEY: '',
        AGENT_MODEL_POLICY: '',
        ORS_API_KEY: '',
        LOGIN_RATE_LIMIT_PER_IP: '1000/minute',
        LOGIN_RATE_LIMIT_PER_ACCOUNT: '1000/minute',
      },
    },
    {
      command: `pnpm --filter web exec next dev --port ${webPort}`,
      cwd: root,
      url: `${webUrl}/login`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        NEXT_PUBLIC_API_BASE_URL: apiUrl,
        NEXT_PUBLIC_APP_ENV: 'local',
      },
    },
  ],
});
