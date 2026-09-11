import { Megaphone, Package, Sparkles } from 'lucide-react';

import { Button } from '../../components/ui/Button';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import { Field } from '../../components/ui/Field';
import { Input } from '../../components/ui/Input';
import { Select } from '../../components/ui/Select';
import { Switch } from '../../components/ui/Switch';
import { CITIES, PLATFORMS, titleCase } from './constants';

export interface ForecastFormState {
  productId: string;
  city: string;
  date: string;
  campaignActive: boolean;
  influencerId: string;
  followers: number;
  engagementRate: number;
  platform: string;
}

export interface ForecastFormProps {
  state: ForecastFormState;
  onChange: <K extends keyof ForecastFormState>(key: K, value: ForecastFormState[K]) => void;
  onSubmit: () => void;
  loading: boolean;
}

export function ForecastForm({ state, onChange, onSubmit, loading }: ForecastFormProps) {
  return (
    <form
      className="space-y-5"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <Card>
        <CardHeader
          title="Product & location"
          description="Inputs for the MODEL1 baseline and MODEL3 city trend"
          icon={<Package className="h-3.5 w-3.5" />}
        />
        <CardBody className="space-y-4">
          <Field label="Product ID" hint="SKU identifier, e.g. SKU-WS-001">
            <Input
              value={state.productId}
              onChange={(e) => onChange('productId', e.target.value)}
              placeholder="SKU-WS-001"
              autoComplete="off"
            />
          </Field>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Field label="City">
              <Select
                value={state.city}
                onChange={(e) => onChange('city', e.target.value)}
                options={CITIES.map((c) => ({ value: c, label: c }))}
              />
            </Field>
            <Field label="Date">
              <Input
                type="date"
                value={state.date}
                onChange={(e) => onChange('date', e.target.value)}
              />
            </Field>
          </div>
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Influencer campaign"
          description="Drives the MODEL2 uplift bundle"
          icon={<Megaphone className="h-3.5 w-3.5" />}
          actions={
            <Switch
              checked={state.campaignActive}
              onCheckedChange={(checked) => onChange('campaignActive', checked)}
              label="Campaign active"
              hideLabel
            />
          }
        />
        <CardBody>
          {state.campaignActive ? (
            <div className="animate-fade-in space-y-4">
              <Field label="Influencer ID">
                <Input
                  value={state.influencerId}
                  onChange={(e) => onChange('influencerId', e.target.value)}
                  placeholder="INF-42"
                  autoComplete="off"
                />
              </Field>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="Followers">
                  <Input
                    type="number"
                    value={state.followers}
                    onChange={(e) => onChange('followers', Number(e.target.value))}
                    // step must divide (value - min) or the browser blocks
                    // submission: with min=1000, a step of 10000 makes common
                    // round figures such as 250000 invalid.
                    step={1000}
                    min={1000}
                    inputMode="numeric"
                  />
                </Field>
                <Field label="Engagement rate" hint="Fraction, e.g. 0.048 = 4.8%">
                  <Input
                    type="number"
                    value={state.engagementRate}
                    onChange={(e) => onChange('engagementRate', Number(e.target.value))}
                    // "any" avoids float step-mismatch on values like 0.048.
                    step="any"
                    min={0}
                    max={1}
                    placeholder="0.048"
                  />
                </Field>
              </div>

              <Field label="Platform">
                <Select
                  value={state.platform}
                  onChange={(e) => onChange('platform', e.target.value)}
                  options={PLATFORMS.map((p) => ({ value: p, label: titleCase(p) }))}
                />
              </Field>
            </div>
          ) : (
            <p className="text-sm leading-relaxed text-content-subtle">
              Enable the campaign to add influencer uplift from MODEL2. With it off, the forecast
              is baseline demand plus city growth only.
            </p>
          )}
        </CardBody>
      </Card>

      <Button
        type="submit"
        variant="primary"
        size="lg"
        fullWidth
        loading={loading}
        leadingIcon={<Sparkles className="h-4 w-4" />}
      >
        {loading ? 'Running three-model pipeline…' : 'Generate forecast'}
      </Button>
    </form>
  );
}
