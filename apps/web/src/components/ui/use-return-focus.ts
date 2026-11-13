import { useLayoutEffect, useRef } from 'react';

/**
 * Radix returns focus only to its own Trigger component. These dialogs are opened from ordinary
 * buttons through state, so the element that was focused when the dialog opened is remembered
 * here and focused again when it closes (Escape or a button), as the UX rules require.
 */
export function useReturnFocus(open: boolean) {
  const target = useRef<HTMLElement | null>(null);
  useLayoutEffect(() => {
    // Runs before Radix moves focus into the dialog (its focus scope uses a passive effect).
    if (open && document.activeElement instanceof HTMLElement) {
      target.current = document.activeElement;
    }
  }, [open]);
  return (event: Event) => {
    event.preventDefault();
    target.current?.focus({ preventScroll: true });
  };
}
