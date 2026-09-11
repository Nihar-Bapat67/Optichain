import type { ReactNode } from 'react';
import { AlertTriangle, Inbox, RefreshCw } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Button } from './Button';

interface StateShellProps {
  icon: ReactNode;
  iconClass?: string;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
  /** `status` announces politely; `alert` interrupts. Errors use alert. */
  role?: 'status' | 'alert';
}

function StateShell({
  icon,
  iconClass,
  title,
  description,
  action,
  children,
  className,
  role = 'status',
}: StateShellProps) {
  return (
    <div
      role={role}
      className={cn(
        'flex flex-col items-center justify-center rounded-xl border border-dashed border-border',
        'bg-surface-raised px-6 py-12 text-center',
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          'flex h-11 w-11 items-center justify-center rounded-lg',
          'bg-surface-sunken text-content-subtle [&>svg]:h-5 [&>svg]:w-5',
          iconClass,
        )}
      >
        {icon}
      </span>
      <h3 className="mt-4 font-display text-md font-semibold text-content">{title}</h3>
      {description ? (
        <div className="mt-1.5 max-w-md text-balance text-sm leading-relaxed text-content-muted">
          {description}
        </div>
      ) : null}
      {children ? <div className="mt-4 w-full max-w-lg">{children}</div> : null}
      {action ? <div className="mt-5 flex items-center gap-2">{action}</div> : null}
    </div>
  );
}

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export function EmptyState({ icon, ...rest }: EmptyStateProps) {
  return <StateShell icon={icon ?? <Inbox />} {...rest} />;
}

export interface ErrorStateProps {
  title?: string;
  description?: ReactNode;
  /** Renders a Retry button when provided. */
  onRetry?: () => void;
  retryLabel?: string;
  children?: ReactNode;
  className?: string;
}

export function ErrorState({
  title = 'Something went wrong',
  description,
  onRetry,
  retryLabel = 'Try again',
  children,
  className,
}: ErrorStateProps) {
  return (
    <StateShell
      role="alert"
      icon={<AlertTriangle />}
      iconClass="bg-danger-soft text-danger"
      title={title}
      description={description}
      className={cn('border-danger-border/70', className)}
      action={
        onRetry ? (
          <Button variant="secondary" onClick={onRetry} leadingIcon={<RefreshCw className="h-4 w-4" />}>
            {retryLabel}
          </Button>
        ) : null
      }
    >
      {children}
    </StateShell>
  );
}

/** Compact inline error for use inside a card that already has a heading. */
export function InlineError({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        'flex items-start gap-2.5 rounded-md border border-danger-border bg-danger-soft px-3.5 py-3',
        className,
      )}
    >
      <AlertTriangle aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-danger" />
      <p className="min-w-0 flex-1 text-sm leading-relaxed text-danger">{message}</p>
      {onRetry ? (
        <Button size="xs" variant="ghost" onClick={onRetry} className="-my-1 shrink-0 text-danger">
          Retry
        </Button>
      ) : null}
    </div>
  );
}
