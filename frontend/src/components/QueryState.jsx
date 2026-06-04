import React from 'react';
import { Loader2, AlertCircle, Inbox, RefreshCw } from 'lucide-react';

/**
 * Reusable layout wrapper for handling API query states: Loading, Error, Empty, and Success.
 */
export default function QueryState({
  isLoading,
  error,
  isEmpty,
  emptyMessage = 'No records found',
  emptyTitle = 'Empty Data',
  refetch,
  children,
}) {
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-border-dark bg-bg-surface rounded-lg">
        <Loader2 className="w-8 h-8 text-accent animate-spin mb-3" />
        <p className="text-text-secondary text-sm font-medium">Loading telemetry platform data...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-8 border border-danger/25 bg-danger/5 rounded-lg text-center">
        <AlertCircle className="w-10 h-10 text-danger mb-3" />
        <h4 className="text-text-primary font-semibold mb-1">Backend Connection Error</h4>
        <p className="text-text-secondary text-sm max-w-md mb-4">
          {error.message || 'Unable to communicate with the FastAPI backend service.'}
        </p>
        {refetch && (
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 px-4 py-2 bg-bg-panel border border-border-light text-text-primary text-xs font-semibold rounded hover:bg-border-dark transition-colors cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry Request
          </button>
        )}
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-border-dark bg-bg-surface rounded-lg">
        <Inbox className="w-10 h-10 text-text-muted mb-3" />
        <h4 className="text-text-secondary font-semibold text-sm mb-1">{emptyTitle}</h4>
        <p className="text-text-muted text-xs max-w-sm">{emptyMessage}</p>
      </div>
    );
  }

  return <>{children}</>;
}
