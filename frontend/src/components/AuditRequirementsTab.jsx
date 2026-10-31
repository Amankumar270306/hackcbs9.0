import React, { useState, useEffect } from 'react';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  Plus,
  Trash2,
  FileSearch,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  BookOpen,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { regulatoryApi } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function AuditRequirementsTab({ audit }) {
  const { activeOrg } = useAuth();
  const orgId = activeOrg?.organization_id;
  const auditId = audit?.id;

  const [auditReqs, setAuditReqs] = useState([]);
  const [approvedReqs, setApprovedReqs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isMapping, setIsMapping] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [selectedReqIds, setSelectedReqIds] = useState([]);
  const [evidenceModalReq, setEvidenceModalReq] = useState(null);
  const [suggestedEvidence, setSuggestedEvidence] = useState([]);
  const [isLoadingEvidence, setIsLoadingEvidence] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const loadData = async () => {
    if (!orgId || !auditId) return;
    setIsLoading(true);
    setErrorMessage('');
    try {
      const [mappedRes, approvedRes] = await Promise.all([
        regulatoryApi.listAuditRequirements(orgId, auditId),
        regulatoryApi.listRequirements({ review_status: 'approved', limit: 100 }),
      ]);
      setAuditReqs(mappedRes || []);
      setApprovedReqs(approvedRes?.items || []);
    } catch (err) {
      setErrorMessage(err.message || 'Failed to load requirements.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [orgId, auditId]);

  const handleMapRequirements = async () => {
    if (selectedReqIds.length === 0) return;
    setIsMapping(true);
    try {
      await regulatoryApi.mapRequirementsToAudit(orgId, auditId, selectedReqIds);
      setShowAddModal(false);
      setSelectedReqIds([]);
      await loadData();
    } catch (err) {
      alert(err.message || 'Failed to map requirements.');
    } finally {
      setIsMapping(false);
    }
  };

  const handleUpdateStatus = async (requirementId, status) => {
    try {
      await regulatoryApi.updateAuditRequirement(orgId, auditId, requirementId, status);
      await loadData();
    } catch (err) {
      alert(err.message || 'Failed to update applicability status.');
    }
  };

  const handleRemoveRequirement = async (requirementId) => {
    if (!confirm('Remove this requirement from the current audit?')) return;
    try {
      await regulatoryApi.removeAuditRequirement(orgId, auditId, requirementId);
      await loadData();
    } catch (err) {
      alert(err.message || 'Failed to remove requirement.');
    }
  };

  const handleOpenEvidence = async (req) => {
    setEvidenceModalReq(req);
    setIsLoadingEvidence(true);
    try {
      const suggestions = await regulatoryApi.suggestAuditEvidence(orgId, auditId, req.id);
      setSuggestedEvidence(suggestions || []);
    } catch (err) {
      console.error(err);
      setSuggestedEvidence([]);
    } finally {
      setIsLoadingEvidence(false);
    }
  };

  // Filter out already mapped requirements for the add modal
  const mappedIds = new Set(auditReqs.map((m) => m.requirement_id));
  const availableToAdd = approvedReqs.filter((r) => !mappedIds.has(r.id));

  return (
    <div className="space-y-5">
      {/* Action Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
        <div>
          <h4 className="text-xs font-bold text-slate-800 flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            Audit Regulatory Requirements ({auditReqs.length})
          </h4>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Approved compliance obligations mapped from the Regulatory Knowledge Base to this assessment.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 rounded-lg transition-colors cursor-pointer"
            title="Refresh"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-xs font-semibold shadow-xs transition-colors cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Map Requirements</span>
          </button>
        </div>
      </div>

      {errorMessage && (
        <div className="p-3 bg-rose-50 border border-rose-200 text-rose-700 rounded-lg text-xs">
          {errorMessage}
        </div>
      )}

      {/* Mapped Requirements Table */}
      {isLoading ? (
        <div className="py-12 text-center text-slate-400 text-xs">
          <RefreshCw className="h-6 w-6 animate-spin mx-auto mb-2 text-blue-500" />
          Loading mapped regulatory requirements...
        </div>
      ) : auditReqs.length === 0 ? (
        <div className="py-12 text-center border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50">
          <BookOpen className="h-8 w-8 text-slate-300 mx-auto mb-2" />
          <h5 className="text-xs font-bold text-slate-700">No Regulatory Requirements Mapped</h5>
          <p className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto">
            Attach approved regulatory requirements extracted by Legal Analyst to begin compliance gap evaluation.
          </p>
          <button
            onClick={() => setShowAddModal(true)}
            className="mt-3 inline-flex items-center gap-1 bg-blue-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold hover:bg-blue-700 cursor-pointer"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Select Requirements</span>
          </button>
        </div>
      ) : (
        <div className="border border-slate-200 rounded-xl overflow-hidden divide-y divide-slate-100 bg-white">
          {auditReqs.map((mapping) => {
            const req = mapping.requirement || {};
            const isApplicable = mapping.applicability_status === 'applicable';
            const isRequiresReview = mapping.applicability_status === 'requires_review';

            return (
              <div key={mapping.id} className="p-4 hover:bg-slate-50/70 transition-colors">
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1.5 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono text-[11px] font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                        {req.requirement_code || req.identifier || 'REQ'}
                      </span>
                      <span className="font-bold text-slate-800 text-xs">{req.title || 'Regulatory Obligation'}</span>
                      <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded font-medium">
                        {req.framework || 'Framework'}
                      </span>
                      <span className="text-[10px] bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded font-medium">
                        {req.category || 'General'}
                      </span>
                      <span
                        className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                          req.obligation_type === 'mandatory'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}
                      >
                        {req.obligation_type || 'mandatory'}
                      </span>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed">
                      {req.requirement_statement || req.description}
                    </p>

                    {req.source_excerpt && (
                      <div className="bg-slate-50 border-l-2 border-slate-300 p-2 text-[11px] text-slate-500 italic font-serif">
                        "{req.source_excerpt}" — {req.source_section ? `[${req.source_section}]` : ''} Pg {req.source_page || 'N/A'}
                      </div>
                    )}
                  </div>

                  {/* Actions & Applicability Toggle */}
                  <div className="flex flex-col sm:flex-row items-end sm:items-center gap-2 shrink-0">
                    <select
                      value={mapping.applicability_status}
                      onChange={(e) => handleUpdateStatus(mapping.requirement_id, e.target.value)}
                      className={`text-xs font-semibold px-2.5 py-1 rounded-lg border cursor-pointer ${
                        isApplicable
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                          : isRequiresReview
                          ? 'bg-amber-50 text-amber-700 border-amber-300'
                          : 'bg-slate-100 text-slate-600 border-slate-300'
                      }`}
                    >
                      <option value="applicable">Applicable</option>
                      <option value="requires_review">Requires Review</option>
                      <option value="not_applicable">Not Applicable</option>
                    </select>

                    <button
                      onClick={() => handleOpenEvidence(req)}
                      className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 bg-blue-50 hover:bg-blue-100 px-2.5 py-1 rounded-lg font-medium transition-colors cursor-pointer border border-blue-200"
                      title="View suggested audit evidence"
                    >
                      <FileSearch className="h-3.5 w-3.5" />
                      <span>Evidence</span>
                    </button>

                    <button
                      onClick={() => handleRemoveRequirement(mapping.requirement_id)}
                      className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition-colors cursor-pointer"
                      title="Remove from audit"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Map Requirements Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Map Regulatory Requirements</h3>
                <p className="text-[11px] text-slate-500">Select approved requirements from the knowledge base to add to this audit.</p>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto flex-1 space-y-3">
              {availableToAdd.length === 0 ? (
                <div className="py-8 text-center text-slate-400 text-xs">
                  No additional approved requirements available to map.
                </div>
              ) : (
                availableToAdd.map((r) => {
                  const isSelected = selectedReqIds.includes(r.id);
                  return (
                    <label
                      key={r.id}
                      className={`flex items-start gap-3 p-3 rounded-xl border transition-colors cursor-pointer ${
                        isSelected ? 'bg-blue-50/70 border-blue-300' : 'bg-white border-slate-200 hover:bg-slate-50'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => {
                          setSelectedReqIds((prev) =>
                            prev.includes(r.id) ? prev.filter((id) => id !== r.id) : [...prev, r.id]
                          );
                        }}
                        className="mt-1 rounded text-blue-600 focus:ring-blue-500 cursor-pointer"
                      />
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[10px] font-bold text-blue-700 bg-blue-100/60 px-1.5 py-0.5 rounded">
                            {r.requirement_code || r.identifier}
                          </span>
                          <span className="font-bold text-slate-800 text-xs">{r.title}</span>
                          <span className="text-[10px] text-slate-500">({r.framework})</span>
                        </div>
                        <p className="text-[11px] text-slate-600">{r.requirement_statement || r.description}</p>
                      </div>
                    </label>
                  );
                })
              )}
            </div>

            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <span className="text-xs text-slate-500">
                {selectedReqIds.length} requirement(s) selected
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-white cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  onClick={handleMapRequirements}
                  disabled={selectedReqIds.length === 0 || isMapping}
                  className="px-4 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700 disabled:opacity-50 cursor-pointer"
                >
                  {isMapping ? 'Mapping...' : 'Confirm Mapping'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Suggested Evidence Modal */}
      {evidenceModalReq && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-xl max-h-[80vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <FileSearch className="h-4 w-4 text-blue-600" />
                  Suggested Audit Evidence
                </h3>
                <p className="text-[11px] text-slate-500 font-mono">
                  {evidenceModalReq.requirement_code || evidenceModalReq.identifier}: {evidenceModalReq.title}
                </p>
              </div>
              <button
                onClick={() => setEvidenceModalReq(null)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-3">
              {isLoadingEvidence ? (
                <div className="py-8 text-center text-slate-400 text-xs">
                  <RefreshCw className="h-5 w-5 animate-spin mx-auto mb-2 text-blue-500" />
                  Analyzing audit documents for matching evidence...
                </div>
              ) : suggestedEvidence.length === 0 ? (
                <div className="py-8 text-center text-slate-400 text-xs">
                  No matching uploaded audit documents found. Upload evidence files under the "Audit Documents" tab.
                </div>
              ) : (
                suggestedEvidence.map((ev, i) => (
                  <div key={i} className="p-3 bg-slate-50 rounded-xl border border-slate-200 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-slate-800">{ev.filename}</span>
                      <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                        {Math.round(ev.relevance_score * 100)}% match
                      </span>
                    </div>
                    {ev.matched_keywords && ev.matched_keywords.length > 0 && (
                      <div className="flex items-center gap-1 flex-wrap text-[10px] text-slate-500">
                        <span>Keywords:</span>
                        {ev.matched_keywords.map((kw, j) => (
                          <span key={j} className="bg-white border border-slate-200 px-1.5 py-0.5 rounded text-slate-700">
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => setEvidenceModalReq(null)}
                className="px-4 py-1.5 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-900 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

