import type { HTMLAttributes, ReactNode, TdHTMLAttributes, ThHTMLAttributes } from 'react';
import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react';
import { cn } from '../../lib/cn';

export type SortDirection = 'asc' | 'desc' | false;

export function TableContainer({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        'scrollbar-slim w-full overflow-x-auto rounded-xl border border-border bg-surface-raised',
        className,
      )}
      {...rest}
    />
  );
}

export interface TableProps extends HTMLAttributes<HTMLTableElement> {
  /** Screen-reader description of the table's purpose. */
  caption?: string;
}

export function Table({ caption, className, children, ...rest }: TableProps) {
  return (
    <table className={cn('w-full border-collapse text-left text-sm', className)} {...rest}>
      {caption ? <caption className="sr-only">{caption}</caption> : null}
      {children}
    </table>
  );
}

export function THead({ className, ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={cn('bg-surface-sunken', className)} {...rest} />;
}

export function TBody({ className, ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn('divide-y divide-border', className)} {...rest} />;
}

export function TR({ className, ...rest }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr className={cn('transition-colors hover:bg-surface-sunken/60', className)} {...rest} />
  );
}

export interface THProps extends ThHTMLAttributes<HTMLTableCellElement> {
  /** Pass `false` for sortable-but-unsorted, or omit entirely for static columns. */
  sortDirection?: SortDirection;
  /** Accepts an optional event so TanStack's `getToggleSortingHandler()` fits directly. */
  onSort?: (event?: unknown) => void;
  align?: 'left' | 'right' | 'center';
  children?: ReactNode;
}

export function TH({
  sortDirection,
  onSort,
  align = 'left',
  className,
  children,
  ...rest
}: THProps) {
  const sortable = typeof onSort === 'function';

  const ariaSort: ThHTMLAttributes<HTMLTableCellElement>['aria-sort'] = !sortable
    ? undefined
    : sortDirection === 'asc'
      ? 'ascending'
      : sortDirection === 'desc'
        ? 'descending'
        : 'none';

  const SortIcon =
    sortDirection === 'asc' ? ArrowUp : sortDirection === 'desc' ? ArrowDown : ChevronsUpDown;

  return (
    <th
      scope="col"
      aria-sort={ariaSort}
      className={cn(
        'whitespace-nowrap border-b border-border px-4 py-2.5',
        'text-2xs font-semibold uppercase tracking-wider text-content-subtle',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        className,
      )}
      {...rest}
    >
      {sortable ? (
        // A real <button> keeps sorting reachable by keyboard, which a
        // click handler on the <th> alone would not.
        <button
          type="button"
          onClick={onSort}
          className={cn(
            'group -mx-1 inline-flex items-center gap-1.5 rounded px-1 py-0.5',
            'uppercase tracking-wider transition-colors hover:text-content',
            align === 'right' && 'flex-row-reverse',
          )}
        >
          {children}
          <SortIcon
            aria-hidden
            className={cn(
              'h-3 w-3 shrink-0 transition-opacity',
              sortDirection ? 'opacity-100' : 'opacity-40 group-hover:opacity-70',
            )}
          />
        </button>
      ) : (
        children
      )}
    </th>
  );
}

export interface TDProps extends TdHTMLAttributes<HTMLTableCellElement> {
  align?: 'left' | 'right' | 'center';
  /** Tabular figures + mono for numeric columns so digits line up. */
  numeric?: boolean;
}

export function TD({ align = 'left', numeric = false, className, ...rest }: TDProps) {
  return (
    <td
      className={cn(
        'px-4 py-3 text-sm text-content-muted',
        align === 'right' && 'text-right',
        align === 'center' && 'text-center',
        numeric && 'font-mono tabular-nums text-content',
        className,
      )}
      {...rest}
    />
  );
}
