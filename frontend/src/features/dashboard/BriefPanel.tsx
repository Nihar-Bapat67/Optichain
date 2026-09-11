import { FileText } from 'lucide-react';

import { Badge } from '../../components/ui/Badge';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { formatRelativeTime } from '../../lib/format';
import type { Brief } from '../../types';

export function BriefPanel({ brief }: { brief: Brief | null }) {
  if (!brief) return null;

  return (
    <Card className="flex h-full flex-col">
      <CardHeader
        title={brief.title}
        description="Auto-generated from the current inventory and signal snapshot"
        icon={<FileText className="h-3.5 w-3.5" />}
      />
      <CardBody className="flex min-h-0 flex-1 flex-col gap-4">
        <div className="flex flex-wrap gap-1.5">
          <Badge tone="danger" dot>
            {brief.stockout_count} stockout
          </Badge>
          <Badge tone="warn" dot>
            {brief.overstock_count} overstock
          </Badge>
          <Badge tone="brand" dot>
            {brief.signal_spikes} spikes
          </Badge>
        </div>

        <p className="text-sm leading-relaxed text-content-muted">{brief.summary}</p>

        <ul className="scrollbar-slim min-h-0 flex-1 space-y-2.5 overflow-y-auto pr-1">
          {brief.bullets.map((bullet) => (
            <li key={bullet} className="flex gap-2.5 text-sm leading-relaxed text-content-muted">
              <span
                aria-hidden
                className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-content-subtle"
              />
              <span className="min-w-0">{bullet}</span>
            </li>
          ))}
        </ul>

        <p className="border-t border-border pt-3 text-2xs text-content-subtle">
          Generated{' '}
          <time dateTime={brief.generated_at}>{formatRelativeTime(brief.generated_at)}</time>
        </p>
      </CardBody>
    </Card>
  );
}
