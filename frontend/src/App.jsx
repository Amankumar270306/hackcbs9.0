import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';

import Header from './components/Header';
import Sidebar from './components/Sidebar';
import OverviewHeader from './components/OverviewHeader';
import MetricCards from './components/MetricCards';
import RiskDistribution from './components/RiskDistribution';
import AgentVelocity from './components/AgentVelocity';
import FindingsByCategory from './components/FindingsByCategory';
import PostureStatusDonut from './components/PostureStatusDonut';
import RecentAuditsTable from './components/RecentAuditsTable';
import EngineFooter from './components/EngineFooter';

import NewAuditModal from './components/NewAuditModal';
import AuditDetailsModal from './components/AuditDetailsModal';
import ExecutiveBriefingModal from './components/ExecutiveBriefingModal';
import AgentDebuggerModal from './components/AgentDebuggerModal';

function DashboardView() {
  const [activeNav, setActiveNav] = useState('overview');
  const [isNewAuditOpen, setIsNewAuditOpen] = useState(false);
  const [isBriefingOpen, setIsBriefingOpen] = useState(false);
  const [isDebuggerOpen, setIsDebuggerOpen] = useState(false);
  const [selectedAudit, setSelectedAudit] = useState(null);

  const handleAuditCreated = (newAudit) => {
    setSelectedAudit(newAudit);
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] text-slate-900 flex flex-col font-sans selection:bg-blue-100 selection:text-blue-700">
      {/* Top Navbar */}
      <Header
        onOpenNewAudit={() => setIsNewAuditOpen(true)}
        onOpenDebugger={() => setIsDebuggerOpen(true)}
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
          {/* Header section with active kubernetes sensor badge & date toggles */}
          <OverviewHeader
            onExportBriefing={() => setIsBriefingOpen(true)}
          />

          {/* 5 Top KPI Cards */}
          <MetricCards />

          {/* Middle Row: Risk Distribution & Agent Velocity */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-5">
            <RiskDistribution
              onExploreMatrix={() => setIsBriefingOpen(true)}
            />
            <AgentVelocity
              onSelectAgent={() => setIsDebuggerOpen(true)}
            />
          </div>

          {/* Second Row: Findings by Category & Posture Status Breakdown */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 sm:gap-5">
            <FindingsByCategory
              onConfigureGuardrails={() => alert('Opening Guardrails Configuration Engine...')}
            />
            <PostureStatusDonut
              onTriggerCheck={() => alert('Triggering instant multi-agent automated check...')}
            />
          </div>

          {/* Recent Audits Table */}
          <RecentAuditsTable
            onSelectAudit={(audit) => setSelectedAudit(audit)}
            onOpenNewAudit={() => setIsNewAuditOpen(true)}
          />

          {/* Engine Footer Banner */}
          <EngineFooter
            onOpenDebugger={() => setIsDebuggerOpen(true)}
          />
        </main>
      </div>

      {/* Modals & Dialogs */}
      <NewAuditModal
        isOpen={isNewAuditOpen}
        onClose={() => setIsNewAuditOpen(false)}
        onAuditCreated={handleAuditCreated}
      />

      <AuditDetailsModal
        audit={selectedAudit}
        onClose={() => setSelectedAudit(null)}
      />

      <ExecutiveBriefingModal
        isOpen={isBriefingOpen}
        onClose={() => setIsBriefingOpen(false)}
      />

      <AgentDebuggerModal
        isOpen={isDebuggerOpen}
        onClose={() => setIsDebuggerOpen(false)}
      />
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
