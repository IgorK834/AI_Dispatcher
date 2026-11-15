import { expect, test as base, type Page } from '@playwright/test';

/**
 * Local demo accounts. The values are the example ones of apps/api/.env.example; the throw-away
 * API of playwright.config.ts is started with exactly these, so no real account is involved.
 */
export const accounts = {
  demo: {
    email: process.env.E2E_DEMO_EMAIL ?? 'demo@example.invalid',
    password: process.env.E2E_DEMO_PASSWORD ?? 'local-demo-password',
  },
  admin: {
    email: process.env.E2E_ADMIN_EMAIL ?? 'admin@example.invalid',
    password: process.env.E2E_ADMIN_PASSWORD ?? 'local-admin-password',
  },
} as const;

/**
 * Cloudflare's "always pass" test widget issues a token without any interaction. The token ends
 * up in a hidden input of the host page, so wait for that field instead of clicking into the
 * iframe.
 */
export async function waitForTurnstileToken(page: Page): Promise<void> {
  await expect(page.locator('input[name="cf-turnstile-response"]')).toHaveValue(/.+/, {
    timeout: 45_000,
  });
}

export async function signIn(page: Page, account: { email: string; password: string }) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(account.email);
  await page.getByLabel('Password').fill(account.password);
  await waitForTurnstileToken(page);
  await page.getByRole('button', { name: 'Sign in' }).click();
}

/**
 * One driver can hold one active assignment, and all specs share one database, so a spec that
 * assigns a plan cancels its assignments again (the product's own `DELETE /assignments/{id}`,
 * as the signed-in user) and leaves the next spec a fleet without assignments.
 */
export async function cancelActiveAssignments(page: Page) {
  const api = `http://localhost:${process.env.E2E_API_PORT ?? '8010'}`;
  const origin = `http://localhost:${process.env.E2E_WEB_PORT ?? '3010'}`;
  const session = await page.request.get(`${api}/api/v1/auth/me`);
  expect(session.ok()).toBe(true);
  const { csrfToken } = (await session.json()) as { csrfToken: string };
  const listed = await page.request.get(`${api}/api/v1/assignments`);
  expect(listed.ok()).toBe(true);
  const { items } = (await listed.json()) as { items: { id: string; status: string }[] };
  for (const item of items.filter((assignment) => assignment.status === 'active')) {
    const cancelled = await page.request.delete(`${api}/api/v1/assignments/${item.id}`, {
      headers: { 'X-CSRF-Token': csrfToken, Origin: origin },
    });
    expect(cancelled.status()).toBe(204);
  }
}

export const test = base;
export { expect };
