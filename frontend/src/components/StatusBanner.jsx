import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { getHealth } from '../api/system.js';
import { Activity, Wifi, WifiOff } from 'lucide-react';

export default function StatusBanner() {
  const { data, error, isError } = useQuery({
    queryKey: ['systemHealth'],
    queryFn: getHealth,
    refetchInterval: 5000, // check health every 5 seconds
    staleTime: 0, // always fetch fresh
    retry: false, // don't retry, just report offline immediately
  });

  const isOffline = isError || !data || data.status === 'offline';
  const latency = data?.latency || 0;
  const isDegraded = !isOffline && latency > 250;

  // Render state
  let statusText = 'Connected';
  let statusColor = 'text-success bg-success/10 border-success/20';
  let dotColor = 'bg-success';
  let Icon = Wifi;

  if (isOffline) {
    statusText = 'Offline';
    statusColor = 'text-danger bg-danger/10 border-danger/20';
    dotColor = 'bg-danger';
    Icon = WifiOff;
  } else if (isDegraded) {
    statusText = 'Degraded';
    statusColor = 'text-warning bg-warning/10 border-warning/20';
    dotColor = 'bg-warning';
    Icon = Activity;
  }

  const timestamp = new Date().toLocaleTimeString();

  return (
    <div className="flex flex-wrap items-center gap-4 px-4 py-2 border-b border-border-dark bg-bg-surface text-xs font-mono select-none">
      <div className={`flex items-center gap-2 px-2.5 py-1 border rounded-full ${statusColor}`}>
        <span className={`w-2 h-2 rounded-full ${dotColor} animate-pulse`} />
        <Icon className="w-3.5 h-3.5" />
        <span className="font-semibold uppercase tracking-wider">{statusText}</span>
      </div>

      <div className="hidden sm:flex items-center gap-4 text-text-secondary">
        <div>
          <span className="text-text-muted">Target:</span>{' '}
          <span className="text-text-primary">/api/v1</span>
        </div>
        <div>
          <span className="text-text-muted">Latency:</span>{' '}
          <span className={`${isDegraded ? 'text-warning' : isOffline ? 'text-danger' : 'text-success'}`}>
            {isOffline ? '--' : `${latency}ms`}
          </span>
        </div>
        <div>
          <span className="text-text-muted">Sync:</span>{' '}
          <span className="text-text-primary">{timestamp}</span>
        </div>
      </div>
    </div>
  );
}
