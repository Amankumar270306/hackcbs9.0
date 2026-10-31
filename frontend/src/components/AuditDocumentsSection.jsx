import React, { useState, useEffect, useRef } from 'react';
import { 
  UploadCloud, 
  FileText, 
  Trash2, 
  RefreshCw, 
  Eye, 
  Download, 
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  Search, 
  Layers, 
  ChevronRight,
  Loader2,
  FileCheck2,
  Info
} from 'lucide-react';
import { documentApi } from '../api/client';
import { useAuth } from '../context/AuthContext';
import DocumentPreviewModal from './DocumentPreviewModal';

const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB

export default function AuditDocumentsSection({ audit, onDocumentCountChange }) {
  const { activeOrg } = useAuth();
  const orgId = activeOrg?.organization_id || activeOrg?.id;
  const auditId = audit?.rawId || (audit?.id && !audit.id.startsWith('AUD-') ? audit.id : audit?.rawId);

  const fileInputRef = useRef(null);

  const [documents, setDocuments] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [totalSize, setTotalSize] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  
  // Upload states
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const [uploadSuccess, setUploadSuccess] = useState(null);

  // Selected document for modal preview
  const [previewDoc, setPreviewDoc] = useState(null);

  // Deletion confirmation state
  const [deletingId, setDeletingId] = useState(null);

  const fetchDocuments = (silent = false) => {
    if (!orgId || !auditId) return;
    if (!silent) setLoading(true);

    documentApi.list(orgId, auditId, {
      search: search.trim() || undefined,
      status: statusFilter !== 'All' ? statusFilter : undefined,
    })
      .then((res) => {
        setDocuments(res.items || []);
        setTotalCount(res.total || 0);
        setTotalSize(res.total_file_size_bytes || 0);
        onDocumentCountChange?.(res.total || 0);
      })
      .catch((err) => {
        console.warn('Failed to load documents:', err);
      })
      .finally(() => {
        if (!silent) setLoading(false);
      });
  };

  useEffect(() => {
    fetchDocuments();
  }, [orgId, auditId, search, statusFilter]);

  // Auto-refresh poll every 4 seconds if any document is processing or queued
  useEffect(() => {
    const hasPending = documents.some((d) => d.status === 'processing' || d.status === 'queued' || d.status === 'uploaded');
    if (!hasPending) return;

    const timer = setInterval(() => {
      fetchDocuments(true);
    }, 4000);

    return () => clearInterval(timer);
  }, [documents, orgId, auditId]);

  const handleFileValidation = (file) => {
    if (!file) return false;
    const lower = file.name.toLowerCase();
    const isPdf = lower.endsWith('.pdf');
    const isDocx = lower.endsWith('.docx');

    if (!isPdf && !isDocx) {
      setUploadError('Invalid file type. Only PDF (.pdf) and Word (.docx) files are supported.');
      return false;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError(`File is too large (${(file.size / (1024 * 1024)).toFixed(1)} MB). Maximum allowed size is 25 MB.`);
      return false;
    }

    return true;
  };

  const uploadFile = async (file) => {
    if (!handleFileValidation(file)) return;

    if (!orgId || !auditId) {
      setUploadError('Audit ID could not be resolved. Please close and re-open the audit.');
      return;
    }

    setUploading(true);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const res = await documentApi.upload(orgId, auditId, file);
      setUploadSuccess(`"${file.name}" uploaded successfully. Extraction and chunking initiated.`);
      fetchDocuments(true);
      setTimeout(() => setUploadSuccess(null), 5000);
    } catch (err) {
      const msg = typeof err === 'string' ? err : (err.message || 'Document upload failed');
      setUploadError(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      uploadFile(e.dataTransfer.files[0]);
    }
  };

  const handleRetry = async (docId, e) => {
    e.stopPropagation();
    try {
      await documentApi.retry(orgId, auditId, docId);
      fetchDocuments(true);
    } catch (err) {
      const msg = typeof err === 'string' ? err : (err.message || 'Failed to retry processing');
      setUploadError(msg);
    }
  };

  const handleDelete = async (docId, docName, e) => {
    e.stopPropagation();
    if (!window.confirm(`Are you sure you want to delete "${docName}"? This will remove its chunks and evidence associations.`)) {
      return;
    }

    try {
      setDeletingId(docId);
      await documentApi.delete(orgId, auditId, docId);
      fetchDocuments(true);
    } catch (err) {
      const msg = typeof err === 'string' ? err : (err.message || 'Failed to delete document');
      setUploadError(msg);
    } finally {
      setDeletingId(null);
    }
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'completed':
        return (
          <span className="inline-flex items-center space-x-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-200">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
            <span>Completed</span>
          </span>
        );
      case 'processing':
        return (
          <span className="inline-flex items-center space-x-1 rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700 border border-blue-200">
            <Loader2 className="h-3 w-3 animate-spin text-blue-600" />
            <span>Processing</span>
          </span>
        );
      case 'queued':
      case 'uploaded':
        return (
          <span className="inline-flex items-center space-x-1 rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-700 border border-amber-200">
            <Clock className="h-3 w-3 text-amber-500" />
            <span>Queued</span>
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center space-x-1 rounded-full bg-rose-50 px-2.5 py-0.5 text-[11px] font-semibold text-rose-700 border border-rose-200">
            <AlertCircle className="h-3 w-3 text-rose-500" />
            <span>Failed</span>
          </span>
        );
      default:
        return (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-600">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="space-y-5">
      {/* Overview Stats Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 rounded-xl border border-slate-200 bg-slate-50/70 p-3.5">
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Target Audit</div>
          <div className="mt-1 font-bold text-slate-800 text-xs truncate">{audit?.targetName || audit?.name}</div>
        </div>
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Total Documents</div>
          <div className="mt-1 font-bold text-slate-800 text-xs flex items-center space-x-1.5">
            <span>{totalCount} files</span>
            <span className="text-slate-400">•</span>
            <span className="text-slate-500 font-normal">{formatBytes(totalSize)}</span>
          </div>
        </div>
        <div>
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Pipeline Status</div>
          <div className="mt-1 font-semibold text-emerald-600 flex items-center space-x-1.5 text-xs">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <span>Deterministic chunking ready</span>
          </div>
        </div>
      </div>

      {/* Drag & Drop Upload Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center p-6 border-2 border-dashed rounded-2xl cursor-pointer transition-all ${
          isDragging
            ? 'border-blue-500 bg-blue-50/50 scale-[1.005]'
            : 'border-slate-300 hover:border-blue-400 bg-slate-50/30 hover:bg-slate-50/80'
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="hidden"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              uploadFile(e.target.files[0]);
            }
          }}
        />

        {uploading ? (
          <div className="flex flex-col items-center space-y-2 py-2">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
            <p className="font-bold text-slate-800 text-xs">Uploading &amp; validating file...</p>
            <p className="text-[11px] text-slate-400">Computing SHA-256 and validating magic bytes</p>
          </div>
        ) : (
          <div className="flex flex-col items-center space-y-2 text-center">
            <div className="rounded-full bg-blue-100 p-2.5 text-blue-600">
              <UploadCloud className="h-6 w-6" />
            </div>
            <div>
              <p className="font-bold text-slate-800 text-xs">
                Drag &amp; drop policy or compliance document here, or <span className="text-blue-600 underline">browse</span>
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Supported formats: <strong className="text-slate-600">PDF (.pdf)</strong> and <strong className="text-slate-600">Word (.docx)</strong> • Max size: 25 MB
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Feedback Alerts */}
      {uploadError && (
        <div className="flex items-center space-x-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 animate-in fade-in">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span className="flex-1">{typeof uploadError === 'string' ? uploadError : (uploadError?.message || JSON.stringify(uploadError))}</span>
          <button onClick={() => setUploadError(null)} className="text-rose-500 hover:text-rose-700 font-bold ml-2">×</button>
        </div>
      )}

      {uploadSuccess && (
        <div className="flex items-center space-x-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-700 animate-in fade-in">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          <span className="flex-1">{uploadSuccess}</span>
          <button onClick={() => setUploadSuccess(null)} className="text-emerald-500 hover:text-emerald-700 font-bold ml-2">×</button>
        </div>
      )}

      {/* Search & Filter Header */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-2">
        <div className="relative w-full sm:w-64">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents..."
            className="w-full rounded-lg border border-slate-200 bg-white pl-8 pr-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:outline-hidden"
          />
        </div>

        <div className="flex items-center space-x-2 w-full sm:w-auto justify-end">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-700 focus:border-blue-500 focus:outline-hidden"
          >
            <option value="All">All Statuses</option>
            <option value="completed">Completed</option>
            <option value="processing">Processing</option>
            <option value="queued">Queued</option>
            <option value="failed">Failed</option>
          </select>

          <button
            onClick={() => fetchDocuments()}
            title="Refresh document status"
            className="flex items-center space-x-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50 cursor-pointer"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin text-blue-600' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Document List Table */}
      <div className="rounded-xl border border-slate-200 overflow-hidden bg-white shadow-2xs">
        {loading && documents.length === 0 ? (
          <div className="flex items-center justify-center py-12 text-slate-400 space-x-2">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            <span className="text-xs">Loading audit documents...</span>
          </div>
        ) : documents.length === 0 ? (
          <div className="py-12 px-4 text-center">
            <FileText className="h-8 w-8 mx-auto text-slate-300 mb-2" />
            <p className="font-bold text-slate-700 text-xs">No documents uploaded yet</p>
            <p className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto">
              Upload compliance documents (SOC 2 reports, PCI-DSS specs, architecture diagrams) to start automated evidence extraction.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70 text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  <th className="py-3 px-4">Document</th>
                  <th className="py-3 px-3">Size</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Pages &amp; Chunks</th>
                  <th className="py-3 px-3">Uploaded</th>
                  <th className="py-3 pr-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => (
                  <tr
                    key={doc.id}
                    onClick={() => setPreviewDoc(doc)}
                    className="hover:bg-blue-50/40 transition-colors cursor-pointer group"
                  >
                    {/* Filename & Type */}
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2.5">
                        <span className={`px-1.5 py-0.5 rounded font-mono font-bold text-[9px] uppercase ${
                          doc.file_extension === 'pdf' ? 'bg-rose-100 text-rose-700' : 'bg-blue-100 text-blue-700'
                        }`}>
                          {doc.file_extension || 'FILE'}
                        </span>
                        <div>
                          <span className="font-semibold text-slate-900 group-hover:text-blue-600 transition-colors block truncate max-w-xs sm:max-w-sm">
                            {doc.original_filename || doc.file_name}
                          </span>
                          <span className="font-mono text-[9px] text-slate-400">
                            {doc.file_hash_sha256?.substring(0, 16)}...
                          </span>
                        </div>
                      </div>
                    </td>

                    {/* Size */}
                    <td className="py-3 px-3 text-slate-600 font-mono text-[11px]">
                      {formatBytes(doc.file_size_bytes)}
                    </td>

                    {/* Status */}
                    <td className="py-3 px-3">
                      {getStatusBadge(doc.status)}
                    </td>

                    {/* Pages & Chunks */}
                    <td className="py-3 px-3 text-slate-600">
                      <div className="flex items-center space-x-2 text-[11px]">
                        <span>{doc.page_count ? `${doc.page_count}p` : 'DOCX'}</span>
                        <span className="text-slate-300">•</span>
                        <span className="font-semibold text-blue-600">{doc.chunk_count} chunks</span>
                      </div>
                    </td>

                    {/* Date */}
                    <td className="py-3 px-3 text-slate-500 text-[11px]">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </td>

                    {/* Actions */}
                    <td className="py-3 pr-4 text-right">
                      <div className="flex items-center justify-end space-x-1" onClick={(e) => e.stopPropagation()}>
                        {/* Preview */}
                        <button
                          onClick={() => setPreviewDoc(doc)}
                          title="Inspect Chunks & Text"
                          className="p-1 rounded text-slate-400 hover:text-blue-600 hover:bg-slate-100 cursor-pointer"
                        >
                          <Eye className="h-4 w-4" />
                        </button>

                        {/* Download */}
                        <button
                          onClick={() => documentApi.download(orgId, auditId, doc.id, doc.original_filename)}
                          title="Download original file"
                          className="p-1 rounded text-slate-400 hover:text-slate-700 hover:bg-slate-100 cursor-pointer"
                        >
                          <Download className="h-4 w-4" />
                        </button>

                        {/* Retry if failed */}
                        {doc.status === 'failed' && (
                          <button
                            onClick={(e) => handleRetry(doc.id, e)}
                            title="Retry Processing"
                            className="p-1 rounded text-amber-500 hover:text-amber-700 hover:bg-amber-50 cursor-pointer"
                          >
                            <RefreshCw className="h-4 w-4" />
                          </button>
                        )}

                        {/* Delete */}
                        <button
                          disabled={deletingId === doc.id}
                          onClick={(e) => handleDelete(doc.id, doc.original_filename, e)}
                          title="Delete Document"
                          className="p-1 rounded text-slate-400 hover:text-rose-600 hover:bg-rose-50 cursor-pointer disabled:opacity-40"
                        >
                          {deletingId === doc.id ? (
                            <Loader2 className="h-4 w-4 animate-spin text-rose-500" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
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

      {/* Document Preview & Chunks Inspector Modal */}
      {previewDoc && (
        <DocumentPreviewModal
          document={previewDoc}
          auditId={auditId}
          onClose={() => setPreviewDoc(null)}
        />
      )}
    </div>
  );
}

