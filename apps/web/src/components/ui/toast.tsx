'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { cn } from './cn';

type ToastTone = 'success' | 'error';
type Toast = { id: number; tone: ToastTone; text: string };

type ToastApi = {
  /** Success toasts disappear by themselves; error toasts stay until dismissed. */
  show: (tone: ToastTone, text: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast needs a ToastProvider');
  return context;
}

export function ToastProvider({
  children,
  dismissLabel,
  successMs = 5000,
}: {
  children: ReactNode;
  dismissLabel: string;
  successMs?: number;
}) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const next = useRef(1);
  const dismiss = useCallback(
    (id: number) => setToasts((all) => all.filter((toast) => toast.id !== id)),
    [],
  );
  const show = useCallback(
    (tone: ToastTone, text: string) => {
      const id = next.current++;
      setToasts((all) => [...all, { id, tone, text }]);
      if (tone === 'success') setTimeout(() => dismiss(id), successMs);
    },
    [dismiss, successMs],
  );
  const api = useMemo(() => ({ show }), [show]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        className="fixed bottom-4 left-4 z-50 flex flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            data-tone={toast.tone}
            className={cn(
              'flex items-center gap-3 rounded-inner bg-ink px-4 py-3 text-sm text-surface',
              toast.tone === 'error' && 'border-l-4 border-red',
            )}
          >
            <span>{toast.text}</span>
            {toast.tone === 'error' && (
              <button
                type="button"
                className="rounded-segment px-2 underline"
                onClick={() => dismiss(toast.id)}
              >
                {dismissLabel}
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
