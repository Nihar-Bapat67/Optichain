import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';
import { cn } from '../lib/cn';
import {
  ToastContext,
  type Toast,
  type ToastContextValue,
  type ToastInput,
  type ToastTone,
} from './toastContext';

const TONE_CONFIG: Record<ToastTone, { icon: typeof Info; accent: string; iconClass: string }> = {
  success: { icon: CheckCircle2, accent: 'bg-ok', iconClass: 'text-ok' },
  error: { icon: XCircle, accent: 'bg-danger', iconClass: 'text-danger' },
  warning: { icon: AlertTriangle, accent: 'bg-warn', iconClass: 'text-warn' },
  info: { icon: Info, accent: 'bg-accent', iconClass: 'text-accent' },
};

let toastCounter = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  }, []);

  const toast = useCallback(
    (input: ToastInput) => {
      const id = `toast-${++toastCounter}`;
      const next: Toast = {
        id,
        tone: input.tone ?? 'info',
        title: input.title,
        description: input.description,
        duration: input.duration ?? 5000,
      };

      // Cap the stack so a burst of failures can't cover the viewport.
      setToasts((prev) => [...prev.slice(-2), next]);

      if (next.duration > 0) {
        timers.current.set(
          id,
          setTimeout(() => dismiss(id), next.duration),
        );
      }
      return id;
    },
    [dismiss],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      toast,
      dismiss,
      success: (title, description) => toast({ tone: 'success', title, description }),
      // Failures linger longer — they usually need the user to act.
      error: (title, description) => toast({ tone: 'error', title, description, duration: 8000 }),
      warning: (title, description) => toast({ tone: 'warning', title, description }),
      info: (title, description) => toast({ tone: 'info', title, description }),
    }),
    [toast, dismiss],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: Toast[];
  onDismiss: (id: string) => void;
}) {
  return (
    <div
      // Announced without stealing focus from the current task.
      role="region"
      aria-live="polite"
      aria-label="Notifications"
      className="pointer-events-none fixed inset-x-0 bottom-0 z-[100] flex flex-col items-center gap-2 p-4 sm:inset-x-auto sm:right-0 sm:top-0 sm:items-end sm:p-5"
    >
      <AnimatePresence initial={false}>
        {toasts.map((t) => {
          const { icon: Icon, accent, iconClass } = TONE_CONFIG[t.tone];
          return (
            <motion.div
              key={t.id}
              layout
              initial={{ opacity: 0, y: 12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.96, transition: { duration: 0.15 } }}
              transition={{ type: 'spring', stiffness: 420, damping: 32 }}
              className={cn(
                'pointer-events-auto relative w-full max-w-sm overflow-hidden',
                'rounded-lg border border-border bg-surface-overlay shadow-lg',
              )}
            >
              <span aria-hidden className={cn('absolute inset-y-0 left-0 w-1', accent)} />
              <div className="flex items-start gap-3 py-3 pl-4 pr-2.5">
                <Icon aria-hidden className={cn('mt-0.5 h-4 w-4 shrink-0', iconClass)} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-content">{t.title}</p>
                  {t.description ? (
                    <p className="mt-0.5 break-words text-xs leading-relaxed text-content-muted">
                      {t.description}
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => onDismiss(t.id)}
                  aria-label={`Dismiss notification: ${t.title}`}
                  className="-m-0.5 rounded p-1.5 text-content-subtle transition-colors hover:bg-surface-sunken hover:text-content"
                >
                  <X aria-hidden className="h-3.5 w-3.5" />
                </button>
              </div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
