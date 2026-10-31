import React, { useState, useEffect } from 'react';
import { 
  X, 
  FileText, 
  FileCode, 
  Layers, 
  Copy, 
  Check, 
  Download, 
  AlertCircle, 
  Clock, 
  Hash, 
  BookOpen,
  ChevronLeft,
  ChevronRight,
  Loader2
} from 'lucide-react';
import { documentApi } from '../api/client';
import { useAuth } from '../context/AuthContext';

export default function DocumentPreviewModal({ document, auditId, onClose }) {
  const { activeOrg } = useAuth();
  const [activeTab, setActiveTab] = useState('text'); // 'text' | 'chunks' | 'metadata'
  const [extractedText, setExtractedText] = useState('');
  const [chunks, setChunks] = useState([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [chunkPage, setChunkPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!document || !activeOrg?.organization_id || !auditId) return;

    setLoading(true);
    setError(null);

    // Fetch extracted text
    documentApi.getText(activeOrg.organization_id, auditId, document.id)
      .then((res) => {
        setExtractedText(res.extracted_text || 'No text extracted yet.');
      })
      .catch((err) => {
        console.warn('Could not fetch extracted text:', err);
        setError('Failed to load extracted text');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [document?.id, auditId, activeOrg?.organization_id]);

  useEffect(() => {
    if (activeTab !== 'chunks' || !document || !activeOrg?.organization_id || !auditId) return;

    setLoading(true);
    documentApi.getChunks(activeOrg.organization_id, auditId, document.id, {
      page: chunkPage,
      size: 10,
    })
      .then((res) => {
        setChunks(res.items || []);
        setTotalChunks(res.total || 0);
      })
      .catch((err) => {
        console.warn('Could not fetch chunks:', err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [activeTab, chunkPage, document?.id, auditId, activeOrg?.organization_id]);

  if (!document) return null;

  const handleCopyText = () => {
    if (!extractedText) return;
    navigator.clipboard.writeText(extractedText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    documentApi.download(activeOrg.organization_id, auditId, document.id, document.original_filename);
  };

  const formatBytes = (bytes) => {
    if (!bytes) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
      <div className="w-full max-w-4xl max-h-[92vh] flex flex-col rounded-2xl border border-slate-200 bg-white shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4 bg-slate-50/80 rounded-t-2xl">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-lg font-bold text-xs uppercase ${
              document.file_extension === 'pdf' ? 'bg-rose-100 text-rose-700' : 'bg-blue-100 text-blue-700'
            }`}>
              {document.file_extension || 'FILE'}
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900 truncate max-w-md">
                {document.original_filename || document.file_name}
              </h3>
              <p className="text-[11px] text-slate-500 flex items-center space-x-2 mt-0.5">
                <span>{formatBytes(document.file_size_bytes)}</span>
                <span>•</span>
                <span>{document.page_count ? `${document.page_count} pages` : 'Docx sections'}</span>
                <span>•</span>
                <span>{document.chunk_count} chunks</span>
                <span>•</span>
                <span className={`font-semibold capitalize ${
                  document.status === 'completed' ? 'text-emerald-600' :
                  document.status === 'failed' ? 'text-rose-600' : 'text-amber-600'
                }`}>
                  {document.status}
                </span>
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={handleDownload}
              title="Download original file"
              className="inline-flex items-center space-x-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <Download className="h-3.5 w-3.5 text-slate-500" />
              <span>Download</span>
            </button>
            <button
              onClick={onClose}
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors cursor-pointer"
            >
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-200 px-6 bg-white gap-6 text-xs font-semibold">
          <button
            onClick={() => setActiveTab('text')}
            className={`py-3 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeTab === 'text'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <FileText className="h-4 w-4" />
            <span>Extracted Text</span>
            {document.extracted_text_length > 0 && (
              <span className="bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded text-[10px]">
                {document.extracted_text_length} chars
              </span>
            )}
          </button>

          <button
            onClick={() => setActiveTab('chunks')}
            className={`py-3 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeTab === 'chunks'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <Layers className="h-4 w-4" />
            <span>Deterministic Chunks & Traceability</span>
            <span className="bg-blue-50 text-blue-600 px-1.5 py-0.2 rounded text-[10px] font-bold">
              {document.chunk_count}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('metadata')}
            className={`py-3 flex items-center space-x-2 border-b-2 cursor-pointer transition-colors ${
              activeTab === 'metadata'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-800'
            }`}
          >
            <BookOpen className="h-4 w-4" />
            <span>Document Metadata</span>
          </button>
        </div>

        {/* Tab Body */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-50/40 text-xs">
          {loading && (
            <div className="flex items-center justify-center py-12 text-slate-400 space-x-2">
              <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
              <span>Loading document data...</span>
            </div>
          )}

          {error && !loading && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-700 flex items-center space-x-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* TAB 1: Extracted Text */}
          {activeTab === 'text' && !loading && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                  Full Document Text Stream
                </span>
                <button
                  onClick={handleCopyText}
                  className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 cursor-pointer font-medium text-[11px]"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                  <span>{copied ? 'Copied' : 'Copy Text'}</span>
                </button>
              </div>

              {document.status === 'failed' && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-rose-800">
                  <div className="font-bold flex items-center space-x-1.5">
                    <AlertCircle className="h-4 w-4 text-rose-600" />
                    <span>Extraction Error</span>
                  </div>
                  <p className="mt-1 text-[11px]">{document.processing_error}</p>
                </div>
              )}

              <div className="rounded-xl border border-slate-200 bg-white p-4 font-mono text-[11px] text-slate-800 leading-relaxed whitespace-pre-wrap max-h-[55vh] overflow-y-auto selection:bg-blue-100">
                {extractedText}
              </div>
            </div>
          )}

          {/* TAB 2: Chunks & Traceability */}
          {activeTab === 'chunks' && !loading && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-600">
                <span>
                  Showing {chunks.length} of {totalChunks} chunks (Target: 800-1,200 tokens, 100-150 overlap)
                </span>
                <div className="flex items-center space-x-1">
                  <button
                    disabled={chunkPage === 1}
                    onClick={() => setChunkPage((p) => Math.max(1, p - 1))}
                    className="p-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
                  >
                    <ChevronLeft className="h-4 w-4" />
                  </button>
                  <span className="px-2 font-bold text-slate-700">Page {chunkPage}</span>
                  <button
                    disabled={chunks.length < 10}
                    onClick={() => setChunkPage((p) => p + 1)}
                    className="p-1 rounded border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
                  >
                    <ChevronRight className="h-4 w-4" />
                  </button>
                </div>
              </div>

              {chunks.length === 0 ? (
                <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-400">
                  <Layers className="h-8 w-8 mx-auto text-slate-300 mb-2" />
                  <p className="font-semibold text-slate-600">No chunks generated</p>
                  <p className="text-[11px] mt-1">
                    {document.status === 'processing'
                      ? 'Document is currently being processed...'
                      : 'Trigger a retry to re-chunk this document.'}
                  </p>
                </div>
              ) : (
                <div className="space-y-3 max-h-[55vh] overflow-y-auto pr-1">
                  {chunks.map((chk) => (
                    <div
                      key={chk.id}
                      className="rounded-xl border border-slate-200 bg-white p-4 space-y-2 shadow-2xs hover:border-blue-300 transition-colors"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2">
                        <div className="flex items-center space-x-2">
                          <span className="font-mono font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded border border-blue-200 text-[10px]">
                            Chunk #{chk.chunk_index}
                          </span>
                          {chk.section_title && (
                            <span className="font-semibold text-slate-800 text-[11px]">
                              {chk.section_title}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center space-x-2 text-[10px] text-slate-500">
                          {chk.page_start !== null && chk.page_start !== undefined && (
                            <span className="bg-slate-100 px-1.5 py-0.5 rounded">
                              Page {chk.page_start}{chk.page_end && chk.page_end !== chk.page_start ? `-${chk.page_end}` : ''}
                            </span>
                          )}
                          <span className="bg-slate-100 px-1.5 py-0.5 rounded">
                            {chk.character_count} chars
                          </span>
                          <span className="bg-slate-100 px-1.5 py-0.5 rounded">
                            ~{chk.token_count || Math.round(chk.character_count / 4)} tokens
                          </span>
                          {chk.start_char_offset !== null && (
                            <span className="font-mono text-slate-400">
                              [{chk.start_char_offset}:{chk.end_char_offset}]
                            </span>
                          )}
                        </div>
                      </div>

                      <p className="text-[11px] text-slate-700 whitespace-pre-wrap leading-relaxed font-sans bg-slate-50/50 p-2.5 rounded-lg border border-slate-100">
                        {chk.content}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Metadata */}
          {activeTab === 'metadata' && (
            <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
              <h4 className="font-bold text-slate-900 border-b border-slate-100 pb-2">
                Document Technical Parameters
              </h4>
              <div className="grid grid-cols-2 gap-4 text-xs">
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Document ID</span>
                  <span className="font-mono text-slate-800 break-all">{document.id}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Audit ID</span>
                  <span className="font-mono text-slate-800 break-all">{document.audit_id}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">SHA-256 Hash</span>
                  <span className="font-mono text-slate-800 text-[11px] break-all">{document.file_hash_sha256}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Storage Filename</span>
                  <span className="font-mono text-slate-800 break-all">{document.stored_filename}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">MIME Type</span>
                  <span className="text-slate-800">{document.mime_type}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">File Size</span>
                  <span className="text-slate-800">{formatBytes(document.file_size_bytes)}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Uploaded At</span>
                  <span className="text-slate-800">{new Date(document.created_at).toLocaleString()}</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px] uppercase font-bold">Processed At</span>
                  <span className="text-slate-800">
                    {document.processed_at ? new Date(document.processed_at).toLocaleString() : 'Pending'}
                  </span>
                </div>
              </div>

              {document.metadata && Object.keys(document.metadata).length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-100">
                  <span className="text-slate-400 block text-[10px] uppercase font-bold mb-1.5">
                    Extracted Document Attributes
                  </span>
                  <pre className="p-3 bg-slate-50 rounded-lg text-[11px] font-mono text-slate-800 overflow-x-auto">
                    {JSON.stringify(document.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between border-t border-slate-200 px-6 py-3 bg-slate-50/80 rounded-b-2xl">
          <div className="text-[11px] text-slate-400 font-mono">
            Deterministic extraction engine • Compliance Sentinel
          </div>
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

