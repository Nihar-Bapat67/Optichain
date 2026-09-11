import { Component, type ErrorInfo, type ReactNode } from 'react';
import { RefreshCw } from 'lucide-react';
import { Button } from './ui/Button';

interface Props {
  children: ReactNode;
  /** Optional label so the message can name the area that failed. */
  section?: string;
}

interface State {
  error: Error | null;
}

/**
 * Stops a render-time throw from blanking the entire app. Without this, one bad
 * value in a chart takes down the whole dashboard.
 */
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[ErrorBoundary] Render failure', error, info.componentStack);
  }

  private reset = () => this.setState({ error: null });

  override render() {
    const { error } = this.state;
    const { children, section } = this.props;

    if (!error) return children;

    return (
      <div
        role="alert"
        className="flex flex-col items-center justify-center rounded-xl border border-danger-border bg-danger-soft/40 px-6 py-12 text-center"
      >
        <h2 className="font-display text-lg font-semibold text-content">
          {section ? `${section} failed to render` : 'Something went wrong'}
        </h2>
        <p className="mt-1.5 max-w-md text-balance text-sm text-content-muted">
          An unexpected error occurred while displaying this content. Your data is unaffected.
        </p>

        {import.meta.env.DEV ? (
          <pre className="scrollbar-slim mt-4 max-w-xl overflow-x-auto rounded-md border border-border bg-surface px-3 py-2 text-left text-xs text-danger">
            {error.message}
          </pre>
        ) : null}

        <Button
          variant="secondary"
          className="mt-5"
          onClick={this.reset}
          leadingIcon={<RefreshCw className="h-4 w-4" />}
        >
          Try again
        </Button>
      </div>
    );
  }
}
