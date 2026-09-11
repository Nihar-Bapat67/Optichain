import { useEffect, useId, useState, type ReactNode } from 'react';
import { cn } from '../../lib/cn';

export interface TooltipProps {
  content: ReactNode;
  side?: 'top' | 'bottom';
  children: ReactNode;
  className?: string;
}

/**
 * Opens on hover *and* focus so the content is reachable without a pointer.
 * Supplementary text only — never the sole source of information.
 */
export function Tooltip({ content, side = 'top', children, className }: TooltipProps) {
  const id = useId();
  const [open, setOpen] = useState(false);

  // Escape is handled at the document level rather than via onKeyDown on the
  // wrapper: it still works when focus has moved elsewhere, and it keeps the
  // wrapper a purely presentational element.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open]);

  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocusCapture={() => setOpen(true)}
      onBlurCapture={() => setOpen(false)}
    >
      <span aria-describedby={open ? id : undefined} className="inline-flex">
        {children}
      </span>

      {open ? (
        <span
          role="tooltip"
          id={id}
          className={cn(
            'pointer-events-none absolute left-1/2 z-50 w-max max-w-xs -translate-x-1/2',
            'animate-fade-in rounded-md border border-border bg-surface-overlay px-2.5 py-1.5',
            'text-xs leading-relaxed text-content shadow-lg',
            side === 'top' ? 'bottom-full mb-1.5' : 'top-full mt-1.5',
          )}
        >
          {content}
        </span>
      ) : null}
    </span>
  );
}
