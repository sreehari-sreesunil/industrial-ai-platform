import React, { useState, useEffect } from 'react';
import { apiDiagnostics } from '../api/client.js';
import { Terminal, ShieldAlert, CheckCircle, ChevronDown, ChevronUp, Radio } from 'lucide-react';

export default function DevPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [, setTick] = useState(0);

  useEffect(() => {
    // Force re-render whenever diagnostics update
    apiDiagnostics.onUpdate = () => {
      setTick((t) => t + 1);
    };
    return () => {
      apiDiagnostics.onUpdate = null;
    };
  }, []);

  const failures = apiDiagnostics.queryFailures;
  const activeCount = apiDiagnostics.activeRequests;
  const lastSyncTime = apiDiagnostics.lastSync 
    ? apiDiagnostics.lastSync.toLocaleTimeString() 
    : 'No requests yet';

  return (
    <div className="fixed bottom-4 right-4 z-50 max-w-md w-full sm:w-[400px] border border-border-dark bg-bg-surface rounded-lg shadow-xl font-mono text-xs overflow-hidden">
      {/* Header bar */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-bg-panel hover:bg-border-dark text-text-primary border-b border-border-dark cursor-pointer select-none"
      >
        <div className="flex items-center gap-2 font-semibold">
          <Terminal className="w-4 h-4 text-accent animate-pulse" />
          <span>DEV OBSERVABILITY PANEL</span>
        </div>
        <div className="flex items-center gap-3">
          {activeCount > 0 && (
            <span className="flex items-center gap-1 text-accent animate-pulse font-bold">
              <Radio className="w-3.5 h-3.5" />
              {activeCount}
            </span>
          )}
          {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
        </div>
      </button>

      {/* Main content */}
      {isOpen && (
        <div className="p-4 bg-bg-surface max-h-[300px] overflow-y-auto space-y-3">
          <div className="grid grid-cols-2 gap-2 text-[11px]">
            <div className="p-2 bg-bg-panel border border-border-dark rounded">
              <div className="text-text-muted">Active Queries</div>
              <div className="text-sm font-semibold text-text-primary mt-1">{activeCount}</div>
            </div>
            <div className="p-2 bg-bg-panel border border-border-dark rounded">
              <div className="text-text-muted">Last Sync Time</div>
              <div className="text-sm font-semibold text-text-primary mt-1 truncate">{lastSyncTime}</div>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between text-[11px] text-text-secondary border-b border-border-dark pb-1 mb-2">
              <span className="font-semibold">ENDPOINT FAILURE LOGS</span>
              <span className="text-text-muted">({failures.length} recorded)</span>
            </div>

            {failures.length === 0 ? (
              <div className="flex items-center justify-center gap-2 p-4 text-text-muted text-[11px] bg-bg-panel rounded border border-border-dark">
                <CheckCircle className="w-4 h-4 text-success" />
                <span>All requests succeeding. Zero failures logged.</span>
              </div>
            ) : (
              <div className="space-y-2">
                {failures.map((f, idx) => (
                  <div 
                    key={idx} 
                    className="p-2 bg-danger/5 border border-danger/15 rounded text-[11px] space-y-1"
                  >
                    <div className="flex items-center justify-between text-danger font-semibold">
                      <span className="flex items-center gap-1">
                        <ShieldAlert className="w-3 h-3" />
                        {f.method} {f.url}
                      </span>
                      <span className="text-text-muted">{f.timestamp}</span>
                    </div>
                    <div className="text-text-secondary select-text break-words">
                      {f.error}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
