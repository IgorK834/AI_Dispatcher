import { accounts, expect, signIn, test } from './fixtures';

test('[AC-FEAT-005-01] the demo user signs in, lands on / and keeps the session after a reload', async ({
  page,
}) => {
  await signIn(page, accounts.demo);
  await expect(page).toHaveURL('/');

  const account = page.getByRole('button', { name: 'Account' });
  await expect(account).toContainText(accounts.demo.email);
  await expect(account).toContainText('Demo');

  await page.reload();
  await expect(page).toHaveURL('/');
  await expect(page.getByRole('button', { name: 'Account' })).toContainText(accounts.demo.email);
});

test('wrong credentials show one message and keep the email', async ({ page }) => {
  await signIn(page, { email: accounts.demo.email, password: 'not-the-password' });
  await expect(page.getByRole('form', { name: 'Sign in' }).getByRole('alert')).toContainText(
    'Wrong email or password',
  );
  await expect(page.getByLabel('Password')).toHaveValue('');
  await expect(page.getByLabel('Email')).toHaveValue(accounts.demo.email);
  await expect(page).toHaveURL(/\/login/);
});

test('a protected page redirects to the sign-in page and returns after sign-in', async ({
  page,
}) => {
  await page.goto('/fleet');
  await expect(page).toHaveURL('/login?next=/fleet');
  await page.getByLabel('Email').fill(accounts.demo.email);
  await page.getByLabel('Password').fill(accounts.demo.password);
  const token = page.locator('input[name="cf-turnstile-response"]');
  await expect(token).toHaveValue(/.+/, { timeout: 45_000 });
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL('/fleet');
});
