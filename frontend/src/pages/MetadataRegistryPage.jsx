import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getOrganizations,
  createOrganization,
  getFacilities,
  createFacility,
  getAssetTypes,
  createAssetType,
  getMetricDefinitions,
  createMetricDefinition,
} from '../api/registry.js';
import {
  Building2,
  MapPin,
  Settings,
  FileSpreadsheet,
  Plus,
  Trash2,
  Sliders,
  CheckCircle,
} from 'lucide-react';
import QueryState from '../components/QueryState.jsx';
import { toast } from 'react-hot-toast';

export default function MetadataRegistryPage() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState('orgs');

  // Form states
  const [orgName, setOrgName] = useState('');
  const [facName, setFacName] = useState('');
  const [facOrgId, setFacOrgId] = useState('');
  const [typeName, setTypeName] = useState('');
  const [typeDesc, setTypeDesc] = useState('');
  
  const [metricName, setMetricName] = useState('');
  const [metricUnit, setMetricUnit] = useState('');
  const [metricDataType, setMetricDataType] = useState('float');
  const [metricMin, setMetricMin] = useState('');
  const [metricMax, setMetricMax] = useState('');
  const [metricAssetTypeId, setMetricAssetTypeId] = useState('');

  // Fetch queries
  const orgsQuery = useQuery({ queryKey: ['organizations'], queryFn: getOrganizations });
  const facsQuery = useQuery({ queryKey: ['facilities'], queryFn: getFacilities });
  const typesQuery = useQuery({ queryKey: ['assetTypes'], queryFn: getAssetTypes });
  const metricsQuery = useQuery({ queryKey: ['metricDefinitions'], queryFn: getMetricDefinitions });

  // Mutations
  const createOrgMutation = useMutation({
    mutationFn: createOrganization,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['organizations'] });
      toast.success('Organization created successfully');
      setOrgName('');
    },
  });

  const createFacMutation = useMutation({
    mutationFn: createFacility,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['facilities'] });
      toast.success('Facility created successfully');
      setFacName('');
      setFacOrgId('');
    },
  });

  const createTypeMutation = useMutation({
    mutationFn: createAssetType,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assetTypes'] });
      toast.success('Asset Type created successfully');
      setTypeName('');
      setTypeDesc('');
    },
  });

  const createMetricMutation = useMutation({
    mutationFn: createMetricDefinition,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metricDefinitions'] });
      toast.success('Metric Definition created successfully');
      setMetricName('');
      setMetricUnit('');
      setMetricDataType('float');
      setMetricMin('');
      setMetricMax('');
      setMetricAssetTypeId('');
    },
  });

  // Helpers
  const organizations = orgsQuery.data || [];
  const facilities = facsQuery.data || [];
  const assetTypes = typesQuery.data || [];
  const metricDefinitions = metricsQuery.data || [];

  const handleCreateOrg = (e) => {
    e.preventDefault();
    if (!orgName.trim()) return toast.error('Organization Name is required');
    createOrgMutation.mutate({ name: orgName.trim() });
  };

  const handleCreateFac = (e) => {
    e.preventDefault();
    if (!facName.trim()) return toast.error('Facility Name is required');
    
    // Auto-select first org if not set
    const selectedOrgId = facOrgId || (organizations[0]?.id?.toString() || '');
    if (!selectedOrgId) return toast.error('An organization must exist first');

    createFacMutation.mutate({
      name: facName.trim(),
      organization_id: parseInt(selectedOrgId, 10),
    });
  };

  const handleCreateType = (e) => {
    e.preventDefault();
    if (!typeName.trim()) return toast.error('Asset Type Name is required');
    createTypeMutation.mutate({
      name: typeName.trim(),
      description: typeDesc.trim() || undefined,
    });
  };

  const handleCreateMetric = (e) => {
    e.preventDefault();
    if (!metricName.trim()) return toast.error('Metric Name is required');
    
    const selectedTypeId = metricAssetTypeId || (assetTypes[0]?.id?.toString() || '');
    if (!selectedTypeId) return toast.error('An Asset Type must exist first');

    const payload = {
      name: metricName.trim(),
      unit: metricUnit.trim() || '',
      data_type: metricDataType,
      asset_type_id: parseInt(selectedTypeId, 10),
    };

    if (metricMin !== '') {
      payload.min_value = parseFloat(metricMin);
      if (isNaN(payload.min_value)) return toast.error('Min value must be a number');
    }
    if (metricMax !== '') {
      payload.max_value = parseFloat(metricMax);
      if (isNaN(payload.max_value)) return toast.error('Max value must be a number');
    }

    if (payload.min_value !== undefined && payload.max_value !== undefined && payload.min_value > payload.max_value) {
      return toast.error('Min value cannot exceed Max value');
    }

    createMetricMutation.mutate(payload);
  };

  const tabs = [
    { id: 'orgs', label: 'Organizations', icon: Building2, query: orgsQuery },
    { id: 'facs', label: 'Facilities', icon: MapPin, query: facsQuery },
    { id: 'types', label: 'Asset Types', icon: Settings, query: typesQuery },
    { id: 'metrics', label: 'Metric Definitions', icon: FileSpreadsheet, query: metricsQuery },
  ];

  const currentTabInfo = tabs.find((t) => t.id === activeTab);

  return (
    <div className="space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-xl font-bold tracking-tight text-text-primary">Metadata Registry</h1>
        <p className="text-text-secondary text-xs mt-0.5">
          Manage core relational entities and metric schemas that validate ingested telemetry.
        </p>
      </div>

      {/* Tabs list */}
      <div className="flex border-b border-border-dark overflow-x-auto select-none">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-5 py-3 border-b-2 font-mono text-xs font-semibold whitespace-nowrap cursor-pointer transition-all ${
                activeTab === tab.id
                  ? 'border-accent text-text-primary bg-bg-surface/50'
                  : 'border-transparent text-text-secondary hover:text-text-primary'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Side: Create form */}
        <div className="bg-bg-surface border border-border-dark rounded-lg p-5 h-fit space-y-4">
          <h3 className="font-semibold text-xs text-text-primary uppercase tracking-wider border-b border-border-dark pb-3 flex items-center gap-2">
            <Plus className="w-4 h-4 text-accent" />
            Add New Record
          </h3>

          {activeTab === 'orgs' && (
            <form onSubmit={handleCreateOrg} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="org-name" className="text-xs text-text-secondary font-semibold font-mono">
                  Organization Name
                </label>
                <input
                  id="org-name"
                  type="text"
                  placeholder="e.g. Acme Industrial Group"
                  value={orgName}
                  onChange={(e) => setOrgName(e.target.value)}
                  className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono"
                  required
                />
              </div>
              <button
                type="submit"
                disabled={createOrgMutation.isPending}
                className="w-full py-2 bg-accent hover:bg-accent-hover text-white text-xs font-semibold rounded disabled:opacity-50 transition-colors cursor-pointer"
              >
                Create Organization
              </button>
            </form>
          )}

          {activeTab === 'facs' && (
            <form onSubmit={handleCreateFac} className="space-y-4">
              {organizations.length === 0 ? (
                <div className="text-center py-4 text-text-muted text-xs font-mono">
                  Please create an organization first.
                </div>
              ) : (
                <>
                  <div className="space-y-1.5">
                    <label htmlFor="fac-name" className="text-xs text-text-secondary font-semibold font-mono">
                      Facility Name
                    </label>
                    <input
                      id="fac-name"
                      type="text"
                      placeholder="e.g. Texas Refining Hub"
                      value={facName}
                      onChange={(e) => setFacName(e.target.value)}
                      className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono"
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label htmlFor="fac-org" className="text-xs text-text-secondary font-semibold font-mono">
                      Belongs to Organization
                    </label>
                    <select
                      id="fac-org"
                      value={facOrgId}
                      onChange={(e) => setFacOrgId(e.target.value)}
                      className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono cursor-pointer"
                      required
                    >
                      <option value="">-- Select Organization --</option>
                      {organizations.map((org) => (
                        <option key={org.id} value={org.id}>
                          {org.name} (ID: {org.id})
                        </option>
                      ))}
                    </select>
                  </div>
                  <button
                    type="submit"
                    disabled={createFacMutation.isPending}
                    className="w-full py-2 bg-accent hover:bg-accent-hover text-white text-xs font-semibold rounded disabled:opacity-50 transition-colors cursor-pointer"
                  >
                    Create Facility
                  </button>
                </>
              )}
            </form>
          )}

          {activeTab === 'types' && (
            <form onSubmit={handleCreateType} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="type-name" className="text-xs text-text-secondary font-semibold font-mono">
                  Asset Type Name
                </label>
                <input
                  id="type-name"
                  type="text"
                  placeholder="e.g. GasTurbine"
                  value={typeName}
                  onChange={(e) => setTypeName(e.target.value)}
                  className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono"
                  required
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="type-desc" className="text-xs text-text-secondary font-semibold font-mono">
                  Description
                </label>
                <textarea
                  id="type-desc"
                  placeholder="Industrial characteristics..."
                  value={typeDesc}
                  onChange={(e) => setTypeDesc(e.target.value)}
                  className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono h-20"
                />
              </div>
              <button
                type="submit"
                disabled={createTypeMutation.isPending}
                className="w-full py-2 bg-accent hover:bg-accent-hover text-white text-xs font-semibold rounded disabled:opacity-50 transition-colors cursor-pointer"
              >
                Create Asset Type
              </button>
            </form>
          )}

          {activeTab === 'metrics' && (
            <form onSubmit={handleCreateMetric} className="space-y-4">
              {assetTypes.length === 0 ? (
                <div className="text-center py-4 text-text-muted text-xs font-mono">
                  Please create an Asset Type first.
                </div>
              ) : (
                <>
                  <div className="space-y-1.5">
                    <label htmlFor="metric-name" className="text-xs text-text-secondary font-semibold font-mono">
                      Metric Name (JSON key)
                    </label>
                    <input
                      id="metric-name"
                      type="text"
                      placeholder="e.g. temperature"
                      value={metricName}
                      onChange={(e) => setMetricName(e.target.value)}
                      className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono"
                      required
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="metric-unit" className="text-xs text-text-secondary font-semibold font-mono">
                      Unit
                    </label>
                    <input
                      id="metric-unit"
                      type="text"
                      placeholder="e.g. Celsius, kPa, Hz"
                      value={metricUnit}
                      onChange={(e) => setMetricUnit(e.target.value)}
                      className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono"
                    />
                  </div>

                  <div className="space-y-1.5">
                    <label htmlFor="metric-datatype" className="text-xs text-text-secondary font-semibold font-mono">
                      Data Type
                    </label>
                    <select
                      id="metric-datatype"
                      value={metricDataType}
                      onChange={(e) => setMetricDataType(e.target.value)}
                      className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono cursor-pointer"
                      required
                    >
                      <option value="integer">Integer</option>
                      <option value="float">Float</option>
                      <option value="boolean">Boolean</option>
                    </select>
                  </div>

                  {metricDataType !== 'boolean' && (
                    <div className="grid grid-cols-2 gap-2">
                      <div className="space-y-1.5">
                        <label htmlFor="metric-min" className="text-[10px] text-text-secondary font-semibold font-mono">
                          Min Bound (Optional)
                        </label>
                        <input
                          id="metric-min"
                          type="number"
                          step="any"
                          placeholder="None"
                          value={metricMin}
                          onChange={(e) => setMetricMin(e.target.value)}
                          className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label htmlFor="metric-max" className="text-[10px] text-text-secondary font-semibold font-mono">
                          Max Bound (Optional)
                        </label>
                        <input
                          id="metric-max"
                          type="number"
                          step="any"
                          placeholder="None"
                          value={metricMax}
                          onChange={(e) => setMetricMax(e.target.value)}
                          className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono"
                        />
                      </div>
                    </div>
                  )}

                  <div className="space-y-1.5">
                    <label htmlFor="metric-type" className="text-xs text-text-secondary font-semibold font-mono">
                      Applies to Asset Type
                    </label>
                    <select
                      id="metric-type"
                      value={metricAssetTypeId}
                      onChange={(e) => setMetricAssetTypeId(e.target.value)}
                      className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono cursor-pointer"
                      required
                    >
                      <option value="">-- Select Asset Type --</option>
                      {assetTypes.map((type) => (
                        <option key={type.id} value={type.id}>
                          {type.name} (ID: {type.id})
                        </option>
                      ))}
                    </select>
                  </div>

                  <button
                    type="submit"
                    disabled={createMetricMutation.isPending}
                    className="w-full py-2 bg-accent hover:bg-accent-hover text-white text-xs font-semibold rounded disabled:opacity-50 transition-colors cursor-pointer"
                  >
                    Register Metric Definition
                  </button>
                </>
              )}
            </form>
          )}
        </div>

        {/* Right Side: List viewport */}
        <div className="lg:col-span-2 bg-bg-surface border border-border-dark rounded-lg p-5">
          <h3 className="font-semibold text-xs text-text-primary uppercase tracking-wider border-b border-border-dark pb-3 flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Sliders className="w-4 h-4 text-accent" />
              Registered Records
            </span>
          </h3>

          <div className="mt-4">
            <QueryState
              isLoading={currentTabInfo.query.isLoading}
              error={currentTabInfo.query.isError ? currentTabInfo.query.error : null}
              isEmpty={currentTabInfo.id === 'orgs' ? organizations.length === 0 :
                       currentTabInfo.id === 'facs' ? facilities.length === 0 :
                       currentTabInfo.id === 'types' ? assetTypes.length === 0 :
                       metricDefinitions.length === 0}
              emptyTitle={`No ${currentTabInfo.label} Registered`}
              emptyMessage={`Create a new record in the panel on the left to register a schema entity.`}
              refetch={() => currentTabInfo.query.refetch()}
            >
              
              {activeTab === 'orgs' && (
                <div className="overflow-x-auto border border-border-dark rounded-lg">
                  <table className="w-full text-left border-collapse text-xs font-mono">
                    <thead>
                      <tr className="bg-bg-panel border-b border-border-dark text-text-secondary text-[10px] uppercase font-semibold">
                        <th className="px-4 py-2.5">ID</th>
                        <th className="px-4 py-2.5">Organization Name</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-dark">
                      {organizations.map((org) => (
                        <tr key={org.id} className="hover:bg-bg-panel/30">
                          <td className="px-4 py-2.5 text-text-muted select-all">#{org.id}</td>
                          <td className="px-4 py-2.5 font-semibold text-text-primary select-all">{org.name}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === 'facs' && (
                <div className="overflow-x-auto border border-border-dark rounded-lg">
                  <table className="w-full text-left border-collapse text-xs font-mono">
                    <thead>
                      <tr className="bg-bg-panel border-b border-border-dark text-text-secondary text-[10px] uppercase font-semibold">
                        <th className="px-4 py-2.5">ID</th>
                        <th className="px-4 py-2.5">Facility Name</th>
                        <th className="px-4 py-2.5">Parent Organization</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-dark">
                      {facilities.map((fac) => {
                        const orgName = fac.organization?.name || 'Unknown Org';
                        return (
                          <tr key={fac.id} className="hover:bg-bg-panel/30">
                            <td className="px-4 py-2.5 text-text-muted select-all">#{fac.id}</td>
                            <td className="px-4 py-2.5 font-semibold text-text-primary select-all">{fac.name}</td>
                            <td className="px-4 py-2.5 text-text-secondary">{orgName}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === 'types' && (
                <div className="overflow-x-auto border border-border-dark rounded-lg">
                  <table className="w-full text-left border-collapse text-xs font-mono">
                    <thead>
                      <tr className="bg-bg-panel border-b border-border-dark text-text-secondary text-[10px] uppercase font-semibold">
                        <th className="px-4 py-2.5">ID</th>
                        <th className="px-4 py-2.5">Type Name</th>
                        <th className="px-4 py-2.5">Description</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-dark">
                      {assetTypes.map((t) => (
                        <tr key={t.id} className="hover:bg-bg-panel/30">
                          <td className="px-4 py-2.5 text-text-muted select-all">#{t.id}</td>
                          <td className="px-4 py-2.5 font-semibold text-text-primary select-all">{t.name}</td>
                          <td className="px-4 py-2.5 text-text-secondary select-all">{t.description || '--'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {activeTab === 'metrics' && (
                <div className="overflow-x-auto border border-border-dark rounded-lg">
                  <table className="w-full text-left border-collapse text-xs font-mono">
                    <thead>
                      <tr className="bg-bg-panel border-b border-border-dark text-text-secondary text-[10px] uppercase font-semibold">
                        <th className="px-4 py-2.5">ID</th>
                        <th className="px-4 py-2.5">Metric / Unit</th>
                        <th className="px-4 py-2.5">Data Type</th>
                        <th className="px-4 py-2.5">Bounds (Min / Max)</th>
                        <th className="px-4 py-2.5">Asset Type Link</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border-dark">
                      {metricDefinitions.map((m) => {
                        const typeName = m.assetType?.name || 'Unknown Type';
                        const unitLabel = m.unit ? `[${m.unit}]` : '';
                        const minLabel = m.minValue !== null ? m.minValue : '--';
                        const maxLabel = m.maxValue !== null ? m.maxValue : '--';

                        return (
                          <tr key={m.id} className="hover:bg-bg-panel/30">
                            <td className="px-4 py-2.5 text-text-muted select-all">#{m.id}</td>
                            <td className="px-4 py-2.5 text-text-primary font-semibold select-all">
                              {m.name} <span className="text-[10px] text-text-muted font-normal">{unitLabel}</span>
                            </td>
                            <td className="px-4 py-2.5 text-text-secondary tracking-wide uppercase text-[10px]">{m.dataType}</td>
                            <td className="px-4 py-2.5 text-text-secondary">
                              {minLabel} / {maxLabel}
                            </td>
                            <td className="px-4 py-2.5 text-text-secondary">{typeName}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}

            </QueryState>
          </div>
        </div>
      </div>
    </div>
  );
}
