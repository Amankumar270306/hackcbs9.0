import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';

import Header from './components/Header';
import Sidebar from './components/Sidebar';
import ReportHubWorkspace from './components/ReportHubWorkspace';
import RegulatoryKnowledgeSection from './components/RegulatoryKnowledgeSection';
import NewAuditModal from './components/NewAuditModal';
import AuditDetailsModal from './components/AuditDetailsModal';

function DashboardView() {
  const [activeNav, setActiveNav] = useState('overview');
  const [isNewAuditOpen, setIsNewAuditOpen] = useState(false);
  const [selectedAudit, setSelectedAudit] = useState(null);

  const handleAuditCreated = (newAudit) => {
    setSelectedAudit(newAudit);
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 flex flex-col font-sans selection:bg-blue-100 selection:text-blue-700">
      {/* Top Navbar */}
      <Header
        onOpenNewAudit={() => setIsNewAuditOpen(true)}
      />

      <div className="flex flex-1">
        {/* Left Sidebar */}
        <Sidebar
          activeNav={activeNav}
          setActiveNav={setActiveNav}
          onOpenNewAudit={() => setIsNewAuditOpen(true)}
        />

        {/* Main Dashboard Workspace */}
        <main className="flex-1 p-4 sm:p-6 lg:p-7 max-w-[1720px] mx-auto w-full space-y-6">
          {activeNav === 'regulatory' ? (
            <RegulatoryKnowledgeSection />
          ) : (
            <ReportHubWorkspace />
          )}
        </main>
      </div>

      {/* New Audit Modal */}
      <NewAuditModal
        isOpen={isNewAuditOpen}
        onClose={() => setIsNewAuditOpen(false)}
        onAuditCreated={handleAuditCreated}
      />

      {/* Audit Details Modal (if opened) */}
      {selectedAudit && (
        <AuditDetailsModal
          audit={selectedAudit}
          onClose={() => setSelectedAudit(null)}
        />
      )}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <DashboardView />
              </ProtectedRoute>
            }
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
