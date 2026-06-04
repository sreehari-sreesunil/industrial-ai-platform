import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { Cpu, AlertCircle, Loader2 } from "lucide-react";

import { login } from "../api/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const token = localStorage.getItem("access_token");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // If already authenticated, redirect away from the login page
  if (token) {
    return <Navigate to="/" replace />;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!username || !password) return;

    setLoading(true);
    setError("");

    try {
      const result = await login(username, password);
      localStorage.setItem("access_token", result.access_token);
      navigate("/");
    } catch (err) {
      console.error("Login error:", err);
      let errorMsg = "Network failure";
      
      if (err.response) {
        if (err.response.status === 401 || err.response.status === 400) {
          errorMsg = "Invalid credentials";
        } else {
          errorMsg = `Server error: ${err.response.status}`;
        }
      } else if (err.request) {
        errorMsg = "Backend unavailable";
      } else {
        errorMsg = err.message || "Network failure";
      }
      
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-base p-4 font-sans">
      <div className="w-full max-w-md bg-bg-surface border border-border-dark p-8 rounded-xl shadow-2xl space-y-6">
        {/* Brand / Logo */}
        <div className="flex flex-col items-center text-center space-y-2">
          <div className="w-12 h-12 bg-accent/10 border border-accent/30 rounded-xl flex items-center justify-center">
            <Cpu className="w-6 h-6 text-accent" />
          </div>
          <h1 className="text-xl font-bold tracking-tight text-text-primary uppercase">
            Industrial AI Observability
          </h1>
          <p className="text-xs text-text-secondary max-w-xs">
            Sign in to access real-time telemetry, assets schema, and device status.
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-danger/10 border border-danger/30 text-danger text-xs font-semibold px-4 py-3 rounded-lg flex items-center gap-2 animate-in fade-in duration-200">
            <AlertCircle className="w-4 h-4 shrink-0 text-danger" />
            <span>{error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={loading}
              placeholder="Enter your username"
              className="w-full bg-bg-input border border-border-dark text-text-primary focus:border-accent focus:ring-1 focus:ring-accent rounded-lg px-4 py-3 text-sm transition-all outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              required
            />
          </div>

          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-text-secondary uppercase tracking-wider">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              placeholder="Enter your password"
              className="w-full bg-bg-input border border-border-dark text-text-primary focus:border-accent focus:ring-1 focus:ring-accent rounded-lg px-4 py-3 text-sm transition-all outline-none disabled:opacity-50 disabled:cursor-not-allowed"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading || !username.trim() || !password.trim()}
            className="w-full mt-2 flex items-center justify-center gap-2 py-3 bg-accent text-text-primary hover:bg-accent-hover active:bg-accent/80 transition-all font-semibold rounded-lg text-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-text-primary" />
                Signing in...
              </>
            ) : (
              "Sign In"
            )}
          </button>
        </form>
      </div>
    </div>
  );
}