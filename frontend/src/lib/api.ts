const base = import.meta.env.VITE_API_URL ?? '';

/** Requests are aborted after this long so a hung backend can't spin forever. */
const DEFAULT_TIMEOUT_MS = 30_000;

export class ApiError extends Error {
  readonly status: number;
  readonly path: string;
  /** Raw response body, useful for surfacing FastAPI's `detail` text. */
  readonly body: string;

  constructor(message: string, status: number, path: string, body: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.path = path;
    this.body = body;
  }

  /** True when the API is unreachable rather than returning an error status. */
  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

/**
 * FastAPI reports errors as `{"detail": "..."}` (or a validation array).
 * Pull out something human-readable without assuming either shape.
 */
function extractDetail(body: string, fallback: string): string {
  if (!body) return fallback;
  try {
    const parsed: unknown = JSON.parse(body);
    if (parsed && typeof parsed === 'object' && 'detail' in parsed) {
      const detail = (parsed as { detail: unknown }).detail;
      if (typeof detail === 'string') return detail;
      if (Array.isArray(detail)) {
        const messages = detail
          .map((d) =>
            d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : null,
          )
          .filter(Boolean);
        if (messages.length) return messages.join('; ');
      }
    }
  } catch {
    // Not JSON — fall through and use the raw text.
  }
  return body.slice(0, 300) || fallback;
}

async function request<T>(path: string, init: RequestInit, signal?: AbortSignal): Promise<T> {
  const timeoutController = new AbortController();
  const timer = setTimeout(() => timeoutController.abort(), DEFAULT_TIMEOUT_MS);

  // Combine the caller's signal (component unmount) with our timeout.
  const onCallerAbort = () => timeoutController.abort();
  signal?.addEventListener('abort', onCallerAbort);

  try {
    const res = await fetch(`${base}${path}`, { ...init, signal: timeoutController.signal });

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new ApiError(
        extractDetail(body, res.statusText || `Request failed (${res.status})`),
        res.status,
        path,
        body,
      );
    }

    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;

    // Caller-initiated aborts should propagate untouched so callers can ignore them.
    if (err instanceof DOMException && err.name === 'AbortError' && signal?.aborted) throw err;

    const message =
      err instanceof DOMException && err.name === 'AbortError'
        ? 'Request timed out'
        : 'Cannot reach the API';
    throw new ApiError(message, 0, path, '');
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener('abort', onCallerAbort);
  }
}

export function fetchJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: 'GET' }, signal);
}

export function postJson<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  return request<T>(
    path,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
    signal,
  );
}

/** Human-readable message for any thrown value, for toasts and inline errors. */
export function toErrorMessage(err: unknown, fallback = 'Something went wrong'): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return fallback;
}
