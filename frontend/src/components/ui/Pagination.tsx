import { useId } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Button } from './Button';
import { Select } from './Select';

export interface PaginationProps {
  pageIndex: number;
  pageCount: number;
  pageSize: number;
  totalRows: number;
  onPageChange: (pageIndex: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  pageSizeOptions?: number[];
  className?: string;
}

export function Pagination({
  pageIndex,
  pageCount,
  pageSize,
  totalRows,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
  className,
}: PaginationProps) {
  const pageSizeId = useId();
  const firstRow = totalRows === 0 ? 0 : pageIndex * pageSize + 1;
  const lastRow = Math.min((pageIndex + 1) * pageSize, totalRows);

  return (
    <nav
      aria-label="Table pagination"
      className={cn(
        'flex flex-col gap-3 border-t border-border px-4 py-3',
        'sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
    >
      <div className="flex items-center gap-3">
        <p className="text-xs text-content-subtle" aria-live="polite">
          {totalRows === 0 ? (
            'No results'
          ) : (
            <>
              Showing <span className="font-medium text-content">{firstRow}</span>–
              <span className="font-medium text-content">{lastRow}</span> of{' '}
              <span className="font-medium text-content">{totalRows}</span>
            </>
          )}
        </p>

        <div className="flex items-center gap-1.5 text-xs text-content-subtle">
          <label htmlFor={pageSizeId} className="hidden sm:inline">
            Rows
          </label>
          <Select
            id={pageSizeId}
            value={String(pageSize)}
            onChange={(e) => onPageSizeChange(Number(e.target.value))}
            aria-label="Rows per page"
            className="h-7 w-[4.5rem] py-0 pl-2 pr-7 text-xs"
            options={pageSizeOptions.map((n) => ({ value: String(n), label: String(n) }))}
          />
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-xs text-content-subtle">
          Page <span className="font-medium text-content">{pageCount === 0 ? 0 : pageIndex + 1}</span> of{' '}
          <span className="font-medium text-content">{pageCount}</span>
        </span>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="secondary"
            iconOnly
            aria-label="Previous page"
            disabled={pageIndex === 0}
            onClick={() => onPageChange(pageIndex - 1)}
            leadingIcon={<ChevronLeft className="h-4 w-4" />}
          />
          <Button
            size="sm"
            variant="secondary"
            iconOnly
            aria-label="Next page"
            disabled={pageIndex >= pageCount - 1}
            onClick={() => onPageChange(pageIndex + 1)}
            leadingIcon={<ChevronRight className="h-4 w-4" />}
          />
        </div>
      </div>
    </nav>
  );
}
