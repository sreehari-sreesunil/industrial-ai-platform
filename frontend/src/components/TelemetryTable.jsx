import React from 'react';
import { Database, Clock, Terminal } from 'lucide-react';

export default function TelemetryTable({ telemetryHistory = [] }) {
  if (telemetryHistory.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 border border-dashed border-border-dark bg-bg-surface rounded-lg text-center">
        <Database className="w-8 h-8 text-text-muted mb-2" />
        <span className="text-text-secondary text-xs font-semibold">No Raw Telemetry Records</span>
        <span className="text-text-muted text-[11px] mt-0.5">Ingest telemetry data to view raw database logs</span>
      </div>
    );
  }

  // Sort history in reverse chronological order (latest first) for operational utility
  const sortedHistory = [...telemetryHistory].sort(
    (a, b) => new Date(b.timestamp) - new Date(a.timestamp)
  );

  return (
    <div className="bg-bg-surface border border-border-dark rounded-lg overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 bg-bg-panel border-b border-border-dark flex items-center gap-2">
        <Terminal className="w-4 h-4 text-text-secondary" />
        <h4 className="font-semibold text-text-primary text-xs">Raw Database Records</h4>
        <span className="ml-auto text-[10px] bg-border-dark text-text-secondary px-2 py-0.5 rounded-full font-mono">
          {sortedHistory.length} records
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse font-mono text-xs select-text">
          <thead>
            <tr className="bg-bg-surface border-b border-border-dark text-text-muted text-[10px] uppercase">
              <th className="px-4 py-2.5 font-medium">Record ID</th>
              <th className="px-4 py-2.5 font-medium flex items-center gap-1">
                <Clock className="w-3.5 h-3.5" /> Timestamp
              </th>
              <th className="px-4 py-2.5 font-medium">Payload Data</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border-dark">
            {sortedHistory.map((record) => {
              const dateStr = new Date(record.timestamp).toLocaleString();
              return (
                <tr key={record.id} className="hover:bg-bg-panel/50 transition-colors">
                  <td className="px-4 py-3 text-text-muted select-all">
                    #{record.id}
                  </td>
                  <td className="px-4 py-3 text-text-secondary whitespace-nowrap">
                    {dateStr}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(record.payload).map(([key, val]) => (
                        <div
                          key={key}
                          className="flex items-center gap-1.5 px-2 py-0.5 bg-bg-input border border-border-light rounded text-[11px]"
                        >
                          <span className="text-text-secondary">{key}:</span>
                          <span className="text-text-primary font-bold">
                            {typeof val === 'number'
                              ? val.toFixed(3).replace(/\.?0+$/, '')
                              : String(val)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
