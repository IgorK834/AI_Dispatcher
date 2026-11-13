import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Button } from './button';
import { ChoiceCard } from './choice-card';
import { Field, Input } from './field';
import { IconButton } from './icon-button';
import { Pill } from './pill';
import { Segmented } from './segmented';

describe('Button', () => {
  it('renders the three variants and sizes with their states', () => {
    render(
      <>
        <Button variant="primary">Save</Button>
        <Button>Cancel</Button>
        <Button variant="danger" small>
          Delete
        </Button>
        <Button disabled>Off</Button>
      </>,
    );
    expect(screen.getByRole('button', { name: 'Save' }).className).toContain('bg-red');
    expect(screen.getByRole('button', { name: 'Cancel' }).className).toContain('bg-surface');
    const danger = screen.getByRole('button', { name: 'Delete' });
    expect(danger.className).toContain('text-red-hover');
    expect(danger.className).toContain('min-h-9');
    expect(screen.getByRole('button', { name: 'Off' })).toBeDisabled();
  });

  it('is disabled and busy while loading, and does not submit twice', async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Save' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('defaults to type="button" so it never submits a form by accident', () => {
    render(<Button>Go</Button>);
    expect(screen.getByRole('button', { name: 'Go' })).toHaveAttribute('type', 'button');
  });
});

describe('IconButton', () => {
  it('has an accessible name and an optional count badge', () => {
    render(<IconButton label="Approvals" icon="!" count={3} />);
    const button = screen.getByRole('button', { name: 'Approvals' });
    expect(button).toHaveTextContent('3');
  });

  it('shows no badge for a zero count', () => {
    render(<IconButton label="Approvals" icon="!" count={0} />);
    expect(screen.getByRole('button', { name: 'Approvals' })).not.toHaveTextContent('0');
  });
});

describe('Segmented', () => {
  it('marks the current option with aria-pressed and reports a choice by mouse or keyboard', async () => {
    const onChange = vi.fn();
    render(
      <Segmented
        label="Language"
        value="en"
        onValueChange={onChange}
        options={[
          { value: 'en', label: 'EN' },
          { value: 'pl', label: 'PL' },
        ]}
      />,
    );
    expect(screen.getByRole('group', { name: 'Language' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'EN' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'PL' })).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(screen.getByRole('button', { name: 'PL' }));
    expect(onChange).toHaveBeenLastCalledWith('pl');
    screen.getByRole('button', { name: 'EN' }).focus();
    await userEvent.keyboard('{Enter}');
    expect(onChange).toHaveBeenLastCalledWith('en');
    expect(onChange).toHaveBeenCalledTimes(2);
  });
});

describe('Pill', () => {
  it('always carries its level as text', () => {
    render(
      <>
        <Pill level="done">Assigned</Pill>
        <Pill level="attention">Assumption</Pill>
        <Pill level="error">Rejected</Pill>
        <Pill level="synthetic">SYNTHETIC DATA</Pill>
      </>,
    );
    for (const text of ['Assigned', 'Assumption', 'Rejected', 'SYNTHETIC DATA']) {
      expect(screen.getByText(text)).toBeInTheDocument();
    }
    expect(screen.getByText('Rejected').className).toContain('bg-red');
    expect(screen.getByText('SYNTHETIC DATA').className).toContain('border');
  });
});

describe('Field', () => {
  it('connects label, hint and error to the control and marks it invalid', () => {
    render(
      <Field id="name" label="Name" hint="As on the licence" error="Name is required">
        {(control) => <Input {...control} />}
      </Field>,
    );
    const input = screen.getByLabelText('Name');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(input).toHaveAccessibleDescription('As on the licence Name is required');
    expect(screen.getByText('Name is required')).toBeVisible();
  });

  it('is valid and quiet without an error', () => {
    render(
      <Field id="city" label="City">
        {(control) => <Input {...control} />}
      </Field>,
    );
    const input = screen.getByLabelText('City');
    expect(input).not.toHaveAttribute('aria-invalid');
    expect(input).not.toHaveAttribute('aria-describedby');
  });
});

describe('ChoiceCard', () => {
  it('is a labelled radio that can be chosen', async () => {
    const onChange = vi.fn();
    render(
      <ChoiceCard
        name="profile"
        value="pl"
        title="Domestic"
        description="Polish rules"
        onChange={onChange}
      />,
    );
    const radio = screen.getByRole('radio', { name: /Domestic/ });
    await userEvent.click(radio);
    expect(radio).toBeChecked();
    expect(onChange).toHaveBeenCalled();
  });
});
