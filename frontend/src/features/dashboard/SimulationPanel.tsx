import { useState } from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { FlaskConical, Play } from 'lucide-react';

import { ChartTooltip } from '../../components/charts/ChartTooltip';
import {
  CHART_COLORS,
  axisTick,
  gridProps,
  lineCursorProps,
} from '../../components/charts/chartTheme';
import { Button } from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { postJson, toErrorMessage } from '../../lib/api';
import { formatCompact, formatNumber } from '../../lib/format';
import { useToast } from '../../providers/toastContext';
import type { SimulateResponse, SkuMeta } from '../../types';

interface SimulationPanelProps {
  skus: SkuMeta[];
  defaultSku: string;
}

export function SimulationPanel({ skus, defaultSku }: SimulationPanelProps) {
  const toast = useToast();

  const [skuId, setSkuId] = useState(defaultSku);
  const [warehouseId, setWarehouseId] = useState('W1');
  const [extraOnOrder, setExtraOnOrder] = useState(0);
  const [leadTimeDelta, setLeadTimeDelta] = useState(0);

  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [running, setRunning] = useState(false);

  async function runSimulation() {
    setRunning(true);
    try {
      // Request body is unchanged from the original implementation.
      const response = await postJson<SimulateResponse>('/api/simulate', {
        sku_id: skuId,
        warehouse_id: warehouseId,
        extra_on_order: extraOnOrder,
        lead_time_delta_days: leadTimeDelta,
      });
      setResult(response);
      toast.success(
        'Simulation complete',
        `${response.sku_id} @ ${response.warehouse_id} — ${formatNumber(
          response.final_projected_stock,
        )} units projected at day 14.`,
      );
    } catch (err) {
      setResult(null);
      // Replaces the previous blocking window.alert().
      toast.error('Simulation failed', toErrorMessage(err, 'Could not run the simulation.'));
    } finally {
      setRunning(false);
    }
  }

  return (
    <Card className="flex h-full flex-col">
      <CardHeader
        title="What-if simulation"
        description="Projects inventory drawdown over 14 days against the model run-rate"
        icon={<FlaskConical className="h-3.5 w-3.5" />}
      />
      <CardBody className="flex min-h-0 flex-1 flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <Field label="SKU">
            <Select
              value={skuId}
              onChange={(e) => setSkuId(e.target.value)}
              options={skus.map((s) => ({ value: s.sku_id, label: s.sku_id }))}
            />
          </Field>
          <Field label="Warehouse">
            <Input
              value={warehouseId}
              onChange={(e) => setWarehouseId(e.target.value)}
              placeholder="W1"
            />
          </Field>
          <Field label="Extra on order" hint="Additional units on an inbound PO">
            <Input
              type="number"
              value={extraOnOrder}
              onChange={(e) => setExtraOnOrder(Number(e.target.value))}
              step={50}
            />
          </Field>
          <Field label="Lead time delta" hint="Days added or removed">
            <Input
              type="number"
              value={leadTimeDelta}
              onChange={(e) => setLeadTimeDelta(Number(e.target.value))}
              step={1}
            />
          </Field>
        </div>

        <Button
          variant="primary"
          fullWidth
          loading={running}
          onClick={() => void runSimulation()}
          leadingIcon={<Play className="h-4 w-4" />}
        >
          {running ? 'Running simulation…' : 'Run simulation'}
        </Button>

        {result ? (
          <div className="min-h-0 flex-1 space-y-3 border-t border-border pt-4">
            <div className="h-40">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={result.points} margin={{ top: 4, right: 4, bottom: 0, left: -12 }}>
                  <defs>
                    <linearGradient id="simGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={CHART_COLORS.series3} stopOpacity={0.32} />
                      <stop offset="100%" stopColor={CHART_COLORS.series3} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...gridProps} />
                  <XAxis
                    dataKey="day"
                    tick={axisTick}
                    tickLine={false}
                    axisLine={{ stroke: CHART_COLORS.grid }}
                    tickFormatter={(d) => `D${d}`}
                  />
                  <YAxis
                    tick={axisTick}
                    tickLine={false}
                    axisLine={false}
                    width={48}
                    tickFormatter={formatCompact}
                  />
                  <Tooltip
                    cursor={lineCursorProps}
                    content={
                      <ChartTooltip
                        labelFormatter={(label) => `Day ${label}`}
                        valueFormatter={(value) => `${formatNumber(value)} units`}
                      />
                    }
                  />
                  <Area
                    type="monotone"
                    dataKey="projected_stock"
                    name="Projected stock"
                    stroke={CHART_COLORS.series3}
                    strokeWidth={2}
                    fill="url(#simGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            <ul className="space-y-1.5">
              {result.assumptions.map((assumption) => (
                <li
                  key={assumption}
                  className="flex gap-2 text-xs leading-relaxed text-content-subtle"
                >
                  <span aria-hidden className="mt-1 h-1 w-1 shrink-0 rounded-full bg-content-subtle" />
                  <span className="min-w-0">{assumption}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="flex-1 border-t border-border pt-4 text-xs leading-relaxed text-content-subtle">
            Adjust the inputs and run the simulation to compare an expedite against an extra
            purchase order.
          </p>
        )}
      </CardBody>
    </Card>
  );
}
