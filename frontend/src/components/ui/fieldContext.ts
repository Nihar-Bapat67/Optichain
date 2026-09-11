import { createContext, useContext } from 'react';

export interface FieldContextValue {
  controlId: string;
  descriptionId?: string;
  errorId?: string;
  invalid: boolean;
}

export const FieldContext = createContext<FieldContextValue | null>(null);

/**
 * Returns the id and aria wiring for a control rendered inside <Field>.
 * Returns null when used standalone, so controls stay usable outside a Field.
 *
 * Lives apart from Field.tsx so that file only exports components — a
 * requirement for React Fast Refresh to work reliably.
 */
export function useFieldControl() {
  const ctx = useContext(FieldContext);
  if (!ctx) return null;

  const describedBy = [ctx.descriptionId, ctx.errorId].filter(Boolean).join(' ') || undefined;
  return {
    id: ctx.controlId,
    'aria-describedby': describedBy,
    'aria-invalid': ctx.invalid || undefined,
  } as const;
}
