import { forwardRef, type SelectHTMLAttributes } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '../../lib/cn';
import { controlBaseClass } from './controlStyles';
import { useFieldControl } from './fieldContext';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /** Convenience alternative to passing <option> children. */
  options?: SelectOption[];
  placeholder?: string;
}

/**
 * Native <select> deliberately: it gets mobile pickers, keyboard behaviour and
 * screen-reader support for free, which a div-based menu would have to rebuild.
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { options, placeholder, className, children, ...rest },
  ref,
) {
  const field = useFieldControl();

  return (
    <div className="relative">
      <select
        ref={ref}
        {...field}
        className={cn(
          controlBaseClass,
          'h-9 cursor-pointer appearance-none py-0 pl-3 pr-9 text-sm',
          className,
        )}
        {...rest}
      >
        {placeholder ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {options?.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
        {children}
      </select>
      <ChevronDown
        aria-hidden
        className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-content-subtle"
      />
    </div>
  );
});
