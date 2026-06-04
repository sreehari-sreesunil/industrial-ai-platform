import React, { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getTelemetryStats } from '../api/telemetry.js';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import { LineChart, BarChart2, Hash, ArrowUpRight, ArrowDownRight, Activity } from 'lucide-react';
import QueryState from './QueryState.jsx';

export default function TelemetryChart({
  assetId,
  metricDefinitions = [],
  telemetryHistory = [],
  selectedMetric,
  setSelectedMetric,
}) {
  // Select first metric if none is selected
  useEffect(() => {
    if (metricDefinitions.length > 0 && !selectedMetric) {
      setSelectedMetric(metricDefinitions[0].name);
    }
  }, [metricDefinitions, selectedMetric, setSelectedMetric]);

  // Fetch stats for the selected metric
  const { data: stats, isLoading: statsLoading, error: statsError, refetch: refetchStats } = useQuery({
    queryKey: ['telemetryStats', assetId, selectedMetric],
    queryFn: () => getTelemetryStats(assetId, selectedMetric),
    enabled: !!assetId && !!selectedMetric && telemetryHistory.length > 0,
    staleTime: 5000, // short stale time for stats
  });

  if (metricDefinitions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center border border-border-dark bg-bg-surface rounded-lg">
        <Activity className="w-10 h-10 text-text-muted mb-3" />
        <h4 className="text-text-secondary font-semibold text-sm mb-1">No Metrics Defined</h4>
        <p className="text-text-muted text-xs max-w-sm">
          This asset type does not have any metric definitions. Go to the Metadata Registry to configure telemetry schemas.
        </p>
      </div>
    );
  }

  // Format telemetry history for Recharts
  const chartData = telemetryHistory
    .map((item) => {
      const val = item.payload[selectedMetric];
      return {
        timestamp: item.timestamp,
        time: new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
        value: typeof val === 'number' ? val : parseFloat(val),
      };
    })
    .filter((item) => !isNaN(item.value))
    .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

  const activeMetricDef = metricDefinitions.find((m) => m.name === selectedMetric) || {};
  const unitSuffix = activeMetricDef.unit ? ` (${activeMetricDef.unit})` : '';

  return (
    <div className="space-y-4">
      {/* Selector & Title Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-bg-panel p-4 rounded-lg border border-border-dark">
        <div>
          <h3 className="font-semibold text-text-primary text-sm flex items-center gap-2">
            <LineChart className="w-4 h-4 text-accent" />
            Telemetry Visualization
          </h3>
          <p className="text-text-muted text-xs mt-0.5">
            Displaying live telemetry stream values and computed bounds
          </p>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto">
          <label htmlFor="metric-select" className="text-xs text-text-secondary font-medium">Metric:</label>
          <select
            id="metric-select"
            value={selectedMetric || ''}
            onChange={(e) => setSelectedMetric(e.target.value)}
            className="flex-1 sm:flex-initial bg-bg-input text-text-primary border border-border-light rounded px-3 py-1.5 text-xs focus:outline-none focus:border-accent font-mono cursor-pointer"
          >
            {metricDefinitions.map((m) => (
              <option key={m.id} value={m.name}>
                {m.name} {m.unit ? `(${m.unit})` : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats Cards */}
      {selectedMetric && telemetryHistory.length > 0 && (
        <QueryState isLoading={statsLoading} error={statsError} refetch={refetchStats}>
          {stats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-bg-surface border border-border-dark p-3.5 rounded-lg">
                <div className="text-text-muted text-xs font-medium flex items-center gap-1.5">
                  <BarChart2 className="w-3.5 h-3.5" />
                  Average
                </div>
                <div className="text-lg font-mono font-semibold text-text-primary mt-1">
                  {stats.avg !== null ? stats.avg.toFixed(2) : '--'}
                  <span className="text-xs text-text-secondary ml-1">{activeMetricDef.unit}</span>
                </div>
              </div>

              <div className="bg-bg-surface border border-border-dark p-3.5 rounded-lg">
                <div className="text-text-muted text-xs font-medium flex items-center gap-1.5">
                  <ArrowDownRight className="w-3.5 h-3.5 text-success" />
                  Minimum
                </div>
                <div className="text-lg font-mono font-semibold text-success mt-1">
                  {stats.min !== null ? stats.min.toFixed(2) : '--'}
                  <span className="text-xs text-text-secondary ml-1">{activeMetricDef.unit}</span>
                </div>
              </div>

              <div className="bg-bg-surface border border-border-dark p-3.5 rounded-lg">
                <div className="text-text-muted text-xs font-medium flex items-center gap-1.5">
                  <ArrowUpRight className="w-3.5 h-3.5 text-danger" />
                  Maximum
                </div>
                <div className="text-lg font-mono font-semibold text-danger mt-1">
                  {stats.max !== null ? stats.max.toFixed(2) : '--'}
                  <span className="text-xs text-text-secondary ml-1">{activeMetricDef.unit}</span>
                </div>
              </div>

              <div className="bg-bg-surface border border-border-dark p-3.5 rounded-lg">
                <div className="text-text-muted text-xs font-medium flex items-center gap-1.5">
                  <Hash className="w-3.5 h-3.5 text-accent" />
                  Datapoints
                </div>
                <div className="text-lg font-mono font-semibold text-text-primary mt-1">
                  {stats.count || 0}
                </div>
              </div>
            </div>
          )}
        </QueryState>
      )}

      {/* Chart Plot Area */}
      <div className="bg-bg-surface border border-border-dark rounded-lg p-4 h-[300px] flex items-center justify-center">
        {chartData.length === 0 ? (
          <div className="text-center text-text-muted text-xs">
            No telemetry points match the selected metric: {selectedMetric}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorMetric" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563eb" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#2563eb" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis
                dataKey="time"
                stroke="#475569"
                fontSize={10}
                fontFamily="var(--font-mono)"
                tickLine={false}
              />
              <YAxis
                stroke="#475569"
                fontSize={10}
                fontFamily="var(--font-mono)"
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e2330',
                  borderColor: '#334155',
                  color: '#f8fafc',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '11px',
                  borderRadius: '4px',
                }}
                labelClassName="text-text-secondary"
              />
              <Area
                type="monotone"
                dataKey="value"
                name={selectedMetric || 'value'}
                stroke="#3b82f6"
                strokeWidth={1.5}
                fillOpacity={1}
                fill="url(#colorMetric)"
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
