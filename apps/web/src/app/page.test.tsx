import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { renderWithIntl } from '@/test/render';
import Home from './page';

describe('[AC-FEAT-000-04] translated home page', () => {
  it('renders the title in both supported locales', () => {
    for (const locale of ['en', 'pl'] as const) {
      const { unmount } = renderWithIntl(<Home />, { locale });
      const title = locale === 'en' ? 'RoutePilot AI' : 'RoutePilot AI — dyspozytor';
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(title);
      unmount();
    }
  });
});
