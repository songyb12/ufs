import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  appName?: string
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: string | null
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null, errorInfo: null }

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    this.setState({ errorInfo: info.componentStack ?? null })
    // Log to console for debugging
    console.error(`[ErrorBoundary${this.props.appName ? `:${this.props.appName}` : ''}]`, error, info)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="flex flex-col items-center justify-center h-64 text-center animate-fade-in">
          <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
            <svg className="w-7 h-7 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          </div>
          <h3 className="text-white font-semibold mb-1">
            {this.props.appName ? `${this.props.appName} Error` : 'Something went wrong'}
          </h3>
          <p className="text-ufs-400 text-sm mb-2 max-w-md">
            {this.state.error?.message ?? 'An unexpected error occurred'}
          </p>

          {/* Error details (collapsible) */}
          {this.state.errorInfo && (
            <details className="mb-4 text-left max-w-lg w-full">
              <summary className="text-xs text-ufs-500 cursor-pointer hover:text-ufs-300 transition-colors">
                Error Details
              </summary>
              <pre className="mt-2 p-3 rounded-lg bg-ufs-800 border border-ufs-600/30 text-[10px] text-ufs-400 overflow-auto max-h-32 whitespace-pre-wrap">
                {this.state.error?.stack ?? ''}
                {'\n\nComponent Stack:'}
                {this.state.errorInfo}
              </pre>
            </details>
          )}

          <div className="flex gap-2">
            <button
              onClick={() => this.setState({ hasError: false, error: null, errorInfo: null })}
              className="px-4 py-2 rounded-lg bg-ufs-700 text-sm text-white hover:bg-ufs-600 transition-colors"
            >
              Try Again
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-lg bg-ufs-800 text-sm text-ufs-400 hover:bg-ufs-700 hover:text-white transition-colors border border-ufs-600/30"
            >
              Reload Page
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
