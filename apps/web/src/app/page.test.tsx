import { screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { agentApi } from '@/test/msw/handlers/agent';
import { renderApp } from '@/test/render-app';
import Home from './page';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

describe('[AC-FEAT-000-04] translated home page', () => {
  it('renders the AI Dispatcher title in both supported locales', async () => {
    for (const locale of ['en', 'pl'] as const) {
      agentApi();
      const { unmount } = renderApp(<Home />, locale);
      const title = locale === 'en' ? 'AI Dispatcher' : 'Dyspozytor AI';
      expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(title);
      expect(
        await screen.findByRole('textbox', { name: locale === 'en' ? 'Message' : 'Wiadomość' }),
      ).toBeInTheDocument();
      unmount();
    }
  });
});
