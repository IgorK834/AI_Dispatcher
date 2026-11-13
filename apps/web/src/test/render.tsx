import { render, type RenderOptions } from '@testing-library/react';
import { NextIntlClientProvider } from 'next-intl';
import type { ReactElement, ReactNode } from 'react';
import en from '../../messages/en.json';
import pl from '../../messages/pl.json';

export const bundles = { en, pl } as const;
export type TestLocale = keyof typeof bundles;

/** Renders with the real message files, so tests read the same texts as users. */
export function renderWithIntl(
  ui: ReactElement,
  { locale = 'en', ...options }: RenderOptions & { locale?: TestLocale } = {},
) {
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <NextIntlClientProvider locale={locale} messages={bundles[locale]} timeZone="UTC">
        {children}
      </NextIntlClientProvider>
    );
  }
  return render(ui, { wrapper: Wrapper, ...options });
}
