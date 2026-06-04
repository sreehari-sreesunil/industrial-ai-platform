import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getDashboardOverview } from '../api/system.js';
import { Box, Settings, Map as MapIcon, FileSpreadsheet, Plus, ArrowRight, Activity, Calendar } from 'lucide-react';
import QueryState from '../components/QueryState.jsx';

export default function HomePage() {
  const { data: overview, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['dashboardOverview'],
    queryFn: getDashboardOverview,
  });

  const assetCount = overview?.asset_count ?? 0;
  const facilityCount = overview?.facility_count ?? 0;
  const assetTypeCount = overview?.asset_type_count ?? 0;
  const metricDefinitionCount = overview?.metric_definition_count ?? 0;
  const recentAssets = overview?.recent_assets ?? [];

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text-primary">System Overview</h1>
        <p className="text-text-secondary text-xs mt-0.5">
          Real-time metrics schema, registry stats, and device status.
        </p>
      </div>

      <QueryState isLoading={isLoading} error={isError ? error : null} refetch={refetch}>
        {/* KPI Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-bg-surface border border-border-dark p-4 rounded-lg relative overflow-hidden">
            <div className="text-text-muted text-xs font-semibold flex items-center gap-1.5 uppercase tracking-wide">
              <Box className="w-4 h-4 text-accent" />
              Total Assets
            </div>
            <div className="text-2xl font-semibold font-mono mt-2 text-text-primary">
              {assetCount}
            </div>
            <Link
              to="/assets"
              className="absolute bottom-2 right-2 text-text-muted hover:text-text-primary p-1 cursor-pointer"
            >
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="bg-bg-surface border border-border-dark p-4 rounded-lg relative overflow-hidden">
            <div className="text-text-muted text-xs font-semibold flex items-center gap-1.5 uppercase tracking-wide">
              <MapIcon className="w-4 h-4 text-success" />
              Facilities
            </div>
            <div className="text-2xl font-semibold font-mono mt-2 text-text-primary">
              {facilityCount}
            </div>
            <Link
              to="/registry"
              className="absolute bottom-2 right-2 text-text-muted hover:text-text-primary p-1 cursor-pointer"
            >
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="bg-bg-surface border border-border-dark p-4 rounded-lg relative overflow-hidden">
            <div className="text-text-muted text-xs font-semibold flex items-center gap-1.5 uppercase tracking-wide">
              <Settings className="w-4 h-4 text-warning" />
              Asset Types
            </div>
            <div className="text-2xl font-semibold font-mono mt-2 text-text-primary">
              {assetTypeCount}
            </div>
            <Link
              to="/registry"
              className="absolute bottom-2 right-2 text-text-muted hover:text-text-primary p-1 cursor-pointer"
            >
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>

          <div className="bg-bg-surface border border-border-dark p-4 rounded-lg relative overflow-hidden">
            <div className="text-text-muted text-xs font-semibold flex items-center gap-1.5 uppercase tracking-wide">
              <FileSpreadsheet className="w-4 h-4 text-danger" />
              Metric Schemas
            </div>
            <div className="text-2xl font-semibold font-mono mt-2 text-text-primary">
              {metricDefinitionCount}
            </div>
            <Link
              to="/registry"
              className="absolute bottom-2 right-2 text-text-muted hover:text-text-primary p-1 cursor-pointer"
            >
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Recent Assets List */}
          <div className="lg:col-span-2 bg-bg-surface border border-border-dark rounded-lg p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-border-dark pb-3">
              <h3 className="font-semibold text-xs text-text-primary flex items-center gap-2 uppercase tracking-wider">
                <Activity className="w-4 h-4 text-accent" />
                Recently Registered Assets
              </h3>
              {assetCount > 0 && (
                <Link
                  to="/assets"
                  className="text-[11px] text-accent hover:underline flex items-center gap-1 cursor-pointer"
                >
                  View All Assets
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              )}
            </div>

            {recentAssets.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-8 text-center text-text-muted">
                <Box className="w-8 h-8 text-text-muted mb-2" />
                <span className="text-xs font-semibold">No assets registered in the database.</span>
                <Link
                  to="/assets"
                  className="mt-3 flex items-center gap-1.5 px-3 py-1.5 bg-accent text-white text-[11px] font-semibold rounded hover:bg-accent-hover transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> Register Asset
                </Link>
              </div>
            ) : (
              <div className="divide-y divide-border-dark">
                {recentAssets.map((asset) => {
                  const facilityName = asset.facility?.name || 'Unknown Location';
                  const typeName = asset.assetType?.name || 'Unknown Type';
                  return (
                    <div
                      key={asset.id}
                      className="flex justify-between items-center py-3 first:pt-0 last:pb-0 hover:bg-bg-panel/20 px-2 rounded-md transition-colors"
                    >
                      <div className="space-y-0.5">
                        <Link
                          to={`/assets/${asset.id}`}
                          className="font-semibold text-xs text-text-primary hover:text-accent hover:underline cursor-pointer"
                        >
                          {asset.name}
                        </Link>
                        <div className="flex items-center gap-3 text-[10px] text-text-secondary font-mono">
                          <span>Facility: {facilityName}</span>
                          <span className="text-text-muted">•</span>
                          <span>Type: {typeName}</span>
                        </div>
                      </div>
                      <Link
                        to={`/assets/${asset.id}`}
                        className="p-1 text-text-muted hover:text-text-primary bg-bg-panel border border-border-dark rounded hover:border-border-light cursor-pointer"
                      >
                        <ArrowRight className="w-3.5 h-3.5" />
                      </Link>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Quick Actions / Getting Started */}
          <div className="bg-bg-surface border border-border-dark rounded-lg p-5 space-y-4">
            <h3 className="font-semibold text-xs text-text-primary uppercase tracking-wider border-b border-border-dark pb-3 flex items-center gap-2">
              <Calendar className="w-4 h-4 text-success" />
              Quick Setup checklist
            </h3>
            <ul className="text-xs space-y-3 font-mono text-text-secondary">
              <li className="flex items-start gap-2.5">
                <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${facilityCount > 0 ? 'bg-success/20 text-success' : 'bg-bg-panel text-text-muted border border-border-dark'}`}>
                  1
                </span>
                <div>
                  <Link to="/registry" className="hover:underline text-text-primary">Create Organization & Facility</Link>
                  <p className="text-[10px] text-text-muted mt-0.5">Required before mapping assets.</p>
                </div>
              </li>
              <li className="flex items-start gap-2.5">
                <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${assetTypeCount > 0 ? 'bg-success/20 text-success' : 'bg-bg-panel text-text-muted border border-border-dark'}`}>
                  2
                </span>
                <div>
                  <Link to="/registry" className="hover:underline text-text-primary">Register Asset Type & Metrics</Link>
                  <p className="text-[10px] text-text-muted mt-0.5">Define metrics (temperature, etc.) for validation.</p>
                </div>
              </li>
              <li className="flex items-start gap-2.5">
                <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${assetCount > 0 ? 'bg-success/20 text-success' : 'bg-bg-panel text-text-muted border border-border-dark'}`}>
                  3
                </span>
                <div>
                  <Link to="/assets" className="hover:underline text-text-primary">Create Asset Node</Link>
                  <p className="text-[10px] text-text-muted mt-0.5">Map asset names to specific facilities & types.</p>
                </div>
              </li>
              <li className="flex items-start gap-2.5">
                <span className="w-4 h-4 rounded-full flex items-center justify-center text-[10px] bg-bg-panel text-text-muted border border-border-dark">
                  4
                </span>
                <div>
                  <span className="text-text-muted">Ingest Real Telemetry</span>
                  <p className="text-[10px] text-text-muted mt-0.5">Go to Asset Details to manually ingest metric values.</p>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </QueryState>
    </div>
  );
}
