import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import StatusBanner from '../components/StatusBanner.jsx';
import DevPanel from '../components/DevPanel.jsx';
import { LayoutDashboard, Box, Settings, Menu, X, Cpu, Upload, LogOut, User } from 'lucide-react';
import CSVUploadModal from '../components/CSVUploadModal.jsx';

function getUsernameFromToken() {
  const token = localStorage.getItem("access_token");
  if (!token) return null;
  try {
    const payloadBase64 = token.split('.')[1];
    const decoded = JSON.parse(atob(payloadBase64));
    return decoded.sub;
  } catch (e) {
    console.error("Error decoding token:", e);
    return null;
  }
}

export default function DashboardLayout() {
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [csvModalOpen, setCsvModalOpen] = useState(false);
  const username = getUsernameFromToken();

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    navigate("/login");
  };

  const navItems = [
    { to: '/', label: 'Overview Dashboard', icon: LayoutDashboard },
    { to: '/assets', label: 'Asset Registry', icon: Box },
    { to: '/registry', label: 'Metadata Registry', icon: Settings },
  ];

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-bg-base text-primary">
      {/* Top Banner (Always Visible) */}
      <StatusBanner />

      <div className="flex flex-1 overflow-hidden relative">
        {/* Sidebar - Desktop */}
        <aside className="hidden md:flex flex-col w-64 bg-bg-surface border-r border-border-dark">
          <div className="flex items-center gap-2.5 px-6 py-5 border-b border-border-dark">
            <Cpu className="w-6 h-6 text-accent" />
            <span className="font-sans font-bold tracking-tight text-sm text-text-primary uppercase">
              Industrial AI
            </span>
          </div>

          <nav className="flex-1 px-4 py-4 space-y-1.5 overflow-y-auto">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2.5 rounded-md text-xs font-semibold tracking-wide transition-all border ${
                      isActive
                        ? 'bg-accent/10 border-accent/30 text-text-primary'
                        : 'border-transparent text-text-secondary hover:bg-bg-panel hover:text-text-primary'
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </NavLink>
              );
            })}
          </nav>
          
          <div className="px-4 py-4 border-t border-border-dark space-y-3">
            {username && (
              <div className="flex items-center gap-2 px-3 py-2 bg-bg-panel/40 border border-border-dark rounded-md text-xs text-text-secondary">
                <User className="w-4 h-4 text-accent shrink-0" />
                <span className="truncate">
                  Logged in as: <strong className="text-text-primary font-semibold">{username}</strong>
                </span>
              </div>
            )}
            
            <button
              onClick={() => setCsvModalOpen(true)}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-accent/10 border border-accent/30 text-text-primary text-xs font-semibold rounded-md hover:bg-accent/20 hover:border-accent/50 transition-all cursor-pointer"
            >
              <Upload className="w-4 h-4 text-accent" />
              Upload Telemetry CSV
            </button>

            <button
              onClick={handleLogout}
              className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-danger/10 border border-danger/30 text-danger text-xs font-semibold rounded-md hover:bg-danger/20 hover:border-danger/50 transition-all cursor-pointer"
            >
              <LogOut className="w-4 h-4" />
              Logout
            </button>

            <div className="text-[10px] text-text-muted font-mono text-center">
              v1.0.0 (FastAPI Core)
            </div>
          </div>
        </aside>

        {/* Sidebar - Mobile overlay */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-40 flex md:hidden bg-bg-base/80 backdrop-blur-sm">
            <aside className="w-64 bg-bg-surface border-r border-border-dark flex flex-col h-full animate-in slide-in-from-left duration-250">
              <div className="flex items-center justify-between px-6 py-5 border-b border-border-dark">
                <div className="flex items-center gap-2">
                  <Cpu className="w-5 h-5 text-accent" />
                  <span className="font-bold text-xs uppercase tracking-wider">Industrial AI</span>
                </div>
                <button
                  onClick={() => setMobileMenuOpen(false)}
                  className="p-1 text-text-secondary hover:text-text-primary cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <nav className="flex-1 px-4 py-4 space-y-1.5 overflow-y-auto">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-3 px-3 py-2.5 rounded-md text-xs font-semibold transition-all border ${
                          isActive
                            ? 'bg-accent/10 border-accent/30 text-text-primary'
                            : 'border-transparent text-text-secondary hover:bg-bg-panel hover:text-text-primary'
                        }`
                      }
                    >
                      <Icon className="w-4 h-4" />
                      {item.label}
                    </NavLink>
                  );
                })}
              </nav>

              <div className="px-4 py-4 border-t border-border-dark space-y-3">
                {username && (
                  <div className="flex items-center gap-2 px-3 py-2 bg-bg-panel/40 border border-border-dark rounded-md text-xs text-text-secondary">
                    <User className="w-4 h-4 text-accent shrink-0" />
                    <span className="truncate">
                      Logged in as: <strong className="text-text-primary font-semibold">{username}</strong>
                    </span>
                  </div>
                )}

                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    setCsvModalOpen(true);
                  }}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-accent/10 border border-accent/30 text-text-primary text-xs font-semibold rounded-md hover:bg-accent/20 transition-all cursor-pointer"
                >
                  <Upload className="w-4 h-4 text-accent" />
                  Upload Telemetry CSV
                </button>

                <button
                  onClick={() => {
                    setMobileMenuOpen(false);
                    handleLogout();
                  }}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-danger/10 border border-danger/30 text-danger text-xs font-semibold rounded-md hover:bg-danger/20 transition-all cursor-pointer"
                >
                  <LogOut className="w-4 h-4" />
                  Logout
                </button>
              </div>
            </aside>
            <div className="flex-1" onClick={() => setMobileMenuOpen(false)} />
          </div>
        )}

        {/* Main Work Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Mobile header controls */}
          <header className="flex md:hidden items-center justify-between px-4 py-3 bg-bg-surface border-b border-border-dark">
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-accent" />
              <span className="font-bold text-xs uppercase tracking-wider">Industrial Platform</span>
            </div>
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="p-1.5 bg-bg-panel border border-border-dark text-text-secondary rounded hover:text-text-primary cursor-pointer"
            >
              <Menu className="w-4 h-4" />
            </button>
          </header>

          {/* Page Container */}
          <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8 space-y-6">
            <Outlet />
          </main>
        </div>
      </div>

      {/* Developer Diagnostic Floating Widget */}
      <DevPanel />

      {/* Bulk CSV Upload Modal */}
      <CSVUploadModal isOpen={csvModalOpen} onClose={() => setCsvModalOpen(false)} />
    </div>
  );
}
