import { useEffect, useState } from 'react';
import { Search, X } from 'lucide-react';
import { cn } from '../../lib/cn';
import { Input } from './Input';

export interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  'aria-label': string;
  /** Debounce in ms — keeps typing responsive when filtering large tables. */
  debounceMs?: number;
  className?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
  'aria-label': ariaLabel,
  debounceMs = 200,
  className,
}: SearchInputProps) {
  const [draft, setDraft] = useState(value);

  // Keep the visible text in sync when the value is reset from outside.
  useEffect(() => {
    setDraft(value);
  }, [value]);

  useEffect(() => {
    if (draft === value) return;
    const timer = setTimeout(() => onChange(draft), debounceMs);
    return () => clearTimeout(timer);
  }, [draft, value, onChange, debounceMs]);

  return (
    <Input
      type="search"
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      placeholder={placeholder}
      aria-label={ariaLabel}
      className={cn('h-8 text-xs', className)}
      leadingIcon={<Search />}
      trailingSlot={
        draft ? (
          <button
            type="button"
            onClick={() => setDraft('')}
            aria-label="Clear search"
            className="rounded p-1 transition-colors hover:bg-surface-sunken hover:text-content"
          >
            <X aria-hidden className="h-3 w-3" />
          </button>
        ) : null
      }
    />
  );
}
