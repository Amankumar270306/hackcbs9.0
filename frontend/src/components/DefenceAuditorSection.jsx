import React, { useState, useEffect } from 'react';
import {
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
  AlertCircle
} from 'lucide-react';
import { defenceApi } from '../api/client';

export default function DefenceAuditorSection({ audit }) {
  const orgId = audit.organization_id;
  const auditId = audit.id;

  // View state
  const [activeSubTab, setActiveSubTab] = useState('controls'); // 'controls', 'findings', 'runs'
  const [readiness, setReadiness] = useState(null);
  const [loadingReadiness, setLoadingReadiness] = useState(true);

  // Data lists
  const [controls, setControls] = useState([]);
  const [findings, setFindings] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loadingData, setLoadingData] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  // Filters
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [selectedMaturity, setSelectedMaturity] = useState('all');
  const [selectedImplStatus, setSelectedImplStatus] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  const [selectedFindingCategory, setSelectedFindingCategory] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');

  // Drawers & Modals
  const [selectedControl, setSelectedControl] = useState(null);
  const [controlDetail, setControlDetail] = useState(null);
  const [loadingControlDetail, setLoadingControlDetail] = useState(false);

  const [selectedFinding, setSelectedFinding] = useState(null);
  const [findingDetail, setFindingDetail] = useState(null);
  const [loadingFindingDetail, setLoadingFindingDetail] = useState(false);

  // Rejection modal
  const [rejectingItem, setRejectingItem] = useState(null); // { type: 'control' | 'finding', id: string }
  const [rejectReason, setRejectReason] = useState('');
  const [submittingAction, setSubmittingAction] = useState(false);

  // Edit modal
  const [editingItem, setEditingItem] = useState(null);
  const [editFormData, setEditFormData] = useState({});

  useEffect(() => {
    loadReadiness();
    loadAllData();
  }, [auditId]);

  const loadReadiness = async () => {
    try {
      setLoadingReadiness(true);
      const res = await defenceApi.checkReadiness(orgId, auditId);
      setReadiness(res);
    } catch (err) {
      console.error('Failed to load defence readiness:', err);
    } finally {
      setLoadingReadiness(false);
    }
  };

  const loadAllData = async () => {
    try {
      setLoadingData(true);
      const [ctrlsRes, findsRes, runsRes] = await Promise.all([
        defenceApi.listControls(orgId, auditId),
        defenceApi.listFindings(orgId, auditId),
        defenceApi.listRuns(orgId, auditId),
      ]);
      setControls(ctrlsRes || []);
      setFindings(findsRes || []);
      setRuns(runsRes || []);
    } catch (err) {
      console.error('Failed to load defence data:', err);
    } finally {
      setLoadingData(false);
    }
  };

  const handleTriggerAnalysis = async () => {
    try {
      setIsExecuting(true);
      await defenceApi.triggerAnalysis(orgId, auditId, {
        model_name: 'gemini-1.5-flash',
        run_in_background: false,
      });
      await loadAllData();
      await loadReadiness();
    } catch (err) {
      alert(`Defence Analysis failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsExecuting(false);
    }
  };

  const openControlDetail = async (ctrl) => {
    setSelectedControl(ctrl);
    try {
      setLoadingControlDetail(true);
      const detail = await defenceApi.getControlDetail(orgId, auditId, ctrl.id);
      setControlDetail(detail);
    } catch (err) {
      console.error('Failed to load control detail:', err);
    } finally {
      setLoadingControlDetail(false);
    }
  };

  const openFindingDetail = async (find) => {
    setSelectedFinding(find);
    try {
      setLoadingFindingDetail(true);
      const detail = await defenceApi.getFindingDetail(orgId, auditId, find.id);
      setFindingDetail(detail);
    } catch (err) {
      console.error('Failed to load finding detail:', err);
    } finally {
      setLoadingFindingDetail(false);
    }
  };

  const handleReviewAction = async (type, id, action) => {
    if (action === 'reject') {
      setRejectingItem({ type, id });
      setRejectReason('');
      return;
    }

    try {
      setSubmittingAction(true);
      if (type === 'control') {
        await defenceApi.reviewControl(orgId, auditId, id, action);
        if (selectedControl && selectedControl.id === id) {
          const updated = await defenceApi.getControlDetail(orgId, auditId, id);
          setControlDetail(updated);
        }
      } else {
        await defenceApi.reviewFinding(orgId, auditId, id, action);
        if (selectedFinding && selectedFinding.id === id) {
          const updated = await defenceApi.getFindingDetail(orgId, auditId, id);
          setFindingDetail(updated);
        }
      }
      await loadAllData();
    } catch (err) {
      alert(`Action failed: ${err.message}`);
    } finally {
      setSubmittingAction(false);
    }
  };

  const submitRejection = async () => {
    if (!rejectReason.trim()) {
      alert('A documented reason is mandatory when rejecting.');
      return;
    }
    try {
      setSubmittingAction(true);
      if (rejectingItem.type === 'control') {
        await defenceApi.reviewControl(orgId, auditId, rejectingItem.id, 'reject', rejectReason);
        if (selectedControl && selectedControl.id === rejectingItem.id) {
          const updated = await defenceApi.getControlDetail(orgId, auditId, rejectingItem.id);
          setControlDetail(updated);
        }
      } else {
        await defenceApi.reviewFinding(orgId, auditId, rejectingItem.id, 'reject', rejectReason);
        if (selectedFinding && selectedFinding.id === rejectingItem.id) {
          const updated = await defenceApi.getFindingDetail(orgId, auditId, rejectingItem.id);
          setFindingDetail(updated);
        }
      }
      setRejectingItem(null);
      await loadAllData();
    } catch (err) {
      alert(`Rejection failed: ${err.message}`);
    } finally {
      setSubmittingAction(false);
    }
  };

  const openEditModal = (type, item) => {
    setEditingItem({ type, id: item.id });
    if (type === 'control') {
      setEditFormData({
        name: item.name || '',
        description: item.description || '',
        category: item.category || '',
        implementation_status: item.implementation_status || 'documented',
        operational_status: item.operational_status || 'unverified',
        evidence_maturity: item.evidence_maturity || 'policy',
        reason: '',
      });
    } else {
      setEditFormData({
        title: item.title || '',
        description: item.description || '',
        finding_category: item.finding_category || 'documentation_gap',
        likelihood_score: item.likelihood_score || 3,
        impact_score: item.impact_score || 3,
        remediation_recommendation: item.remediation_recommendation || '',
        reason: '',
      });
    }
  };

  const submitEdit = async () => {
    try {
      setSubmittingAction(true);
      if (editingItem.type === 'control') {
        await defenceApi.editControl(orgId, auditId, editingItem.id, editFormData);
        if (selectedControl && selectedControl.id === editingItem.id) {
          const updated = await defenceApi.getControlDetail(orgId, auditId, editingItem.id);
          setControlDetail(updated);
        }
      } else {
        await defenceApi.editFinding(orgId, auditId, editingItem.id, editFormData);
        if (selectedFinding && selectedFinding.id === editingItem.id) {
          const updated = await defenceApi.getFindingDetail(orgId, auditId, editingItem.id);
          setFindingDetail(updated);
        }
      }
      setEditingItem(null);
      await loadAllData();
    } catch (err) {
      alert(`Edit failed: ${err.message}`);
    } finally {
      setSubmittingAction(false);
    }
  };

  // Helper formatting badges
  const getAssessmentStatusBadge = (status) => {
    switch (status) {
      case 'effective_documented_control':
        return <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300"><CheckCircle2 className="w-3 h-3" /> Effective Documented Control</span>;
      case 'partially_supported_control':
        return <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300"><AlertTriangle className="w-3 h-3" /> Partially Supported</span>;
      case 'insufficient_evidence':
        return <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-300"><HelpCircle className="w-3 h-3" /> Insufficient Evidence</span>;
      case 'contradictory_evidence':
        return <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 border border-purple-300"><AlertCircle className="w-3 h-3" /> Contradictory Evidence</span>;
      case 'confirmed_weakness':
        return <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-300"><XCircle className="w-3 h-3" /> Confirmed Weakness</span>;
      case 'not_applicable':
        return <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 border border-blue-300">Not Applicable</span>;
      default:
        return <span className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-100 text-slate-600">{status || 'Pending'}</span>;
    }
  };

  const getMaturityBadge = (maturity) => {
    const colors = {
      policy: 'bg-indigo-50 text-indigo-700 border-indigo-200',
      design: 'bg-blue-50 text-blue-700 border-blue-200',
      implementation: 'bg-teal-50 text-teal-700 border-teal-200',
      operational: 'bg-emerald-50 text-emerald-800 border-emerald-300 font-bold',
    };
    return (
      <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border ${colors[maturity] || 'bg-slate-100 text-slate-600 border-slate-200'}`}>
        {maturity || 'policy'}
      </span>
    );
  };

  const getSeverityBadge = (severity) => {
    const badges = {
      critical: 'bg-rose-100 text-rose-800 border-rose-300 font-bold',
      very_high: 'bg-orange-100 text-orange-800 border-orange-300 font-bold',
      high: 'bg-amber-100 text-amber-800 border-amber-300 font-bold',
      medium: 'bg-yellow-100 text-yellow-800 border-yellow-300',
      low: 'bg-blue-50 text-blue-700 border-blue-200',
    };
    return (
      <span className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded border ${badges[severity] || 'bg-slate-100 text-slate-700'}`}>
        {severity || 'medium'}
      </span>
    );
  };

  // Metrics computation
  const totalControls = controls.length;
  const effectiveCount = controls.filter(c => c.assessment_status === 'effective_documented_control').length;
  const partialCount = controls.filter(c => c.assessment_status === 'partially_supported_control').length;
  const insufficientCount = controls.filter(c => c.assessment_status === 'insufficient_evidence').length;
  const weaknessCount = controls.filter(c => c.assessment_status === 'confirmed_weakness').length;
  const findingsCount = findings.length;

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 rounded-2xl p-5 text-white shadow-xl border border-indigo-900/50">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <span className="p-1.5 bg-emerald-500/20 text-emerald-400 rounded-lg border border-emerald-500/30">
                <ShieldCheck className="h-5 w-5" />
              </span>
              <h2 className="text-base font-bold tracking-tight">Defence Auditor: Controls &amp; Safeguards Evaluation</h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-500/30 border border-indigo-400/30 text-indigo-200 font-semibold">
                Milestone 6
              </span>
            </div>
            <p className="text-xs text-slate-300 max-w-2xl">
              Evaluates documented safeguards against approved regulatory requirements and threat scenarios. Analyzes evidence maturity from policy to operational effectiveness.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {readiness && (
              <span className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-xl border ${
                readiness.is_ready
                  ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                  : 'bg-amber-500/10 text-amber-300 border-amber-500/30'
              }`}>
                {readiness.is_ready ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <AlertTriangle className="w-4 h-4 text-amber-400" />}
                {readiness.is_ready ? 'Audit Ready' : 'Prerequisites Incomplete'}
              </span>
            )}

            <button
              onClick={handleTriggerAnalysis}
              disabled={isExecuting || (readiness && !readiness.is_ready)}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-md cursor-pointer ${
                isExecuting || (readiness && !readiness.is_ready)
                  ? 'bg-slate-700 text-slate-400 cursor-not-allowed border border-slate-600'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white border border-emerald-400 hover:shadow-emerald-500/20'
              }`}
            >
              {isExecuting ? <RotateCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4 fill-current" />}
              {isExecuting ? 'Auditing Safeguards...' : 'Run Defence Audit'}
            </button>
          </div>
        </div>

        {/* Readiness Warnings / Blockers */}
        {readiness && (!readiness.is_ready || readiness.warnings.length > 0) && (
          <div className="mt-4 pt-3 border-t border-indigo-900/40 text-xs space-y-1.5">
            {readiness.blockers.map((b, idx) => (
              <div key={idx} className="flex items-center gap-2 text-rose-300">
                <AlertCircle className="w-3.5 h-3.5 shrink-0 text-rose-400" />
                <span>{b}</span>
              </div>
            ))}
            {readiness.warnings.map((w, idx) => (
              <div key={idx} className="flex items-center gap-2 text-amber-300">
                <Info className="w-3.5 h-3.5 shrink-0 text-amber-400" />
                <span>{w}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Metric Counters */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <div className="bg-white rounded-xl border border-slate-200 p-3 shadow-xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Controls Found</div>
          <div className="text-xl font-extrabold text-slate-900 mt-0.5">{totalControls}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-3 shadow-xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-600">Effective</div>
          <div className="text-xl font-extrabold text-emerald-700 mt-0.5">{effectiveCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-3 shadow-xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-amber-600">Partially Supported</div>
          <div className="text-xl font-extrabold text-amber-700 mt-0.5">{partialCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-3 shadow-xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Insufficient Proof</div>
          <div className="text-xl font-extrabold text-slate-700 mt-0.5">{insufficientCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-3 shadow-xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-rose-600">Weaknesses</div>
          <div className="text-xl font-extrabold text-rose-700 mt-0.5">{weaknessCount}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 p-3 shadow-xs">
          <div className="text-[10px] font-bold uppercase tracking-wider text-indigo-600">Findings &amp; Gaps</div>
          <div className="text-xl font-extrabold text-indigo-700 mt-0.5">{findingsCount}</div>
        </div>
      </div>

      {/* Sub-tabs Navigation */}
      <div className="flex border-b border-slate-200 text-xs font-semibold gap-6">
        <button
          onClick={() => setActiveSubTab('controls')}
          className={`py-2.5 flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeSubTab === 'controls'
              ? 'border-emerald-600 text-emerald-700 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <Shield className="w-4 h-4" />
          <span>Security Controls Inventory</span>
          <span className="bg-slate-100 text-slate-600 text-[10px] px-2 py-0.5 rounded-full">{totalControls}</span>
        </button>

        <button
          onClick={() => setActiveSubTab('findings')}
          className={`py-2.5 flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeSubTab === 'findings'
              ? 'border-indigo-600 text-indigo-700 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <AlertCircle className="w-4 h-4" />
          <span>Findings &amp; Evidence Gaps</span>
          <span className="bg-rose-50 text-rose-700 text-[10px] px-2 py-0.5 rounded-full font-bold">{findingsCount}</span>
        </button>

        <button
          onClick={() => setActiveSubTab('runs')}
          className={`py-2.5 flex items-center gap-2 border-b-2 transition-colors cursor-pointer ${
            activeSubTab === 'runs'
              ? 'border-blue-600 text-blue-700 font-bold'
              : 'border-transparent text-slate-500 hover:text-slate-900'
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>Analysis Runs History</span>
          <span className="bg-slate-100 text-slate-600 text-[10px] px-2 py-0.5 rounded-full">{runs.length}</span>
        </button>
      </div>

      {/* Tab: Controls Inventory */}
      {activeSubTab === 'controls' && (
        <div className="space-y-4">
          {/* Controls Filters */}
          <div className="flex flex-wrap items-center gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search controls by name, code, category..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-hidden focus:ring-1 focus:ring-emerald-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold text-slate-500">Maturity:</span>
              <select
                value={selectedMaturity}
                onChange={(e) => setSelectedMaturity(e.target.value)}
                className="bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-xs text-slate-700"
              >
                <option value="all">All Levels</option>
                <option value="policy">Policy (Claimed)</option>
                <option value="design">Design (Architecture)</option>
                <option value="implementation">Implementation (Configured)</option>
                <option value="operational">Operational (Verified Logs)</option>
              </select>
            </div>
          </div>

          {/* Controls List Table */}
          {loadingData ? (
            <div className="py-12 text-center text-slate-400 flex items-center justify-center gap-2">
              <RotateCw className="w-5 h-5 animate-spin" />
              <span>Loading controls inventory...</span>
            </div>
          ) : controls.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center space-y-3">
              <Shield className="w-10 h-10 mx-auto text-slate-300" />
              <h3 className="text-sm font-bold text-slate-700">No controls evaluated yet</h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Run the Defence Auditor to discover security safeguards from uploaded documents and evaluate them against requirements.
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden shadow-xs">
              {controls
                .filter(c => {
                  if (selectedMaturity !== 'all' && c.evidence_maturity !== selectedMaturity) return false;
                  if (searchQuery) {
                    const q = searchQuery.toLowerCase();
                    return (
                      c.name.toLowerCase().includes(q) ||
                      c.control_code.toLowerCase().includes(q) ||
                      c.category.toLowerCase().includes(q) ||
                      c.description.toLowerCase().includes(q)
                    );
                  }
                  return true;
                })
                .map((ctrl) => (
                  <div
                    key={ctrl.id}
                    className="p-4 hover:bg-slate-50/80 transition-colors flex items-center justify-between gap-4 cursor-pointer"
                    onClick={() => openControlDetail(ctrl)}
                  >
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2 py-0.5 rounded">
                          {ctrl.control_code}
                        </span>
                        <h4 className="text-xs font-bold text-slate-900 truncate">{ctrl.name}</h4>
                        {getAssessmentStatusBadge(ctrl.assessment_status)}
                        {getMaturityBadge(ctrl.evidence_maturity)}
                      </div>
                      <p className="text-xs text-slate-500 line-clamp-2">{ctrl.description}</p>
                      <div className="flex items-center gap-4 text-[11px] text-slate-400">
                        <span>Category: <strong className="text-slate-600 font-medium">{ctrl.category}</strong></span>
                        <span>Citations: <strong className="text-slate-600 font-medium">{ctrl.evidence_count} excerpts</strong></span>
                        <span>Mappings: <strong className="text-slate-600 font-medium">{ctrl.requirement_count} reqs, {ctrl.threat_count} threats</strong></span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          openControlDetail(ctrl);
                        }}
                        className="px-3 py-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 text-xs font-medium flex items-center gap-1.5 cursor-pointer"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>Inspect</span>
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: Findings & Gaps */}
      {activeSubTab === 'findings' && (
        <div className="space-y-4">
          {/* Findings Filter */}
          <div className="flex flex-wrap items-center gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search findings by title, code, recommendation..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 bg-white border border-slate-200 rounded-lg text-xs focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold text-slate-500">Severity:</span>
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="bg-white border border-slate-200 rounded-lg px-2 py-1.5 text-xs text-slate-700"
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical (20-25)</option>
                <option value="very_high">Very High (15-19)</option>
                <option value="high">High (10-14)</option>
                <option value="medium">Medium (5-9)</option>
                <option value="low">Low (1-4)</option>
              </select>
            </div>
          </div>

          {findings.length === 0 ? (
            <div className="bg-white rounded-xl border border-slate-200 p-8 text-center space-y-2">
              <CheckCircle2 className="w-10 h-10 mx-auto text-emerald-500" />
              <h3 className="text-sm font-bold text-slate-800">No security gaps detected</h3>
              <p className="text-xs text-slate-500">Documented controls sufficiently address active requirements and threats.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {findings
                .filter(f => {
                  if (selectedSeverity !== 'all' && f.severity !== selectedSeverity) return false;
                  if (searchQuery) {
                    const q = searchQuery.toLowerCase();
                    return (
                      f.title.toLowerCase().includes(q) ||
                      f.finding_code.toLowerCase().includes(q) ||
                      f.description.toLowerCase().includes(q)
                    );
                  }
                  return true;
                })
                .map((find) => (
                  <div
                    key={find.id}
                    onClick={() => openFindingDetail(find)}
                    className="bg-white rounded-xl border border-slate-200 p-4 hover:border-indigo-300 hover:shadow-md transition-all flex flex-col justify-between cursor-pointer space-y-3"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-bold text-rose-700 bg-rose-50 border border-rose-200 px-2 py-0.5 rounded">
                          {find.finding_code}
                        </span>
                        <div className="flex items-center gap-1.5">
                          {getSeverityBadge(find.severity)}
                          <span className="font-mono text-[10px] font-bold text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">
                            Risk {find.risk_score || find.likelihood_score * find.impact_score}/25
                          </span>
                        </div>
                      </div>

                      <h4 className="text-xs font-bold text-slate-900 leading-snug">{find.title}</h4>
                      <p className="text-xs text-slate-500 line-clamp-2">{find.description}</p>
                    </div>

                    <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
                      <span>Category: <strong className="text-slate-600 font-medium">{find.finding_category || 'Gap'}</strong></span>
                      <span className="text-indigo-600 font-semibold hover:underline flex items-center gap-1">
                        Inspect Details <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: Analysis Runs */}
      {activeSubTab === 'runs' && (
        <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100 overflow-hidden">
          {runs.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-400">No historical defence runs logged yet.</div>
          ) : (
            runs.map((r) => (
              <div key={r.id} className="p-4 flex items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-700 font-bold">{r.id.slice(0, 8)}...</span>
                    <span className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded ${
                      r.status === 'completed' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'
                    }`}>
                      {r.status}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">{r.model_name}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-slate-500">
                    <span>Discovered: <strong>{r.controls_discovered_count} controls</strong></span>
                    <span>Assessments: <strong>{r.assessments_count}</strong></span>
                    <span>Gaps: <strong>{r.findings_count}</strong></span>
                    <span>Duration: <strong>{r.execution_duration_ms ? `${(r.execution_duration_ms / 1000).toFixed(1)}s` : '—'}</strong></span>
                  </div>
                </div>
                <div className="text-[11px] text-slate-400 font-mono">
                  {new Date(r.created_at).toLocaleString()}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Control Detail Modal / Drawer */}
      {selectedControl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-indigo-700 bg-indigo-50 border border-indigo-200 px-2.5 py-1 rounded">
                  {selectedControl.control_code}
                </span>
                <h3 className="text-sm font-bold text-slate-900">{selectedControl.name}</h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => openEditModal('control', controlDetail || selectedControl)}
                  className="px-2.5 py-1 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 text-xs font-medium flex items-center gap-1 cursor-pointer"
                >
                  <Edit3 className="w-3.5 h-3.5" /> Edit
                </button>
                <button
                  onClick={() => {
                    setSelectedControl(null);
                    setControlDetail(null);
                  }}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Modal Body */}
            <div className="p-6 overflow-y-auto space-y-5 text-xs flex-1">
              {loadingControlDetail ? (
                <div className="py-12 text-center text-slate-400 flex items-center justify-center gap-2">
                  <RotateCw className="w-4 h-4 animate-spin" />
                  <span>Loading full control evidence dossier...</span>
                </div>
              ) : controlDetail ? (
                <>
                  {/* Status & Maturity Banner */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200">
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Assessment</div>
                      <div className="mt-1">{getAssessmentStatusBadge(controlDetail.assessment_status)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Maturity Level</div>
                      <div className="mt-1">{getMaturityBadge(controlDetail.evidence_maturity)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Implementation</div>
                      <div className="mt-1 font-semibold text-slate-800 capitalize">{controlDetail.implementation_status}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Operational Telemetry</div>
                      <div className="mt-1 font-semibold text-slate-800 capitalize">{controlDetail.operational_status}</div>
                    </div>
                  </div>

                  {/* Description & Objective */}
                  <div className="space-y-3">
                    <div>
                      <h4 className="text-[11px] uppercase tracking-wider font-bold text-slate-500">Control Specification</h4>
                      <p className="mt-1 text-slate-700 leading-relaxed">{controlDetail.description}</p>
                    </div>
                    <div>
                      <h4 className="text-[11px] uppercase tracking-wider font-bold text-slate-500">Risk &amp; Control Objective</h4>
                      <p className="mt-1 text-slate-700 leading-relaxed">{controlDetail.control_objective}</p>
                    </div>
                  </div>

                  {/* Primary Assessment Details */}
                  {controlDetail.assessments && controlDetail.assessments.length > 0 && (
                    <div className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-4 space-y-2">
                      <div className="flex items-center gap-2">
                        <FileCheck className="w-4 h-4 text-indigo-600" />
                        <h4 className="font-bold text-indigo-900 text-xs">Auditor Evaluation &amp; Rationale</h4>
                      </div>
                      <p className="text-slate-800 leading-relaxed">{controlDetail.assessments[0].assessment_explanation}</p>
                      {controlDetail.assessments[0].evidence_limitations && (
                        <div className="mt-2 text-[11px] text-amber-800 bg-amber-50 p-2.5 rounded-lg border border-amber-200">
                          <strong>Evidence Limitations:</strong> {controlDetail.assessments[0].evidence_limitations}
                        </div>
                      )}
                      {controlDetail.assessments[0].missing_information && (
                        <div className="text-[11px] text-slate-700 bg-slate-100 p-2.5 rounded-lg border border-slate-200">
                          <strong>Required Information:</strong> {controlDetail.assessments[0].missing_information}
                        </div>
                      )}
                    </div>
                  )}

                  {/* Verbatim Evidence Citations */}
                  <div>
                    <h4 className="text-[11px] uppercase tracking-wider font-bold text-slate-500 mb-2">Verbatim Evidence Citations ({controlDetail.evidence_references?.length || 0})</h4>
                    <div className="space-y-2">
                      {controlDetail.evidence_references?.map((ev, i) => (
                        <div key={i} className="bg-slate-50 border border-slate-200 rounded-xl p-3 space-y-1.5">
                          <div className="flex items-center justify-between text-[11px] text-slate-500">
                            <span className="font-medium text-slate-800 flex items-center gap-1.5">
                              <FileText className="w-3.5 h-3.5 text-blue-600" />
                              {ev.original_filename || 'Audit Document'}
                            </span>
                            <span>Page {ev.page_number || 1} • {ev.section_title || 'General'}</span>
                          </div>
                          <div className="font-mono text-xs text-slate-800 bg-white p-2.5 rounded border border-slate-200 italic">
                            "{ev.exact_excerpt}"
                          </div>
                          {ev.relevance_explanation && (
                            <div className="text-[11px] text-slate-500">
                              <strong>Relevance:</strong> {ev.relevance_explanation}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Mappings */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="border border-slate-200 rounded-xl p-3 space-y-2">
                      <h4 className="text-[11px] font-bold text-slate-700 flex items-center gap-1.5">
                        <Shield className="w-3.5 h-3.5 text-emerald-600" /> Regulatory Requirements Mapped
                      </h4>
                      {controlDetail.requirement_mappings?.length === 0 ? (
                        <p className="text-slate-400 text-[11px]">No direct requirement mapping.</p>
                      ) : (
                        controlDetail.requirement_mappings?.map((rm, i) => (
                          <div key={i} className="bg-slate-50 p-2 rounded text-[11px]">
                            <strong className="text-slate-800 font-mono">{rm.requirement_identifier}:</strong> {rm.requirement_statement}
                          </div>
                        ))
                      )}
                    </div>

                    <div className="border border-slate-200 rounded-xl p-3 space-y-2">
                      <h4 className="text-[11px] font-bold text-slate-700 flex items-center gap-1.5">
                        <ShieldAlert className="w-3.5 h-3.5 text-rose-600" /> Threats Mitigated
                      </h4>
                      {controlDetail.threat_mappings?.length === 0 ? (
                        <p className="text-slate-400 text-[11px]">No direct threat scenario mapping.</p>
                      ) : (
                        controlDetail.threat_mappings?.map((tm, i) => (
                          <div key={i} className="bg-slate-50 p-2 rounded text-[11px]">
                            <strong className="text-slate-800">{tm.threat_title}</strong>
                            <div className="text-slate-500 capitalize">Level: {tm.mitigation_level}</div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Audit Review Trail */}
                  {controlDetail.audit_history && controlDetail.audit_history.length > 0 && (
                    <div className="border-t border-slate-200 pt-3 space-y-2">
                      <h4 className="text-[11px] uppercase tracking-wider font-bold text-slate-400">Review History &amp; Audit Trail</h4>
                      <div className="space-y-1.5">
                        {controlDetail.audit_history.map((h, i) => (
                          <div key={i} className="flex items-center justify-between text-[11px] bg-slate-50 px-3 py-1.5 rounded border border-slate-200">
                            <div>
                              <strong className="capitalize text-slate-800">{h.action}</strong> by {h.reviewer_email || 'Auditor'}
                              {h.reason && <span className="text-slate-500 italic"> — "{h.reason}"</span>}
                            </div>
                            <span className="text-slate-400 font-mono">{new Date(h.created_at).toLocaleTimeString()}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>

            {/* Modal Review Actions Footer */}
            <div className="p-4 border-t border-slate-200 flex items-center justify-between bg-slate-50">
              <span className="text-xs text-slate-500">Human Auditor Review Action</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleReviewAction('control', selectedControl.id, 'reject')}
                  className="px-3 py-1.5 rounded-lg border border-rose-300 text-rose-700 hover:bg-rose-50 text-xs font-bold cursor-pointer"
                >
                  Reject Safeguard
                </button>
                <button
                  onClick={() => handleReviewAction('control', selectedControl.id, 'request_more_information')}
                  className="px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-700 text-xs font-medium cursor-pointer"
                >
                  Request Evidence
                </button>
                <button
                  onClick={() => handleReviewAction('control', selectedControl.id, 'approve')}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold cursor-pointer"
                >
                  Approve Safeguard
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Finding Detail Modal / Drawer */}
      {selectedFinding && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden">
            <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold text-rose-700 bg-rose-50 border border-rose-200 px-2.5 py-1 rounded">
                  {selectedFinding.finding_code}
                </span>
                <h3 className="text-sm font-bold text-slate-900">{selectedFinding.title}</h3>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => openEditModal('finding', findingDetail || selectedFinding)}
                  className="px-2.5 py-1 rounded-lg border border-slate-200 hover:bg-slate-100 text-slate-600 text-xs font-medium flex items-center gap-1 cursor-pointer"
                >
                  <Edit3 className="w-3.5 h-3.5" /> Edit
                </button>
                <button
                  onClick={() => {
                    setSelectedFinding(null);
                    setFindingDetail(null);
                  }}
                  className="p-1 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            <div className="p-6 overflow-y-auto space-y-4 text-xs flex-1">
              {loadingFindingDetail ? (
                <div className="py-12 text-center text-slate-400 flex items-center justify-center gap-2">
                  <RotateCw className="w-4 h-4 animate-spin" />
                  <span>Loading finding details...</span>
                </div>
              ) : findingDetail ? (
                <>
                  <div className="flex items-center justify-between bg-slate-50 p-3 rounded-xl border border-slate-200">
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Severity Rating</div>
                      <div className="mt-1">{getSeverityBadge(findingDetail.severity)}</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Likelihood</div>
                      <div className="mt-1 font-bold text-slate-800">{findingDetail.likelihood_score} / 5</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Impact</div>
                      <div className="mt-1 font-bold text-slate-800">{findingDetail.impact_score} / 5</div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase font-bold text-slate-400">Calculated Risk</div>
                      <div className="mt-1 font-extrabold text-indigo-700">{findingDetail.risk_score} / 25</div>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-[11px] uppercase tracking-wider font-bold text-slate-500">Detailed Description</h4>
                    <p className="mt-1 text-slate-700 leading-relaxed">{findingDetail.description}</p>
                  </div>

                  <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3 space-y-1">
                    <h4 className="text-[11px] font-bold text-emerald-900">Remediation Guidance</h4>
                    <p className="text-emerald-800 leading-relaxed">{findingDetail.remediation_recommendation}</p>
                  </div>

                  {findingDetail.related_controls && findingDetail.related_controls.length > 0 && (
                    <div>
                      <h4 className="text-[11px] uppercase tracking-wider font-bold text-slate-500 mb-1.5">Associated Controls</h4>
                      <div className="space-y-1.5">
                        {findingDetail.related_controls.map((c, i) => (
                          <div key={i} className="flex items-center gap-2 p-2 bg-slate-50 rounded border border-slate-200">
                            <span className="font-mono text-xs font-bold text-slate-700">{c.control_code}</span>
                            <span className="text-slate-800">{c.name}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              ) : null}
            </div>

            <div className="p-4 border-t border-slate-200 flex items-center justify-between bg-slate-50">
              <span className="text-xs text-slate-500">Review Decision</span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handleReviewAction('finding', selectedFinding.id, 'reject')}
                  className="px-3 py-1.5 rounded-lg border border-rose-300 text-rose-700 hover:bg-rose-50 text-xs font-bold cursor-pointer"
                >
                  Dismiss / Reject
                </button>
                <button
                  onClick={() => handleReviewAction('finding', selectedFinding.id, 'approve')}
                  className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold cursor-pointer"
                >
                  Confirm Finding
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Mandatory Rejection Reason Modal */}
      {rejectingItem && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-md w-full p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <XCircle className="w-4 h-4 text-rose-600" />
                Document Rejection Rationale
              </h3>
              <button
                onClick={() => setRejectingItem(null)}
                className="text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <p className="text-xs text-slate-500">
              A clear, documented reason is mandatory when rejecting a security safeguard or finding in Compliance Sentinel.
            </p>
            <textarea
              rows={4}
              placeholder="Enter exact reason for rejection (e.g., contradicts architecture diagram section 2.1)..."
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              className="w-full p-2.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:ring-1 focus:ring-rose-500 focus:outline-hidden"
            />
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                onClick={() => setRejectingItem(null)}
                className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={submitRejection}
                disabled={submittingAction || !rejectReason.trim()}
                className="px-4 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 rounded-lg disabled:opacity-50 cursor-pointer"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Manual Edit Modal */}
      {editingItem && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl max-w-lg w-full p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Edit3 className="w-4 h-4 text-indigo-600" />
                Edit {editingItem.type === 'control' ? 'Security Safeguard' : 'Finding Details'}
              </h3>
              <button onClick={() => setEditingItem(null)} className="text-slate-400 hover:text-slate-600 cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              {editingItem.type === 'control' ? (
                <>
                  <div>
                    <label className="font-semibold text-slate-700 block mb-1">Safeguard Name</label>
                    <input
                      type="text"
                      value={editFormData.name || ''}
                      onChange={(e) => setEditFormData({ ...editFormData, name: e.target.value })}
                      className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                    />
                  </div>
                  <div>
                    <label className="font-semibold text-slate-700 block mb-1">Category</label>
                    <input
                      type="text"
                      value={editFormData.category || ''}
                      onChange={(e) => setEditFormData({ ...editFormData, category: e.target.value })}
                      className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                    />
                  </div>
                  <div>
                    <label className="font-semibold text-slate-700 block mb-1">Maturity Level</label>
                    <select
                      value={editFormData.evidence_maturity || 'policy'}
                      onChange={(e) => setEditFormData({ ...editFormData, evidence_maturity: e.target.value })}
                      className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                    >
                      <option value="policy">Policy (Claimed)</option>
                      <option value="design">Design (Architecture)</option>
                      <option value="implementation">Implementation (Configured)</option>
                      <option value="operational">Operational (Verified Logs)</option>
                    </select>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="font-semibold text-slate-700 block mb-1">Finding Title</label>
                    <input
                      type="text"
                      value={editFormData.title || ''}
                      onChange={(e) => setEditFormData({ ...editFormData, title: e.target.value })}
                      className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="font-semibold text-slate-700 block mb-1">Likelihood (1-5)</label>
                      <input
                        type="number"
                        min="1"
                        max="5"
                        value={editFormData.likelihood_score || 3}
                        onChange={(e) => setEditFormData({ ...editFormData, likelihood_score: parseInt(e.target.value) || 1 })}
                        className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                      />
                    </div>
                    <div>
                      <label className="font-semibold text-slate-700 block mb-1">Impact (1-5)</label>
                      <input
                        type="number"
                        min="1"
                        max="5"
                        value={editFormData.impact_score || 3}
                        onChange={(e) => setEditFormData({ ...editFormData, impact_score: parseInt(e.target.value) || 1 })}
                        className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="font-semibold text-slate-700 block mb-1">Remediation Recommendation</label>
                    <textarea
                      rows={3}
                      value={editFormData.remediation_recommendation || ''}
                      onChange={(e) => setEditFormData({ ...editFormData, remediation_recommendation: e.target.value })}
                      className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                    />
                  </div>
                </>
              )}

              <div>
                <label className="font-semibold text-slate-700 block mb-1">Change Reason</label>
                <input
                  type="text"
                  placeholder="Reason for modification..."
                  value={editFormData.reason || ''}
                  onChange={(e) => setEditFormData({ ...editFormData, reason: e.target.value })}
                  className="w-full p-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button onClick={() => setEditingItem(null)} className="px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 rounded-lg cursor-pointer">
                Cancel
              </button>
              <button
                onClick={submitEdit}
                disabled={submittingAction}
                className="px-4 py-1.5 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 rounded-lg cursor-pointer"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FileCheck(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" />
      <path d="M14 2v4a2 2 0 0 0 2 2h4" />
      <path d="m9 15 2 2 4-4" />
    </svg>
  );
}

