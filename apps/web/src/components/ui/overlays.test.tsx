import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Button } from './button';
import { ConfirmDialog, ModalDialog } from './dialog';
import { LiveRegion } from './live-region';
import { Sheet } from './sheet';
import { Tabs } from './tabs';
import { ToastProvider, useToast } from './toast';
import { Tooltip, TooltipProvider } from './tooltip';

function ConfirmHarness({ onConfirm }: { onConfirm: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button onClick={() => setOpen(true)}>Delete</Button>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Delete driver D3?"
        description="The driver and the state history are removed."
        confirmLabel="Delete driver"
        cancelLabel="Cancel"
        destructive
        onConfirm={onConfirm}
      />
    </>
  );
}

describe('ConfirmDialog', () => {
  it('names the item, sends nothing before the confirm button, and uses the verb label', async () => {
    const onConfirm = vi.fn();
    render(<ConfirmHarness onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = screen.getByRole('alertdialog', { name: 'Delete driver D3?' });
    expect(onConfirm).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete driver' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it('closes with Escape and returns focus to the trigger', async () => {
    render(<ConfirmHarness onConfirm={vi.fn()} />);
    const trigger = screen.getByRole('button', { name: 'Delete' });
    await userEvent.click(trigger);
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('traps focus inside the dialog', async () => {
    render(<ConfirmHarness onConfirm={vi.fn()} />);
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    const dialog = screen.getByRole('alertdialog');
    for (let step = 0; step < 4; step += 1) {
      await userEvent.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }
  });
});

describe('ModalDialog and Sheet', () => {
  it('render a titled dialog with its content', () => {
    render(
      <ModalDialog open onOpenChange={() => undefined} title="Details" description="More">
        <p>Body</p>
      </ModalDialog>,
    );
    expect(screen.getByRole('dialog', { name: 'Details' })).toHaveTextContent('Body');
  });

  it('puts a form in a side sheet with a close button', async () => {
    const onOpenChange = vi.fn();
    render(
      <Sheet open onOpenChange={onOpenChange} title="Edit driver" closeLabel="Close">
        <p>Form</p>
      </Sheet>,
    );
    expect(screen.getByRole('dialog', { name: 'Edit driver' })).toHaveTextContent('Form');
    await userEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

describe('Tooltip', () => {
  it('shows its text on keyboard focus of the trigger', async () => {
    render(
      <TooltipProvider>
        <Tooltip content="Imported offers are read-only">
          <button type="button">Edit</button>
        </Tooltip>
      </TooltipProvider>,
    );
    await userEvent.tab();
    expect(await screen.findByRole('tooltip')).toHaveTextContent('Imported offers are read-only');
  });
});

describe('Tabs', () => {
  it('switches the visible panel', async () => {
    function Harness() {
      const [value, setValue] = useState('drivers');
      return (
        <Tabs
          label="Fleet sections"
          value={value}
          onValueChange={setValue}
          items={[
            { value: 'drivers', label: 'Drivers', content: <p>Driver table</p> },
            { value: 'vehicles', label: 'Vehicles', content: <p>Vehicle table</p> },
          ]}
        />
      );
    }
    render(<Harness />);
    expect(screen.getByRole('tablist', { name: 'Fleet sections' })).toBeInTheDocument();
    expect(screen.getByText('Driver table')).toBeVisible();
    await userEvent.click(screen.getByRole('tab', { name: 'Vehicles' }));
    expect(screen.getByText('Vehicle table')).toBeVisible();
    expect(screen.getByRole('tab', { name: 'Vehicles' })).toHaveAttribute('aria-selected', 'true');
  });
});

function ToastButtons() {
  const toast = useToast();
  return (
    <>
      <Button onClick={() => toast.show('success', 'Driver saved')}>ok</Button>
      <Button onClick={() => toast.show('error', 'Could not save')}>fail</Button>
    </>
  );
}

describe('Toast', () => {
  afterEach(() => vi.useRealTimers());

  it('lets success toasts disappear and keeps error toasts until dismissed', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    render(
      <ToastProvider dismissLabel="Dismiss" successMs={1000}>
        <ToastButtons />
      </ToastProvider>,
    );
    await userEvent.click(screen.getByRole('button', { name: 'ok' }));
    await userEvent.click(screen.getByRole('button', { name: 'fail' }));
    expect(screen.getByText('Driver saved')).toBeVisible();
    expect(screen.getByText('Could not save')).toBeVisible();
    act(() => vi.advanceTimersByTime(1500));
    expect(screen.queryByText('Driver saved')).not.toBeInTheDocument();
    expect(screen.getByText('Could not save')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(screen.queryByText('Could not save')).not.toBeInTheDocument();
  });

  it('announces toasts politely', () => {
    render(
      <ToastProvider dismissLabel="Dismiss">
        <p>page</p>
      </ToastProvider>,
    );
    expect(screen.getAllByRole('status')[0]).toHaveAttribute('aria-live', 'polite');
  });
});

describe('LiveRegion', () => {
  it('is a polite status region', () => {
    render(<LiveRegion>Run finished</LiveRegion>);
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });
});
