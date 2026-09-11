import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '../../lib/cn';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Lifts the card on hover — use only when the whole card is a link or button. */
  interactive?: boolean;
}

export function Card({ interactive = false, className, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border border-border bg-surface-raised shadow-xs',
        interactive &&
          'cursor-pointer transition-[border-color,box-shadow,transform] duration-200 ease-out hover:-translate-y-0.5 hover:border-border-strong hover:shadow-md',
        className,
      )}
      {...rest}
    />
  );
}

// `title` is omitted from the native attributes so it can carry rich content
// here instead of the browser's plain-text tooltip string.
export interface CardHeaderProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title'> {
  title: ReactNode;
  description?: ReactNode;
  icon?: ReactNode;
  /** Right-aligned controls: filters, menus, links. */
  actions?: ReactNode;
  /** Heading level — pick the one that fits the page outline. */
  as?: 'h2' | 'h3' | 'h4';
}

export function CardHeader({
  title,
  description,
  icon,
  actions,
  as: Heading = 'h3',
  className,
  ...rest
}: CardHeaderProps) {
  return (
    <div
      className={cn(
        // Actions stack under the title on narrow screens; a fixed-width
        // control beside the heading would otherwise force the card to
        // overflow the viewport.
        'flex flex-col gap-3 border-b border-border px-5 py-4',
        'sm:flex-row sm:items-start sm:justify-between sm:gap-4',
        className,
      )}
      {...rest}
    >
      <div className="flex min-w-0 items-start gap-3">
        {icon ? (
          <span
            aria-hidden
            className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-surface-sunken text-content-muted"
          >
            {icon}
          </span>
        ) : null}
        <div className="min-w-0">
          <Heading className="truncate font-display text-md font-semibold text-content">
            {title}
          </Heading>
          {description ? (
            <p className="mt-0.5 text-xs leading-relaxed text-content-subtle">{description}</p>
          ) : null}
        </div>
      </div>
      {actions ? (
        <div className="flex w-full items-center gap-2 sm:w-auto sm:shrink-0">{actions}</div>
      ) : null}
    </div>
  );
}

export function CardBody({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-5', className)} {...rest} />;
}

export function CardFooter({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'flex items-center justify-between gap-3 border-t border-border px-5 py-3',
        className,
      )}
      {...rest}
    />
  );
}
