import { Activity } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Badge } from '../ui/Badge';
import { NAV_ITEMS, type PageKey } from './navigation';

export interface SidebarProps {
  activePage: PageKey;
  onNavigate: (page: PageKey) => void;
  /** Health pill shown in the sidebar footer; omitted while health is unknown. */
  apiOk?: boolean;
  className?: string;
}

export function BrandMark() {
  return (
    <div className="flex items-center gap-2.5">
      <span
        aria-hidden
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-brand text-white shadow-sm"
      >
        <Activity className="h-4 w-4" strokeWidth={2.5} />
      </span>
      <div className="min-w-0 leading-tight">
        <p className="truncate font-display text-sm font-semibold text-content">Control Tower</p>
        <p className="truncate text-2xs text-content-subtle">Supply chain intelligence</p>
      </div>
    </div>
  );
}

export function SidebarNav({ activePage, onNavigate, apiOk, className }: SidebarProps) {
  return (
    <div className={cn('flex h-full flex-col', className)}>
      <div className="flex h-topbar shrink-0 items-center border-b border-border px-4">
        <BrandMark />
      </div>

      <nav aria-label="Primary" className="flex-1 space-y-0.5 overflow-y-auto p-3">
        {NAV_ITEMS.map(({ key, label, description, icon: Icon }) => {
          const active = key === activePage;
          return (
            <button
              key={key}
              type="button"
              onClick={() => onNavigate(key)}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'group flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left',
                'transition-colors duration-150',
                active
                  ? 'bg-accent-soft text-accent'
                  : 'text-content-muted hover:bg-surface-sunken hover:text-content',
              )}
            >
              <Icon
                aria-hidden
                className={cn(
                  'mt-0.5 h-4 w-4 shrink-0',
                  active ? 'text-accent' : 'text-content-subtle group-hover:text-content-muted',
                )}
              />
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{label}</span>
                <span
                  className={cn(
                    'mt-0.5 block text-2xs leading-snug',
                    active ? 'text-accent/70' : 'text-content-subtle',
                  )}
                >
                  {description}
                </span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="shrink-0 border-t border-border p-3">
        {apiOk === undefined ? (
          <Badge tone="neutral" dot className="w-full justify-center py-1.5">
            Checking API…
          </Badge>
        ) : (
          <Badge
            tone={apiOk ? 'ok' : 'warn'}
            dot
            className="w-full justify-center py-1.5"
          >
            API {apiOk ? 'healthy' : 'degraded'}
          </Badge>
        )}
      </div>
    </div>
  );
}
