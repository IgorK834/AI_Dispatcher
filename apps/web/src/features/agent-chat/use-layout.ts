'use client';

import { useEffect, useState } from 'react';

/** Three columns from 1280 px, the trace as a drawer from 768 px, stacked cards below (AC-FEAT-005-25). */
export type ChatLayout = 'three-column' | 'drawer' | 'stacked';

export const WIDE_QUERY = '(min-width: 1280px)';
export const MEDIUM_QUERY = '(min-width: 768px)';

export function useChatLayout(): ChatLayout {
  const [layout, setLayout] = useState<ChatLayout>('three-column');
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return;
    const wide = window.matchMedia(WIDE_QUERY);
    const medium = window.matchMedia(MEDIUM_QUERY);
    const update = () =>
      setLayout(wide.matches ? 'three-column' : medium.matches ? 'drawer' : 'stacked');
    update();
    wide.addEventListener('change', update);
    medium.addEventListener('change', update);
    return () => {
      wide.removeEventListener('change', update);
      medium.removeEventListener('change', update);
    };
  }, []);
  return layout;
}
