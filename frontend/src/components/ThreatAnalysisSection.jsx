import React, { useState, useEffect } from 'react';
import {
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
  Server,
  Layers,
  ChevronRight,
  ChevronDown,
  Info,
  Clock,
  ArrowRight,
  Crosshair,
  Key,
  Database,
  Lock,
  Globe,
  GitBranch,
  ShieldCheck
} from 'lucide-react';
import { threatApi } from '../api/client';

export default function ThreatAnalysisSection({ audit }) {
  const orgId = audit.organization_id;
  const auditId = audit.id;

  // View state
  const [activeSubTab, setActiveSubTab] = useState('threats'); // 'threats', 'assets', 'surfaces', 'runs'
  const [readiness, setReadiness] = useState(null);
  const [loadingReadiness, setLoadingReadiness] = useState(true);

  // Data lists
  const [threats, setThreats] = useState([]);
  const [assets, setAssets] = useState([]);
  const [surfaces, setSurfaces] = useState([]);
  const [runs, setRuns] = useState([]);
  const [loadingData, setLoadingData] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);

  // Filters
  const [selectedStride, setSelectedStride] = useState('all');
  const [selectedSeverity, setSelectedSeverity] = useState('all');
  const [selectedReviewStatus, setSelectedReviewStatus] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Selected item modals
  const [selectedThreat, setSelectedThreat] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Action modals
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [actionThreatId, setActionThreatId] = useState(null);

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editFormData, setEditFormData] = useState({
    threat_title: '',
    threat_description: '',
    likelihood_score: 3,
    impact_score: 3,
    cia_confidentiality: 'medium',
    cia_integrity: 'medium',
    cia_availability: 'medium',
    reason: '',
  });

  // Load readiness and data on mount
  useEffect(() => {
    fetchReadiness();
    fetchData();
  }, [auditId]);

  const fetchReadiness = async () => {
    try {
      setLoadingReadiness(true);
      const res = await threatApi.checkReadiness(orgId, auditId);
      setReadiness(res);
    } catch (err) {
      console.error('Failed to load threat readiness:', err);
    } finally {
      setLoadingReadiness(false);
    }
  };

  const fetchData = async () => {
    try {
      setLoadingData(true);
      const [threatsRes, assetsRes, surfacesRes, runsRes] = await Promise.all([
        threatApi.listThreats(orgId, auditId, {
          stride_category: selectedStride,
          severity: selectedSeverity,
          review_status: selectedReviewStatus,
          search: searchQuery,
          page_size: 50,
        }),
        threatApi.listAssets(orgId, auditId),
        threatApi.listAttackSurfaces(orgId, auditId),
        threatApi.listThreatRuns(orgId, auditId),
      ]);

      setThreats(threatsRes.threats || []);
      setAssets(assetsRes || []);
      setSurfaces(surfacesRes || []);
      setRuns(runsRes || []);
    } catch (err) {
      console.error('Failed to fetch threat modeling data:', err);
    } finally {
      setLoadingData(false);
    }
  };

  // Re-fetch threats when filters change
  useEffect(() => {
    const handler = setTimeout(() => {
      fetchFilteredThreats();
    }, 250);
    return () => clearTimeout(handler);
  }, [selectedStride, selectedSeverity, selectedReviewStatus, searchQuery]);

  const fetchFilteredThreats = async () => {
    try {
      const res = await threatApi.listThreats(orgId, auditId, {
        stride_category: selectedStride,
        severity: selectedSeverity,
        review_status: selectedReviewStatus,
        search: searchQuery,
        page_size: 50,
      });
      setThreats(res.threats || []);
    } catch (err) {
      console.error('Failed to filter threats:', err);
    }
  };

  const handleTriggerAnalysis = async () => {
    try {
      setIsExecuting(true);
      await threatApi.triggerThreatAnalysis(orgId, auditId, {
        model_name: 'gemini-1.5-flash',
        run_in_background: false,
      });
      await fetchReadiness();
      await fetchData();
    } catch (err) {
      alert(`Threat Analysis execution failed: ${err.message || 'Unknown error'}`);
    } finally {
      setIsExecuting(false);
    }
  };

  const openThreatDetail = async (threatId) => {
    try {
      setLoadingDetail(true);
      const detail = await threatApi.getThreatDetail(orgId, auditId, threatId);
      setSelectedThreat(detail);
    } catch (err) {
      alert(`Failed to load threat details: ${err.message}`);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleAcceptThreat = async (threatId) => {
    try {
      const updated = await threatApi.acceptThreat(orgId, auditId, threatId, 'Accepted by auditor.');
      setSelectedThreat(updated);
      fetchFilteredThreats();
    } catch (err) {
      alert(`Failed to accept threat: ${err.message}`);
    }
  };

  const handleRejectClick = (threatId) => {
    setActionThreatId(threatId);
    setRejectReason('');
    setRejectModalOpen(true);
  };

  const handleConfirmReject = async () => {
    if (!rejectReason.trim()) {
      alert('Please supply a justification reason.');
      return;
    }
    try {
      const updated = await threatApi.rejectThreat(orgId, auditId, actionThreatId, rejectReason.trim());
      setRejectModalOpen(false);
      setSelectedThreat(updated);
      fetchFilteredThreats();
    } catch (err) {
      alert(`Failed to reject threat: ${err.message}`);
    }
  };

  const handleRequestInfo = async (threatId) => {
    const reason = prompt('Specify what additional architectural information or evidence is needed:');
    if (reason === null) return;
    try {
      const updated = await threatApi.requestMoreInformation(orgId, auditId, threatId, reason || 'More info requested');
      setSelectedThreat(updated);
      fetchFilteredThreats();
    } catch (err) {
      alert(`Failed to request review: ${err.message}`);
    }
  };

  const handleEditClick = (threat) => {
    setActionThreatId(threat.id);
    setEditFormData({
      threat_title: threat.threat_title,
      threat_description: threat.threat_description,
      likelihood_score: threat.likelihood_score,
      impact_score: threat.impact_score,
      cia_confidentiality: threat.cia_confidentiality,
      cia_integrity: threat.cia_integrity,
      cia_availability: threat.cia_availability,
      reason: '',
    });
    setEditModalOpen(true);
  };

  const handleConfirmEdit = async () => {
    try {
      const updated = await threatApi.editThreat(orgId, auditId, actionThreatId, editFormData);
      setEditModalOpen(false);
      setSelectedThreat(updated);
      fetchFilteredThreats();
    } catch (err) {
      alert(`Failed to update threat: ${err.message}`);
    }
  };

  // Helper colors
  const getStrideBadge = (cat) => {
    const map = {
      'Spoofing': 'bg-amber-50 text-amber-700 border-amber-200',
      'Tampering': 'bg-purple-50 text-purple-700 border-purple-200',
      'Repudiation': 'bg-slate-100 text-slate-700 border-slate-300',
      'Information Disclosure': 'bg-blue-50 text-blue-700 border-blue-200',
      'Denial of Service': 'bg-red-50 text-red-700 border-red-200',
      'Elevation of Privilege': 'bg-rose-50 text-rose-700 border-rose-200',
    };
    return map[cat] || 'bg-slate-100 text-slate-700 border-slate-200';
  };

  const getSeverityBadge = (sev) => {
    const map = {
      'critical': 'bg-rose-600 text-white font-bold',
      'very_high': 'bg-red-500 text-white font-bold',
      'high': 'bg-orange-500 text-white font-semibold',
      'medium': 'bg-amber-400 text-slate-900 font-medium',
      'low': 'bg-emerald-500 text-white font-medium',
    };
    return map[sev] || 'bg-slate-400 text-white';
  };

  const getReviewBadge = (status) => {
    const map = {
      'pending_review': 'bg-amber-50 text-amber-700 border-amber-200',
      'accepted': 'bg-emerald-50 text-emerald-700 border-emerald-200',
      'rejected': 'bg-rose-50 text-rose-700 border-rose-200',
      'edited': 'bg-blue-50 text-blue-700 border-blue-200',
      'needs_more_information': 'bg-purple-50 text-purple-700 border-purple-200',
    };
    return map[status] || 'bg-slate-100 text-slate-600 border-slate-200';
  };

  return (
    <div className="space-y-5">
      {/* Top Pre-Flight & Trigger Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-xs">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-start space-x-3">
            <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 text-rose-600 shrink-0">
              <Crosshair className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h4 className="font-bold text-slate-900 text-sm">Adversarial Strategist</h4>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 border border-slate-200">
                  STRIDE + CIA Triad
                </span>
                {readiness && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-bold border ${
                      readiness.is_ready
                        ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                        : 'bg-amber-50 text-amber-700 border-amber-200'
                    }`}
                  >
                    {readiness.is_ready ? 'Audit Ready for Analysis' : 'Pre-flight Incomplete'}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">
                Analyzes architecture documents, maps attack surfaces, builds multi-step attack trees, and aligns threats with approved regulations.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3 w-full md:w-auto justify-end">
            <button
              onClick={handleTriggerAnalysis}
              disabled={isExecuting || (readiness && !readiness.is_ready)}
              className={`inline-flex items-center space-x-2 px-4 py-2 rounded-lg font-bold text-xs shadow-xs transition-all cursor-pointer ${
                isExecuting
                  ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
                  : readiness && !readiness.is_ready
                  ? 'bg-slate-200 text-slate-500 cursor-not-allowed'
                  : 'bg-rose-600 hover:bg-rose-700 text-white active:scale-98'
              }`}
            >
              {isExecuting ? (
                <>
                  <RotateCw className="h-4 w-4 animate-spin" />
                  <span>Analyzing Threat Paths...</span>
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 fill-current" />
                  <span>Execute Threat Analysis</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Readiness Validation Notices */}
        {readiness && readiness.validation_messages && readiness.validation_messages.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-2 items-center">
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Readiness Check:</span>
            {readiness.validation_messages.map((msg, idx) => (
              <span
                key={idx}
                className={`text-[10px] px-2 py-0.5 rounded-md border flex items-center space-x-1 ${
                  readiness.is_ready
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
                    : 'bg-amber-50 text-amber-800 border-amber-200'
                }`}
              >
                {readiness.is_ready ? <CheckCircle2 className="h-3 w-3 text-emerald-600" /> : <AlertTriangle className="h-3 w-3 text-amber-600" />}
                <span>{msg}</span>
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Sub-tab Navigation */}
      <div className="flex items-center justify-between border-b border-slate-200">
        <div className="flex space-x-6 text-xs font-semibold">
          <button
            onClick={() => setActiveSubTab('threats')}
            className={`py-2.5 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeSubTab === 'threats'
                ? 'border-rose-600 text-rose-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <ShieldAlert className="h-4 w-4" />
            <span>Threat Scenarios</span>
            <span className="bg-rose-100 text-rose-700 px-1.5 py-0.2 rounded text-[10px] font-bold">
              {threats.length}
            </span>
          </button>

          <button
            onClick={() => setActiveSubTab('assets')}
            className={`py-2.5 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeSubTab === 'assets'
                ? 'border-rose-600 text-rose-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Database className="h-4 w-4" />
            <span>Discovered Assets</span>
            <span className="bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded text-[10px] font-bold">
              {assets.length}
            </span>
          </button>

          <button
            onClick={() => setActiveSubTab('surfaces')}
            className={`py-2.5 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeSubTab === 'surfaces'
                ? 'border-rose-600 text-rose-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Globe className="h-4 w-4" />
            <span>Attack Surfaces</span>
            <span className="bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded text-[10px] font-bold">
              {surfaces.length}
            </span>
          </button>

          <button
            onClick={() => setActiveSubTab('runs')}
            className={`py-2.5 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeSubTab === 'runs'
                ? 'border-rose-600 text-rose-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Clock className="h-4 w-4" />
            <span>Execution Runs</span>
            <span className="bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded text-[10px] font-bold">
              {runs.length}
            </span>
          </button>
        </div>

        <button
          onClick={fetchData}
          className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 cursor-pointer"
          title="Refresh Data"
        >
          <RotateCw className={`h-3.5 w-3.5 ${loadingData ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* ========================================================================= */}
      {/* 1. THREATS INVENTORY VIEW                                                 */}
      {/* ========================================================================= */}
      {activeSubTab === 'threats' && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-50/70 p-3 rounded-xl border border-slate-200">
            {/* Search */}
            <div className="relative">
              <Search className="h-3.5 w-3.5 absolute left-2.5 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search threat title or attack objective..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-lg pl-8 pr-3 py-1.5 text-xs text-slate-800 focus:outline-rose-500"
              />
            </div>

            {/* STRIDE Category */}
            <div>
              <select
                value={selectedStride}
                onChange={(e) => setSelectedStride(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700 focus:outline-rose-500"
              >
                <option value="all">All STRIDE Categories</option>
                <option value="Spoofing">Spoofing</option>
                <option value="Tampering">Tampering</option>
                <option value="Repudiation">Repudiation</option>
                <option value="Information Disclosure">Information Disclosure</option>
                <option value="Denial of Service">Denial of Service</option>
                <option value="Elevation of Privilege">Elevation of Privilege</option>
              </select>
            </div>

            {/* Severity */}
            <div>
              <select
                value={selectedSeverity}
                onChange={(e) => setSelectedSeverity(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700 focus:outline-rose-500"
              >
                <option value="all">All Severities</option>
                <option value="critical">Critical (20-25)</option>
                <option value="very_high">Very High (15-19)</option>
                <option value="high">High (10-14)</option>
                <option value="medium">Medium (5-9)</option>
                <option value="low">Low (1-4)</option>
              </select>
            </div>

            {/* Review Status */}
            <div>
              <select
                value={selectedReviewStatus}
                onChange={(e) => setSelectedReviewStatus(e.target.value)}
                className="w-full bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 text-xs text-slate-700 focus:outline-rose-500"
              >
                <option value="all">All Review Statuses</option>
                <option value="pending_review">Pending Review</option>
                <option value="accepted">Accepted</option>
                <option value="rejected">Rejected</option>
                <option value="edited">Edited</option>
                <option value="needs_more_information">Needs More Info</option>
              </select>
            </div>
          </div>

          {/* Threat List */}
          {threats.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center bg-slate-50/50">
              <Crosshair className="h-8 w-8 mx-auto text-slate-300" />
              <p className="mt-2 text-xs font-semibold text-slate-700">No Threat Scenarios Found</p>
              <p className="text-[11px] text-slate-400 mt-1 max-w-md mx-auto">
                {readiness && readiness.is_ready
                  ? "Click 'Execute Threat Analysis' above to generate evidence-backed threat scenarios and attack paths."
                  : 'Ensure audit documents and approved regulatory requirements are uploaded before running threat modeling.'}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3">
              {threats.map((t) => (
                <div
                  key={t.id}
                  className="rounded-xl border border-slate-200 bg-white p-4 hover:border-slate-300 hover:shadow-xs transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${getSeverityBadge(t.severity)}`}>
                          {t.severity.replace('_', ' ')}
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getStrideBadge(t.stride_category)}`}>
                          {t.stride_category}
                        </span>
                        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${getReviewBadge(t.review_status)}`}>
                          {t.review_status.replace(/_/g, ' ')}
                        </span>
                        {t.is_provisional && (
                          <span className="text-[10px] font-bold px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-300">
                            Provisional
                          </span>
                        )}
                      </div>
                      <h5 className="font-bold text-slate-900 text-xs">{t.threat_title}</h5>
                    </div>

                    {/* Deterministic Risk Meter */}
                    <div className="text-right shrink-0">
                      <div className="text-[10px] font-bold text-slate-400 uppercase">Deterministic Risk</div>
                      <div className="text-sm font-black text-slate-900">
                        {t.risk_score} <span className="text-[10px] font-normal text-slate-400">/ 25</span>
                      </div>
                      <div className="text-[9px] text-slate-400">
                        L:{t.likelihood_score} × I:{t.impact_score}
                      </div>
                    </div>
                  </div>

                  <p className="text-[11px] text-slate-600 line-clamp-2">{t.threat_description}</p>

                  <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-slate-100 text-[10px] text-slate-500">
                    <div className="flex items-center space-x-3">
                      <span><strong>Vector:</strong> {t.attack_vector || 'N/A'}</span>
                      <span><strong>Entry:</strong> {t.entry_point || 'N/A'}</span>
                      <span className="bg-slate-100 px-1.5 py-0.5 rounded font-mono">
                        {t.attack_nodes_count} attack steps
                      </span>
                      <span className="bg-blue-50 text-blue-700 border border-blue-200 px-1.5 py-0.5 rounded font-mono">
                        {t.mapped_requirements_count} mapped requirements
                      </span>
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => openThreatDetail(t.id)}
                        className="inline-flex items-center space-x-1 text-rose-600 hover:text-rose-700 font-bold px-2 py-1 rounded hover:bg-rose-50 cursor-pointer"
                      >
                        <Eye className="h-3.5 w-3.5" />
                        <span>Inspect Attack Tree &amp; Details</span>
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* 2. DISCOVERED ASSETS VIEW                                                 */}
      {/* ========================================================================= */}
      {activeSubTab === 'assets' && (
        <div className="space-y-3">
          {assets.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center bg-slate-50/50">
              <Database className="h-8 w-8 mx-auto text-slate-300" />
              <p className="mt-2 text-xs font-semibold text-slate-700">No Assets Discovered Yet</p>
              <p className="text-[11px] text-slate-400 mt-1">Execute threat analysis to discover critical assets from architecture evidence.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {assets.map((a) => (
                <div key={a.id} className="rounded-xl border border-slate-200 bg-white p-3.5 space-y-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                          {a.asset_category}
                        </span>
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${a.criticality === 'critical' ? 'bg-rose-100 text-rose-800' : 'bg-slate-100 text-slate-600'}`}>
                          {a.criticality}
                        </span>
                      </div>
                      <h5 className="font-bold text-slate-900 text-xs mt-1">{a.name}</h5>
                    </div>
                    <span className="text-[10px] font-mono text-slate-400">{a.data_classification || 'Unclassified'}</span>
                  </div>
                  <p className="text-[11px] text-slate-600">{a.description}</p>
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-[10px] text-slate-400">
                    <span>Owner: {a.owner}</span>
                    <span>Evidence: <strong>{a.evidence_classification}</strong></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* 3. ATTACK SURFACES VIEW                                                   */}
      {/* ========================================================================= */}
      {activeSubTab === 'surfaces' && (
        <div className="space-y-3">
          {surfaces.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center bg-slate-50/50">
              <Globe className="h-8 w-8 mx-auto text-slate-300" />
              <p className="mt-2 text-xs font-semibold text-slate-700">No Attack Surfaces Identified</p>
              <p className="text-[11px] text-slate-400 mt-1">Execute threat analysis to map public entry points and trust boundaries.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {surfaces.map((s) => (
                <div key={s.id} className="rounded-xl border border-slate-200 bg-white p-3.5 space-y-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200">
                        {s.surface_type}
                      </span>
                      <h5 className="font-bold text-slate-900 text-xs mt-1">{s.name}</h5>
                    </div>
                    <span className="text-[10px] font-mono bg-purple-50 text-purple-700 px-2 py-0.5 rounded border border-purple-200">
                      {s.trust_boundary}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-600">{s.description}</p>
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-[10px] text-slate-400">
                    <span>Access: <strong>{s.access_requirements}</strong></span>
                    <span>Evidence: <strong>{s.evidence_classification}</strong></span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* 4. EXECUTION RUNS VIEW                                                    */}
      {/* ========================================================================= */}
      {activeSubTab === 'runs' && (
        <div className="space-y-3">
          {runs.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center bg-slate-50/50">
              <Clock className="h-8 w-8 mx-auto text-slate-300" />
              <p className="mt-2 text-xs font-semibold text-slate-700">No Threat Analysis Executions Yet</p>
            </div>
          ) : (
            <div className="space-y-2">
              {runs.map((r) => (
                <div key={r.id} className="rounded-xl border border-slate-200 bg-white p-3.5 flex items-center justify-between text-xs">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-0.5 rounded font-bold text-[10px] uppercase ${r.status === 'completed' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-rose-50 text-rose-700 border border-rose-200'}`}>
                        {r.status}
                      </span>
                      <span className="font-mono text-[11px] font-bold text-slate-800">{r.model_name}</span>
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">
                      Discovered {r.assets_discovered_count} assets, {r.attack_surfaces_count} surfaces, generated {r.threats_generated_count} threats in {r.execution_duration_ms ? `${(r.execution_duration_ms / 1000).toFixed(2)}s` : 'N/A'}.
                    </p>
                  </div>
                  <div className="text-right text-[10px] text-slate-400">
                    <div>{new Date(r.created_at).toLocaleString()}</div>
                    {r.status === 'failed' && (
                      <button
                        onClick={() => threatApi.retryThreatRun(orgId, auditId, r.id).then(fetchData)}
                        className="mt-1 text-rose-600 hover:text-rose-700 font-bold underline cursor-pointer"
                      >
                        Retry Execution
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* THREAT DETAIL DRAWER / MODAL                                              */}
      {/* ========================================================================= */}
      {selectedThreat && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-4xl max-h-[92vh] flex flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 bg-white shrink-0">
              <div className="flex items-center space-x-3">
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase ${getSeverityBadge(selectedThreat.severity)}`}>
                  {selectedThreat.severity.replace('_', ' ')}
                </span>
                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${getStrideBadge(selectedThreat.stride_category)}`}>
                  {selectedThreat.stride_category}
                </span>
                <h4 className="font-bold text-slate-900 text-sm truncate max-w-lg">{selectedThreat.threat_title}</h4>
              </div>
              <button
                onClick={() => setSelectedThreat(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Scrollable Content */}
            <div className="p-6 overflow-y-auto space-y-6 text-xs flex-1">
              {/* Risk & CIA Meter */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 bg-slate-50 p-4 rounded-xl border border-slate-200">
                <div>
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Deterministic Risk Score</div>
                  <div className="text-xl font-black text-rose-600 mt-1">
                    {selectedThreat.risk_score} <span className="text-xs font-normal text-slate-400">/ 25</span>
                  </div>
                  <div className="text-[10px] text-slate-500 mt-0.5">
                    Likelihood ({selectedThreat.likelihood_score}) × Impact ({selectedThreat.impact_score})
                  </div>
                </div>

                <div>
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Confidentiality</div>
                  <div className="mt-1 font-bold text-slate-800 uppercase">{selectedThreat.cia_confidentiality}</div>
                  <p className="text-[10px] text-slate-400">Data exposure risk</p>
                </div>

                <div>
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Integrity</div>
                  <div className="mt-1 font-bold text-slate-800 uppercase">{selectedThreat.cia_integrity}</div>
                  <p className="text-[10px] text-slate-400">Tampering / modification</p>
                </div>

                <div>
                  <div className="text-[10px] font-bold text-slate-400 uppercase">Availability</div>
                  <div className="mt-1 font-bold text-slate-800 uppercase">{selectedThreat.cia_availability}</div>
                  <p className="text-[10px] text-slate-400">Service disruption</p>
                </div>
              </div>

              {/* Provisional Warning */}
              {selectedThreat.is_provisional && (
                <div className="rounded-xl border border-amber-200 bg-amber-50 p-3.5 space-y-1">
                  <div className="flex items-center space-x-1.5 font-bold text-amber-900">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>Provisional Assessment — Architecture Assumptions Required</span>
                  </div>
                  <p className="text-[11px] text-amber-800">
                    This threat rating is provisional due to unstated assumptions or missing architecture configurations.
                  </p>
                  {selectedThreat.assumptions && selectedThreat.assumptions.length > 0 && (
                    <ul className="list-disc list-inside text-[11px] text-amber-800 pt-1">
                      {selectedThreat.assumptions.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* Scenario Narrative */}
              <div>
                <h5 className="font-bold text-slate-900 mb-1.5">Scenario Narrative</h5>
                <p className="text-slate-700 leading-relaxed bg-slate-50 p-3 rounded-lg border border-slate-200">
                  {selectedThreat.threat_description}
                </p>
              </div>

              {/* Attack Vector & Preconditions */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Attack Objective</span>
                  <p className="text-slate-800 font-semibold mt-1">{selectedThreat.attack_objective || 'N/A'}</p>
                </div>
                <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">Preconditions</span>
                  <p className="text-slate-800 font-semibold mt-1">{selectedThreat.preconditions || 'N/A'}</p>
                </div>
              </div>

              {/* Attack Path Tree Visualizer */}
              <div>
                <h5 className="font-bold text-slate-900 mb-2 flex items-center space-x-2">
                  <GitBranch className="h-4 w-4 text-rose-600" />
                  <span>Attack Path Decomposition (Attack Tree)</span>
                </h5>
                <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 space-y-3">
                  {selectedThreat.attack_path_nodes && selectedThreat.attack_path_nodes.length > 0 ? (
                    selectedThreat.attack_path_nodes.map((node, idx) => (
                      <div
                        key={node.id || idx}
                        className="flex items-start space-x-3 bg-white p-3 rounded-lg border border-slate-200 shadow-2xs"
                      >
                        <div className="h-6 w-6 rounded-full bg-rose-50 border border-rose-200 text-rose-600 font-bold flex items-center justify-center shrink-0 text-[10px]">
                          {node.sequence_number || idx + 1}
                        </div>
                        <div className="flex-1">
                          <div className="flex items-center space-x-2">
                            <span className="font-bold text-slate-800">{node.node_id}</span>
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-100 font-mono text-slate-600">
                              {node.node_type}
                            </span>
                            {node.logical_operator && (
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-purple-100 text-purple-700 font-bold">
                                {node.logical_operator}
                              </span>
                            )}
                          </div>
                          <p className="text-slate-600 mt-1 text-[11px]">{node.description}</p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-400 italic">No structured attack nodes generated for this scenario.</p>
                  )}
                </div>
              </div>

              {/* Mapped Regulatory Requirements */}
              <div>
                <h5 className="font-bold text-slate-900 mb-2 flex items-center space-x-2">
                  <ShieldCheck className="h-4 w-4 text-blue-600" />
                  <span>Mapped Approved Regulatory Requirements</span>
                </h5>
                <div className="space-y-2">
                  {selectedThreat.requirement_mappings && selectedThreat.requirement_mappings.length > 0 ? (
                    selectedThreat.requirement_mappings.map((m) => (
                      <div key={m.id} className="p-3 bg-blue-50/40 rounded-lg border border-blue-200">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            <span className="font-bold font-mono text-blue-700">{m.requirement_code}</span>
                            <span className="text-[10px] bg-white px-2 py-0.5 rounded border border-blue-200 font-semibold text-blue-800">
                              {m.framework_name}
                            </span>
                            <span className="text-[10px] text-slate-500 font-semibold">({m.category})</span>
                          </div>
                          <span className="text-[10px] font-bold text-blue-800 uppercase">{m.relationship_type.replace('_', ' ')}</span>
                        </div>
                        <p className="text-slate-800 font-medium mt-1">{m.requirement_title}</p>
                        {m.rationale && (
                          <p className="text-[11px] text-blue-900 mt-1 italic">Rationale: {m.rationale}</p>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-400 italic">No direct regulatory mappings identified for this threat.</p>
                  )}
                </div>
              </div>

              {/* Evidence & Citations */}
              <div>
                <h5 className="font-bold text-slate-900 mb-2 flex items-center space-x-2">
                  <FileText className="h-4 w-4 text-emerald-600" />
                  <span>Evidence Traceability Citations</span>
                </h5>
                <div className="space-y-2">
                  {selectedThreat.evidence_references && selectedThreat.evidence_references.length > 0 ? (
                    selectedThreat.evidence_references.map((ev) => (
                      <div key={ev.id} className="p-3 bg-emerald-50/30 rounded-lg border border-emerald-200">
                        <div className="flex items-center justify-between text-[10px] text-emerald-900 font-semibold">
                          <span>File: {ev.original_filename} (Page {ev.page_number || 'N/A'})</span>
                          <span className="font-bold uppercase">{ev.evidence_classification}</span>
                        </div>
                        <blockquote className="mt-1 text-[11px] text-slate-700 italic border-l-2 border-emerald-500 pl-2">
                          "{ev.exact_excerpt}"
                        </blockquote>
                      </div>
                    ))
                  ) : (
                    <p className="text-slate-400 italic">No direct source excerpts linked to this threat.</p>
                  )}
                </div>
              </div>

              {/* Audit Trail */}
              {selectedThreat.audit_history && selectedThreat.audit_history.length > 0 && (
                <div>
                  <h5 className="font-bold text-slate-900 mb-2">Review Audit Trail</h5>
                  <div className="space-y-1.5">
                    {selectedThreat.audit_history.map((h) => (
                      <div key={h.id} className="flex items-center justify-between p-2 rounded bg-slate-50 border border-slate-200 text-[11px]">
                        <div>
                          <span className="font-bold text-slate-800">{h.reviewer_name || 'Auditor'}</span>:{' '}
                          <span className="font-semibold text-rose-600">{h.action}</span>
                          {h.reason && <span className="text-slate-500"> — "{h.reason}"</span>}
                        </div>
                        <span className="text-[10px] text-slate-400 font-mono">
                          {new Date(h.created_at).toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Modal Actions Footer */}
            <div className="flex flex-wrap items-center justify-between px-6 py-3 border-t border-slate-200 bg-slate-50 shrink-0 gap-2">
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleAcceptThreat(selectedThreat.id)}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-bold text-xs bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer"
                >
                  <Check className="h-3.5 w-3.5" />
                  <span>Accept Threat</span>
                </button>

                <button
                  onClick={() => handleRejectClick(selectedThreat.id)}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-bold text-xs bg-rose-600 hover:bg-rose-700 text-white cursor-pointer"
                >
                  <X className="h-3.5 w-3.5" />
                  <span>Reject</span>
                </button>

                <button
                  onClick={() => handleEditClick(selectedThreat)}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-semibold text-xs bg-slate-200 hover:bg-slate-300 text-slate-700 cursor-pointer"
                >
                  <Edit3 className="h-3.5 w-3.5" />
                  <span>Edit Scenario</span>
                </button>

                <button
                  onClick={() => handleRequestInfo(selectedThreat.id)}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg font-semibold text-xs bg-purple-100 hover:bg-purple-200 text-purple-800 cursor-pointer"
                >
                  <HelpCircle className="h-3.5 w-3.5" />
                  <span>Request More Info</span>
                </button>
              </div>

              <button
                onClick={() => setSelectedThreat(null)}
                className="px-4 py-1.5 rounded-lg bg-slate-200 hover:bg-slate-300 font-semibold text-slate-700 cursor-pointer"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* REJECT MODAL (MANDATORY REASON)                                           */}
      {/* ========================================================================= */}
      {rejectModalOpen && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-md bg-white rounded-xl shadow-xl p-5 border border-slate-200 space-y-4">
            <h4 className="font-bold text-slate-900 text-sm">Reject Threat Scenario</h4>
            <p className="text-xs text-slate-500">
              Provide an architectural or compensatory justification for rejecting this threat scenario.
            </p>
            <textarea
              rows={3}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. System employs strict hardware-backed mTLS authentication, eliminating unauthenticated spoofing vector."
              className="w-full text-xs p-2.5 rounded-lg border border-slate-300 focus:outline-rose-500"
            />
            <div className="flex items-center justify-end space-x-2 pt-2">
              <button
                onClick={() => setRejectModalOpen(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-semibold text-slate-700 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmReject}
                className="px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-xs font-bold text-white cursor-pointer"
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* EDIT MODAL                                                                */}
      {/* ========================================================================= */}
      {editModalOpen && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg bg-white rounded-xl shadow-xl p-5 border border-slate-200 space-y-4">
            <h4 className="font-bold text-slate-900 text-sm">Modify Threat Scenario Parameters</h4>
            
            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Threat Title</label>
                <input
                  type="text"
                  value={editFormData.threat_title}
                  onChange={(e) => setEditFormData({ ...editFormData, threat_title: e.target.value })}
                  className="w-full p-2 border border-slate-300 rounded-lg text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Likelihood (1-5)</label>
                  <select
                    value={editFormData.likelihood_score}
                    onChange={(e) => setEditFormData({ ...editFormData, likelihood_score: parseInt(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded-lg text-xs"
                  >
                    <option value={1}>1 - Very Low</option>
                    <option value={2}>2 - Low</option>
                    <option value={3}>3 - Moderate</option>
                    <option value={4}>4 - High</option>
                    <option value={5}>5 - Very High</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-slate-700 block mb-1">Impact (1-5)</label>
                  <select
                    value={editFormData.impact_score}
                    onChange={(e) => setEditFormData({ ...editFormData, impact_score: parseInt(e.target.value) })}
                    className="w-full p-2 border border-slate-300 rounded-lg text-xs"
                  >
                    <option value={1}>1 - Negligible</option>
                    <option value={2}>2 - Minor</option>
                    <option value={3}>3 - Moderate</option>
                    <option value={4}>4 - Major</option>
                    <option value={5}>5 - Severe</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Auditor Justification</label>
                <input
                  type="text"
                  placeholder="Reason for modifying parameters"
                  value={editFormData.reason}
                  onChange={(e) => setEditFormData({ ...editFormData, reason: e.target.value })}
                  className="w-full p-2 border border-slate-300 rounded-lg text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setEditModalOpen(false)}
                className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-xs font-semibold text-slate-700 cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmEdit}
                className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-xs font-bold text-white cursor-pointer"
              >
                Save &amp; Recalculate Risk
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

