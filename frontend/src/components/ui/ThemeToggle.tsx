import { Monitor, Moon, Sun } from 'lucide-react';
import { cn } from '../../lib/cn';
import { useTheme, type ThemePreference } from '../../providers/themeContext';

const OPTIONS: { value: ThemePreference; label: string; Icon: typeof Sun }[] = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'System', Icon: Monitor },
];

/**
 * Segmented control rather than a two-way switch, so "follow the OS" stays a
 * first-class choice instead of being inferred.
 */
export function ThemeToggle({ className }: { className?: string }) {
  const { preference, setPreference } = useTheme();

  return (
    <div
      role="radiogroup"
      aria-label="Colour theme"
      className={cn(
        'inline-flex items-center gap-0.5 rounded-md border border-border bg-surface-sunken p-0.5',
        className,
      )}
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = preference === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={active}
            aria-label={`${label} theme`}
            title={`${label} theme`}
            onClick={() => setPreference(value)}
            className={cn(
              'flex h-7 w-7 items-center justify-center rounded transition-colors duration-150',
              active
                ? 'bg-surface-raised text-content shadow-xs'
                : 'text-content-subtle hover:text-content',
            )}
          >
            <Icon aria-hidden className="h-3.5 w-3.5" />
          </button>
        );
      })}
    </div>
  );
}
