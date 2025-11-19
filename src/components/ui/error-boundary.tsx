import React from "react";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error | null;
}

class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // log to console for now; could integrate Sentry/Telemetry
    console.error("ErrorBoundary caught an error:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-4 bg-red-50 border border-red-200 rounded">
          <div className="text-sm font-semibold text-red-700">Erro ao renderizar o componente</div>
          <div className="text-xs text-red-600 mt-1">Verifique o console para mais detalhes.</div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default ErrorBoundary;
