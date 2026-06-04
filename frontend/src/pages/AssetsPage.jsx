import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { getAssets, createAsset } from '../api/assets.js';
import { getFacilities, getAssetTypes } from '../api/registry.js';
import { Box, Plus, Search, FileText, X, AlertCircle } from 'lucide-react';
import QueryState from '../components/QueryState.jsx';
import { toast } from 'react-hot-toast';

export default function AssetsPage() {
  const queryClient = useQueryClient();
  const [searchTerm, setSearchTerm] = useState('');
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form states
  const [name, setName] = useState('');
  const [facilityId, setFacilityId] = useState('');
  const [assetTypeId, setAssetTypeId] = useState('');

  // Fetch data
  const assetsQuery = useQuery({ queryKey: ['assets'], queryFn: getAssets });
  const facilitiesQuery = useQuery({ queryKey: ['facilities'], queryFn: getFacilities });
  const assetTypesQuery = useQuery({ queryKey: ['assetTypes'], queryFn: getAssetTypes });

  // Mutation
  const createMutation = useMutation({
    mutationFn: createAsset,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets'] });
      toast.success('Asset created successfully');
      setIsModalOpen(false);
      setName('');
      setFacilityId('');
      setAssetTypeId('');
    },
  });

  const isLoading = assetsQuery.isLoading || facilitiesQuery.isLoading || assetTypesQuery.isLoading;
  const isError = assetsQuery.isError || facilitiesQuery.isError || assetTypesQuery.isError;
  const error = assetsQuery.error || facilitiesQuery.error || assetTypesQuery.error;

  const assets = assetsQuery.data || [];
  const facilities = facilitiesQuery.data || [];
  const assetTypes = assetTypesQuery.data || [];

  const filteredAssets = assets.filter((asset) => {
    const fName = asset.facility?.name || '';
    const tName = asset.assetType?.name || '';
    const term = searchTerm.toLowerCase();
    return (
      asset.name.toLowerCase().includes(term) ||
      asset.id.toString().includes(term) ||
      fName.toLowerCase().includes(term) ||
      tName.toLowerCase().includes(term)
    );
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!name.trim()) return toast.error('Asset Name is required');
    if (!facilityId) return toast.error('Facility selection is required');
    if (!assetTypeId) return toast.error('Asset Type selection is required');

    createMutation.mutate({
      name: name.trim(),
      facility_id: parseInt(facilityId, 10),
      asset_type_id: parseInt(assetTypeId, 10),
    });
  };

  const openRegisterModal = () => {
    if (facilities.length === 0 || assetTypes.length === 0) {
      toast.error('You must define at least one Facility and one Asset Type first.', {
        id: 'registry-prereq',
      });
      return;
    }
    // Set default select values
    setFacilityId(facilities[0]?.id?.toString() || '');
    setAssetTypeId(assetTypes[0]?.id?.toString() || '');
    setIsModalOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary">Asset Registry</h1>
          <p className="text-text-secondary text-xs mt-0.5">
            Overview and registration of industrial asset nodes mapped in the system.
          </p>
        </div>

        <button
          onClick={openRegisterModal}
          className="flex items-center gap-2 px-3 py-2 bg-accent text-white text-xs font-semibold rounded hover:bg-accent-hover transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          Register Asset
        </button>
      </div>

      {/* Main Panel */}
      <div className="bg-bg-surface border border-border-dark rounded-lg p-4 space-y-4">
        {/* Controls */}
        <div className="flex items-center gap-3 bg-bg-input border border-border-dark px-3 py-2 rounded-md max-w-md">
          <Search className="w-4 h-4 text-text-muted" />
          <input
            type="text"
            placeholder="Search by ID, name, facility or type..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-transparent border-none text-text-primary text-xs focus:outline-none font-mono"
          />
          {searchTerm && (
            <button onClick={() => setSearchTerm('')} className="text-text-muted hover:text-text-primary">
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Query State wrapper */}
        <QueryState
          isLoading={isLoading}
          error={isError ? error : null}
          isEmpty={assets.length === 0}
          emptyTitle="No Assets Configured"
          emptyMessage="No assets are defined in the database schema. Register an asset using the button above to begin."
          refetch={() => {
            assetsQuery.refetch();
            facilitiesQuery.refetch();
            assetTypesQuery.refetch();
          }}
        >
          {filteredAssets.length === 0 && searchTerm ? (
            <div className="p-8 text-center text-text-muted text-xs font-mono border border-dashed border-border-dark rounded bg-bg-panel/30">
              No assets matched search filter: "{searchTerm}"
            </div>
          ) : (
            <div className="overflow-x-auto border border-border-dark rounded-lg">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-bg-panel border-b border-border-dark text-text-secondary text-[10px] uppercase font-mono tracking-wider">
                    <th className="px-4 py-3 font-semibold">Node ID</th>
                    <th className="px-4 py-3 font-semibold">Asset Name</th>
                    <th className="px-4 py-3 font-semibold">Facility Location</th>
                    <th className="px-4 py-3 font-semibold">Asset Schema Type</th>
                    <th className="px-4 py-3 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-dark font-mono">
                  {filteredAssets.map((asset) => {
                    const fName = asset.facility?.name || 'Unknown Location';
                    const tName = asset.assetType?.name || 'Unknown Type';
                    return (
                      <tr key={asset.id} className="hover:bg-bg-panel/45 transition-colors">
                        <td className="px-4 py-3 text-text-muted select-all">#{asset.id}</td>
                        <td className="px-4 py-3 font-semibold text-text-primary select-all">{asset.name}</td>
                        <td className="px-4 py-3 text-text-secondary">{fName}</td>
                        <td className="px-4 py-3 text-text-secondary">{tName}</td>
                        <td className="px-4 py-3 text-right">
                          <Link
                            to={`/assets/${asset.id}`}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-bg-panel border border-border-light text-text-primary text-[10px] font-semibold rounded hover:bg-border-dark transition-all cursor-pointer"
                          >
                            <FileText className="w-3.5 h-3.5 text-accent" />
                            Console
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </QueryState>
      </div>

      {/* Register Asset Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-bg-base/85 backdrop-blur-sm">
          <div className="w-full max-w-md bg-bg-surface border border-border-light rounded-lg shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex items-center justify-between px-5 py-4 bg-bg-panel border-b border-border-dark">
              <div className="flex items-center gap-2">
                <Box className="w-4 h-4 text-accent" />
                <h3 className="font-semibold text-text-primary text-xs uppercase tracking-wider">
                  Register Asset Node
                </h3>
              </div>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-text-secondary hover:text-text-primary cursor-pointer p-0.5"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <form onSubmit={handleSubmit} className="p-5 space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="modal-name" className="text-xs text-text-secondary font-semibold font-mono">
                  Asset Name
                </label>
                <input
                  id="modal-name"
                  type="text"
                  placeholder="e.g. Compressor Station A"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="modal-facility" className="text-xs text-text-secondary font-semibold font-mono">
                  Facility Location
                </label>
                <select
                  id="modal-facility"
                  value={facilityId}
                  onChange={(e) => setFacilityId(e.target.value)}
                  className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono cursor-pointer"
                  required
                >
                  {facilities.map((fac) => (
                    <option key={fac.id} value={fac.id}>
                      {fac.name} (Org ID: {fac.organizationId})
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label htmlFor="modal-type" className="text-xs text-text-secondary font-semibold font-mono">
                  Asset Type Schema
                </label>
                <select
                  id="modal-type"
                  value={assetTypeId}
                  onChange={(e) => setAssetTypeId(e.target.value)}
                  className="w-full bg-bg-input border border-border-light rounded px-3 py-2 text-xs focus:outline-none focus:border-accent text-text-primary font-mono cursor-pointer"
                  required
                >
                  {assetTypes.map((type) => (
                    <option key={type.id} value={type.id}>
                      {type.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Warnings / Infos */}
              <div className="flex gap-2 p-3 bg-accent/5 border border-accent/15 rounded text-[11px] text-text-secondary">
                <AlertCircle className="w-4 h-4 text-accent shrink-0 mt-0.5" />
                <span>
                  The asset type selection links this asset node to registered schemas. Telemetry ingestion validates against this type's metrics.
                </span>
              </div>

              {/* Modal Footer */}
              <div className="flex justify-end gap-3 pt-2 border-t border-border-dark">
                <button
                  type="button"
                  onClick={() => setIsOpen ? setIsOpen(false) : setIsModalOpen(false)}
                  className="px-4 py-2 border border-border-light rounded text-xs font-semibold text-text-primary hover:bg-bg-panel cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="px-4 py-2 bg-accent text-white text-xs font-semibold rounded hover:bg-accent-hover disabled:opacity-50 transition-colors cursor-pointer"
                >
                  {createMutation.isPending ? 'Registering...' : 'Register Node'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
