import { useCallback, useEffect, useRef, useState } from 'react';

export interface AsyncState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  /** True only for the very first load — lets the UI show skeletons once, then keep stale data. */
  initialLoading: boolean;
  refresh: () => void;
}

/**
 * Runs an async loader and tracks its state, aborting the in-flight request when
 * dependencies change or the component unmounts. That prevents both the
 * "setState on unmounted component" warning and out-of-order responses
 * overwriting newer data.
 */
export function useAsyncData<T>(
  loader: (signal: AbortSignal) => Promise<T>,
  deps: readonly unknown[],
  options: { enabled?: boolean } = {},
): AsyncState<T> {
  const { enabled = true } = options;

  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [nonce, setNonce] = useState(0);

  // Keep the latest loader in a ref so callers can pass an inline closure
  // without it re-triggering the effect on every render.
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    let active = true;

    setLoading(true);
    setError(null);

    loaderRef
      .current(controller.signal)
      .then((result) => {
        if (!active) return;
        setData(result);
        setError(null);
      })
      .catch((err: unknown) => {
        if (!active || controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : 'Request failed');
      })
      .finally(() => {
        if (!active) return;
        setLoading(false);
        setHasLoaded(true);
      });

    return () => {
      active = false;
      controller.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled, nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return { data, error, loading, initialLoading: loading && !hasLoaded, refresh };
}
