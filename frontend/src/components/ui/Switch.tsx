import { useId } from 'react';
import { cn } from '../../lib/cn';

export interface SwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  label: string;
  /** Hide the visible label but keep the accessible name. */
  hideLabel?: boolean;
  description?: string;
  disabled?: boolean;
  id?: string;
  className?: string;
}

/**
 * `role="switch"` + `aria-checked` is what makes this announce as a toggle
 * rather than a nondescript button, and Space/Enter work natively on <button>.
 */
export function Switch({
  checked,
  onCheckedChange,
  label,
  hideLabel = false,
  description,
  disabled = false,
  id,
  className,
}: SwitchProps) {
  const generatedId = useId();
  const switchId = id ?? generatedId;
  const descriptionId = description ? `${switchId}-description` : undefined;

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <button
        id={switchId}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={descriptionId}
        disabled={disabled}
        onClick={() => onCheckedChange(!checked)}
        className={cn(
          'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full',
          'transition-colors duration-200 ease-out',
          'disabled:cursor-not-allowed disabled:opacity-50',
          checked ? 'bg-accent' : 'bg-border-strong',
        )}
      >
        <span
          aria-hidden
          className={cn(
            'inline-block h-4 w-4 transform rounded-full bg-white shadow-sm',
            'transition-transform duration-200 ease-out',
            checked ? 'translate-x-[1.125rem]' : 'translate-x-0.5',
          )}
        />
      </button>

      <div className={cn('min-w-0', hideLabel && 'sr-only')}>
        <label
          htmlFor={switchId}
          className={cn(
            'block text-sm font-medium text-content',
            !disabled && 'cursor-pointer',
          )}
        >
          {label}
        </label>
        {description ? (
          <p id={descriptionId} className="text-xs text-content-subtle">
            {description}
          </p>
        ) : null}
      </div>
    </div>
  );
}
