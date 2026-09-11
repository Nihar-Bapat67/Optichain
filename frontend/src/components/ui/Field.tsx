import { useId, type ReactNode } from 'react';
import { cn } from '../../lib/cn';
import { FieldContext } from './fieldContext';

export interface FieldProps {
  label: ReactNode;
  /** Helper text rendered under the control and linked via aria-describedby. */
  hint?: ReactNode;
  error?: string | null;
  required?: boolean;
  /** Visually hide the label but keep it available to screen readers. */
  hideLabel?: boolean;
  className?: string;
  children: ReactNode;
}

/**
 * Wires a label, control, hint and error message together with generated ids.
 * Controls read this via `useFieldControl()`, so callers never have to invent
 * an id or remember the aria attributes.
 */
export function Field({
  label,
  hint,
  error,
  required = false,
  hideLabel = false,
  className,
  children,
}: FieldProps) {
  const uid = useId();
  const controlId = `${uid}-control`;
  const descriptionId = hint ? `${uid}-hint` : undefined;
  const errorId = error ? `${uid}-error` : undefined;

  return (
    <FieldContext.Provider
      value={{ controlId, descriptionId, errorId, invalid: Boolean(error) }}
    >
      <div className={cn('space-y-1.5', className)}>
        <label
          htmlFor={controlId}
          className={cn('block text-xs font-medium text-content-muted', hideLabel && 'sr-only')}
        >
          {label}
          {required ? (
            <span className="ml-0.5 text-danger" aria-hidden>
              *
            </span>
          ) : null}
        </label>

        {children}

        {hint && !error ? (
          <p id={descriptionId} className="text-xs leading-relaxed text-content-subtle">
            {hint}
          </p>
        ) : null}

        {error ? (
          <p id={errorId} className="text-xs font-medium text-danger">
            {error}
          </p>
        ) : null}
      </div>
    </FieldContext.Provider>
  );
}
