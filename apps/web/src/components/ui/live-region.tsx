import type { ReactNode } from 'react';

/** The one polite live region that announces an agent run's status (FR-22, AC-FEAT-005-19). */
export function LiveRegion({ children }: { children: ReactNode }) {
  return (
    <div role="status" aria-live="polite" aria-atomic="true">
      {children}
    </div>
  );
}
