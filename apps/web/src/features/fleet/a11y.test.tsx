import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { forwardRef, useImperativeHandle } from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../../messages/en.json';
import { LiveRegion } from '@/components/ui/live-region';
import { LoginForm } from '@/features/auth';
import { fiveDrivers } from '@/test/fixtures/fleet';
import { apiUrl } from '@/test/msw/handlers';
import { fleetApi } from '@/test/msw/handlers/fleet';
import { server } from '@/test/msw/server';
import { navigation } from '@/test/navigation';
import { renderWithIntl } from '@/test/render';
import { renderWithSession, signInAs } from '@/test/session';
import { FleetScreen } from './fleet-screen';
import { renderFleet } from './test-utils';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);
vi.mock('@marsidev/react-turnstile', () => ({
  Turnstile: forwardRef<{ reset: () => void }>(function FakeTurnstile(_props, ref) {
    useImperativeHandle(ref, () => ({ reset: () => undefined }));
    return <button type="button">captcha</button>;
  }),
}));

beforeEach(() => navigation.reset('/fleet'));

function expectNamedControls(container: HTMLElement) {
  const controls = container.querySelectorAll<HTMLElement>(
    'input:not([type="hidden"]), select, textarea',
  );
  expect(controls.length).toBeGreaterThan(0);
  for (const control of controls) expect(control).toHaveAccessibleName();
}

describe('[AC-FEAT-005-19] accessibility of the key forms and dialogs', () => {
  it('gives every input of the login form an accessible name', async () => {
    signInAs(null);
    server.use(
      http.get(apiUrl('/api/v1/auth/captcha-config'), () =>
        HttpResponse.json({ provider: 'turnstile', siteKey: 'k' }),
      ),
    );
    const { container } = renderWithSession(<LoginForm showLocalHint={false} />);
    await screen.findByRole('button', { name: 'captcha' });
    expectNamedControls(container);
    expect(screen.getByLabelText(en.auth.form.email)).toBeVisible();
    expect(screen.getByLabelText(en.auth.form.password)).toBeVisible();
  });

  it('gives every input of the driver and vehicle forms an accessible name', async () => {
    const user = userEvent.setup();
    fleetApi({ drivers: fiveDrivers(), vehicles: fiveDrivers().map((item) => item.vehicle!) });
    renderFleet(<FleetScreen />);
    await screen.findByRole('table');
    await user.click(screen.getByRole('button', { name: en.fleet.addDriver }));
    expectNamedControls(
      await screen.findByRole('dialog', { name: en.fleet.driverForm.createTitle }),
    );
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await user.click(screen.getByRole('button', { name: en.fleet.addVehicle }));
    expectNamedControls(
      await screen.findByRole('dialog', { name: en.fleet.vehicleForm.createTitle }),
    );
  });

  it('opens the driver sheet by keyboard, keeps focus inside, and Escape returns focus to the trigger', async () => {
    const user = userEvent.setup();
    fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    await screen.findByRole('table');
    const trigger = screen.getByRole('button', { name: en.fleet.addDriver });
    trigger.focus();
    await user.keyboard('{Enter}');
    const dialog = await screen.findByRole('dialog', { name: en.fleet.driverForm.createTitle });
    for (let step = 0; step < 14; step += 1) {
      await user.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('traps focus in the delete dialog and Escape returns focus to the Delete button', async () => {
    const user = userEvent.setup();
    fleetApi({ drivers: fiveDrivers() });
    renderFleet(<FleetScreen />);
    const table = await screen.findByRole('table');
    const trigger = within(table).getByRole('button', { name: 'Delete Ewa Sowa' });
    await user.click(trigger);
    const dialog = await screen.findByRole('alertdialog');
    for (let step = 0; step < 5; step += 1) {
      await user.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }
    await user.keyboard('{Escape}');
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('writes every status badge and every bar value as text, never as colour alone', async () => {
    fleetApi({ drivers: fiveDrivers(), assigned: [fiveDrivers()[0]!.id] });
    renderFleet(<FleetScreen />);
    const table = await screen.findByRole('table');
    const badges = within(table).getAllByText(
      new RegExp(
        `^(${en.fleet.status.assigned}|${en.fleet.status.free}|${en.fleet.status.synthetic})$`,
      ),
    );
    expect(badges.length).toBeGreaterThanOrEqual(10);
    for (const meter of within(table).getAllByRole('meter')) {
      expect(meter).toHaveAccessibleName();
      expect(meter.getAttribute('aria-valuetext')).toMatch(/\d/);
      expect(meter.parentElement).toHaveTextContent(/left of/);
    }
  });

  it('announces the run status in one polite live region', () => {
    renderWithIntl(<LiveRegion>Run finished</LiveRegion>);
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByRole('status')).toHaveTextContent('Run finished');
  });
});
