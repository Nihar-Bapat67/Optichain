import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../lib/cn';

export type ButtonVariant =
  | 'primary'
  | 'secondary'
  | 'ghost'
  | 'outline'
  | 'danger'
  | 'success';
export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg';

const VARIANTS: Record<ButtonVariant, string> = {
  primary:
    'bg-accent text-accent-fg shadow-xs hover:bg-accent-hover active:bg-accent-hover disabled:hover:bg-accent',
  secondary:
    'bg-surface-raised text-content border border-border shadow-xs hover:bg-surface-sunken hover:border-border-strong',
  ghost: 'text-content-muted hover:bg-surface-sunken hover:text-content',
  outline:
    'border border-border-strong text-content hover:bg-surface-sunken hover:border-accent/50',
  danger: 'bg-danger text-danger-fg shadow-xs hover:opacity-90',
  success: 'bg-ok text-ok-fg shadow-xs hover:opacity-90',
};

const SIZES: Record<ButtonSize, string> = {
  xs: 'h-7 px-2.5 text-xs gap-1.5 rounded-sm',
  sm: 'h-8 px-3 text-xs gap-1.5 rounded-md',
  md: 'h-9 px-3.5 text-sm gap-2 rounded-md',
  lg: 'h-11 px-5 text-md gap-2 rounded-lg',
};

const ICON_ONLY: Record<ButtonSize, string> = {
  xs: 'w-7 px-0',
  sm: 'w-8 px-0',
  md: 'w-9 px-0',
  lg: 'w-11 px-0',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Renders a spinner, disables interaction, and marks the control busy. */
  loading?: boolean;
  iconOnly?: boolean;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
  fullWidth?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = 'secondary',
    size = 'md',
    loading = false,
    iconOnly = false,
    leadingIcon,
    trailingIcon,
    fullWidth = false,
    disabled,
    className,
    children,
    type = 'button',
    ...rest
  },
  ref,
) {
  const isDisabled = disabled || loading;

  return (
    <button
      ref={ref}
      type={type}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      className={cn(
        'inline-flex select-none items-center justify-center whitespace-nowrap font-medium',
        'transition-colors duration-150 ease-out',
        'disabled:pointer-events-none disabled:opacity-50',
        VARIANTS[variant],
        SIZES[size],
        iconOnly && ICON_ONLY[size],
        fullWidth && 'w-full',
        className,
      )}
      {...rest}
    >
      {loading ? (
        <Loader2 aria-hidden className="h-4 w-4 shrink-0 animate-spin" />
      ) : (
        leadingIcon
      )}
      {!iconOnly && children}
      {!loading && trailingIcon}
    </button>
  );
});
