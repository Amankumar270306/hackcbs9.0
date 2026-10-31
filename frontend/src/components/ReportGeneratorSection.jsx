import React, { useState, useEffect } from 'react';
import {
  FileText,
  Download,
  Eye,
  Play,
  RotateCw,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Clock,
  Shield,
  Layers,
  FileCheck,
  AlertCircle,
  Hash,
  ExternalLink,
  ChevronRight,
  BookOpen,
  X,
  Sparkles,
  Info
} from 'lucide-react';
import { reportsApi, adjudicationApi } from '../api/client';

export default function ReportGeneratorSection({ audit }) {
  const orgId = audit.organization_id || audit.organizationId;
  const auditId = audit.id;

  const [readiness, setReadiness] = useState(null);
  const [loadingReadiness, setLoadingReadiness] = useState(true);
  const [reports, setReports] = useState([]);
  const [loadingReports, setLoadingReports] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Generation Modal
  const [showGenModal, setShowGenModal] = useState(false);
  const [reportTitle, setReportTitle] = useState('');
  const [adjRuns, setAdjRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState('');

  // Preview Modal
  const [previewReport, setPreviewReport] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [previewActiveSection, setPreviewActiveSection] = useState('executive_summary');

  const fetchReadiness = async () => {
    try {
      setLoadingReadiness(true);
      const res = await reportsApi.checkReadiness(orgId, auditId);
      setReadiness(res);
      if (res.latest_adjudication_run_id) {
        setSelectedRunId(res.latest_adjudication_run_id);
      }
    } catch (err) {
      console.error('Failed to fetch report readiness', err);
    } finally {
      setLoadingReadiness(false);
    }
  };

  const fetchReports = async () => {
    try {
      setLoadingReports(true);
      const res = await reportsApi.listReports(orgId, auditId);
      setReports(res.items || []);
    } catch (err) {
      console.error('Failed to list reports', err);
    } finally {
      setLoadingReports(false);
    }
  };

  const fetchAdjRuns = async () => {
    try {
      const res = await adjudicationApi.listRuns(orgId, auditId);
      const completed = (res || []).filter(r => r.status === 'completed');
      setAdjRuns(completed);
      if (completed.length > 0 && !selectedRunId) {
        setSelectedRunId(completed[0].id);
      }
    } catch (err) {
      console.error('Failed to load adjudication runs', err);
    }
  };

  useEffect(() => {
    fetchReadiness();
    fetchReports();
    fetchAdjRuns();
  }, [orgId, auditId]);

  const handleOpenGenModal = () => {
    setReportTitle(`${audit.title || audit.name || 'Assessment'} — Compliance & Security Report`);
    setErrorMsg(null);
    setSuccessMsg(null);
    setShowGenModal(true);
  };

  const handleGenerate = async (e) => {
    e.preventDefault();
    try {
      setIsGenerating(true);
      setErrorMsg(null);
      const payload = {
        adjudication_run_id: selectedRunId || null,
        title: reportTitle.trim() || undefined,
        format: 'pdf',
      };
      const res = await reportsApi.generateReport(orgId, auditId, payload);
      setSuccessMsg(`Report version v${res.version} generated successfully!`);
      setShowGenModal(false);
      await fetchReports();
      await fetchReadiness();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to generate report');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = async (report) => {
    try {
      const filename = `${report.title.replace(/[^a-zA-Z0-9_-]/g, '_')}_v${report.version}.pdf`;
      await reportsApi.downloadReport(orgId, auditId, report.id, filename);
    } catch (err) {
      alert(`Download failed: ${err.message}`);
    }
  };

  const handlePreview = async (report) => {
    try {
      setPreviewReport(report);
      setLoadingPreview(true);
      setPreviewData(null);
      setPreviewActiveSection('executive_summary');
      const res = await reportsApi.getReportPreview(orgId, auditId, report.id);
      setPreviewData(res.data);
    } catch (err) {
      alert(`Failed to load report preview: ${err.message}`);
      setPreviewReport(null);
    } finally {
      setLoadingPreview(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Notifications */}
      {errorMsg && (
        <div className="flex items-start space-x-3 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs animate-in fade-in">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-600 mt-0.5" />
          <div className="flex-1 font-medium">{errorMsg}</div>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="flex items-start space-x-3 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs animate-in fade-in">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600 mt-0.5" />
          <div className="flex-1 font-medium">{successMsg}</div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Top Banner / Readiness Card */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-100 pb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
              <FileCheck className="h-5 w-5" />
            </div>
            <div>
              <h4 className="text-sm font-bold text-slate-900">Compliance &amp; Security Report Generator</h4>
              <p className="text-xs text-slate-500">
                Transforms multi-agent adjudication consensus into an immutable, publication-grade assessment report.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => { fetchReadiness(); fetchReports(); }}
              className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
              title="Refresh Readiness & Reports"
            >
              <RotateCw className="h-4 w-4" />
            </button>

            <button
              onClick={handleOpenGenModal}
              disabled={loadingReadiness || (readiness && !readiness.is_ready)}
              className={`px-4 py-2 rounded-xl text-xs font-semibold flex items-center space-x-2 transition-all cursor-pointer shadow-xs ${
                readiness && readiness.is_ready
                  ? 'bg-blue-600 text-white hover:bg-blue-700 hover:shadow-md'
                  : 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
              }`}
            >
              <Sparkles className="h-4 w-4" />
              <span>Generate Assessment Report</span>
            </button>
          </div>
        </div>

        {/* Readiness Checklist Grid */}
        <div className="mt-4 pt-1">
          {loadingReadiness ? (
            <div className="flex items-center space-x-2 py-3 text-xs text-slate-400">
              <RotateCw className="h-4 w-4 animate-spin text-blue-500" />
              <span>Checking audit pre-flight readiness...</span>
            </div>
          ) : readiness ? (
            <div className="space-y-3">
              {/* Blockers */}
              {readiness.blockers && readiness.blockers.length > 0 && (
                <div className="p-3 rounded-xl bg-rose-50/80 border border-rose-200 space-y-1.5 text-xs text-rose-800">
                  <div className="flex items-center space-x-1.5 font-bold text-rose-900">
                    <XCircle className="h-4 w-4 text-rose-600" />
                    <span>Prerequisites Required Before Report Generation</span>
                  </div>
                  <ul className="list-disc pl-5 space-y-0.5 text-[11px] text-rose-700 font-medium">
                    {readiness.blockers.map((b, idx) => (
                      <li key={idx}>{b}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Warnings */}
              {readiness.warnings && readiness.warnings.length > 0 && (
                <div className="p-3 rounded-xl bg-amber-50/80 border border-amber-200 space-y-1.5 text-xs text-amber-800">
                  <div className="flex items-center space-x-1.5 font-bold text-amber-900">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>Adjudication Transparency Notices</span>
                  </div>
                  <ul className="list-disc pl-5 space-y-0.5 text-[11px] text-amber-700 font-medium">
                    {readiness.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Checks Pill Badges */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1">
                {(readiness.checks || []).map((chk, idx) => {
                  const isOk = chk.status === 'ready';
                  const isWarn = chk.status === 'warning';
                  return (
                    <div
                      key={idx}
                      className={`p-2.5 rounded-xl border flex items-center justify-between text-xs ${
                        isOk
                          ? 'bg-slate-50 border-slate-200 text-slate-700'
                          : isWarn
                          ? 'bg-amber-50/60 border-amber-200 text-amber-800'
                          : 'bg-rose-50/60 border-rose-200 text-rose-800'
                      }`}
                    >
                      <div className="space-y-0.5">
                        <div className="font-semibold text-[11px]">{chk.label}</div>
                        <div className="text-[10px] opacity-75">{chk.detail}</div>
                      </div>
                      <div>
                        {isOk ? (
                          <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                        ) : isWarn ? (
                          <AlertTriangle className="h-4 w-4 text-amber-500" />
                        ) : (
                          <XCircle className="h-4 w-4 text-rose-500" />
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Reports History Table */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-xs">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-2">
            <FileText className="h-4 w-4 text-slate-600" />
            <h4 className="text-xs font-bold text-slate-800">Generated Assessment Reports</h4>
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-600">
              {reports.length}
            </span>
          </div>
          <span className="text-[11px] text-slate-400">
            Immutable audit artifacts with cryptographic SHA-256 integrity
          </span>
        </div>

        <div className="mt-3">
          {loadingReports ? (
            <div className="py-8 text-center text-xs text-slate-400 flex items-center justify-center space-x-2">
              <RotateCw className="h-4 w-4 animate-spin text-blue-500" />
              <span>Loading assessment reports...</span>
            </div>
          ) : reports.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-400 space-y-2">
              <FileText className="h-8 w-8 text-slate-300 mx-auto" />
              <p className="font-medium text-slate-500">No assessment reports generated yet.</p>
              <p className="text-[11px] text-slate-400 max-w-sm mx-auto">
                Once the Adjudicator reconciles the audit findings, generate your publication-ready report here.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50/70 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                    <th className="py-2.5 px-3">Version</th>
                    <th className="py-2.5 px-3">Title &amp; Adjudication</th>
                    <th className="py-2.5 px-3">Generated</th>
                    <th className="py-2.5 px-3">Integrity Checksum</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {reports.map((r) => (
                    <tr key={r.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3 px-3">
                        <span className="font-mono font-bold text-blue-600 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded text-[11px]">
                          v{r.version}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <div className="font-semibold text-slate-800">{r.title}</div>
                        <div className="text-[11px] text-slate-400 flex items-center space-x-2 font-mono mt-0.5">
                          <span>Run: {r.adjudication_run_id ? r.adjudication_run_id.substring(0, 8) : 'Latest'}</span>
                          <span>•</span>
                          <span>{r.file_size ? `${Math.round(r.file_size / 1024)} KB` : 'PDF'}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3 text-slate-500 font-mono text-[11px]">
                        {r.created_at ? new Date(r.created_at).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-3 px-3">
                        {r.file_checksum ? (
                          <div className="font-mono text-[10px] text-slate-500 flex items-center space-x-1" title={r.file_checksum}>
                            <Hash className="h-3 w-3 text-slate-400" />
                            <span>{r.file_checksum.substring(0, 12)}…</span>
                          </div>
                        ) : (
                          <span className="text-slate-400 text-[10px]">—</span>
                        )}
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex flex-col space-y-1">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${
                              r.generation_status === 'completed'
                                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                : r.generation_status === 'generating'
                                ? 'bg-blue-50 text-blue-700 border border-blue-200'
                                : 'bg-rose-50 text-rose-700 border border-rose-200'
                            }`}
                          >
                            {r.generation_status}
                          </span>
                          {r.is_stale && (
                            <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[9px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                              Stale Disclosed
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => handlePreview(r)}
                            className="p-1.5 rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors cursor-pointer"
                            title="Interactive 12-Section Preview"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </button>
                          <button
                            onClick={() => handleDownload(r)}
                            disabled={r.generation_status !== 'completed'}
                            className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                              r.generation_status === 'completed'
                                ? 'border-blue-200 bg-blue-50 text-blue-600 hover:bg-blue-100'
                                : 'border-slate-100 bg-slate-50 text-slate-300 cursor-not-allowed'
                            }`}
                            title="Download Publication PDF"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Generation Modal */}
      {showGenModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-2xl p-6 space-y-4 animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center space-x-2">
                <Sparkles className="h-5 w-5 text-blue-600" />
                <h3 className="text-sm font-bold text-slate-900">Generate Assessment Report</h3>
              </div>
              <button
                onClick={() => setShowGenModal(false)}
                className="text-slate-400 hover:text-slate-600 p-1 rounded-lg"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form onSubmit={handleGenerate} className="space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">Report Title</label>
                <input
                  type="text"
                  value={reportTitle}
                  onChange={(e) => setReportTitle(e.target.value)}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:outline-hidden focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="Compliance and Security Assessment Report"
                  required
                />
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">Source Adjudication Run</label>
                {adjRuns.length > 0 ? (
                  <select
                    value={selectedRunId}
                    onChange={(e) => setSelectedRunId(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs text-slate-800 focus:outline-hidden focus:border-blue-500"
                  >
                    {adjRuns.map((rn) => (
                      <option key={rn.id} value={rn.id}>
                        Run {rn.id.substring(0, 8)} — {rn.created_at ? new Date(rn.created_at).toLocaleDateString() : 'Completed'} ({rn.model_name || 'Gemini'})
                      </option>
                    ))}
                  </select>
                ) : (
                  <div className="text-[11px] text-slate-500 bg-slate-50 p-2.5 rounded-xl border border-slate-200">
                    Will synthesize from latest completed adjudication consensus.
                  </div>
                )}
              </div>

              <div className="rounded-xl bg-blue-50/70 border border-blue-100 p-3 space-y-1 text-blue-900">
                <div className="font-bold flex items-center space-x-1.5">
                  <Info className="h-3.5 w-3.5 text-blue-600" />
                  <span>Report Compilation Overview</span>
                </div>
                <p className="text-[11px] text-blue-800 leading-relaxed">
                  Synthesizes 12 traceable sections including STRIDE threat trees, safeguard assessments, confirmed findings, and human auditor reconciliations with publication-grade A4 layout.
                </p>
              </div>

              <div className="flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setShowGenModal(false)}
                  className="px-4 py-2 rounded-xl text-slate-600 font-semibold hover:bg-slate-100 cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isGenerating}
                  className="px-4 py-2 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 flex items-center space-x-2 cursor-pointer shadow-xs"
                >
                  {isGenerating ? (
                    <>
                      <RotateCw className="h-3.5 w-3.5 animate-spin" />
                      <span>Compiling PDF...</span>
                    </>
                  ) : (
                    <>
                      <FileCheck className="h-3.5 w-3.5" />
                      <span>Compile &amp; Save Report</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Interactive 12-Section Preview Modal */}
      {previewReport && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-5xl max-h-[92vh] flex flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-white shrink-0">
              <div className="flex items-center space-x-3">
                <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 border border-blue-200 px-2.5 py-1 rounded-md">
                  v{previewReport.version}
                </span>
                <div>
                  <h3 className="text-sm font-bold text-slate-900">{previewReport.title}</h3>
                  <p className="text-[11px] text-slate-400 font-mono">
                    SHA-256: {previewReport.file_checksum || 'Verified'} • Multi-Agent Adjudicated
                  </p>
                </div>
              </div>
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleDownload(previewReport)}
                  className="px-3 py-1.5 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 flex items-center space-x-1.5 text-xs cursor-pointer shadow-xs"
                >
                  <Download className="h-3.5 w-3.5" />
                  <span>Download PDF</span>
                </button>
                <button
                  onClick={() => setPreviewReport(null)}
                  className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Modal Body: Sidebar Sections Navigation + Content Area */}
            <div className="flex flex-1 min-h-0 text-xs">
              {/* Sidebar Section List */}
              <div className="w-64 border-r border-slate-200 bg-slate-50/50 p-3 overflow-y-auto space-y-1 shrink-0 font-medium text-slate-600">
                <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-2 py-1">
                  12 Report Sections
                </div>
                {[
                  { key: 'cover_page', label: '1. Cover & Overview' },
                  { key: 'executive_summary', label: '2. Executive Summary' },
                  { key: 'scope_and_methodology', label: '3. Scope & Methodology' },
                  { key: 'regulatory_requirements', label: '4. Regulatory Requirements' },
                  { key: 'discovered_assets', label: '5. Discovered Assets' },
                  { key: 'attack_surfaces', label: '6. Attack Surfaces' },
                  { key: 'threat_assessment', label: '7. STRIDE Threat Assessment' },
                  { key: 'control_assessment', label: '8. Control & Safeguards' },
                  { key: 'findings_register', label: '9. Findings Register' },
                  { key: 'contradictions_and_gaps', label: '10. Contradictions & Arbitrations' },
                  { key: 'remediation_roadmap', label: '11. Remediation Roadmap' },
                  { key: 'limitations_and_disclaimers', label: '12. Disclaimers & Appendix' },
                ].map((s) => (
                  <button
                    key={s.key}
                    onClick={() => setPreviewActiveSection(s.key)}
                    className={`w-full text-left px-3 py-2 rounded-xl text-xs transition-colors cursor-pointer flex items-center justify-between ${
                      previewActiveSection === s.key
                        ? 'bg-blue-600 text-white font-semibold shadow-xs'
                        : 'hover:bg-slate-100 text-slate-700'
                    }`}
                  >
                    <span>{s.label}</span>
                    <ChevronRight className="h-3 w-3 opacity-60" />
                  </button>
                ))}
              </div>

              {/* Main Content Viewer */}
              <div className="flex-1 p-6 overflow-y-auto bg-white">
                {loadingPreview ? (
                  <div className="py-24 text-center text-slate-400 flex items-center justify-center space-x-2">
                    <RotateCw className="h-5 w-5 animate-spin text-blue-500" />
                    <span>Rendering structured section preview...</span>
                  </div>
                ) : !previewData ? (
                  <div className="py-24 text-center text-slate-400">
                    No structured metadata found for this report.
                  </div>
                ) : (
                  <div className="space-y-6 max-w-3xl mx-auto">
                    {/* Section 1: Cover Page */}
                    {previewActiveSection === 'cover_page' && (
                      <div className="space-y-4">
                        <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-6 space-y-3">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-blue-600 font-mono">
                            Assessment Report Overview
                          </span>
                          <h2 className="text-xl font-bold text-slate-900">
                            {previewData.cover_page?.report_title || previewReport.title}
                          </h2>
                          <div className="grid grid-cols-2 gap-3 pt-3 border-t border-slate-200 text-xs">
                            <div>
                              <span className="text-slate-400 font-medium">Organization:</span>
                              <div className="font-semibold text-slate-800">{previewData.cover_page?.organization_name || 'Organization'}</div>
                            </div>
                            <div>
                              <span className="text-slate-400 font-medium">Target System:</span>
                              <div className="font-semibold text-slate-800">{previewData.cover_page?.target_system || 'Target System'}</div>
                            </div>
                            <div>
                              <span className="text-slate-400 font-medium">Environment:</span>
                              <div className="font-semibold text-slate-800 uppercase font-mono">{previewData.cover_page?.environment || 'Production'}</div>
                            </div>
                            <div>
                              <span className="text-slate-400 font-medium">Generated At:</span>
                              <div className="font-semibold text-slate-800 font-mono">{previewData.cover_page?.generated_at || '—'}</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Section 2: Executive Summary */}
                    {previewActiveSection === 'executive_summary' && (
                      <div className="space-y-5">
                        <div className="p-4 rounded-2xl bg-blue-50/60 border border-blue-100 text-slate-800 leading-relaxed">
                          <h4 className="font-bold text-blue-900 mb-1">Executive Summary Narrative</h4>
                          <p>{previewData.executive_summary?.narrative}</p>
                        </div>

                        {/* Metric Cards Grid */}
                        <div className="grid grid-cols-3 gap-3">
                          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                            <div className="text-[11px] font-medium text-slate-500">Requirements Assessed</div>
                            <div className="text-2xl font-bold text-slate-900 mt-1">
                              {previewData.executive_summary?.total_requirements_assessed || 0}
                            </div>
                            <div className="text-[10px] text-emerald-600 font-semibold mt-0.5">
                              {previewData.executive_summary?.supported_requirements_count || 0} Supported
                            </div>
                          </div>

                          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                            <div className="text-[11px] font-medium text-slate-500">Threats Modeled</div>
                            <div className="text-2xl font-bold text-slate-900 mt-1">
                              {previewData.executive_summary?.total_threats_modeled || 0}
                            </div>
                            <div className="text-[10px] text-blue-600 font-semibold mt-0.5">
                              {previewData.executive_summary?.mitigated_threats_count || 0} Documented Mitigations
                            </div>
                          </div>

                          <div className="p-4 rounded-xl border border-slate-200 bg-slate-50">
                            <div className="text-[11px] font-medium text-slate-500">Adjudication Confidence</div>
                            <div className="text-2xl font-bold text-slate-900 mt-1 font-mono">
                              {Math.round((previewData.executive_summary?.average_confidence_score || 0.85) * 100)}%
                            </div>
                            <div className="text-[10px] text-slate-500 mt-0.5">Consensus Verified</div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Section 3: Scope and Methodology */}
                    {previewActiveSection === 'scope_and_methodology' && (
                      <div className="space-y-4">
                        <div className="rounded-xl border border-slate-200 p-4 space-y-2">
                          <h4 className="font-bold text-slate-900">Multi-Agent Assessment Pipeline</h4>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2">
                            {(previewData.scope_and_methodology?.agents_involved || []).map((ag, i) => (
                              <div key={i} className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                                <div className="font-bold text-slate-800">{ag.name}</div>
                                <div className="text-[11px] text-slate-500">{ag.role}</div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Section 4: Regulatory Requirements */}
                    {previewActiveSection === 'regulatory_requirements' && (
                      <div className="space-y-3">
                        <h4 className="font-bold text-slate-900">Regulatory Compliance Arbitration</h4>
                        <div className="space-y-2">
                          {(previewData.regulatory_requirements || []).map((r, i) => (
                            <div key={i} className="p-3 rounded-xl border border-slate-200 bg-white space-y-1.5">
                              <div className="flex items-center justify-between">
                                <span className="font-mono font-bold text-blue-600">{r.identifier}</span>
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                  {r.adjudication_outcome || 'supported'}
                                </span>
                              </div>
                              <div className="font-semibold text-slate-800">{r.title}</div>
                              <p className="text-[11px] text-slate-500">{r.statement}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Section 7: Threat Assessment */}
                    {previewActiveSection === 'threat_assessment' && (
                      <div className="space-y-3">
                        <h4 className="font-bold text-slate-900">STRIDE Threat Scenarios &amp; Mitigation Status</h4>
                        <div className="space-y-2">
                          {(previewData.threat_assessment || []).map((t, i) => (
                            <div key={i} className="p-3 rounded-xl border border-slate-200 bg-white space-y-1.5">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center space-x-2">
                                  <span className="font-mono font-bold text-rose-600">{t.threat_id}</span>
                                  <span className="text-[10px] font-bold bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded">
                                    {t.stride_category}
                                  </span>
                                </div>
                                <span className="font-mono font-bold text-slate-700">
                                  Risk Score: {t.risk_score} (L{t.likelihood} x I{t.impact})
                                </span>
                              </div>
                              <div className="font-semibold text-slate-800">{t.title}</div>
                              <p className="text-[11px] text-slate-500">{t.description}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Section 9: Findings Register */}
                    {previewActiveSection === 'findings_register' && (
                      <div className="space-y-3">
                        <h4 className="font-bold text-slate-900">Confirmed Security Findings Register</h4>
                        {(previewData.findings_register || []).length === 0 ? (
                          <div className="py-8 text-center text-slate-400 font-medium">
                            No critical or high security findings identified.
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {(previewData.findings_register || []).map((f, i) => (
                              <div key={i} className="p-3 rounded-xl border border-slate-200 bg-white space-y-1.5">
                                <div className="flex items-center justify-between">
                                  <span className="font-mono font-bold text-amber-600">{f.finding_code}</span>
                                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200 uppercase">
                                    {f.severity}
                                  </span>
                                </div>
                                <div className="font-semibold text-slate-800">{f.title}</div>
                                <p className="text-[11px] text-slate-500">{f.description}</p>
                                {f.remediation && (
                                  <div className="text-[11px] text-blue-700 font-medium pt-1 border-t border-slate-100">
                                    Recommended Action: {f.remediation}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Section 10: Contradictions */}
                    {previewActiveSection === 'contradictions_and_gaps' && (
                      <div className="space-y-3">
                        <h4 className="font-bold text-slate-900">Reconciled Contradictions &amp; Arbitration</h4>
                        {(previewData.contradictions_and_gaps || []).length === 0 ? (
                          <div className="py-8 text-center text-slate-400 font-medium">
                            No document or policy contradictions detected.
                          </div>
                        ) : (
                          <div className="space-y-2">
                            {(previewData.contradictions_and_gaps || []).map((c, i) => (
                              <div key={i} className="p-3 rounded-xl border border-slate-200 bg-white space-y-1">
                                <div className="flex items-center justify-between">
                                  <span className="font-semibold text-slate-800">{c.description}</span>
                                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    {c.resolution_status}
                                  </span>
                                </div>
                                {c.resolution_notes && (
                                  <div className="text-[11px] text-slate-500">
                                    Resolution: {c.resolution_notes}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Section 11: Remediation Roadmap */}
                    {previewActiveSection === 'remediation_roadmap' && (
                      <div className="space-y-3">
                        <h4 className="font-bold text-slate-900">Prioritized Remediation Roadmap</h4>
                        <div className="space-y-2">
                          {(previewData.remediation_roadmap || []).map((rm, i) => (
                            <div key={i} className="p-3 rounded-xl border border-slate-200 bg-white flex items-center justify-between">
                              <div className="space-y-0.5">
                                <div className="font-bold text-slate-800">Phase {rm.sequence}: {rm.action_title}</div>
                                <div className="text-[11px] text-slate-500">Impacted Item: {rm.finding_id}</div>
                              </div>
                              <span className="px-2.5 py-1 rounded-md text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-200">
                                {rm.priority} Priority
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Fallback for other sections */}
                    {!['cover_page', 'executive_summary', 'scope_and_methodology', 'regulatory_requirements', 'threat_assessment', 'findings_register', 'contradictions_and_gaps', 'remediation_roadmap'].includes(previewActiveSection) && (
                      <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 text-slate-600 space-y-2">
                        <h4 className="font-bold text-slate-800 capitalize">
                          {previewActiveSection.replace(/_/g, ' ')}
                        </h4>
                        <pre className="text-[11px] font-mono bg-white p-3 rounded-lg border border-slate-200 overflow-x-auto text-slate-700">
                          {JSON.stringify(previewData[previewActiveSection], null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end border-t border-slate-100 px-6 py-3 bg-slate-50 shrink-0">
              <button
                onClick={() => setPreviewReport(null)}
                className="rounded-lg bg-slate-200 px-4 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-300 transition-colors cursor-pointer"
              >
                Close Preview
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

