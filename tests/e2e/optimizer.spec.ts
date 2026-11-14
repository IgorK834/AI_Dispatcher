import { accounts, expect, signIn, test } from './fixtures';

// The run uses the real engine on the seeded demo data. A fleet run with the API defaults takes
// minutes (bench/README.md), so the form is set to three planning days and two offers per plan
// (about 3 s); the scope is still the whole fleet and all three objectives. One day is not enough:
// the demo offers are picked up on working days, so on a Saturday or Sunday a one-day horizon finds
// no plan (every offer is OUTSIDE_HORIZON) and the scenario would fail on weekends and nightly runs.
test.setTimeout(10 * 60_000);

test('[AC-FEAT-005-13] a fleet optimisation shows progress and a result, and its plan can be assigned', async ({
  page,
}) => {
  await signIn(page, accounts.demo);
  await expect(page).toHaveURL('/');

  // The start page also links to the optimizer (the AI-off panel), so name the navigation.
  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Optimizer' })
    .click();
  await expect(page).toHaveURL('/optimizer');
  await page.getByLabel('Planning horizon').selectOption('3');
  await page.getByLabel('Max offers per plan').selectOption('2');
  await page.getByRole('button', { name: 'Start optimisation' }).click();

  await expect(
    page.getByRole('status').filter({ hasText: 'Optimisation in progress' }),
  ).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole('heading', { name: 'Result', exact: true })).toBeVisible({
    timeout: 8 * 60_000,
  });

  for (const objective of ['Most profitable', 'Fastest', 'Lowest fuel']) {
    await expect(page.getByRole('region', { name: objective }).first()).toBeVisible();
  }
  await expect(
    page.getByRole('img', { name: /Engine: .*Greedy: .*Best single offer: / }),
  ).toBeVisible();
  await expect(page.getByRole('region', { name: /^Rejected offers \(\d+\)$/ })).toBeVisible();
  await expect(
    page.getByText(/planning estimate based on a simplified model/).first(),
  ).toBeVisible();

  // Open the first plan of the "Most profitable" solution.
  await page
    .getByRole('region', { name: 'Most profitable' })
    .first()
    .getByRole('link', { name: 'Open plan' })
    .first()
    .click();
  await expect(page).toHaveURL(/\/plans\/[0-9a-f-]{36}\?job=/);
  await expect(page.getByRole('heading', { level: 1 })).toContainText('→');
  const driverText = await page
    .getByText(/^Driver /)
    .first()
    .innerText();
  const driverName = driverText.replace(/^Driver /, '');

  await page.getByRole('button', { name: 'Assign this plan' }).click();
  const dialog = page.getByRole('alertdialog', { name: 'Assign this plan?' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', { name: 'Assign plan' }).click();
  await expect(page.getByText('Assigned', { exact: true })).toBeVisible();

  // The fleet screen now shows the driver as assigned.
  await page.getByRole('link', { name: 'Fleet' }).click();
  await expect(page).toHaveURL('/fleet');
  const row = page.getByRole('row').filter({ hasText: driverName });
  await expect(row.getByText('Assigned', { exact: true })).toBeVisible();
});
