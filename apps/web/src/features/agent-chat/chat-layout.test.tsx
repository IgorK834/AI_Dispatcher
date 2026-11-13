import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { agentApi } from '@/test/msw/handlers/agent';
import { navigation } from '@/test/navigation';
import { renderApp } from '@/test/render-app';
import { ChatScreen } from './chat-screen';
import { installFakeEventSource } from './test-utils';

vi.mock('next/navigation', async () => (await import('@/test/navigation')).navigationModule);

installFakeEventSource();

/** jsdom has no layout; `matchMedia` answers min-width queries for the chosen viewport width. */
function setViewport(width: number) {
  vi.stubGlobal('matchMedia', (query: string) => {
    const minimum = Number(/min-width:\s*(\d+)px/.exec(query)?.[1] ?? 0);
    return {
      matches: width >= minimum,
      media: query,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    };
  });
}

afterEach(() => vi.unstubAllGlobals());

async function renderAt(width: number) {
  navigation.reset('/');
  agentApi();
  setViewport(width);
  renderApp(<ChatScreen />);
  await screen.findByRole('textbox', { name: 'Message' });
  return document.querySelector('[data-layout]') as HTMLElement;
}

describe('[AC-FEAT-005-25] the AI Dispatcher layout', () => {
  it('shows three columns at 1280 px: conversation, trace and map side by side', async () => {
    const root = await renderAt(1280);
    expect(root).toHaveAttribute('data-layout', 'three-column');
    expect(root.querySelector('.grid')?.className).toContain('grid-cols-[');
    expect(screen.getByRole('region', { name: 'Agent trace' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Proposed routes' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Agent trace' })).not.toBeInTheDocument();
  });

  it('moves the trace into a drawer at 900 px', async () => {
    const root = await renderAt(900);
    expect(root).toHaveAttribute('data-layout', 'drawer');
    expect(screen.queryByRole('region', { name: 'Agent trace' })).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Agent trace' }));
    expect(await screen.findByRole('dialog', { name: 'Agent trace' })).toBeInTheDocument();
  });

  it('stacks the conversation, trace and map as cards at 600 px', async () => {
    const root = await renderAt(600);
    expect(root).toHaveAttribute('data-layout', 'stacked');
    const cards = [...root.querySelectorAll(':scope > div > div')];
    expect(cards).toHaveLength(3);
    expect(screen.getByRole('region', { name: 'Agent trace' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Agent trace' })).not.toBeInTheDocument();
  });

  it.each([1280, 900, 600])(
    'has no fixed width that could scroll the page at %s px',
    async (width) => {
      const root = await renderAt(width);
      expect(root.className).toContain('min-w-0');
      expect(root.querySelectorAll('[style*="width"]')).toHaveLength(0);
      expect(root.innerHTML).not.toMatch(/overflow-x-(scroll|auto)/);
    },
  );
});
