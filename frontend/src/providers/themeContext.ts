import { createContext, useContext } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

/** Must match the key read by the pre-paint script in index.html. */
export const THEME_STORAGE_KEY = 'control-tower-theme';

export interface ThemeContextValue {
  /** What the user picked — may be 'system'. */
  preference: ThemePreference;
  /** What is actually rendered right now. */
  resolved: ResolvedTheme;
  setPreference: (preference: ThemePreference) => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within <ThemeProvider>');
  return ctx;
}
