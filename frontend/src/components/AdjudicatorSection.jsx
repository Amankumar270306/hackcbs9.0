import React, { useState, useEffect } from 'react';
import {
  Scale,
  ShieldCheck,
  ShieldAlert,
  Play,
  RotateCw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  Search,
  Filter,
  Eye,
  Edit3,
  Check,
  X,
  FileText,
  Clock,
  Layers,
  ChevronRight,
  Info,
  ArrowRight,
  Lock,
  Database,
  Key,
  Shield,
  FileCode,
  Sliders,
  AlertCircle,
  GitCompare,
  TrendingUp,
  RefreshCw,
  History,
  MessageSquare
} from 'lucide-react';
import { adjudicationApi } from '../api/client';

export default function AdjudicatorSection({ audit }) {
  const orgId = audit.organization_id || audit.organizationId;
  const auditId = audit.id;

  // View navigation
  const [activeSubTab, setActiveSubTab] = useState('decisions'); // 'decisions', 'contradictions', 'runs'
  const [readiness, setReadiness] = useState(null);
  const [loadingReadiness, setLoadingReadiness] = useState(true);
  const [staleStatus, setStaleStatus] = useState(null);

  // Data lists
  const [decisions, setDecisions] = useState([]);
  const [contradictions, setContradictions] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loadingData, setLoadingData] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedOutcome, setSelectedOutcome] = useState('all');
  const [selectedReviewStatus, setSelectedReviewStatus] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const [selectedContraCategory, setSelectedContraCategory] = useState('all');
  const [selectedContraStatus, setSelectedContraStatus] = useState('all');

  // Drawers & Modals
  const [selectedDecision, setSelectedDecision] = useState(null);
  const [decisionDetail, setDecisionDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const [reviewModal, setReviewModal] = useState({ isOpen: false, action: null, decisionId: null, justification: '' });
  const [editModal, setEditModal] = useState({ isOpen: false, decision: null, summary: '', reasoning: '', outcomeStatus: '', confidence: 0.8, justification: '' });
  const [resolveContraModal, setResolveContraModal] = useState({ isOpen: false, contradictionId: null, status: 'resolved', notes: '' });

  // 1. Load Readiness & Stale Status
  const fetchStatusAndReadiness = async () => {
    try {
      setLoadingReadiness(true);
      const [rData, sData] = await Promise.all([
        adjudicationApi.getReadiness(orgId, auditId),
        adjudicationApi.getStaleStatus(orgId, auditId).catch(() => null),
      ]);
      setReadiness(rData);
      setStaleStatus(sData);
    } catch (err) {
      console.error('Failed fetching readiness:', err);
    } finally {
      setLoadingReadiness(false);
    }
  };

  // 2. Load Core Data
  const loadData = async () => {
    try {
      setLoadingData(true);
      const [dList, cList, rList] = await Promise.all([
        adjudicationApi.listDecisions(orgId, auditId, {
          category: selectedCategory,
          outcome: selectedOutcome,
          review_status: selectedReviewStatus,
          search: searchQuery,
        }),
        adjudicationApi.listContradictions(orgId, auditId, {
          category: selectedContraCategory,
          resolution_status: selectedContraStatus,
        }),
        adjudicationApi.listRuns(orgId, auditId),
      ]);
      setDecisions(dList || []);
      setContradictions(cList || []);
      setRuns(rList || []);
    } catch (err) {
      console.error('Failed loading adjudication data:', err);
    } finally {
      setLoadingData(false);
    }
  };

  useEffect(() => {
    fetchStatusAndReadiness();
  }, [orgId, auditId]);

  useEffect(() => {
    loadData();
  }, [orgId, auditId, selectedCategory, selectedOutcome, selectedReviewStatus, searchQuery, selectedContraCategory, selectedContraStatus]);

  // Load Decision Detail
  const openDecisionDrawer = async (decisionId) => {
    setSelectedDecision(decisionId);
    try {
      setLoadingDetail(true);
      const detail = await adjudicationApi.getDecision(orgId, auditId, decisionId);
      setDecisionDetail(detail);
    } catch (err) {
      console.error('Failed loading decision detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  // Trigger Adjudication Run
  const handleTriggerRun = async () => {
    try {
      setIsExecuting(true);
      await adjudicationApi.triggerRun(orgId, auditId, { model_name: 'gemini-1.5-flash', run_in_background: false });
      await fetchStatusAndReadiness();
      await loadData();
    } catch (err) {
      alert(`Adjudication execution failed: ${err.message || err}`);
    } finally {
      setIsExecuting(false);
    }
  };

  // Submit Review
  const handleSubmitReview = async () => {
    if (!reviewModal.justification || reviewModal.justification.trim().length < 3) {
      alert('A review justification of at least 3 characters is mandatory.');
      return;
    }
    try {
      await adjudicationApi.reviewDecision(orgId, auditId, reviewModal.decisionId, reviewModal.action, reviewModal.justification);
      setReviewModal({ isOpen: false, action: null, decisionId: null, justification: '' });
      if (selectedDecision) openDecisionDrawer(selectedDecision);
      loadData();
    } catch (err) {
      alert(`Failed to submit review: ${err.message || err}`);
    }
  };

  // Submit Edit
  const handleSubmitEdit = async () => {
    if (!editModal.justification || editModal.justification.trim().length < 3) {
      alert('A justification for modifying an adjudication decision is mandatory.');
      return;
    }
    try {
      await adjudicationApi.editDecision(orgId, auditId, editModal.decision.id, {
        summary: editModal.summary,
        reasoning: editModal.reasoning,
        outcome_status: editModal.outcomeStatus,
        confidence_score: parseFloat(editModal.confidence),
        justification: editModal.justification,
      });
      setEditModal({ isOpen: false, decision: null, summary: '', reasoning: '', outcomeStatus: '', confidence: 0.8, justification: '' });
      if (selectedDecision) openDecisionDrawer(selectedDecision);
      loadData();
    } catch (err) {
      alert(`Failed to save edit: ${err.message || err}`);
    }
  };

  // Submit Contradiction Resolution
  const handleResolveContradiction = async () => {
    if (!resolveContraModal.notes || resolveContraModal.notes.trim().length < 3) {
      alert('Resolution notes or reason for dismissal are mandatory.');
      return;
    }
    try {
      await adjudicationApi.resolveContradiction(orgId, auditId, resolveContraModal.contradictionId, resolveContraModal.status, resolveContraModal.notes);
      setResolveContraModal({ isOpen: false, contradictionId: null, status: 'resolved', notes: '' });
      loadData();
    } catch (err) {
      alert(`Failed resolving contradiction: ${err.message || err}`);
    }
  };

  const getOutcomeBadge = (outcome) => {
    const o = (outcome || '').toLowerCase();
    if (o.includes('supported') || o.includes('mitigated')) {
      return <span className="bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded text-[10px] font-bold">{outcome}</span>;
    }
    if (o.includes('partial')) {
      return <span className="bg-amber-50 text-amber-700 border border-amber-200 px-2 py-0.5 rounded text-[10px] font-bold">{outcome}</span>;
    }
    if (o.includes('insufficient') || o.includes('weakness') || o.includes('nonconformance')) {
      return <span className="bg-rose-50 text-rose-700 border border-rose-200 px-2 py-0.5 rounded text-[10px] font-bold">{outcome}</span>;
    }
    return <span className="bg-slate-100 text-slate-700 border border-slate-200 px-2 py-0.5 rounded text-[10px] font-bold">{outcome}</span>;
  };

  const getSeverityBadge = (severity) => {
    const s = (severity || 'medium').toLowerCase();
    if (s === 'critical') return <span className="bg-rose-600 text-white font-bold px-2 py-0.5 rounded text-[10px] uppercase">Critical</span>;
    if (s === 'high') return <span className="bg-rose-100 text-rose-800 border border-rose-300 font-bold px-2 py-0.5 rounded text-[10px] uppercase">High</span>;
    if (s === 'medium') return <span className="bg-amber-100 text-amber-800 border border-amber-300 font-bold px-2 py-0.5 rounded text-[10px] uppercase">Medium</span>;
    return <span className="bg-blue-100 text-blue-800 border border-blue-300 font-bold px-2 py-0.5 rounded text-[10px] uppercase">Low</span>;
  };

  return (
    <div className="space-y-6">
      {/* Stale Warning Banner */}
      {staleStatus && staleStatus.has_stale_decisions && (
        <div className="rounded-xl border border-amber-300 bg-amber-50/90 p-4 shadow-sm flex items-start justify-between">
          <div className="flex items-start space-x-3">
            <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 shrink-0" />
            <div>
              <h4 className="text-xs font-bold text-amber-900">Upstream Changes Detected — Adjudication Stale</h4>
              <p className="text-[11px] text-amber-800 mt-0.5">
                {staleStatus.stale_reasons.join(' ')} Re-run adjudication to synchronize consensus.
              </p>
            </div>
          </div>
          <button
            onClick={handleTriggerRun}
            disabled={isExecuting}
            className="flex items-center space-x-1.5 px-3 py-1.5 bg-amber-600 text-white rounded-lg text-xs font-bold hover:bg-amber-700 transition shadow-xs cursor-pointer shrink-0"
          >
            <RotateCw className={`h-3.5 w-3.5 ${isExecuting ? 'animate-spin' : ''}`} />
            <span>Re-run Consensus</span>
          </button>
        </div>
      )}

      {/* Top Header Card */}
      <div className="rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-5 shadow-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="p-1.5 bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 rounded-lg">
                <Scale className="h-5 w-5" />
              </span>
              <h2 className="text-base font-bold tracking-tight text-white">Adjudicator &amp; Multi-Agent Consensus</h2>
              <span className="bg-indigo-500/30 text-indigo-200 text-[10px] font-mono font-bold px-2 py-0.5 rounded border border-indigo-400/30">
                Milestone 7
              </span>
            </div>
            <p className="text-xs text-slate-300 max-w-2xl">
              Cross-agent arbitration layer reconciling Legal Analyst requirements, Adversarial Strategist threats, and Defence Auditor safeguards into an auditable consensus record.
            </p>
          </div>

          <div className="flex items-center space-x-3 shrink-0">
            <button
              onClick={handleTriggerRun}
              disabled={isExecuting || (readiness && !readiness.is_ready)}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl font-bold text-xs shadow-md transition cursor-pointer ${
                isExecuting || (readiness && !readiness.is_ready)
                  ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
                  : 'bg-indigo-600 hover:bg-indigo-500 text-white'
              }`}
            >
              {isExecuting ? (
                <>
                  <RotateCw className="h-4 w-4 animate-spin text-white" />
                  <span>Reconciling Agents...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-white text-white" />
                  <span>Run Adjudicator</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Readiness Preflight Checklist */}
        {readiness && (
          <div className="mt-4 pt-4 border-t border-slate-800 grid grid-cols-2 sm:grid-cols-4 gap-3 text-[11px]">
            <div className="flex items-center space-x-2">
              {readiness.has_legal_analyst_data ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              ) : (
                <HelpCircle className="h-3.5 w-3.5 text-slate-500 shrink-0" />
              )}
              <span className="text-slate-300">
                {readiness.approved_requirements_count} Approved Reqs ({readiness.requirements_count} Total)
              </span>
            </div>
            <div className="flex items-center space-x-2">
              {readiness.has_adversarial_strategist_data ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              ) : (
                <HelpCircle className="h-3.5 w-3.5 text-slate-500 shrink-0" />
              )}
              <span className="text-slate-300">
                {readiness.accepted_threats_count} Accepted Threats ({readiness.threats_count} Total)
              </span>
            </div>
            <div className="flex items-center space-x-2">
              {readiness.has_defence_auditor_data ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              ) : (
                <HelpCircle className="h-3.5 w-3.5 text-slate-500 shrink-0" />
              )}
              <span className="text-slate-300">{readiness.controls_count} Safeguards / Controls</span>
            </div>
            <div className="flex items-center space-x-2">
              {readiness.evidence_chunks_count > 0 ? (
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
              ) : (
                <HelpCircle className="h-3.5 w-3.5 text-slate-500 shrink-0" />
              )}
              <span className="text-slate-300">{readiness.evidence_chunks_count} Evidence Chunks</span>
            </div>
          </div>
        )}
      </div>

      {/* Sub-Tabs Switcher */}
      <div className="flex items-center justify-between border-b border-slate-200 pb-2">
        <div className="flex space-x-3 text-xs font-bold">
          <button
            onClick={() => setActiveSubTab('decisions')}
            className={`flex items-center space-x-1.5 pb-2 px-1 border-b-2 cursor-pointer transition ${
              activeSubTab === 'decisions'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Scale className="h-4 w-4" />
            <span>Consensus Decisions</span>
            <span className="bg-indigo-100 text-indigo-700 px-1.5 py-0.2 rounded text-[10px] font-bold">
              {decisions.length}
            </span>
          </button>

          <button
            onClick={() => setActiveSubTab('contradictions')}
            className={`flex items-center space-x-1.5 pb-2 px-1 border-b-2 cursor-pointer transition ${
              activeSubTab === 'contradictions'
                ? 'border-rose-600 text-rose-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <GitCompare className="h-4 w-4" />
            <span>Cross-Agent Contradictions</span>
            <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
              contradictions.filter(c => c.resolution_status === 'unresolved').length > 0
                ? 'bg-rose-100 text-rose-700 font-extrabold'
                : 'bg-slate-100 text-slate-600'
            }`}>
              {contradictions.length}
            </span>
          </button>

          <button
            onClick={() => setActiveSubTab('runs')}
            className={`flex items-center space-x-1.5 pb-2 px-1 border-b-2 cursor-pointer transition ${
              activeSubTab === 'runs'
                ? 'border-indigo-600 text-indigo-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <History className="h-4 w-4" />
            <span>Execution Runs</span>
            <span className="bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded text-[10px] font-bold">
              {runs.length}
            </span>
          </button>
        </div>

        <button
          onClick={loadData}
          disabled={loadingData}
          className="text-slate-400 hover:text-slate-600 p-1.5 rounded-lg hover:bg-slate-100 cursor-pointer"
          title="Refresh Data"
        >
          <RotateCw className={`h-4 w-4 ${loadingData ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* 1. DECISIONS EXPLORER */}
      {activeSubTab === 'decisions' && (
        <div className="space-y-4">
          {/* Filters Bar */}
          <div className="flex flex-wrap items-center gap-2 bg-slate-50 p-2.5 rounded-xl border border-slate-200 text-xs">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search consensus decisions by reasoning, keyword..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center space-x-1">
              <span className="text-[11px] font-bold text-slate-400">Category:</span>
              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-xs font-semibold focus:outline-hidden"
              >
                <option value="all">All Categories</option>
                <option value="requirement_compliance">Requirement Compliance</option>
                <option value="threat_mitigation">Threat Mitigation</option>
                <option value="control_effectiveness">Control Effectiveness</option>
                <option value="cross_cutting">Cross Cutting</option>
              </select>
            </div>

            <div className="flex items-center space-x-1">
              <span className="text-[11px] font-bold text-slate-400">Review:</span>
              <select
                value={selectedReviewStatus}
                onChange={(e) => setSelectedReviewStatus(e.target.value)}
                className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-xs font-semibold focus:outline-hidden"
              >
                <option value="all">All Statuses</option>
                <option value="pending_review">Pending Review</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
                <option value="edited">Edited</option>
                <option value="more_info_requested">More Info Requested</option>
              </select>
            </div>
          </div>

          {/* Decisions List */}
          {decisions.length === 0 ? (
            <div className="text-center py-12 rounded-xl border border-dashed border-slate-200 bg-slate-50/50">
              <Scale className="h-8 w-8 text-slate-300 mx-auto mb-2" />
              <h4 className="text-xs font-bold text-slate-700">No Consensus Decisions Found</h4>
              <p className="text-[11px] text-slate-400 mt-1 max-w-md mx-auto">
                Run the Adjudicator to reconcile Legal Analyst requirements, Adversarial Strategist threats, and Defence Auditor controls.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {decisions.map((d) => (
                <div
                  key={d.id}
                  onClick={() => openDecisionDrawer(d.id)}
                  className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs hover:border-indigo-300 hover:shadow-md transition cursor-pointer"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="space-y-1 flex-1">
                      <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                        <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                          {d.decision_category.replace('_', ' ').toUpperCase()}
                        </span>
                        {getOutcomeBadge(d.outcome_status)}
                        {d.is_provisional && (
                          <span className="bg-amber-100 text-amber-800 text-[10px] font-bold px-2 py-0.2 rounded border border-amber-300">
                            Provisional
                          </span>
                        )}
                        {d.requires_human_review && (
                          <span className="bg-rose-100 text-rose-800 text-[10px] font-bold px-2 py-0.2 rounded border border-rose-300">
                            Requires Review
                          </span>
                        )}
                        {d.is_stale && (
                          <span className="bg-amber-500 text-white text-[10px] font-bold px-1.5 py-0.2 rounded">
                            Stale
                          </span>
                        )}
                      </div>

                      <h4 className="text-xs font-bold text-slate-900 mt-1">{d.summary}</h4>
                      <p className="text-[11px] text-slate-600 line-clamp-2 mt-0.5">{d.reasoning}</p>
                    </div>

                    <div className="text-right shrink-0 space-y-1">
                      <div className="text-[10px] font-bold text-slate-400 uppercase">Confidence</div>
                      <div className="font-mono text-xs font-bold text-slate-900">
                        {Math.round(d.confidence_score * 100)}%
                      </div>
                      <div className="text-[10px] text-indigo-600 font-semibold flex items-center justify-end space-x-0.5 mt-2">
                        <span>Inspect Sources</span>
                        <ChevronRight className="h-3 w-3" />
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 2. CONTRADICTIONS EXPLORER */}
      {activeSubTab === 'contradictions' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between bg-slate-50 p-2.5 rounded-xl border border-slate-200 text-xs">
            <div className="flex items-center space-x-2">
              <span className="font-bold text-slate-700">Filter Status:</span>
              <select
                value={selectedContraStatus}
                onChange={(e) => setSelectedContraStatus(e.target.value)}
                className="bg-white border border-slate-200 rounded-lg px-2 py-1 text-xs font-semibold focus:outline-hidden"
              >
                <option value="all">All Contradictions</option>
                <option value="unresolved">Unresolved</option>
                <option value="resolved">Resolved</option>
                <option value="clarification_requested">Clarification Requested</option>
                <option value="dismissed">Dismissed</option>
              </select>
            </div>
            <div className="text-[11px] text-slate-500 font-medium">
              Detects conflicting statements and maturity discrepancies across agents.
            </div>
          </div>

          {contradictions.length === 0 ? (
            <div className="text-center py-12 rounded-xl border border-dashed border-slate-200 bg-slate-50/50">
              <CheckCircle2 className="h-8 w-8 text-emerald-400 mx-auto mb-2" />
              <h4 className="text-xs font-bold text-slate-700">Zero Contradictions Detected</h4>
              <p className="text-[11px] text-slate-400 mt-1 max-w-md mx-auto">
                Outputs from Legal Analyst, Adversarial Strategist, and Defence Auditor are mutually consistent.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {contradictions.map((c) => (
                <div
                  key={c.id}
                  className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs space-y-3"
                >
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center space-x-2">
                        {getSeverityBadge(c.severity)}
                        <span className="font-mono text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                          {c.contradiction_category.replace('_', ' ').toUpperCase()}
                        </span>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                          c.resolution_status === 'resolved'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border-amber-200'
                        }`}>
                          {c.resolution_status.replace('_', ' ').toUpperCase()}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-slate-900 mt-1">{c.title}</h4>
                      <p className="text-[11px] text-slate-600">{c.description}</p>
                    </div>

                    {c.resolution_status !== 'resolved' && (
                      <button
                        onClick={() => setResolveContraModal({ isOpen: true, contradictionId: c.id, status: 'resolved', notes: '' })}
                        className="px-3 py-1.5 bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 rounded-lg text-xs font-bold transition cursor-pointer"
                      >
                        Resolve Conflict
                      </button>
                    )}
                  </div>

                  {/* Conflicting Claims Comparison */}
                  {c.conflicting_claims && c.conflicting_claims.length >= 2 && (
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                      <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 text-[11px]">
                        <span className="font-bold text-slate-700 flex items-center space-x-1 mb-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-blue-500"></span>
                          <span>Claim A ({c.conflicting_claims[0].source_agent})</span>
                        </span>
                        <p className="text-slate-600 italic">"{c.conflicting_claims[0].claim}"</p>
                      </div>

                      <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3 text-[11px]">
                        <span className="font-bold text-slate-700 flex items-center space-x-1 mb-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-rose-500"></span>
                          <span>Claim B ({c.conflicting_claims[1].source_agent})</span>
                        </span>
                        <p className="text-slate-600 italic">"{c.conflicting_claims[1].claim}"</p>
                      </div>
                    </div>
                  )}

                  {/* Impact Summary */}
                  <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px]">
                    <div className="flex items-center space-x-1.5 text-slate-500">
                      <AlertCircle className="h-3.5 w-3.5 text-slate-400" />
                      <span><strong>Impact:</strong> {c.impact}</span>
                    </div>
                    {c.resolution_notes && (
                      <span className="text-emerald-700 font-medium">Notes: {c.resolution_notes}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 3. EXECUTION RUNS HISTORY */}
      {activeSubTab === 'runs' && (
        <div className="space-y-3">
          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 font-bold text-slate-500 uppercase text-[10px]">
                <tr>
                  <th className="py-2.5 px-4">Run ID &amp; Model</th>
                  <th className="py-2.5 px-4">Status</th>
                  <th className="py-2.5 px-4">Requirements</th>
                  <th className="py-2.5 px-4">Threats</th>
                  <th className="py-2.5 px-4">Decisions</th>
                  <th className="py-2.5 px-4">Contradictions</th>
                  <th className="py-2.5 px-4">Duration</th>
                  <th className="py-2.5 px-4">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {runs.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/50 transition">
                    <td className="py-2.5 px-4 font-mono font-bold text-slate-700">
                      {r.id.slice(0, 8)}... ({r.model_name})
                    </td>
                    <td className="py-2.5 px-4">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        r.status === 'completed'
                          ? 'bg-emerald-100 text-emerald-800'
                          : r.status === 'running'
                          ? 'bg-blue-100 text-blue-800 animate-pulse'
                          : 'bg-rose-100 text-rose-800'
                      }`}>
                        {r.status.toUpperCase()}
                      </span>
                    </td>
                    <td className="py-2.5 px-4">{r.requirements_processed_count}</td>
                    <td className="py-2.5 px-4">{r.threats_processed_count}</td>
                    <td className="py-2.5 px-4 font-bold text-indigo-700">{r.decisions_generated_count}</td>
                    <td className="py-2.5 px-4 font-bold text-rose-700">{r.contradictions_detected_count}</td>
                    <td className="py-2.5 px-4 font-mono text-[11px] text-slate-500">
                      {r.execution_duration_ms ? `${(r.execution_duration_ms / 1000).toFixed(1)}s` : '—'}
                    </td>
                    <td className="py-2.5 px-4 text-slate-400 font-mono text-[10px]">
                      {new Date(r.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* DECISION DETAIL DRAWER / MODAL */}
      {selectedDecision && decisionDetail && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-900/40 backdrop-blur-xs">
          <div className="w-full max-w-2xl h-full bg-white shadow-2xl flex flex-col animate-in slide-in-from-right duration-200">
            {/* Header */}
            <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs font-bold text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                    {decisionDetail.decision_category.replace('_', ' ').toUpperCase()}
                  </span>
                  {getOutcomeBadge(decisionDetail.outcome_status)}
                </div>
                <h3 className="text-sm font-bold text-slate-900">{decisionDetail.summary}</h3>
              </div>
              <button
                onClick={() => setSelectedDecision(null)}
                className="p-1 rounded-lg text-slate-400 hover:bg-slate-200 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Scrollable Body */}
            <div className="p-6 overflow-y-auto space-y-5 text-xs flex-1">
              {/* Detailed Reasoning */}
              <div>
                <h4 className="font-bold text-slate-800 uppercase text-[10px] tracking-wider mb-1.5">
                  Reconciliation Reasoning
                </h4>
                <div className="rounded-xl border border-slate-200 p-3 bg-slate-50/40 text-slate-700 leading-relaxed">
                  {decisionDetail.reasoning}
                </div>
              </div>

              {/* Confidence & Review Controls Bar */}
              <div className="rounded-xl border border-slate-200 bg-white p-3.5 flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Deterministic Confidence</span>
                  <div className="text-sm font-bold text-indigo-700 mt-0.5">
                    {Math.round(decisionDetail.confidence_score * 100)}%
                  </div>
                </div>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setReviewModal({ isOpen: true, action: 'approve', decisionId: decisionDetail.id, justification: '' })}
                    className="px-3 py-1.5 bg-emerald-600 text-white rounded-lg font-bold text-xs hover:bg-emerald-700 transition cursor-pointer flex items-center space-x-1"
                  >
                    <Check className="h-3.5 w-3.5" />
                    <span>Approve</span>
                  </button>

                  <button
                    onClick={() => setReviewModal({ isOpen: true, action: 'reject', decisionId: decisionDetail.id, justification: '' })}
                    className="px-3 py-1.5 bg-rose-600 text-white rounded-lg font-bold text-xs hover:bg-rose-700 transition cursor-pointer flex items-center space-x-1"
                  >
                    <X className="h-3.5 w-3.5" />
                    <span>Reject</span>
                  </button>

                  <button
                    onClick={() => setEditModal({
                      isOpen: true,
                      decision: decisionDetail,
                      summary: decisionDetail.summary,
                      reasoning: decisionDetail.reasoning,
                      outcomeStatus: decisionDetail.outcome_status,
                      confidence: decisionDetail.confidence_score,
                      justification: '',
                    })}
                    className="px-3 py-1.5 bg-slate-100 text-slate-700 border border-slate-200 rounded-lg font-bold text-xs hover:bg-slate-200 transition cursor-pointer flex items-center space-x-1"
                  >
                    <Edit3 className="h-3.5 w-3.5" />
                    <span>Edit</span>
                  </button>
                </div>
              </div>

              {/* Evidence Limitations & Missing Info */}
              {(decisionDetail.evidence_limitations || (decisionDetail.missing_information && decisionDetail.missing_information.length > 0)) && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/50 p-3.5 space-y-2">
                  <span className="font-bold text-amber-900 flex items-center space-x-1">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>Evidence Limitations &amp; Missing Telemetry</span>
                  </span>
                  {decisionDetail.evidence_limitations && (
                    <p className="text-[11px] text-amber-800">{decisionDetail.evidence_limitations}</p>
                  )}
                  {decisionDetail.missing_information && decisionDetail.missing_information.length > 0 && (
                    <ul className="list-disc pl-4 text-[11px] text-amber-800 space-y-0.5">
                      {decisionDetail.missing_information.map((m, idx) => (
                        <li key={idx}>{m}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* Verified Sources & Verbatim Citations */}
              <div>
                <h4 className="font-bold text-slate-800 uppercase text-[10px] tracking-wider mb-2">
                  Traceable Supporting Sources ({decisionDetail.sources ? decisionDetail.sources.length : 0})
                </h4>
                {decisionDetail.sources && decisionDetail.sources.length > 0 ? (
                  <div className="space-y-2.5">
                    {decisionDetail.sources.map((s) => (
                      <div key={s.id} className="rounded-lg border border-slate-200 p-3 bg-slate-50/60 space-y-1.5">
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-bold text-indigo-700 font-mono">
                            {s.source_agent.toUpperCase()} ({s.source_entity_type})
                          </span>
                          <span className="text-slate-400 font-mono text-[10px]">
                            {s.citation_reference} (p. {s.page_number || '1'})
                          </span>
                        </div>
                        {s.exact_excerpt && (
                          <div className="border-l-2 border-indigo-400 pl-2 text-[11px] italic text-slate-600 bg-white p-2 rounded">
                            "{s.exact_excerpt}"
                          </div>
                        )}
                        {!s.is_citation_valid && (
                          <div className="text-[10px] text-rose-600 font-bold">
                            Warning: Citation invalid - {s.citation_validation_notes}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-400 italic">No direct document chunks cited for this decision.</p>
                )}
              </div>

              {/* Review Audit History */}
              {decisionDetail.audit_history && decisionDetail.audit_history.length > 0 && (
                <div>
                  <h4 className="font-bold text-slate-800 uppercase text-[10px] tracking-wider mb-2">
                    Human Review History
                  </h4>
                  <div className="space-y-2">
                    {decisionDetail.audit_history.map((h) => (
                      <div key={h.id} className="rounded-lg border border-slate-100 p-2.5 bg-slate-50 text-[11px]">
                        <div className="flex items-center justify-between font-semibold">
                          <span className="text-slate-800">
                            {h.action.toUpperCase()} by {h.user_name || 'Auditor'}
                          </span>
                          <span className="text-slate-400 font-mono text-[10px]">
                            {new Date(h.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p className="text-slate-600 mt-1 italic">"{h.justification}"</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-4 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => setSelectedDecision(null)}
                className="px-4 py-1.5 rounded-lg bg-slate-200 text-slate-700 font-semibold text-xs hover:bg-slate-300 transition cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* HUMAN REVIEW ACTION MODAL */}
      {reviewModal.isOpen && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-900">
              Confirm {reviewModal.action === 'approve' ? 'Approval' : 'Rejection'}
            </h3>
            <p className="text-xs text-slate-600">
              Please enter your justification. This will be recorded permanently in the immutable audit trail.
            </p>
            <textarea
              rows={3}
              placeholder="Mandatory review justification (min 3 chars)..."
              value={reviewModal.justification}
              onChange={(e) => setReviewModal({ ...reviewModal, justification: e.target.value })}
              className="w-full p-2.5 border border-slate-200 rounded-lg text-xs focus:ring-1 focus:ring-indigo-500 focus:outline-hidden"
            />
            <div className="flex items-center justify-end space-x-2">
              <button
                onClick={() => setReviewModal({ isOpen: false, action: null, decisionId: null, justification: '' })}
                className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 font-bold text-xs hover:bg-slate-200 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitReview}
                className={`px-4 py-1.5 rounded-lg text-white font-bold text-xs cursor-pointer ${
                  reviewModal.action === 'approve' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700'
                }`}
              >
                Confirm {reviewModal.action === 'approve' ? 'Approval' : 'Rejection'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* EDIT DECISION MODAL */}
      {editModal.isOpen && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-900">Edit Consensus Decision</h3>
            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Decision Summary</label>
                <input
                  type="text"
                  value={editModal.summary}
                  onChange={(e) => setEditModal({ ...editModal, summary: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg text-xs"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Reasoning</label>
                <textarea
                  rows={3}
                  value={editModal.reasoning}
                  onChange={(e) => setEditModal({ ...editModal, reasoning: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg text-xs"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Outcome Status</label>
                <select
                  value={editModal.outcomeStatus}
                  onChange={(e) => setEditModal({ ...editModal, outcomeStatus: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg text-xs"
                >
                  <option value="supported_by_documented_evidence">supported_by_documented_evidence</option>
                  <option value="partially_supported">partially_supported</option>
                  <option value="insufficient_evidence">insufficient_evidence</option>
                  <option value="contradictory_evidence">contradictory_evidence</option>
                  <option value="documented_mitigations_supported">documented_mitigations_supported</option>
                  <option value="partially_mitigated">partially_mitigated</option>
                  <option value="insufficient_mitigation_evidence">insufficient_mitigation_evidence</option>
                  <option value="documented_control_weakness">documented_control_weakness</option>
                  <option value="requires_human_review">requires_human_review</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Mandatory Justification</label>
                <textarea
                  rows={2}
                  placeholder="Justify changes to this adjudication record..."
                  value={editModal.justification}
                  onChange={(e) => setEditModal({ ...editModal, justification: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setEditModal({ isOpen: false, decision: null, summary: '', reasoning: '', outcomeStatus: '', confidence: 0.8, justification: '' })}
                className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 font-bold text-xs hover:bg-slate-200 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitEdit}
                className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs cursor-pointer"
              >
                Save &amp; Record Audit Log
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RESOLVE CONTRADICTION MODAL */}
      {resolveContraModal.isOpen && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-white rounded-2xl shadow-xl p-5 space-y-4">
            <h3 className="text-sm font-bold text-slate-900">Resolve Cross-Agent Contradiction</h3>
            <p className="text-xs text-slate-600">
              Select resolution outcome and provide explanatory notes.
            </p>
            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Resolution Status</label>
                <select
                  value={resolveContraModal.status}
                  onChange={(e) => setResolveContraModal({ ...resolveContraModal, status: e.target.value })}
                  className="w-full p-2 border border-slate-200 rounded-lg text-xs"
                >
                  <option value="resolved">Resolved (Exception / Clarification accepted)</option>
                  <option value="clarification_requested">Clarification Requested from SecOps</option>
                  <option value="dismissed">Dismissed as Non-Applicable</option>
                  <option value="unresolved">Mark Unresolved</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Resolution Notes</label>
                <textarea
                  rows={3}
                  placeholder="Mandatory resolution justification..."
                  value={resolveContraModal.notes}
                  onChange={(e) => setResolveContraModal({ ...resolveContraModal, notes: e.target.value })}
                  className="w-full p-2.5 border border-slate-200 rounded-lg text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setResolveContraModal({ isOpen: false, contradictionId: null, status: 'resolved', notes: '' })}
                className="px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 font-bold text-xs hover:bg-slate-200 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleResolveContradiction}
                className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white font-bold text-xs cursor-pointer"
              >
                Confirm Resolution
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
