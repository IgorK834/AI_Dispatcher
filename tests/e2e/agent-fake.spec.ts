import { accounts, cancelActiveAssignments, expect, signIn, test } from './fixtures';

// The approval and rejection paths of the AI Dispatcher on scripted chat models (FEAT-007 FR-3,
// OQ-007-04): the API of this run (`scripts/e2e/e2e_api.py`, APP_ENV=test) has no chat model until
// a spec switches the scripted offline evaluation models on, and the spec switches them off again,
// so the "AI is off" scenario of demo.spec.ts keeps its real meaning. The tests run in this order
// on purpose: a rejection saves nothing, so the later approval still finds the driver unassigned.
test.describe.configure({ mode: 'serial' });
test.setTimeout(5 * 60_000);

const apiUrl = `http://localhost:${process.env.E2E_API_PORT ?? '8010'}`;

test.afterAll(async ({ request }) => {
  await request.get(`${apiUrl}/__e2e/ai/off`);
});

async function askForAPlan(
  page: import('@playwright/test').Page,
  request: import('@playwright/test').APIRequestContext,
) {
  // Switch the scripted models on; they play their script from the start.
  expect((await request.get(`${apiUrl}/__e2e/ai/on`)).ok()).toBe(true);
  await signIn(page, accounts.demo);
  await expect(page).toHaveURL('/');
  await page
    .getByLabel('Message')
    .fill('Find the best load for driver D1 and ask me to approve it');
  await page.getByRole('button', { name: 'Send' }).click();

  // The agent trace shows the steps while the run works, then the approval card appears.
  const trace = page.getByRole('region', { name: 'Agent trace' });
  await expect(trace.getByText(/\d+ steps?/)).toBeVisible();
  // The run optimises one driver with the real engine before it asks for the approval.
  const card = page.getByRole('region', { name: /^Approve \d+ assignments?\?$/ });
  await expect(card).toBeVisible({ timeout: 4 * 60_000 });
  return card;
}

test('[AC-FEAT-007-03] @ai-fake rejecting the proposal assigns nothing', async ({
  page,
  request,
}) => {
  const card = await askForAPlan(page, request);
  await card.getByRole('button', { name: 'Reject' }).click();
  await expect(page.getByText('Rejected. Nothing was assigned.')).toBeVisible();

  await page
    .getByRole('navigation', { name: 'Main navigation' })
    .getByRole('link', { name: 'Fleet' })
    .click();
  await expect(page).toHaveURL('/fleet');
  await expect(page.getByRole('row').first()).toBeVisible();
  await expect(page.getByText('Assigned', { exact: true })).toHaveCount(0);
});

test('[AC-FEAT-007-03] @ai-fake approving the proposal assigns the plan and the fleet shows it', async ({
  page,
  request,
}) => {
  const card = await askForAPlan(page, request);
  await card.getByRole('button', { name: 'Approve and assign' }).click();
  await expect(page.getByText('Approved. The assignments are saved.')).toBeVisible();

  await page.getByRole('link', { name: 'See the assignments in the fleet' }).click();
  await expect(page).toHaveURL('/fleet');
  await expect(page.getByText('Assigned', { exact: true }).first()).toBeVisible();

  // Leave the shared fleet without assignments for the next spec.
  await cancelActiveAssignments(page);
});
