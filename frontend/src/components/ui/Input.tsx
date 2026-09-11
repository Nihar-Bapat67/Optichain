import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react';
import { cn } from '../../lib/cn';
import { controlBaseClass } from './controlStyles';
import { useFieldControl } from './fieldContext';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  leadingIcon?: ReactNode;
  trailingSlot?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { leadingIcon, trailingSlot, className, ...rest },
  ref,
) {
  // Present when rendered inside <Field>; supplies id + aria wiring.
  const field = useFieldControl();

  const input = (
    <input
      ref={ref}
      {...field}
      className={cn(
        controlBaseClass,
        'h-9 px-3 text-sm',
        leadingIcon && 'pl-9',
        trailingSlot && 'pr-9',
        className,
      )}
      {...rest}
    />
  );

  if (!leadingIcon && !trailingSlot) return input;

  return (
    <div className="relative">
      {leadingIcon ? (
        <span
          aria-hidden
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-content-subtle [&>svg]:h-4 [&>svg]:w-4"
        >
          {leadingIcon}
        </span>
      ) : null}
      {input}
      {trailingSlot ? (
        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-content-subtle">
          {trailingSlot}
        </span>
      ) : null}
    </div>
  );
});
