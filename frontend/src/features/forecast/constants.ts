/** Hour offsets that the MODEL2 lift curve is predicted for. */
export const LIFT_HOURS = ['6h', '12h', '24h', '48h', '72h', '96h'] as const;

export const PLATFORMS = [
  'instagram',
  'tiktok',
  'youtube',
  'twitter',
  'facebook',
  'pinterest',
  'snapchat',
  'linkedin',
] as const;

export const CITIES = [
  'Mumbai',
  'Delhi',
  'Bangalore',
  'Hyderabad',
  'Chennai',
  'Pune',
  'Kolkata',
  'Ahmedabad',
  'Jaipur',
  'Surat',
  'New York',
  'Los Angeles',
  'London',
  'Dubai',
  'Singapore',
  'Tokyo',
  'Paris',
  'Sydney',
  'Toronto',
] as const;

export function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
