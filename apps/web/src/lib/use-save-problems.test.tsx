import { renderHook, act } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactNode } from 'react';
import type { UseFormReturn } from 'react-hook-form';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import en from '../../messages/en.json';
import { useSaveProblems } from './use-save-problems';

const show = vi.fn();
vi.mock('@/components/ui/toast', () => ({ useToast: () => ({ show }) }));

type Values = { name: string; plate: string };
const setError = vi.fn();
const form = { setError } as unknown as UseFormReturn<Values>;
const texts = {
  noPermission: 'No permission',
  unknownFields: (fields: string) => `Unknown: ${fields}`,
};

function Wrapper({ children }: { children: ReactNode }) {
  return (
    <NextIntlClientProvider locale="en" messages={en}>
      {children}
    </NextIntlClientProvider>
  );
}

function setup(options: { onConflict?: () => void; fieldForCode?: Record<string, 'name'> } = {}) {
  return renderHook(
    () => useSaveProblems<Values>({ form, fields: ['name', 'plate'], texts, ...options }),
    { wrapper: Wrapper },
  );
}

const outcome = (status: number, error: unknown) => ({
  error,
  response: new Response(null, { status }),
});

beforeEach(() => {
  show.mockClear();
  setError.mockClear();
});

describe('useSaveProblems', () => {
  it('sends a version conflict to the conflict handler only', () => {
    const onConflict = vi.fn();
    const { result } = setup({ onConflict });
    act(() => result.current.handle(outcome(409, { code: 'VERSION_CONFLICT' })));
    expect(onConflict).toHaveBeenCalledOnce();
    expect(show).not.toHaveBeenCalled();
  });

  it('shows the "no permission" toast for 403', () => {
    const { result } = setup();
    act(() => result.current.handle(outcome(403, { code: 'FORBIDDEN' })));
    expect(show).toHaveBeenCalledWith('error', 'No permission');
  });

  it('puts a problem code that belongs to one field under that field', () => {
    const { result } = setup({ fieldForCode: { DUPLICATE_RESOURCE: 'name' } });
    act(() => result.current.handle(outcome(409, { code: 'DUPLICATE_RESOURCE' })));
    expect(setError).toHaveBeenCalledWith('name', expect.objectContaining({ type: 'server' }));
  });

  it('puts 422 messages under their fields and lists unknown fields in the form alert', () => {
    const { result } = setup();
    act(() =>
      result.current.handle(
        outcome(422, {
          code: 'VALIDATION_ERROR',
          errors: [
            { field: 'plate', message: 'Too short' },
            { field: 'colour', message: 'Not allowed' },
          ],
        }),
      ),
    );
    expect(setError).toHaveBeenCalledWith('plate', { type: 'server', message: 'Too short' });
    expect(result.current.formError).toBe('Unknown: colour');
    act(() => result.current.clearFormError());
    expect(result.current.formError).toBeNull();
  });

  it('shows any other problem as a toast, with the request id when there is one', () => {
    const { result } = setup();
    act(() => result.current.handle(outcome(500, { code: 'INTERNAL_ERROR', requestId: 'req-1' })));
    expect(show).toHaveBeenCalledWith('error', expect.stringMatching(/\(req-1\)$/));
    act(() => result.current.handle(outcome(500, { code: 'INTERNAL_ERROR' })));
    expect(show).toHaveBeenLastCalledWith('error', expect.not.stringContaining('('));
  });
});
