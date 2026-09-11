import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { cn } from '../../lib/cn';

export interface DropdownMenuProps {
  trigger: (props: {
    ref: React.Ref<HTMLButtonElement>;
    onClick: () => void;
    'aria-expanded': boolean;
    'aria-haspopup': 'menu';
    'aria-controls': string;
  }) => ReactNode;
  children: ReactNode;
  align?: 'start' | 'end';
  className?: string;
}

export function DropdownMenu({
  trigger,
  children,
  align = 'end',
  className,
}: DropdownMenuProps) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;

    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className={cn('relative inline-flex', className)}>
      {trigger({
        ref: triggerRef,
        onClick: () => setOpen((v) => !v),
        'aria-expanded': open,
        'aria-haspopup': 'menu',
        'aria-controls': id,
      })}

      <AnimatePresence>
        {open ? (
          <motion.div
            id={id}
            role="menu"
            initial={{ opacity: 0, scale: 0.97, y: -4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: -4, transition: { duration: 0.1 } }}
            transition={{ duration: 0.14, ease: [0.16, 1, 0.3, 1] }}
            onClick={() => setOpen(false)}
            className={cn(
              'absolute top-full z-50 mt-1.5 min-w-[11rem] origin-top overflow-hidden',
              'rounded-lg border border-border bg-surface-overlay p-1 shadow-lg',
              align === 'end' ? 'right-0' : 'left-0',
            )}
          >
            {children}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

export interface DropdownItemProps {
  onSelect?: () => void;
  icon?: ReactNode;
  disabled?: boolean;
  tone?: 'default' | 'danger';
  children: ReactNode;
}

export function DropdownItem({
  onSelect,
  icon,
  disabled = false,
  tone = 'default',
  children,
}: DropdownItemProps) {
  return (
    <button
      role="menuitem"
      type="button"
      disabled={disabled}
      onClick={onSelect}
      className={cn(
        'flex w-full items-center gap-2.5 rounded px-2.5 py-1.5 text-left text-sm',
        'transition-colors disabled:pointer-events-none disabled:opacity-50',
        tone === 'danger'
          ? 'text-danger hover:bg-danger-soft'
          : 'text-content-muted hover:bg-surface-sunken hover:text-content',
      )}
    >
      {icon ? (
        <span aria-hidden className="shrink-0 [&>svg]:h-3.5 [&>svg]:w-3.5">
          {icon}
        </span>
      ) : null}
      {children}
    </button>
  );
}

export function DropdownLabel({ children }: { children: ReactNode }) {
  return (
    <p className="px-2.5 py-1.5 text-2xs font-semibold uppercase tracking-wider text-content-subtle">
      {children}
    </p>
  );
}

export function DropdownSeparator() {
  return <div role="separator" className="my-1 h-px bg-border" />;
}
