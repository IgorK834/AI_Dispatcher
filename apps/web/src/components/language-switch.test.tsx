import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { bundles, renderWithIntl } from '@/test/render';
import { LanguageSwitch } from './language-switch';

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh }) }));

describe('[AC-FEAT-000-04] language switch', () => {
  it('offers both languages, marks the current one and stores the other in a cookie', () => {
    for (const locale of ['en', 'pl'] as const) {
      const messages = bundles[locale];
      const { unmount } = renderWithIntl(<LanguageSwitch />, { locale });
      expect(screen.getAllByRole('button')).toHaveLength(2);
      const nextLocale = locale === 'en' ? 'pl' : 'en';
      expect(
        screen.getByRole('button', { name: messages.common.language[locale] }),
      ).toHaveAttribute('aria-pressed', 'true');
      fireEvent.click(screen.getByRole('button', { name: messages.common.language[nextLocale] }));
      expect(document.cookie).toContain(`locale=${nextLocale}`);
      expect(refresh).toHaveBeenCalled();
      unmount();
    }
  });
});
