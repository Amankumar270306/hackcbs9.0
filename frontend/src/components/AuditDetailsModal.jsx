import React, { useState, useEffect } from 'react';
import { 
  X, 
  ShieldAlert, 
  CheckCircle2, 
  Bot, 
  Terminal, 
  GitPullRequest, 
  Clock, 
  Server,
  Layers, 
  ArrowRight,
  FileText,
  Shield,
  ShieldCheck,
  Scale,
  FileCheck
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { auditApi } from '../api/client';
import AuditDocumentsSection from './AuditDocumentsSection';
import AuditRequirementsTab from './AuditRequirementsTab';
import ThreatAnalysisSection from './ThreatAnalysisSection';
import DefenceAuditorSection from './DefenceAuditorSection';
import AdjudicatorSection from './AdjudicatorSection';
import ReportGeneratorSection from './ReportGeneratorSection';

export default function AuditDetailsModal({ audit, onClose }) {
  if (!audit) return null;

  const { activeOrg } = useAuth();
  const orgId = activeOrg?.organization_id || activeOrg?.id;

  const [activeTab, setActiveTab] = useState('documents'); // default to 'documents' to showcase Milestone 3
  const [docCount, setDocCount] = useState(audit.document_count || 0);

  // Normalize audit ID to always use the real database UUID
  const initialRealId = audit.rawId || (audit.id && !audit.id.startsWith('AUD-') ? audit.id : null);
  const [realId, setRealId] = useState(initialRealId);

  useEffect(() => {
    if (audit.rawId) {
      setRealId(audit.rawId);
    } else if (audit.id && !audit.id.startsWith('AUD-')) {
      setRealId(audit.id);
    } else if (orgId && audit.id && audit.id.startsWith('AUD-')) {
      auditApi.list(orgId).then((res) => {
        const items = res.items || [];
        const prefix = audit.id.replace('AUD-2024-', '').toLowerCase();
        const match = items.find(
          (a) =>
            a.id.toLowerCase().startsWith(prefix) ||
            a.name === (audit.targetName || audit.name)
        );
        if (match) {
          setRealId(match.id);
        }
      }).catch(console.warn);
    }
  }, [audit, orgId]);

  const effectiveId = realId || audit.rawId || audit.id;
  const displayId = audit.displayId || (audit.id && audit.id.startsWith('AUD-') ? audit.id : (effectiveId ? `AUD-2024-${effectiveId.slice(0, 4).toUpperCase()}` : audit.id));

  const normalizedAudit = {
    ...audit,
    id: effectiveId,
    rawId: effectiveId,
    displayId: displayId,
    organization_id: audit.organization_id || orgId,
    organizationId: audit.organization_id || orgId,
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
      <div className="w-full max-w-5xl max-h-[92vh] flex flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl animate-in fade-in zoom-in-95 duration-200 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-white z-10 shrink-0">
          <div className="flex items-center space-x-3">
            <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-md border border-blue-200">
              {displayId}
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">{audit.targetName || audit.name}</h3>
              <p className="text-[11px] text-slate-400 font-mono">{audit.targetSub || audit.application_name || 'Production Environment'}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Tab Switcher */}
        <div className="flex border-b border-slate-200 px-6 bg-slate-50/70 text-xs font-semibold gap-6 shrink-0">
          <button
            onClick={() => setActiveTab('documents')}
            className={`py-3 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeTab === 'documents'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <FileText className="h-4 w-4" />
            <span>Audit Documents &amp; Evidence</span>
            <span className="bg-blue-100 text-blue-700 px-1.5 py-0.2 rounded text-[10px] font-bold">
              {docCount}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('requirements')}
            className={`py-3 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeTab === 'requirements'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Shield className="h-4 w-4" />
            <span>Regulatory Requirements</span>
          </button>

          <button
            onClick={() => setActiveTab('threats')}
            className={`py-3 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeTab === 'threats'
                ? 'border-rose-600 text-rose-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <ShieldAlert className="h-4 w-4" />
            <span>Threat Analysis (STRIDE)</span>
          </button>

          <button
            onClick={() => setActiveTab('defence')}
            className={`py-3 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeTab === 'defence'
                ? 'border-emerald-600 text-emerald-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <ShieldCheck className="h-4 w-4" />
            <span>Defence Auditor &amp; Controls</span>
          </button>

          <button
            onClick={() => setActiveTab('adjudicator')}
            className={`py-3 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeTab === 'adjudicator' || activeTab === 'consensus'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Scale className="h-4 w-4" />
            <span>Adjudicator &amp; Consensus</span>
          </button>

          <button
            onClick={() => setActiveTab('reports')}
            className={`py-3 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeTab === 'reports'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <FileCheck className="h-4 w-4" />
            <span>Compliance Report</span>
          </button>
        </div>

        {/* Modal Scrollable Body */}
        <div className="p-6 overflow-y-auto space-y-5 text-xs flex-1">
          {activeTab === 'documents' ? (
            <AuditDocumentsSection
              audit={normalizedAudit}
              onDocumentCountChange={(cnt) => setDocCount(cnt)}
            />
          ) : activeTab === 'requirements' ? (
            <AuditRequirementsTab audit={normalizedAudit} />
          ) : activeTab === 'threats' ? (
            <ThreatAnalysisSection audit={normalizedAudit} />
          ) : activeTab === 'defence' ? (
            <DefenceAuditorSection audit={normalizedAudit} />
          ) : activeTab === 'adjudicator' || activeTab === 'consensus' ? (
            <AdjudicatorSection audit={normalizedAudit} />
          ) : (
            <ReportGeneratorSection audit={normalizedAudit} />
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end border-t border-slate-100 px-6 py-3 bg-slate-50 shrink-0">
          <button
            onClick={onClose}
            className="rounded-lg bg-slate-200 px-4 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-300 transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
