import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ShieldCheck, Loader2 } from 'lucide-react';

export default function ProtectedRoute({ children }) {
  const { isAuthenticated, isLoading } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#F8FAFC] flex flex-col items-center justify-center space-y-4">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-md ring-4 ring-emerald-500/20 animate-pulse">
          <ShieldCheck className="h-7 w-7" />
        </div>
        <div className="flex items-center space-x-2 text-slate-600 font-medium text-sm">
          <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
          <span>Verifying Compliance Sentinel session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}

