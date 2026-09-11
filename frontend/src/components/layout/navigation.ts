import { LayoutDashboard, Zap, type LucideIcon } from 'lucide-react';

export type PageKey = 'dashboard' | 'forecast';

export interface NavItem {
  key: PageKey;
  label: string;
  description: string;
  icon: LucideIcon;
}

/** Single source of truth for navigation — sidebar, mobile drawer and topbar all read this. */
export const NAV_ITEMS: NavItem[] = [
  {
    key: 'dashboard',
    label: 'Control Tower',
    description: 'Inventory risk, demand signals and the weekly brief',
    icon: LayoutDashboard,
  },
  {
    key: 'forecast',
    label: 'Demand Forecast',
    description: 'Three-model agent: baseline, influencer uplift, city growth',
    icon: Zap,
  },
];

export function navItemFor(key: PageKey): NavItem {
  return NAV_ITEMS.find((item) => item.key === key) ?? NAV_ITEMS[0];
}
