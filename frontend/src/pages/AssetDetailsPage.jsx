import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getAssets } from '../api/assets.js';
import { getMetricDefinitions } from '../api/registry.js';
import { getTelemetryHistory, getLatestTelemetry, ingestTelemetry } from '../api/telemetry.js';
import {
  ArrowLeft,
  Cpu,
  MapPin,
  Settings,
  Database,
  Radio,
  FileSpreadsheet,
  Play,
  AlertTriangle,
} from 'lucide-react';
import QueryState from '../components/QueryState.jsx';
import TelemetryChart from '../components/TelemetryChart.jsx';
import TelemetryTable from '../components/TelemetryTable.jsx';
import { toast } from 'react-hot-toast';

export default function AssetDetailsPage() {
  const { id } = useParams();
  const assetIdNum = parseInt(id, 10);
  const queryClient = useQueryClient();

  // Selected metric state for chart visualization
  const [selectedMetric, setSelectedMetric] = useState('');

  // Ingestion form state
  const [ingestPayload, setIngestPayload] = useState({});

  // 1. Fetch Assets list to find our asset
  const assetsQuery = useQuery({ queryKey: ['assets'], queryFn: getAssets });

  // Find asset
  const asset = assetsQuery.data?.find((a) => a.id === assetIdNum);

  // 2. Fetch Metric Definitions filtered by asset type ID
  const metricsQuery = useQuery({
    queryKey: ['metricDefinitions', asset?.assetType?.id],
    queryFn: () => getMetricDefinitions(asset?.assetType?.id),
    enabled: !!asset?.assetType?.id,
  });

  // 3. Fetch Telemetry Data
  const telemetryHistoryQuery = useQuery({
    queryKey: ['telemetryHistory', assetIdNum],
    queryFn: () => getTelemetryHistory(assetIdNum),
    enabled: !isNaN(assetIdNum),
  });

  const latestTelemetryQuery = useQuery({
    queryKey: ['latestTelemetry', assetIdNum],
    queryFn: () => getLatestTelemetry(assetIdNum),
    enabled: !isNaN(assetIdNum),
    refetchInterval: 5000, // Poll latest pulse every 5 seconds
  });

  // Ingest Mutation
  const ingestMutation = useMutation({
    mutationFn: ingestTelemetry,
    onSuccess: () => {
      // Invalidate telemetry queries so UI refreshes automatically
      queryClient.invalidateQueries({ queryKey: ['telemetryHistory', assetIdNum] });
      queryClient.invalidateQueries({ queryKey: ['latestTelemetry', assetIdNum] });
      queryClient.invalidateQueries({ queryKey: ['telemetryStats', assetIdNum] });
      
      toast.success('Telemetry ingested successfully');
      setIngestPayload({}); // Clear form inputs
    },
  });

  // Loading / Error combinations
  const isLoading =
    assetsQuery.isLoading ||
    (asset && metricsQuery.isLoading) ||
    telemetryHistoryQuery.isLoading;

  const isError =
    assetsQuery.isError ||
    (asset && metricsQuery.isError) ||
    telemetryHistoryQuery.isError;

  const error =
    assetsQuery.error ||
    metricsQuery.error ||
    telemetryHistoryQuery.error;

  const refetchAll = () => {
    assetsQuery.refetch();
    if (asset?.assetType?.id) {
      metricsQuery.refetch();
    }
    telemetryHistoryQuery.refetch();
    latestTelemetryQuery.refetch();
  };

  const activeMetrics = metricsQuery.data || [];

  const handleInputChange = (metricName, val, dataType) => {
    setIngestPayload((prev) => ({
      ...prev,
      [metricName]: { val, dataType },
    }));
  };

  const handleIngestSubmit = (e) => {
    e.preventDefault();
    if (activeMetrics.length === 0) return;

    const payload = {};
    let hasValues = false;

    for (const metric of activeMetrics) {
      const field = ingestPayload[metric.name];
      if (field && field.val !== '') {
        hasValues = true;
        let parsedVal = field.val;
        
        // Parse numerical limits & types
        if (metric.dataType === 'integer') {
          parsedVal = parseInt(field.val, 10);
          if (isNaN(parsedVal)) {
            toast.error(`Value for "${metric.name}" must be an integer.`);
            return;
          }
        } else if (metric.dataType === 'float') {
          parsedVal = parseFloat(field.val);
          if (isNaN(parsedVal)) {
            toast.error(`Value for "${metric.name}" must be a floating point number.`);
            return;
          }
        } else if (metric.dataType === 'boolean') {
          parsedVal = field.val === 'true' || field.val === true;
        }

        // Bound validations
        if (metric.minValue !== null && parsedVal < metric.minValue) {
          toast.error(`"${metric.name}" value falls below minimum bound of ${metric.minValue}`);
          return;
        }
        if (metric.maxValue !== null && parsedVal > metric.maxValue) {
          toast.error(`"${metric.name}" value exceeds maximum bound of ${metric.maxValue}`);
          return;
        }

        payload[metric.name] = parsedVal;
      }
    }

    if (!hasValues) {
      toast.error('Please input at least one telemetry value.');
      return;
    }

    // Ingest telemetry data points
    ingestMutation.mutate({
      asset_id: assetIdNum,
      timestamp: new Date().toISOString(),
      payload,
    });
  };

  // If assets have finished loading and asset does not exist
  const isAssetNotFound = !isLoading && assetsQuery.data && !asset;

  return (
    <div className="space-y-6">
      {/* Breadcrumbs / Back button */}
      <div className="flex items-center gap-2 text-xs">
        <Link
          to="/assets"
          className="flex items-center gap-1.5 text-text-secondary hover:text-text-primary transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Assets
        </Link>
      </div>

      {isAssetNotFound ? (
        <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-danger/20 bg-danger/5 rounded-lg">
          <Database className="w-10 h-10 text-danger mb-3" />
          <h4 className="text-text-primary font-semibold mb-1">Asset Node Not Found</h4>
          <p className="text-text-secondary text-sm max-w-sm">
            Asset ID #{assetIdNum} does not exist in the assets database.
          </p>
        </div>
      ) : (
        <QueryState isLoading={isLoading} error={isError ? error : null} refetch={refetchAll}>
          {asset && (
            <div className="space-y-6">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-border-dark pb-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2.5">
                    <div className="p-1.5 bg-accent/10 border border-accent/20 rounded">
                      <Cpu className="w-5 h-5 text-accent" />
                    </div>
                    <h1 className="text-xl font-bold tracking-tight text-text-primary select-all">
                      {asset.name}
                    </h1>
                  </div>
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-text-secondary font-mono">
                    <span className="text-text-muted">Node ID: <span className="text-text-secondary select-all">#{asset.id}</span></span>
                    <span className="text-text-muted">•</span>
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5" /> Facility:{' '}
                      <span className="text-text-primary">{asset.facility?.name || 'Unknown Location'}</span>
                    </span>
                    <span className="text-text-muted">•</span>
                    <span className="flex items-center gap-1">
                      <Settings className="w-3.5 h-3.5" /> Type:{' '}
                      <span className="text-text-primary">{asset.assetType?.name || 'Unknown Type'}</span>
                    </span>
                    {latestTelemetryQuery.data ? (
                      <>
                        <span className="text-text-muted">•</span>
                        <span className="flex items-center gap-1 text-success">
                          <Radio className="w-3.5 h-3.5 animate-pulse" />
                          Last Pulse: <span className="text-text-primary select-all">{new Date(latestTelemetryQuery.data.timestamp).toLocaleString()}</span>
                        </span>
                      </>
                    ) : (
                      <>
                        <span className="text-text-muted">•</span>
                        <span className="flex items-center gap-1 text-text-muted font-semibold">
                          <Radio className="w-3.5 h-3.5 text-text-muted" />
                          Last Pulse: <span className="text-text-muted font-normal">No data received</span>
                        </span>
                      </>
                    )}
                  </div>
                </div>
              </div>

              {/* Observation Console Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Left Column: Stats Panel & Manual Ingestion */}
                <div className="space-y-6">
                  {/* Latest Telemetry Pulse */}
                  <div className="bg-bg-surface border border-border-dark rounded-lg p-5 space-y-4">
                    <h3 className="font-semibold text-xs text-text-primary uppercase tracking-wider border-b border-border-dark pb-3 flex items-center gap-2">
                      <Radio className={`w-4 h-4 ${latestTelemetryQuery.data ? 'text-accent animate-pulse' : 'text-text-muted'}`} />
                      Live Telemetry Snapshot
                    </h3>

                    {latestTelemetryQuery.isLoading ? (
                      <div className="text-center py-4 font-mono text-[11px] text-text-muted">
                        Polling latest snapshot...
                      </div>
                    ) : latestTelemetryQuery.data ? (
                      <div className="space-y-3 font-mono text-xs">
                        <div className="flex justify-between items-center text-[10px] text-text-secondary border-b border-border-dark/50 pb-1.5">
                          <span>Pulse Timestamp:</span>
                          <span className="text-text-primary select-all font-semibold">
                            {new Date(latestTelemetryQuery.data.timestamp).toLocaleTimeString()}
                          </span>
                        </div>
                        <div className="grid grid-cols-1 gap-2">
                          {Object.entries(latestTelemetryQuery.data.payload).map(([key, val]) => {
                            const def = activeMetrics.find((m) => m.name === key) || {};
                            return (
                              <div
                                key={key}
                                className="flex justify-between items-center p-2.5 bg-bg-panel border border-border-dark rounded"
                              >
                                <span className="text-text-secondary">{key}</span>
                                <span className="font-bold text-text-primary select-all">
                                  {typeof val === 'number' ? val.toFixed(2).replace(/\.?0+$/, '') : String(val)}
                                  <span className="text-[10px] text-text-secondary ml-1 font-normal select-none">
                                    {def.unit}
                                  </span>
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ) : (
                      <div className="text-center py-4 font-mono text-[11px] text-text-muted border border-dashed border-border-dark rounded bg-bg-panel/30">
                        No telemetry ingested yet.
                      </div>
                    )}
                  </div>

                  {/* Telemetry Ingestion Form */}
                  <div className="bg-bg-surface border border-border-dark rounded-lg p-5 space-y-4">
                    <h3 className="font-semibold text-xs text-text-primary uppercase tracking-wider border-b border-border-dark pb-3 flex items-center gap-2">
                      <Play className="w-4 h-4 text-success" />
                      Ingest Telemetry Station
                    </h3>

                    {activeMetrics.length === 0 ? (
                      <div className="flex flex-col items-center justify-center p-6 text-center border border-dashed border-warning/25 bg-warning/5 rounded-lg">
                        <AlertTriangle className="w-8 h-8 text-warning mb-2 animate-bounce" />
                        <h4 className="text-text-primary font-semibold text-xs uppercase tracking-wider mb-1">
                          No Metrics Configured
                        </h4>
                        <p className="text-text-secondary text-[10px] max-w-xs leading-relaxed">
                          There are no metrics configured for asset type "{asset.assetType?.name || 'unknown'}". Define metric schemas in the Metadata Registry to enable ingestion.
                        </p>
                      </div>
                    ) : (
                      <form onSubmit={handleIngestSubmit} className="space-y-4">
                        {activeMetrics.map((metric) => {
                          const inputVal = ingestPayload[metric.name]?.val || '';
                          const boundsText = [];
                          if (metric.minValue !== null) boundsText.push(`min: ${metric.minValue}`);
                          if (metric.maxValue !== null) boundsText.push(`max: ${metric.maxValue}`);
                          const placeholder = boundsText.length > 0 ? boundsText.join(', ') : 'Enter value';

                          return (
                            <div key={metric.id} className="space-y-1">
                              <label className="flex justify-between items-center font-mono text-xs text-text-secondary">
                                <span>
                                  {metric.name}{' '}
                                  {metric.unit ? (
                                    <span className="text-[10px] text-text-muted">({metric.unit})</span>
                                  ) : (
                                    ''
                                  )}
                                </span>
                                <span className="text-[10px] text-text-muted tracking-wide uppercase">
                                  {metric.dataType}
                                </span>
                              </label>
                              {metric.dataType === 'boolean' ? (
                                <select
                                  value={inputVal}
                                  onChange={(e) => handleInputChange(metric.name, e.target.value, 'boolean')}
                                  className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono cursor-pointer"
                                >
                                  <option value="">-- Select State --</option>
                                  <option value="true">True / Active</option>
                                  <option value="false">False / Inactive</option>
                                </select>
                              ) : (
                                <input
                                  type="number"
                                  step={metric.dataType === 'float' ? 'any' : '1'}
                                  placeholder={placeholder}
                                  value={inputVal}
                                  onChange={(e) => handleInputChange(metric.name, e.target.value, metric.dataType)}
                                  className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono"
                                />
                              )}
                            </div>
                          );
                        })}

                        <button
                          type="submit"
                          disabled={ingestMutation.isPending}
                          className="w-full py-2 bg-success text-white text-xs font-semibold rounded hover:bg-success/90 transition-colors disabled:opacity-50 cursor-pointer font-mono uppercase tracking-wider"
                        >
                          {ingestMutation.isPending ? 'Ingesting...' : 'Submit Ingestion Pulse'}
                        </button>
                      </form>
                    )}
                  </div>
                </div>

                {/* Right Column: Visualization & Raw Database Records */}
                <div className="lg:col-span-2 space-y-6">
                  {telemetryHistoryQuery.data && telemetryHistoryQuery.data.length > 0 ? (
                    <>
                      {/* Historical Plot */}
                      <TelemetryChart
                        assetId={assetIdNum}
                        metricDefinitions={activeMetrics}
                        telemetryHistory={telemetryHistoryQuery.data}
                        selectedMetric={selectedMetric}
                        setSelectedMetric={setSelectedMetric}
                      />

                      {/* Raw Data Records Table */}
                      <TelemetryTable telemetryHistory={telemetryHistoryQuery.data} />
                    </>
                  ) : (
                    <div className="flex flex-col items-center justify-center p-12 text-center border border-dashed border-border-dark bg-bg-surface rounded-lg h-[400px]">
                      <FileSpreadsheet className="w-12 h-12 text-text-muted mb-4" />
                      <h3 className="text-text-primary font-semibold text-sm mb-1">No Telemetry Ingested Yet</h3>
                      <p className="text-text-secondary text-xs max-w-sm mb-6 leading-relaxed">
                        This asset node is active but has not received any time-series data yet. Ingest telemetry to begin observability.
                      </p>
                      <div className="flex flex-col sm:flex-row gap-3">
                        <span className="text-[10px] text-text-muted font-mono uppercase bg-bg-panel border border-border-dark px-3 py-2 rounded">
                          Option 1: Upload CSV via Sidebar
                        </span>
                        <span className="text-[10px] text-text-muted font-mono uppercase bg-bg-panel border border-border-dark px-3 py-2 rounded">
                          Option 2: Submit Ingestion Pulse on Left
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </QueryState>
      )}
    </div>
  );
}
