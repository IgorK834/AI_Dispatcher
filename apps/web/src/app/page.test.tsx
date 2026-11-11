import { render, screen, cleanup, fireEvent } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import { afterEach, describe, expect, it, vi } from 'vitest';
import en from '../../messages/en.json';
import pl from '../../messages/pl.json';

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ refresh }) }));

afterEach(cleanup);

describe('[AC-FEAT-000-04] translated home page', () => {
  it('renders the title in both supported locales', async () => {
    const { default: Home } = await import('./page');
    for (const locale of ['en', 'pl'] as const) {
      const messages = { en, pl }[locale];
      render(
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Home />
        </NextIntlClientProvider>,
      );
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(messages.common.appTitle);
      expect(screen.getAllByRole('button')).toHaveLength(2);
      const nextLocale = locale === 'en' ? 'pl' : 'en';
      fireEvent.click(screen.getByRole('button', { name: messages.common.language[nextLocale] }));
      expect(document.cookie).toContain(`locale=${nextLocale}`);
      expect(refresh).toHaveBeenCalled();
      cleanup();
    }
  });
});
