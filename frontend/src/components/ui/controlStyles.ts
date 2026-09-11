import { cn } from '../../lib/cn';

/**
 * Shared visual contract for text inputs and selects, so both react identically
 * to hover, focus, disabled and invalid states.
 */
export const controlBaseClass = cn(
  'w-full rounded-md border border-border bg-surface text-content',
  'placeholder:text-content-subtle',
  'transition-[border-color,box-shadow] duration-150 ease-out',
  'hover:border-border-strong',
  'focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/25 focus:ring-offset-0',
  'disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-content-subtle',
  'aria-[invalid=true]:border-danger aria-[invalid=true]:focus:ring-danger/25',
);
