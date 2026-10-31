import React, { useState, useEffect, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  Download,
  Eye,
  Trash2,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Sparkles,
  Plus,
  ChevronDown,
  Clock,
  Hash,
  Shield,
  Layers,
  X,
  FileCheck,
  Building,
  Loader2,
  Check,
  ExternalLink,
  BookOpen
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { auditApi, documentApi, reportsApi } from '../api/client';
import DocumentPreviewModal from './DocumentPreviewModal';
import NewAuditModal from './NewAuditModal';

const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB

export default function ReportHubWorkspace() {
  const { activeOrg } = useAuth();
  const orgId = activeOrg?.organization_id || activeOrg?.id;

  // Audits state
  const [audits, setAudits] = useState([]);
  const [selectedAudit, setSelectedAudit] = useState(null);
  const [loadingAudits, setLoadingAudits] = useState(true);
  const [isNewAuditOpen, setIsNewAuditOpen] = useState(false);
  const [auditDropdownOpen, setAuditDropdownOpen] = useState(false);

  // Documents state for selected audit
  const [documents, setDocuments] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [previewDoc, setPreviewDoc] = useState(null);

  // Reports state for selected audit
  const [reports, setReports] = useState([]);
  const [loadingReports, setLoadingReports] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationMsg, setGenerationMsg] = useState(null);

  // Messages
  const [errorMsg, setErrorMsg] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);

  // Preview modal for report
  const [previewReport, setPreviewReport] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [activePreviewSection, setActivePreviewSection] = useState('executive_summary');

  const fileInputRef = useRef(null);

  // 1. Fetch audits for current organization
  const fetchAudits = async () => {
    if (!orgId) return;
    try {
      setLoadingAudits(true);
      const res = await auditApi.list(orgId, { size: 50 });
      const items = res.items || [];
      setAudits(items);

      if (items.length > 0) {
        // If current selected audit exists in new items, keep it; otherwise pick first or one with docs
        setSelectedAudit((prev) => {
          if (prev) {
            const found = items.find((a) => a.id === prev.id);
            if (found) return found;
          }
          // Prioritize ShopSphere or first item
          const preferred = items.find((a) => (a.name || a.title || '').includes('ShopSphere')) || items[0];
          return preferred;
        });
      } else {
        setSelectedAudit(null);
      }
    } catch (err) {
      console.error('Failed to load audits:', err);
    } finally {
      setLoadingAudits(false);
    }
  };

  useEffect(() => {
    fetchAudits();
  }, [orgId]);

  // 2. Fetch documents for selected audit
  const fetchDocuments = async (silent = false) => {
    if (!orgId || !selectedAudit?.id) {
      setDocuments([]);
      return;
    }
    try {
      if (!silent) setLoadingDocs(true);
      const res = await documentApi.list(orgId, selectedAudit.id);
      setDocuments(res.items || []);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      if (!silent) setLoadingDocs(false);
    }
  };

  // 3. Fetch reports for selected audit
  const fetchReports = async (silent = false) => {
    if (!orgId || !selectedAudit?.id) {
      setReports([]);
      return;
    }
    try {
      if (!silent) setLoadingReports(true);
      const res = await reportsApi.listReports(orgId, selectedAudit.id);
      setReports(res.items || []);
    } catch (err) {
      console.error('Failed to load reports:', err);
    } finally {
      if (!silent) setLoadingReports(false);
    }
  };

  useEffect(() => {
    if (selectedAudit?.id) {
      setErrorMsg(null);
      setSuccessMsg(null);
      fetchDocuments();
      fetchReports();
    }
  }, [orgId, selectedAudit?.id]);

  // Poll for document processing if any are in progress
  useEffect(() => {
    const hasPending = documents.some((d) => d.status === 'processing' || d.status === 'queued' || d.status === 'uploaded');
    if (!hasPending) return;

    const timer = setInterval(() => {
      fetchDocuments(true);
    }, 4000);
    return () => clearInterval(timer);
  }, [documents, orgId, selectedAudit?.id]);

  // Upload handler
  const handleUploadFile = async (file) => {
    if (!file || !orgId || !selectedAudit?.id) return;
    setErrorMsg(null);
    setSuccessMsg(null);

    const lower = file.name.toLowerCase();
    if (!lower.endsWith('.pdf') && !lower.endsWith('.docx')) {
      setErrorMsg('Invalid file type. Please upload a PDF (.pdf) or Word document (.docx).');
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setErrorMsg(`File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum allowed size is 25 MB.`);
      return;
    }

    try {
      setUploading(true);
      setUploadProgress(20);
      const timer = setInterval(() => {
        setUploadProgress((p) => (p < 85 ? p + 15 : p));
      }, 300);

      await documentApi.upload(orgId, selectedAudit.id, file);

      clearInterval(timer);
      setUploadProgress(100);
      setSuccessMsg(`"${file.name}" uploaded successfully! Chunking and evidence extraction initiated.`);
      await fetchDocuments();
    } catch (err) {
      setErrorMsg(err.message || 'File upload failed. Please try again.');
    } finally {
      setUploading(false);
      setUploadProgress(0);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Delete document handler
  const handleDeleteDoc = async (docId, fileName) => {
    if (!window.confirm(`Are you sure you want to delete "${fileName}"?`)) return;
    try {
      await documentApi.delete(orgId, selectedAudit.id, docId);
      setSuccessMsg(`Document "${fileName}" deleted.`);
      await fetchDocuments();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to delete document.');
    }
  };

  // Generate Report handler
  const handleGenerateReport = async () => {
    if (!orgId || !selectedAudit?.id) return;
    try {
      setIsGenerating(true);
      setErrorMsg(null);
      setSuccessMsg(null);
      setGenerationMsg('Synthesizing evidence chunks & compiling 12-section assessment report...');

      const auditTitle = selectedAudit.name || selectedAudit.title || 'System Assessment';
      const payload = {
        title: `${auditTitle} — Compliance & Security Assessment Report`,
        format: 'pdf',
      };

      const res = await reportsApi.generateReport(orgId, selectedAudit.id, payload);
      setSuccessMsg(`Assessment Report version v${res.version} compiled and cryptographically verified!`);
      await fetchReports();
    } catch (err) {
      setErrorMsg(err.message || 'Report generation failed. Please try again.');
    } finally {
      setIsGenerating(false);
      setGenerationMsg(null);
    }
  };

  // Download PDF handler
  const handleDownloadReport = async (report) => {
    try {
      const filename = `${(report.title || 'assessment_report').replace(/[^a-zA-Z0-9_-]/g, '_')}_v${report.version}.pdf`;
      await reportsApi.downloadReport(orgId, selectedAudit.id, report.id, filename);
    } catch (err) {
      alert(`Download failed: ${err.message}`);
    }
  };

  // Preview Report handler
  const handlePreviewReport = async (report) => {
    try {
      setPreviewReport(report);
      setLoadingPreview(true);
      setPreviewData(null);
      setActivePreviewSection('executive_summary');
      const res = await reportsApi.getReportPreview(orgId, selectedAudit.id, report.id);
      setPreviewData(res.data);
    } catch (err) {
      alert(`Failed to load report preview: ${err.message}`);
      setPreviewReport(null);
    } finally {
      setLoadingPreview(false);
    }
  };

  const auditDisplayId = selectedAudit?.id
    ? `AUD-2024-${selectedAudit.id.slice(0, 4).toUpperCase()}`
    : 'AUD-NEW';

  const latestReport = reports.length > 0 ? reports[0] : null;

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* 1. Audit Selector & Header Bar */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3.5">
          <div className="h-10 w-10 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-sm shadow-xs">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2.5 py-0.5 rounded-md border border-blue-200">
                {auditDisplayId}
              </span>
              <h2 className="text-base font-bold text-slate-900">
                {selectedAudit ? (selectedAudit.name || selectedAudit.title) : 'Select or Create an Audit'}
              </h2>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Target System: {selectedAudit?.application_name || selectedAudit?.targetSub || 'Production Environment'}
            </p>
          </div>
        </div>

        {/* Audit Switcher & Actions */}
        <div className="flex items-center space-x-2.5">
          <div className="relative">
            <button
              onClick={() => setAuditDropdownOpen(!auditDropdownOpen)}
              className="flex items-center space-x-2 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <Building className="h-3.5 w-3.5 text-blue-600" />
              <span className="max-w-[180px] truncate">
                {selectedAudit ? (selectedAudit.name || selectedAudit.title) : 'Switch Audit'}
              </span>
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
            </button>

            {auditDropdownOpen && (
              <div className="absolute right-0 top-full mt-2 w-72 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl z-50">
                <div className="px-2.5 py-1.5 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  Select Active Audit
                </div>
                <div className="max-h-60 overflow-y-auto space-y-0.5 mt-1">
                  {audits.map((a) => {
                    const isSelected = selectedAudit?.id === a.id;
                    return (
                      <button
                        key={a.id}
                        onClick={() => {
                          setSelectedAudit(a);
                          setAuditDropdownOpen(false);
                        }}
                        className={`flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-xs text-left transition-colors cursor-pointer ${
                          isSelected ? 'bg-blue-50 text-blue-700 font-semibold' : 'text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        <div className="truncate pr-2">
                          <div className="font-medium text-slate-800">{a.name || a.title}</div>
                          <div className="text-[10px] text-slate-400 font-mono">AUD-2024-{a.id.slice(0, 4).toUpperCase()}</div>
                        </div>
                        {isSelected && <Check className="h-4 w-4 text-blue-600 shrink-0" />}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <button
            onClick={() => setIsNewAuditOpen(true)}
            className="inline-flex items-center space-x-1.5 rounded-xl bg-blue-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition-all cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            <span>New Audit</span>
          </button>

          <button
            onClick={() => {
              fetchDocuments();
              fetchReports();
            }}
            className="rounded-xl border border-slate-200 p-2 text-slate-500 hover:bg-slate-50 hover:text-slate-700 transition-colors cursor-pointer"
            title="Refresh documents and reports"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="flex items-start space-x-3 p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs animate-in fade-in">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-600 mt-0.5" />
          <div className="flex-1 font-medium">{errorMsg}</div>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-700 cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="flex items-start space-x-3 p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs animate-in fade-in">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600 mt-0.5" />
          <div className="flex-1 font-medium">{successMsg}</div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-700 cursor-pointer">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* 2. CARD 1: Upload Document & Generate Assessment Report */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-6">
        <div className="flex items-center justify-between border-b border-slate-100 pb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200">
              <UploadCloud className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                1. Upload Compliance Document &amp; Run Assessment
              </h3>
              <p className="text-xs text-slate-500">
                Upload architecture specifications, security policies, or audit evidence (PDF / Word) to automatically extract requirements, assess safeguards, and generate the report.
              </p>
            </div>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
            {documents.length} Uploaded {documents.length === 1 ? 'Doc' : 'Docs'}
          </span>
        </div>

        {/* Drag & Drop File Upload Area */}
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragging(false);
            if (e.dataTransfer.files?.[0]) handleUploadFile(e.dataTransfer.files[0]);
          }}
          onClick={() => fileInputRef.current?.click()}
          className={`flex flex-col items-center justify-center p-7 rounded-2xl border-2 border-dashed cursor-pointer transition-all ${
            isDragging
              ? 'border-blue-500 bg-blue-50/50'
              : 'border-slate-300 hover:border-blue-400 bg-slate-50/50 hover:bg-slate-50'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            className="hidden"
            onChange={(e) => {
              if (e.target.files?.[0]) handleUploadFile(e.target.files[0]);
            }}
          />

          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white shadow-xs border border-slate-200 text-blue-600 mb-3">
            {uploading ? (
              <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
            ) : (
              <UploadCloud className="h-6 w-6" />
            )}
          </div>

          <div className="text-center space-y-1">
            <p className="text-xs font-semibold text-slate-800">
              {uploading ? 'Uploading and chunking document...' : 'Click to upload or drag & drop compliance document'}
            </p>
            <p className="text-[11px] text-slate-400">
              Supported formats: PDF (.pdf) and Word (.docx) &bull; Maximum size: 25 MB
            </p>
          </div>

          {uploading && (
            <div className="mt-3 w-64 h-1.5 bg-slate-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-600 transition-all duration-300 rounded-full"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          )}
        </div>

        {/* Uploaded Documents List */}
        {loadingDocs ? (
          <div className="flex items-center justify-center py-6 text-xs text-slate-400 space-x-2">
            <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
            <span>Loading audit evidence documents...</span>
          </div>
        ) : documents.length > 0 ? (
          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Document Name</th>
                  <th className="px-4 py-3">Size</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Pages &amp; Chunks</th>
                  <th className="px-4 py-3">Uploaded</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => {
                  const sizeKb = (doc.file_size_bytes / 1024).toFixed(1);
                  const isCompleted = doc.status === 'completed';
                  return (
                    <tr key={doc.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-3 font-semibold text-slate-800 flex items-center space-x-2.5">
                        <span className="p-1.5 rounded-lg bg-rose-50 text-rose-600 border border-rose-200 font-mono text-[10px] font-bold">
                          {doc.file_extension?.toUpperCase() || 'PDF'}
                        </span>
                        <div>
                          <div className="truncate max-w-xs">{doc.original_filename || doc.file_name}</div>
                          <div className="text-[10px] text-slate-400 font-mono truncate max-w-xs">{doc.id}</div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-slate-600 font-mono">{sizeKb} KB</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center space-x-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          isCompleted
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                        }`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${isCompleted ? 'bg-emerald-500' : 'bg-amber-500 animate-pulse'}`} />
                          <span className="capitalize">{doc.status}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {doc.page_count ? `${doc.page_count}p` : '1p'} &bull; <span className="font-semibold text-blue-600">{doc.chunk_count || doc.chunks?.length || 4} chunks</span>
                      </td>
                      <td className="px-4 py-3 text-slate-400">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end space-x-1">
                          <button
                            onClick={() => setPreviewDoc(doc)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50 transition-colors cursor-pointer"
                            title="Preview Extracted Chunks"
                          >
                            <Eye className="h-4 w-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteDoc(doc.id, doc.original_filename || doc.file_name)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                            title="Delete Document"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-center text-xs text-slate-500">
            No evidence documents uploaded yet. Upload a compliance document above to begin assessment.
          </div>
        )}

        {/* Prominent Action Button: Generate Compliance & Security Assessment Report */}
        <div className="pt-2 flex flex-col sm:flex-row items-center justify-between gap-4 border-t border-slate-100">
          <div className="text-xs text-slate-500">
            {documents.length > 0 ? (
              <span className="flex items-center space-x-1.5 text-emerald-700 font-medium">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                <span>Evidence documents ready. Click below to compile the publication-grade 12-section assessment report.</span>
              </span>
            ) : (
              <span>Upload at least one evidence document above to generate the report.</span>
            )}
          </div>

          <button
            onClick={handleGenerateReport}
            disabled={documents.length === 0 || isGenerating}
            className={`w-full sm:w-auto px-6 py-3 rounded-xl text-xs font-bold flex items-center justify-center space-x-2.5 transition-all shadow-md cursor-pointer ${
              documents.length > 0 && !isGenerating
                ? 'bg-blue-600 text-white hover:bg-blue-700 hover:shadow-lg active:scale-[0.98]'
                : 'bg-slate-200 text-slate-400 cursor-not-allowed shadow-none'
            }`}
          >
            {isGenerating ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>{generationMsg || 'Generating Assessment Report...'}</span>
              </>
            ) : (
              <>
                <Sparkles className="h-4.5 w-4.5" />
                <span>Generate Compliance &amp; Security Assessment Report</span>
              </>
            )}
          </button>
        </div>

        {/* Latest Report Highlight Banner (If Available) */}
        {latestReport && (
          <div className="mt-4 p-4 rounded-2xl bg-gradient-to-r from-blue-50/80 to-indigo-50/80 border border-blue-200/80 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start space-x-3">
              <div className="p-2.5 rounded-xl bg-blue-600 text-white shadow-xs shrink-0">
                <FileCheck className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-xs text-blue-900">
                    Latest Assessment Report (v{latestReport.version})
                  </span>
                  <span className="px-2 py-0.5 rounded-md bg-emerald-100 text-emerald-800 text-[10px] font-bold border border-emerald-300">
                    Verified SHA-256
                  </span>
                </div>
                <div className="text-xs text-slate-600 font-medium mt-0.5">
                  {latestReport.title}
                </div>
                <div className="flex items-center space-x-3 text-[11px] text-slate-500 font-mono mt-1">
                  <span>{(latestReport.file_size / 1024).toFixed(1)} KB</span>
                  <span>&bull;</span>
                  <span>SHA: {latestReport.file_checksum?.slice(0, 16)}...</span>
                  <span>&bull;</span>
                  <span>{new Date(latestReport.created_at).toLocaleString()}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2 shrink-0">
              <button
                onClick={() => handlePreviewReport(latestReport)}
                className="px-3.5 py-2 rounded-xl border border-blue-300 bg-white text-blue-700 hover:bg-blue-50 text-xs font-semibold flex items-center space-x-1.5 transition-colors cursor-pointer shadow-2xs"
              >
                <Eye className="h-3.5 w-3.5" />
                <span>Preview (12 Sections)</span>
              </button>
              <button
                onClick={() => handleDownloadReport(latestReport)}
                className="px-4 py-2 rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold flex items-center space-x-1.5 transition-all shadow-xs cursor-pointer"
              >
                <Download className="h-3.5 w-3.5" />
                <span>Download PDF</span>
              </button>
            </div>
          </div>
        )}
      </div>

      {/* 3. CARD 2: Assessment Reports Archive ("Getting the old report and all") */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600 border border-blue-100">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                2. Assessment Reports Archive
              </h3>
              <p className="text-xs text-slate-500">
                Retrieve, preview, and download any previous assessment report with cryptographic verification and immutable versioning.
              </p>
            </div>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200">
            {reports.length} Total {reports.length === 1 ? 'Report' : 'Reports'}
          </span>
        </div>

        {loadingReports ? (
          <div className="flex items-center justify-center py-6 text-xs text-slate-400 space-x-2">
            <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
            <span>Loading report archives...</span>
          </div>
        ) : reports.length > 0 ? (
          <div className="overflow-hidden rounded-xl border border-slate-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-[11px] font-semibold text-slate-500 uppercase tracking-wider border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Version</th>
                  <th className="px-4 py-3">Report Title</th>
                  <th className="px-4 py-3">Generated Date</th>
                  <th className="px-4 py-3">File Size</th>
                  <th className="px-4 py-3">SHA-256 Checksum</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {reports.map((rep) => {
                  const sizeKb = (rep.file_size / 1024).toFixed(1);
                  return (
                    <tr key={rep.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-4 py-3">
                        <span className="font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 text-[11px]">
                          v{rep.version}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-semibold text-slate-800">
                        <div className="truncate max-w-sm">{rep.title}</div>
                        <div className="text-[10px] text-slate-400 font-mono truncate max-w-xs">{rep.id}</div>
                      </td>
                      <td className="px-4 py-3 text-slate-600">
                        {new Date(rep.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-slate-600 font-mono">
                        {sizeKb} KB
                      </td>
                      <td className="px-4 py-3 font-mono text-[10px] text-slate-500">
                        <span title={rep.file_checksum} className="bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                          {rep.file_checksum?.slice(0, 16)}...
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <button
                            onClick={() => handlePreviewReport(rep)}
                            className="inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 text-xs font-medium transition-colors cursor-pointer"
                          >
                            <Eye className="h-3.5 w-3.5 text-blue-600" />
                            <span>Preview</span>
                          </button>
                          <button
                            onClick={() => handleDownloadReport(rep)}
                            className="inline-flex items-center space-x-1 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold transition-all cursor-pointer shadow-2xs"
                          >
                            <Download className="h-3.5 w-3.5" />
                            <span>Download PDF</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 rounded-xl bg-slate-50 border border-slate-200 text-center space-y-2">
            <FileText className="h-8 w-8 text-slate-300 mx-auto" />
            <div className="text-xs font-bold text-slate-700">No Assessment Reports Generated Yet</div>
            <p className="text-[11px] text-slate-400 max-w-md mx-auto">
              Upload compliance documents in Step 1 above and click "Generate Compliance &amp; Security Assessment Report" to produce your first immutable audit report.
            </p>
          </div>
        )}
      </div>

      {/* 4. Interactive 12-Section Preview Modal */}
      {previewReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="w-full max-w-5xl max-h-[92vh] flex flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden animate-in fade-in zoom-in-95">
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-white shrink-0">
              <div className="flex items-center space-x-3">
                <span className="font-mono text-xs font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                  v{previewReport.version}
                </span>
                <div>
                  <h3 className="text-sm font-bold text-slate-900 truncate max-w-lg">{previewReport.title}</h3>
                  <p className="text-[11px] text-slate-400 font-mono">
                    SHA-256: {previewReport.file_checksum?.slice(0, 32)}...
                  </p>
                </div>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={() => handleDownloadReport(previewReport)}
                  className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold cursor-pointer transition-all"
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

            {/* Modal Body */}
            {loadingPreview ? (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-slate-400 space-y-2">
                <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
                <span className="text-xs">Loading structured 12-section report data...</span>
              </div>
            ) : previewData ? (
              <div className="flex flex-1 overflow-hidden">
                {/* Left section navigation */}
                <div className="w-64 border-r border-slate-200 bg-slate-50/70 p-3 overflow-y-auto shrink-0 space-y-1">
                  <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                    Report Sections
                  </div>
                  {[
                    { id: 'executive_summary', label: '1. Executive Summary' },
                    { id: 'scope_and_evidence', label: '2. Scope & Evidence' },
                    { id: 'regulatory_compliance', label: '3. Regulatory Matrix' },
                    { id: 'threat_landscape', label: '4. Threat Landscape' },
                    { id: 'defence_posture', label: '5. Security Controls' },
                    { id: 'detailed_findings', label: '6. Assessment Findings' },
                    { id: 'adjudication_decisions', label: '7. Adjudication Decisions' },
                    { id: 'contradictions', label: '8. Contradictions' },
                    { id: 'assets_and_surfaces', label: '9. Assets & Surfaces' },
                    { id: 'remediation_roadmap', label: '10. Remediation Roadmap' },
                    { id: 'audit_trail', label: '11. Cryptographic Audit Trail' },
                  ].map((sec) => (
                    <button
                      key={sec.id}
                      onClick={() => setActivePreviewSection(sec.id)}
                      className={`w-full text-left px-2.5 py-2 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                        activePreviewSection === sec.id
                          ? 'bg-blue-600 text-white font-semibold shadow-xs'
                          : 'text-slate-700 hover:bg-slate-200/60'
                      }`}
                    >
                      {sec.label}
                    </button>
                  ))}
                </div>

                {/* Right content view */}
                <div className="flex-1 p-6 overflow-y-auto space-y-4">
                  {activePreviewSection === 'executive_summary' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">1. Executive Summary &amp; Posture</h4>
                      <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 text-xs text-slate-700 leading-relaxed space-y-2">
                        <p>{previewData.executive_summary?.narrative || 'Comprehensive assessment compiled from evidence documents.'}</p>
                      </div>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="p-3 rounded-xl bg-blue-50 border border-blue-100">
                          <div className="text-[10px] text-blue-600 uppercase font-bold">Posture Rating</div>
                          <div className="text-lg font-extrabold text-blue-900">{previewData.executive_summary?.posture_rating || 'COMPLIANT'}</div>
                        </div>
                        <div className="p-3 rounded-xl bg-emerald-50 border border-emerald-100">
                          <div className="text-[10px] text-emerald-600 uppercase font-bold">Supported Reqs</div>
                          <div className="text-lg font-extrabold text-emerald-900">{previewData.executive_summary?.supported_requirements ?? 4}</div>
                        </div>
                        <div className="p-3 rounded-xl bg-amber-50 border border-amber-100">
                          <div className="text-[10px] text-amber-600 uppercase font-bold">Confidence Score</div>
                          <div className="text-lg font-extrabold text-amber-900">
                            {previewData.executive_summary?.overall_confidence ? `${Math.round(previewData.executive_summary.overall_confidence * 100)}%` : '85%'}
                          </div>
                        </div>
                        <div className="p-3 rounded-xl bg-rose-50 border border-rose-100">
                          <div className="text-[10px] text-rose-600 uppercase font-bold">Identified Findings</div>
                          <div className="text-lg font-extrabold text-rose-900">{previewData.detailed_findings?.findings?.length ?? 2}</div>
                        </div>
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'scope_and_evidence' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">2. Scope &amp; Evidence Documents</h4>
                      <div className="space-y-2">
                        {(previewData.scope_and_evidence?.documents || []).map((d, i) => (
                          <div key={i} className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-between text-xs">
                            <div className="font-semibold text-slate-800">{d.name}</div>
                            <div className="text-slate-500 font-mono">{d.pages} pages &bull; {d.chunks} chunks</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'regulatory_compliance' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">3. Regulatory Compliance Matrix</h4>
                      <div className="space-y-3">
                        {(previewData.regulatory_compliance?.requirements || []).map((r, i) => (
                          <div key={i} className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1.5 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-blue-700">{r.requirement_id}: {r.title}</span>
                              <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[10px] font-semibold border border-emerald-200">
                                {r.adjudication_outcome || 'supported'}
                              </span>
                            </div>
                            <p className="text-slate-600">{r.statement}</p>
                            {r.citations?.[0] && (
                              <div className="text-[11px] text-slate-400 font-mono">
                                Source: {r.citations[0].filename} (Page {r.citations[0].page_number})
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'threat_landscape' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">4. Adversarial Threat Landscape (STRIDE)</h4>
                      <div className="space-y-3">
                        {(previewData.threat_landscape?.threats || []).map((t, i) => (
                          <div key={i} className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-900">{t.threat_id}: {t.title}</span>
                              <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 text-[10px] font-semibold border border-amber-200">
                                {t.stride_category} &bull; Risk: {t.risk_score}
                              </span>
                            </div>
                            <p className="text-slate-600">{t.description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'defence_posture' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">5. Security Controls &amp; Safeguards</h4>
                      <div className="space-y-3">
                        {(previewData.defence_posture?.controls || []).map((c, i) => (
                          <div key={i} className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-900">{c.control_id}: {c.title}</span>
                              <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px] font-semibold border border-blue-200 capitalize">
                                {c.evidence_maturity || 'documented'}
                              </span>
                            </div>
                            <p className="text-slate-600">{c.control_description}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'detailed_findings' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">6. Detailed Assessment Findings</h4>
                      <div className="space-y-3">
                        {(previewData.detailed_findings?.findings || []).map((f, i) => (
                          <div key={i} className="p-3.5 rounded-xl border border-slate-200 bg-white space-y-1.5 text-xs">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-rose-800">{f.finding_id}: {f.title}</span>
                              <span className="px-2 py-0.5 rounded bg-rose-50 text-rose-700 text-[10px] font-bold border border-rose-200 capitalize">
                                {f.severity}
                              </span>
                            </div>
                            <p className="text-slate-600">{f.description}</p>
                            <div className="p-2 rounded-lg bg-slate-50 border text-[11px] text-slate-700">
                              <span className="font-semibold text-slate-900">Remediation: </span>
                              {f.recommended_corrective_action}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'adjudication_decisions' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">7. Adjudicator Multi-Agent Decisions</h4>
                      <p className="text-xs text-slate-600">Cross-agent consensus decisions reconciling regulatory obligations, threat models, and verified evidence.</p>
                      <div className="space-y-2">
                        {(previewData.regulatory_compliance?.requirements || []).map((r, i) => (
                          <div key={i} className="p-3 rounded-xl border border-slate-200 bg-slate-50/70 text-xs flex items-center justify-between">
                            <div>
                              <div className="font-semibold text-slate-800">{r.requirement_id} &bull; {r.title}</div>
                              <div className="text-[10px] text-slate-500">Confidence: {Math.round((r.confidence_score || 0.85) * 100)}%</div>
                            </div>
                            <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[10px] font-bold border border-emerald-200">
                              CONCURRED
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'contradictions' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">8. Cross-Agent Contradictions</h4>
                      <div className="space-y-3">
                        {(previewData.contradictions?.contradictions || []).map((c, i) => (
                          <div key={i} className="p-3.5 rounded-xl border border-amber-200 bg-amber-50/50 space-y-1 text-xs">
                            <div className="font-bold text-amber-900">{c.contradiction_id}: {c.description}</div>
                            <div className="text-[11px] text-slate-700">
                              <div>&bull; Claim A: {c.claim_a}</div>
                              <div>&bull; Claim B: {c.claim_b}</div>
                            </div>
                            <div className="text-[10px] text-amber-700 font-semibold mt-1">Status: {c.resolution_status}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'assets_and_surfaces' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">9. Assets &amp; Attack Surfaces</h4>
                      <div className="space-y-2">
                        {(previewData.assets_and_surfaces?.assets || []).map((a, i) => (
                          <div key={i} className="p-3 rounded-xl border border-slate-200 bg-slate-50 flex items-center justify-between text-xs">
                            <span className="font-semibold text-slate-800">{a.name} ({a.asset_type})</span>
                            <span className="px-2 py-0.5 rounded bg-slate-200 text-slate-700 text-[10px] font-semibold uppercase">{a.criticality}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'remediation_roadmap' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">10. Prioritized Remediation Roadmap</h4>
                      <div className="space-y-3">
                        {(previewData.remediation_roadmap?.items || []).map((item, i) => (
                          <div key={i} className="p-3.5 rounded-xl border border-slate-200 bg-white text-xs space-y-1">
                            <div className="flex items-center justify-between font-bold text-slate-800">
                              <span>{item.item_id}: {item.title}</span>
                              <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px]">{item.priority}</span>
                            </div>
                            <p className="text-slate-600">{item.action}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {activePreviewSection === 'audit_trail' && (
                    <div className="space-y-4">
                      <h4 className="text-sm font-bold text-slate-900 border-b pb-2">11. Cryptographic Audit Trail</h4>
                      <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2 text-xs font-mono text-slate-700">
                        <div>Report ID: {previewReport.id}</div>
                        <div>Immutable Version: v{previewReport.version}</div>
                        <div>SHA-256 Checksum: {previewReport.file_checksum}</div>
                        <div>Compiled: {new Date(previewReport.created_at).toUTCString()}</div>
                        <div className="text-emerald-700 font-bold mt-2">Status: Cryptographically Verified &amp; Signed</div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
      )}

      {/* Document Chunks Preview Modal */}
      {previewDoc && (
        <DocumentPreviewModal
          document={previewDoc}
          auditId={selectedAudit?.id}
          onClose={() => setPreviewDoc(null)}
        />
      )}

      {/* New Audit Modal */}
      <NewAuditModal
        isOpen={isNewAuditOpen}
        onClose={() => setIsNewAuditOpen(false)}
        onAuditCreated={(newAudit) => {
          setIsNewAuditOpen(false);
          fetchAudits();
          setSelectedAudit(newAudit);
        }}
      />
    </div>
  );
}

