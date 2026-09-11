import { useRef, type ReactNode } from 'react';
import { cn } from '../../lib/cn';

export interface TabItem<T extends string> {
  value: T;
  label: string;
  icon?: ReactNode;
  badge?: ReactNode;
}

export interface TabsProps<T extends string> {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  'aria-label': string;
  className?: string;
}

/**
 * Follows the ARIA tabs pattern: roving tabindex plus arrow-key navigation, so
 * the tablist is a single tab stop rather than one stop per tab.
 */
export function Tabs<T extends string>({
  items,
  value,
  onChange,
  'aria-label': ariaLabel,
  className,
}: TabsProps<T>) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  function handleKeyDown(event: React.KeyboardEvent, index: number) {
    const lastIndex = items.length - 1;
    let next: number | null = null;

    if (event.key === 'ArrowRight') next = index === lastIndex ? 0 : index + 1;
    else if (event.key === 'ArrowLeft') next = index === 0 ? lastIndex : index - 1;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = lastIndex;

    if (next === null) return;
    event.preventDefault();
    onChange(items[next].value);
    refs.current[next]?.focus();
  }

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        'inline-flex items-center gap-0.5 rounded-lg border border-border bg-surface-sunken p-0.5',
        className,
      )}
    >
      {items.map((item, index) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            ref={(el) => {
              refs.current[index] = el;
            }}
            role="tab"
            type="button"
            aria-selected={active}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(item.value)}
            onKeyDown={(e) => handleKeyDown(e, index)}
            className={cn(
              'inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5',
              'text-xs font-medium transition-colors duration-150',
              active
                ? 'bg-surface-raised text-content shadow-xs'
                : 'text-content-muted hover:text-content',
            )}
          >
            {item.icon ? (
              <span aria-hidden className="[&>svg]:h-3.5 [&>svg]:w-3.5">
                {item.icon}
              </span>
            ) : null}
            {item.label}
            {item.badge}
          </button>
        );
      })}
    </div>
  );
}
