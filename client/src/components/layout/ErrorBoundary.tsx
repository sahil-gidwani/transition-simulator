import { Component, type ErrorInfo, type ReactNode } from 'react';
import { secondaryAction } from '../ui/actions';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled render error', error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-64 flex-col items-center justify-center gap-4 py-16 text-center">
          <h2 className="text-xl font-semibold text-ink-100">
            Something broke — the verdict is unavailable.
          </h2>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className={secondaryAction}
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
