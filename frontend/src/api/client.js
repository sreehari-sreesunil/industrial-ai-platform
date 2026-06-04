import axios from 'axios';
import { toast } from 'react-hot-toast';

const client = axios.create({
  baseURL: '/api/v1',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Event listener hook capability for developer panel to count/log query failures
export const apiDiagnostics = {
  lastSync: null,
  activeRequests: 0,
  queryFailures: [],
  onUpdate: null,
  
  logFailure(url, method, errorMsg) {
    this.queryFailures.push({
      timestamp: new Date().toLocaleTimeString(),
      url,
      method,
      error: errorMsg,
    });
    // Keep last 15 failures
    if (this.queryFailures.length > 15) {
      this.queryFailures.shift();
    }
    if (this.onUpdate) this.onUpdate();
  },
  
  logSuccess() {
    this.lastSync = new Date();
    if (this.onUpdate) this.onUpdate();
  }
};

client.interceptors.request.use(
  (config) => {
    const token =
      localStorage.getItem(
        "access_token"
      );

    if (token) {
      config.headers.Authorization =
        `Bearer ${token}`;
    }

    apiDiagnostics.activeRequests++;

    if (apiDiagnostics.onUpdate) {
      apiDiagnostics.onUpdate();
    }

    return config;
  },
  (error) => {
    apiDiagnostics.activeRequests--;

    if (apiDiagnostics.onUpdate) {
      apiDiagnostics.onUpdate();
    }

    return Promise.reject(error);
  }
);

client.interceptors.response.use(
  (response) => {
    apiDiagnostics.activeRequests--;
    apiDiagnostics.logSuccess();
    return response;
  },
  (error) => {
    apiDiagnostics.activeRequests--;
    const method = error.config?.method?.toUpperCase() || 'UNKNOWN';
    const url = error.config?.url || 'unknown';
    
    // Automatic 401 Unauthorized handling (excluding login page submissions)
    if (error.response?.status === 401 && !url.includes('/auth/login')) {
      localStorage.removeItem("access_token");
      window.location.href = '/login';
      return Promise.reject(error);
    }

    let errorMsg = 'An unexpected error occurred.';
    if (error.response) {
      const data = error.response.data;
      errorMsg = typeof data === 'string' 
        ? data 
        : data?.detail || data?.message || `Request failed with status ${error.response.status}`;
    } else if (error.request) {
      errorMsg = 'No response received from backend. Check if the server is running.';
    } else {
      errorMsg = error.message;
    }
    
    apiDiagnostics.logFailure(url, method, errorMsg);
    
    // Don't show toast for liveness/readiness/health checks to prevent toast storms if backend is down
    // Also skip 404 errors for the `/latest` endpoint, which represent empty states.
    const isIgnoredError = url.includes('/health') || 
                          url.includes('/system/') || 
                          (url.includes('/latest') && error.response?.status === 404);
    if (!isIgnoredError) {
      toast.error(`${method} ${url}: ${errorMsg}`, {
        id: `${method}-${url}`, // prevent duplicate toasts for the same endpoint
        duration: 4000,
      });
    }
    
    return Promise.reject(error);
  }
);

export default client;
