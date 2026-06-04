import React from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { router } from './routes/router.jsx';
import './index.css';

// Configure TanStack Query global defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30000, // 30 seconds
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <Toaster
        position="top-right"
        toastOptions={{
          className: 'bg-bg-panel text-text-primary border border-border-light text-xs font-sans',
          duration: 3500,
          style: {
            backgroundColor: '#1e2330',
            borderColor: '#334155',
            color: '#f8fafc',
          },
        }}
      />
    </QueryClientProvider>
  </React.StrictMode>
);
