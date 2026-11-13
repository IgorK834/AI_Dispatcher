import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithIntl } from '@/test/render';
import { ApiUnreachable } from './api-unreachable';

describe('ApiUnreachable', () => {
  it('names the API address, hints at the cause and offers a retry', async () => {
    const onRetry = vi.fn();
    renderWithIntl(<ApiUnreachable onRetry={onRetry} />);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Cannot reach the API at http://localhost:8000',
    );
    expect(screen.getByRole('alert')).toHaveTextContent('port 8000');
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('speaks Polish for the Polish locale', () => {
    renderWithIntl(<ApiUnreachable onRetry={() => undefined} />, { locale: 'pl' });
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Nie można połączyć się');
  });
});
