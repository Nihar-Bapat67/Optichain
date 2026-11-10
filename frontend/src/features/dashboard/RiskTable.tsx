import { Fragment, useMemo, useState } from 'react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnFiltersState,
  type SortingState,
} from '@tanstack/react-table';
import { ChevronDown, ShieldCheck } from 'lucide-react';

import { Badge } from '../../components/ui/Badge';
import { EmptyState } from '../../components/ui/States';
import { Pagination } from '../../components/ui/Pagination';
import { SearchInput } from '../../components/ui/SearchInput';
import { Tabs } from '../../components/ui/Tabs';
import { Tooltip } from '../../components/ui/Tooltip';
import {
  TBody,
  TD,
  TH,
  THead,
  TR,
  Table,
  TableContainer,
} from '../../components/ui/Table';
import { formatNumber, formatSeverity } from '../../lib/format';
import type { Risk } from '../../types';

const columnHelper = createColumnHelper<Risk>();

type RiskFilter = 'all' | 'stockout' | 'overstock';

/** Severity is 0–1; these bands turn it into a readable label. */
function severityTone(severity: number) {
  if (severity >= 0.6) return 'danger' as const;
  if (severity >= 0.3) return 'warn' as const;
  return 'neutral' as const;
}

export function RiskTable({ risks }: { risks: Risk[] }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'severity', desc: true }]);
  const [globalFilter, setGlobalFilter] = useState('');
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([]);
  const [pagination, setPagination] = useState({ pageIndex: 0, pageSize: 10 });
  const [expandedRisk, setExpandedRisk] = useState<string | null>(null);

  const riskFilter: RiskFilter =
    (columnFilters.find((f) => f.id === 'risk_type')?.value as RiskFilter) ?? 'all';

  const counts = useMemo(
    () => ({
      all: risks.length,
      stockout: risks.filter((r) => r.risk_type === 'stockout').length,
      overstock: risks.filter((r) => r.risk_type === 'overstock').length,
    }),
    [risks],
  );

  const columns = useMemo(
    () => [
      columnHelper.accessor('sku_id', {
        header: 'SKU',
        cell: (info) => (
          <span className="font-mono text-xs font-medium text-content">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('warehouse_id', {
        header: 'Warehouse',
        cell: (info) => <span className="font-mono text-xs">{info.getValue()}</span>,
      }),
      columnHelper.accessor('risk_type', {
        header: 'Type',
        // Custom filter so the tab value 'all' bypasses filtering entirely.
        filterFn: (row, id, value) => value === 'all' || row.getValue(id) === value,
        cell: (info) => (
          <Badge tone={info.getValue() === 'stockout' ? 'danger' : 'warn'} dot>
            {info.getValue() === 'stockout' ? 'Stockout' : 'Overstock'}
          </Badge>
        ),
      }),
      columnHelper.accessor('severity', {
        header: 'Severity',
        cell: (info) => {
          const value = info.getValue();
          const tone = severityTone(value);
          return (
            <div className="flex items-center justify-end gap-2">
              <span
                aria-hidden
                className="h-1.5 w-14 overflow-hidden rounded-full bg-surface-sunken"
              >
                <span
                  className={
                    tone === 'danger'
                      ? 'block h-full rounded-full bg-danger'
                      : tone === 'warn'
                        ? 'block h-full rounded-full bg-warn'
                        : 'block h-full rounded-full bg-content-subtle'
                  }
                  style={{ width: `${Math.min(100, Math.max(4, value * 100))}%` }}
                />
              </span>
              <span className="w-10 text-right font-mono text-xs tabular-nums text-content">
                {formatSeverity(value)}
              </span>
            </div>
          );
        },
      }),
      columnHelper.accessor('weeks_of_cover', {
        header: 'Wks cover',
        cell: (info) => formatNumber(info.getValue(), 1),
      }),
      columnHelper.accessor('expected_demand_in_lead_time', {
        header: 'Lead demand',
        cell: (info) => formatNumber(info.getValue()),
      }),
      columnHelper.accessor('available_units', {
        header: 'Available',
        cell: (info) => formatNumber(info.getValue()),
      }),
      columnHelper.display({
        id: 'quantiles',
        header: 'P10 / P50 / P90',
        cell: (info) => {
          const risk = info.row.original;
          if (risk.p10_demand == null || risk.p50_demand == null || risk.p90_demand == null) {
            return <span className="text-content-subtle">—</span>;
          }
          return (
            <span className="font-mono text-xs tabular-nums">
              {formatNumber(risk.p10_demand)} / {formatNumber(risk.p50_demand)} /{' '}
              {formatNumber(risk.p90_demand)}
            </span>
          );
        },
      }),
      columnHelper.accessor('lead_time_days', {
        header: 'Lead (d)',
        cell: (info) => formatNumber(info.getValue()),
      }),
      columnHelper.accessor('reasons', {
        header: 'Why',
        enableSorting: false,
        cell: (info) => {
          const reasons = info.getValue();
          const joined = reasons.join(' ');
          return (
            <Tooltip content={<span className="block max-w-xs">{joined}</span>}>
              <span className="line-clamp-2 max-w-[18rem] cursor-help text-xs leading-snug text-content-subtle">
                {joined}
              </span>
            </Tooltip>
          );
        },
      }),
    ],
    [],
  );

  const table = useReactTable({
    data: risks,
    columns,
    state: { sorting, globalFilter, columnFilters, pagination },
    onSortingChange: setSorting,
    onGlobalFilterChange: setGlobalFilter,
    onColumnFiltersChange: setColumnFilters,
    onPaginationChange: setPagination,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  const numericColumns = new Set([
    'severity',
    'weeks_of_cover',
    'expected_demand_in_lead_time',
    'available_units',
    'lead_time_days',
  ]);

  function setRiskFilter(next: RiskFilter) {
    setColumnFilters(next === 'all' ? [] : [{ id: 'risk_type', value: next }]);
    setPagination((p) => ({ ...p, pageIndex: 0 }));
  }

  if (risks.length === 0) {
    return (
      <EmptyState
        icon={<ShieldCheck />}
        title="No risk flags"
        description="Every monitored SKU × warehouse position is within threshold. Nothing needs attention right now."
      />
    );
  }

  const rows = table.getRowModel().rows;

  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <Tabs
          aria-label="Filter risks by type"
          value={riskFilter}
          onChange={setRiskFilter}
          items={[
            { value: 'all', label: `All (${counts.all})` },
            { value: 'stockout', label: `Stockout (${counts.stockout})` },
            { value: 'overstock', label: `Overstock (${counts.overstock})` },
          ]}
        />
        <SearchInput
          value={globalFilter}
          onChange={(value) => {
            setGlobalFilter(value);
            setPagination((p) => ({ ...p, pageIndex: 0 }));
          }}
          placeholder="Search SKU or warehouse…"
          aria-label="Search risk register"
          className="sm:w-64"
        />
      </div>

      <TableContainer>
        <Table caption="Unified inventory risk register, sortable and filterable">
          <THead>
            <tr>
              {table.getHeaderGroups()[0].headers.map((header) => {
                const canSort = header.column.getCanSort();
                return (
                  <TH
                    key={header.id}
                    align={numericColumns.has(header.column.id) ? 'right' : 'left'}
                    sortDirection={canSort ? header.column.getIsSorted() : undefined}
                    onSort={canSort ? header.column.getToggleSortingHandler() : undefined}
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </TH>
                );
              })}
            </tr>
          </THead>
          <TBody>
            {rows.map((row) => {
              const risk = row.original;
              const rowKey = `${risk.sku_id}:${risk.warehouse_id}:${risk.risk_type}`;
              const expanded = expandedRisk === rowKey;
              return (
                <Fragment key={row.id}>
              <TR
                className={expanded ? 'bg-surface-sunken/60' : undefined}
                aria-expanded={expanded}
              >
                {row.getVisibleCells().map((cell) => (
                  <TD
                    key={cell.id}
                    align={numericColumns.has(cell.column.id) ? 'right' : 'left'}
                    numeric={
                      numericColumns.has(cell.column.id) && cell.column.id !== 'severity'
                    }
                  >
                    {cell.column.id === 'sku_id' ? (
                      <button
                        type="button"
                        className="group inline-flex items-center gap-2 text-left"
                        onClick={() => setExpandedRisk(expanded ? null : rowKey)}
                        aria-label={`${expanded ? 'Hide' : 'Show'} details for ${risk.sku_id}`}
                      >
                        <ChevronDown
                          aria-hidden
                          className={`h-3.5 w-3.5 shrink-0 text-content-subtle transition-transform ${expanded ? 'rotate-180' : ''}`}
                        />
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </button>
                    ) : (
                      flexRender(cell.column.columnDef.cell, cell.getContext())
                    )}
                  </TD>
                ))}
              </TR>
              {expanded ? (
                <TR key={`${row.id}-details`} className="bg-surface-sunken/40">
                  <TD colSpan={row.getVisibleCells().length} className="px-5 py-4">
                    <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_auto]">
                      <div>
                        <p className="text-2xs font-semibold uppercase tracking-wider text-content-subtle">
                          Risk rationale
                        </p>
                        <ul className="mt-2 space-y-1.5">
                          {risk.reasons.map((reason) => (
                            <li
                              key={reason}
                              className="flex gap-2 text-sm leading-relaxed text-content-muted"
                            >
                              <span aria-hidden className="mt-2 h-1 w-1 shrink-0 rounded-full bg-accent" />
                              <span>{reason}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm md:min-w-64">
                        <div>
                          <dt className="text-xs text-content-subtle">Lead-time demand</dt>
                          <dd className="font-mono tabular-nums text-content">
                            {formatNumber(risk.expected_demand_in_lead_time)}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-xs text-content-subtle">Available units</dt>
                          <dd className="font-mono tabular-nums text-content">
                            {formatNumber(risk.available_units)}
                          </dd>
                        </div>
                        <div>
                          <dt className="text-xs text-content-subtle">Lead time</dt>
                          <dd className="font-mono tabular-nums text-content">
                            {formatNumber(risk.lead_time_days)} days
                          </dd>
                        </div>
                        <div>
                          <dt className="text-xs text-content-subtle">Coverage</dt>
                          <dd className="font-mono tabular-nums text-content">
                            {formatNumber(risk.weeks_of_cover, 1)} weeks
                          </dd>
                        </div>
                      </dl>
                    </div>
                  </TD>
                </TR>
              ) : null}
            </Fragment>
              );
            })}
          </TBody>
        </Table>

        {rows.length === 0 ? (
          <p className="px-4 py-10 text-center text-sm text-content-subtle">
            No rows match the current filters.
          </p>
        ) : null}

        <Pagination
          pageIndex={pagination.pageIndex}
          pageCount={table.getPageCount()}
          pageSize={pagination.pageSize}
          totalRows={table.getFilteredRowModel().rows.length}
          onPageChange={(pageIndex) => setPagination((p) => ({ ...p, pageIndex }))}
          onPageSizeChange={(pageSize) => setPagination({ pageIndex: 0, pageSize })}
        />
      </TableContainer>
    </div>
  );
}
