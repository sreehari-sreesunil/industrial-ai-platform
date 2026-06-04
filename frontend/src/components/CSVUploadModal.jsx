import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { X, Upload, Download, CheckCircle, XCircle, AlertTriangle, Loader2, FileText, Terminal } from 'lucide-react';
import { getAssetTypes, getMetricDefinitions } from '../api/registry.js';
import { uploadTelemetryCSV } from '../api/telemetry.js';
import { toast } from 'react-hot-toast';

export default function CSVUploadModal({ isOpen, onClose }) {
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState(null);
  const [selectedAssetTypeId, setSelectedAssetTypeId] = useState('');
  
  // Progress states
  const [uploadState, setUploadState] = useState('idle'); // idle, uploading, processing, success, error
  const [currentProgressStep, setCurrentProgressStep] = useState(0); // 0 = upload, 1 = process, 2 = validate
  const [uploadResult, setUploadResult] = useState(null);
  
  // Fetch asset types and metric definitions for generating dynamic CSV templates
  const { data: assetTypes = [] } = useQuery({
    queryKey: ['assetTypes'],
    queryFn: getAssetTypes,
    enabled: isOpen,
  });

  const { data: metricDefinitions = [] } = useQuery({
    queryKey: ['metricDefinitions'],
    queryFn: () => getMetricDefinitions(),
    enabled: isOpen,
  });

  // Set default asset type when loaded
  useEffect(() => {
    if (assetTypes.length > 0 && !selectedAssetTypeId) {
      setSelectedAssetTypeId(assetTypes[0].id.toString());
    }
  }, [assetTypes, selectedAssetTypeId]);

  // Reset modal state on close/open
  useEffect(() => {
    if (isOpen) {
      setSelectedFile(null);
      setUploadState('idle');
      setCurrentProgressStep(0);
      setUploadResult(null);
    }
  }, [isOpen]);

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      if (file.name.endsWith('.csv')) {
        setSelectedFile(file);
      } else {
        toast.error('Only CSV files are supported');
      }
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleDownloadTemplate = () => {
    // Filter metrics for the selected asset type
    const activeMetrics = metricDefinitions.filter(
      (m) => m.assetType?.id?.toString() === selectedAssetTypeId
    );
    
    // Build CSV header
    const headers = ['timestamp', 'asset_id'];
    activeMetrics.forEach((m) => {
      headers.push(m.name);
    });

    // If no metrics registered, fall back to some sample headers
    if (activeMetrics.length === 0) {
      headers.push('temperature', 'pressure');
    }

    // Build sample row
    const nowIso = new Date().toISOString();
    const sampleRow = [nowIso, '1'];
    activeMetrics.forEach((m) => {
      // provide reasonable sample values
      if (m.dataType === 'float' || m.dataType === 'integer') {
        const min = m.minValue !== null ? m.minValue : 10;
        const max = m.maxValue !== null ? m.maxValue : 100;
        sampleRow.push(((min + max) / 2).toFixed(1));
      } else {
        sampleRow.push('0');
      }
    });

    if (activeMetrics.length === 0) {
      sampleRow.push('72.5', '18.0');
    }

    const csvContent = [headers.join(','), sampleRow.join(',')].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    
    const assetTypeName = assetTypes.find(t => t.id.toString() === selectedAssetTypeId)?.name || 'telemetry';
    const filename = `${assetTypeName.toLowerCase().replace(/[^a-z0-9]/g, '_')}_template.csv`;
    
    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('CSV template downloaded');
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploadState('uploading');
    setCurrentProgressStep(0);

    // Operational timing simulation for progress state, then execute actual call
    // Step 0: Uploading CSV (0.8s)
    setTimeout(() => {
      setCurrentProgressStep(1);
      setUploadState('processing');
      
      // Step 1: Processing telemetry (0.8s)
      setTimeout(async () => {
        setCurrentProgressStep(2);
        
        try {
          const result = await uploadTelemetryCSV(selectedFile);
          setUploadResult(result);
          
          if (result.failed_rows > 0) {
            setUploadState('result');
            toast.warn(`CSV processed with ${result.failed_rows} failures.`);
          } else {
            setUploadState('success');
            toast.success(`Successfully uploaded all ${result.inserted_rows} telemetry rows.`);
            queryClient.invalidateQueries({ queryKey: ['telemetry'] });
            queryClient.invalidateQueries({ queryKey: ['latestTelemetry'] });
          }
        } catch (error) {
          setUploadState('error');
          // Error toasts are handled globally in client.js unless toast suppressed
        }
      }, 800);
    }, 800);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-bg-base/85 backdrop-blur-sm">
      <div className="w-full max-w-lg bg-bg-surface border border-border-light rounded-lg shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 bg-bg-panel border-b border-border-dark">
          <div className="flex items-center gap-2">
            <Upload className="w-4 h-4 text-accent" />
            <h3 className="font-semibold text-text-primary text-xs uppercase tracking-wider font-sans">
              Bulk Telemetry CSV Ingest
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-text-secondary hover:text-text-primary cursor-pointer p-0.5"
            disabled={uploadState === 'uploading' || uploadState === 'processing'}
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 space-y-5">
          {uploadState === 'idle' && (
            <>
              {/* Drag and Drop Zone */}
              <div
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                className="flex flex-col items-center justify-center border-2 border-dashed border-border-light hover:border-accent bg-bg-panel/20 hover:bg-bg-panel/40 p-8 rounded-lg cursor-pointer transition-all text-center relative group"
              >
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <FileText className="w-10 h-10 text-text-secondary group-hover:text-accent mb-3 transition-colors" />
                {selectedFile ? (
                  <div>
                    <p className="text-text-primary text-xs font-semibold font-mono">{selectedFile.name}</p>
                    <p className="text-text-muted text-[10px] mt-1 font-mono">
                      {(selectedFile.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-text-primary text-xs font-semibold">Drag & drop telemetry CSV here</p>
                    <p className="text-text-secondary text-[10px] mt-1">or click to browse local files</p>
                  </div>
                )}
              </div>

              {/* Template Download Section */}
              <div className="bg-bg-panel/40 border border-border-dark p-4 rounded-lg space-y-3">
                <div className="flex items-start gap-2.5">
                  <Download className="w-4 h-4 text-accent shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-text-primary text-xs font-semibold font-sans">Download Schema-Driven Template</h4>
                    <p className="text-text-secondary text-[10px] mt-0.5">
                      Generate a formatted CSV template matching the exact metrics configured for the asset type.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3 pt-1">
                  <select
                    value={selectedAssetTypeId}
                    onChange={(e) => setSelectedAssetTypeId(e.target.value)}
                    className="flex-1 bg-bg-input border border-border-light rounded px-3 py-1.5 text-xs text-text-primary font-mono focus:outline-none focus:border-accent cursor-pointer"
                  >
                    {assetTypes.map((type) => (
                      <option key={type.id} value={type.id}>
                        {type.name} Schema Template
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={handleDownloadTemplate}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-bg-panel border border-border-light text-text-primary text-xs font-semibold rounded hover:bg-border-dark transition-colors cursor-pointer shrink-0"
                  >
                    Download
                  </button>
                </div>
              </div>
            </>
          )}

          {/* Uploading/Processing Progress State */}
          {(uploadState === 'uploading' || uploadState === 'processing') && (
            <div className="py-6 space-y-6">
              <div className="flex items-center justify-center">
                <Loader2 className="w-10 h-10 text-accent animate-spin" />
              </div>

              <div className="max-w-xs mx-auto space-y-3">
                <div className="flex items-center justify-between text-xs font-semibold">
                  <span className="text-text-primary">Ingestion Engine In Progress</span>
                  <span className="text-accent font-mono">
                    {uploadState === 'uploading' ? '33%' : '66%'}
                  </span>
                </div>
                <div className="h-1.5 w-full bg-border-dark rounded-full overflow-hidden">
                  <div
                    className="h-full bg-accent transition-all duration-500 rounded-full"
                    style={{ width: uploadState === 'uploading' ? '33%' : '66%' }}
                  />
                </div>
              </div>

              <div className="max-w-xs mx-auto border border-border-dark bg-bg-panel/30 p-3.5 rounded space-y-2.5 font-mono text-[11px]">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${currentProgressStep >= 0 ? 'bg-success animate-pulse' : 'bg-border-light'}`} />
                  <span className={currentProgressStep > 0 ? 'text-text-muted line-through' : 'text-text-primary font-semibold'}>
                    Uploading CSV file payload...
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${currentProgressStep >= 1 ? 'bg-success animate-pulse' : 'bg-border-light'}`} />
                  <span className={currentProgressStep > 1 ? 'text-text-muted line-through' : currentProgressStep === 1 ? 'text-text-primary font-semibold' : 'text-text-secondary'}>
                    Processing telemetry time-series...
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full ${currentProgressStep >= 2 ? 'bg-success animate-pulse' : 'bg-border-light'}`} />
                  <span className={currentProgressStep === 2 ? 'text-text-primary font-semibold' : 'text-text-secondary'}>
                    Validating schema data constraints...
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Success State */}
          {uploadState === 'success' && (
            <div className="py-6 flex flex-col items-center justify-center text-center space-y-4">
              <CheckCircle className="w-12 h-12 text-success" />
              <div>
                <h4 className="text-text-primary font-bold text-sm">Telemetry Ingest Complete</h4>
                <p className="text-text-secondary text-xs mt-1 max-w-sm">
                  CSV file was parsed and all metrics were successfully committed to the database.
                </p>
              </div>
            </div>
          )}

          {/* Error State (Complete Request Failure) */}
          {uploadState === 'error' && (
            <div className="py-6 flex flex-col items-center justify-center text-center space-y-4">
              <XCircle className="w-12 h-12 text-danger" />
              <div>
                <h4 className="text-text-primary font-bold text-sm">Ingestion Pipeline Failed</h4>
                <p className="text-text-secondary text-xs mt-1 max-w-sm">
                  The API rejected the CSV payload. Verify the file format and network connection.
                </p>
              </div>
              <button
                onClick={() => setUploadState('idle')}
                className="px-4 py-2 bg-bg-panel border border-border-light text-text-primary text-xs font-semibold rounded hover:bg-border-dark transition-colors cursor-pointer"
              >
                Try Again
              </button>
            </div>
          )}

          {/* Partial Result / Failure Log Console */}
          {uploadState === 'result' && uploadResult && (
            <div className="space-y-4">
              {/* Outcome Banner */}
              <div className="flex items-start gap-3 p-3.5 bg-warning/5 border border-warning/20 rounded-lg">
                <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
                <div>
                  <h4 className="text-text-primary text-xs font-semibold">Partial Ingestion Warnings</h4>
                  <p className="text-text-secondary text-[10px] mt-0.5">
                    Parsed <span className="text-text-primary font-bold">{uploadResult.total_rows}</span> rows. 
                    Ingested <span className="text-success font-bold font-mono">{uploadResult.inserted_rows}</span>. 
                    Failed <span className="text-danger font-bold font-mono">{uploadResult.failed_rows}</span>.
                  </p>
                </div>
              </div>

              {/* Console log for failures */}
              {uploadResult.errors && uploadResult.errors.length > 0 && (
                <div className="space-y-1.5">
                  <div className="flex items-center gap-1.5 text-text-secondary text-[10px] font-semibold font-mono uppercase tracking-wider">
                    <Terminal className="w-3.5 h-3.5" />
                    Validation Error Logs
                  </div>
                  <div className="bg-bg-input border border-border-dark rounded-lg p-3 max-h-48 overflow-y-auto font-mono text-[10px] text-danger space-y-1.5">
                    {uploadResult.errors.map((err, idx) => (
                      <div key={idx} className="flex gap-2">
                        <span className="text-text-muted shrink-0 select-none">[ROW {err.row}]</span>
                        <span className="select-text">{err.error}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex justify-end gap-3 px-5 py-4 bg-bg-panel border-t border-border-dark">
          {uploadState === 'idle' ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-border-light rounded text-xs font-semibold text-text-primary hover:bg-bg-panel cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!selectedFile}
                onClick={handleUpload}
                className="px-4 py-2 bg-accent text-white text-xs font-semibold rounded hover:bg-accent-hover disabled:opacity-50 transition-colors cursor-pointer"
              >
                Upload & Ingest
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => {
                queryClient.invalidateQueries();
                onClose();
              }}
              className="px-4 py-2 bg-accent text-white text-xs font-semibold rounded hover:bg-accent-hover transition-colors cursor-pointer"
            >
              Done
            </button>
          )}
        </div>

      </div>
    </div>
  );
}
