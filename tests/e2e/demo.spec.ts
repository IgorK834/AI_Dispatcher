import { accounts, cancelActiveAssignments, expect, signIn, test } from './fixtures';

// The demo scenario of FEAT-007 FR-3 on the seeded data, without any model key. It is one test
// with named steps, because every step builds on the state of the one before (the driver that is
// added is edited and deleted; the plan that is opened is assigned).
//
// Like optimizer.spec.ts, the optimisation is set to three planning days and two offers per plan
// (a few seconds), and the scope is still the whole fleet and all three objectives.
test.setTimeout(10 * 60_000);
// A step that cannot find its element fails after 20 s, not after the whole test timeout.
test.use({ actionTimeout: 20_000 });

const stamp = Date.now().toString(36);
const vehicleLabel = `E2E van ${stamp}`;
const driverName = `E2E driver ${stamp}`;
const driverRenamed = `${driverName} renamed`;
// Windows tomorrow and the day after, so that the offer is never in the past (local time, as the form reads it).
const day = (offset: number, time: string) => {
  const date = new Date(Date.now() + offset * 24 * 3600_000);
  const month = String(date.getMonth() + 1).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${String(date.getDate()).padStart(2, '0')}T${time}`;
};

test('[AC-FEAT-007-03] the demo scenario: sign in, language, fleet CRUD, offers, optimizer, assignment and the AI-off panel', async ({
  page,
}) => {
  await test.step('1. admin signs in; the language switches to Polish and back', async () => {
    await signIn(page, accounts.admin);
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('button', { name: 'Account' })).toContainText('Admin');

    const language = page.getByRole('group', { name: 'Language' });
    await language.getByRole('button', { name: 'Polski' }).click();
    await expect(page.getByRole('navigation', { name: 'Nawigacja główna' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Flota' })).toBeVisible();

    await page
      .getByRole('group', { name: 'Język' })
      .getByRole('button', { name: 'English' })
      .click();
    await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
  });

  await test.step('2. fleet: add a vehicle and a driver, edit the driver, delete it after confirmation', async () => {
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Fleet' })
      .click();
    await expect(page).toHaveURL('/fleet');

    // A vehicle (the form is prefilled with valid defaults).
    await page.getByRole('tab', { name: /^Vehicles/ }).click();
    await page.getByRole('button', { name: 'Add vehicle' }).click();
    const vehicleSheet = page.getByRole('dialog', { name: 'Add vehicle' });
    await vehicleSheet.getByLabel('Label').fill(vehicleLabel);
    await vehicleSheet.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('Vehicle saved')).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: vehicleLabel })).toBeVisible();

    // A driver.
    await page.getByRole('tab', { name: /^Drivers/ }).click();
    await page.getByRole('button', { name: 'Add driver' }).click();
    const driverSheet = page.getByRole('dialog', { name: 'Add driver' });
    await driverSheet.getByLabel('Name').fill(driverName);
    await driverSheet.getByLabel('Home city').fill('Katowice');
    await driverSheet.getByLabel('Home latitude').fill('50.2649');
    await driverSheet.getByLabel('Home longitude').fill('19.0238');
    await driverSheet.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('Driver saved')).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: driverName })).toBeVisible();

    // Edit it: the toast confirms the save and the new name is in the list.
    await page.getByRole('button', { name: `Edit ${driverName}` }).click();
    const editSheet = page.getByRole('dialog', { name: 'Edit driver' });
    await editSheet.getByLabel('Name').fill(driverRenamed);
    await editSheet.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('Driver saved')).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: driverRenamed })).toBeVisible();

    // Delete it: nothing happens before the confirmation.
    await page.getByRole('button', { name: `Delete ${driverRenamed}` }).click();
    const confirm = page.getByRole('alertdialog', { name: `Delete driver ${driverRenamed}?` });
    await expect(confirm).toBeVisible();
    await confirm.getByRole('button', { name: 'Delete driver' }).click();
    await expect(page.getByText('Driver deleted')).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: driverRenamed })).toHaveCount(0);

    // And the vehicle, so that the fleet is as it was for the next spec.
    await page.getByRole('tab', { name: /^Vehicles/ }).click();
    await page.getByRole('button', { name: `Delete ${vehicleLabel}` }).click();
    const vehicleConfirm = page.getByRole('alertdialog', {
      name: `Delete vehicle ${vehicleLabel}?`,
    });
    await vehicleConfirm.getByRole('button', { name: 'Delete vehicle' }).click();
    await expect(page.getByText('Vehicle deleted')).toBeVisible();
    await expect(page.getByRole('row').filter({ hasText: vehicleLabel })).toHaveCount(0);
  });

  await test.step('3. offers: add a manual offer, an imported offer is read-only, filter by country', async () => {
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Offers' })
      .click();
    await expect(page).toHaveURL('/offers');

    // An imported (synthetic) offer has no edit button, only the read-only notice.
    await expect(page.getByRole('button', { name: /^Edit / })).toHaveCount(0);
    await expect(page.getByLabel(/^Imported offer .* is read-only$/).first()).toBeVisible();

    await page.getByRole('button', { name: 'Add manual offer' }).click();
    const sheet = page.getByRole('dialog', { name: 'Add manual offer' });
    await sheet.getByLabel('Description').fill(`E2E load ${stamp}`);
    await sheet.getByLabel('Weight (kg)').fill('400');
    await sheet.getByLabel('Pallet count').fill('3');
    await sheet.getByLabel('Price (EUR)').fill('150');
    const loading = sheet.getByRole('group', { name: 'Loading stop', exact: true });
    await loading.getByLabel('City').fill('Katowice');
    await loading.getByLabel('Country code').fill('PL');
    await loading.getByLabel('Window opens').fill(day(1, '08:00'));
    await loading.getByLabel('Window closes').fill(day(1, '12:00'));
    const unloading = sheet.getByRole('group', { name: 'Unloading stop', exact: true });
    await unloading.getByLabel('City').fill('Berlin');
    await unloading.getByLabel('Country code').fill('DE');
    await unloading.getByLabel('Window opens').fill(day(2, '08:00'));
    await unloading.getByLabel('Window closes').fill(day(2, '12:00'));
    await sheet.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('Offer saved')).toBeVisible();

    // The manual offer is the only one with an edit button: show manual offers only.
    await page.getByLabel('Source').selectOption({ label: 'Manual' });
    await expect(page.getByRole('button', { name: /^Edit / })).toHaveCount(1);

    // Filter by destination country: the manual offer goes to Germany, not to France.
    // The filter applies when the field loses focus.
    await page.getByLabel('Destination country').fill('DE');
    await page.getByLabel('Destination country').blur();
    await expect(page).toHaveURL(/destinationCountry=DE/);
    await expect(page.getByRole('button', { name: /^Edit / })).toHaveCount(1);
    await page.getByLabel('Destination country').fill('FR');
    await page.getByLabel('Destination country').blur();
    await expect(page).toHaveURL(/destinationCountry=FR/);
    await expect(page.getByRole('button', { name: /^Edit / })).toHaveCount(0);

    // Delete the manual offer again (confirmation first), so that the offers are as they were.
    await page.getByLabel('Destination country').fill('');
    await page.getByLabel('Destination country').blur();
    await expect(page.getByRole('button', { name: /^Edit / })).toHaveCount(1);
    await page.getByRole('button', { name: /^Delete / }).click();
    const offerConfirm = page.getByRole('alertdialog', { name: /^Delete offer / });
    await offerConfirm.getByRole('button', { name: 'Delete offer' }).click();
    await expect(page.getByText('Offer deleted')).toBeVisible();
    await expect(page.getByRole('button', { name: /^Edit / })).toHaveCount(0);
    await page.getByLabel('Source').selectOption({ label: 'All sources' });
  });

  await test.step('4. optimizer: a fleet run, the "profit" plan with three variants, CO₂ and the notice', async () => {
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'Optimizer' })
      .click();
    await expect(page).toHaveURL('/optimizer');
    await page.getByLabel('Planning horizon').selectOption('3');
    await page.getByLabel('Max offers per plan').selectOption('2');
    await page.getByRole('button', { name: 'Start optimisation' }).click();
    await expect(page.getByRole('heading', { name: 'Result', exact: true })).toBeVisible({
      timeout: 8 * 60_000,
    });

    await page
      .getByRole('region', { name: 'Most profitable' })
      .first()
      .getByRole('link', { name: 'Open plan' })
      .first()
      .click();
    await expect(page).toHaveURL(/\/plans\/[0-9a-f-]{36}\?job=/);

    const variants = page.getByRole('region', { name: 'Variants' });
    for (const variant of ['Most profitable', 'Fastest', 'Lowest fuel']) {
      await expect(variants.getByText(variant).first()).toBeVisible();
    }
    await expect(variants.getByText(/kg/).first()).toBeVisible();
    await expect(variants.getByText('CO₂').first()).toBeVisible();
    await expect(
      page.getByText(/planning estimate based on a simplified model/).first(),
    ).toBeVisible();
  });

  await test.step('5. assign the plan after confirmation; the fleet view shows the assignment', async () => {
    const driverText = await page
      .getByText(/^Driver (?!cost)/)
      .first()
      .innerText();
    const assignedDriver = driverText.replace(/^Driver /, '');

    await page.getByRole('button', { name: 'Assign this plan' }).click();
    const dialog = page.getByRole('alertdialog', { name: 'Assign this plan?' });
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button', { name: 'Assign plan' }).click();
    await expect(page.getByText('Assigned', { exact: true })).toBeVisible();

    await page.getByRole('link', { name: 'Fleet' }).click();
    await expect(page).toHaveURL('/fleet');
    const row = page.getByRole('row').filter({ hasText: assignedDriver });
    await expect(row.getByText('Assigned', { exact: true })).toBeVisible();

    // Leave the shared fleet without assignments for the next spec.
    await cancelActiveAssignments(page);
  });

  await test.step('6. AI Dispatcher: the "AI is off" panel links to the optimizer', async () => {
    await page
      .getByRole('navigation', { name: 'Main navigation' })
      .getByRole('link', { name: 'AI Dispatcher' })
      .click();
    await expect(page.getByText('AI is off — no model key is configured')).toBeVisible();
    await page.getByRole('link', { name: 'Open the manual optimizer' }).click();
    await expect(page).toHaveURL('/optimizer');
  });
});
