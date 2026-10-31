import React, { useState, useEffect } from 'react';
import {
  BookOpen,
  Plus,
  FileText,
  Upload,
  Bot,
  Play,
  CheckCircle2,
  XCircle,
  Edit3,
  Clock,
  Search,
  Filter,
  AlertTriangle,
  ChevronRight,
  ExternalLink,
  ShieldCheck,
  RefreshCw,
} from 'lucide-react';
import { regulatoryApi } from '../api/client';
import { useAuth } from '../context/AuthContext';

const STANDARD_CATEGORIES = [
  'Identity and Access Management',
  'Data Protection & Encryption',
  'Network Security',
  'Incident Response & Management',
  'Vulnerability Management',
  'Logging & Auditing',
  'Third-Party & Vendor Risk',
  'Business Continuity & Disaster Recovery',
  'Physical & Environmental Security',
  'Human Resources & Personnel Security',
  'Compliance & Governance',
  'Cryptography & Key Management',
  'Secure Software Development Lifecycle',
  'Asset & Inventory Management',
  'Endpoint & Device Security',
  'Threat Intelligence & Monitoring',
  'Privacy & Consent Management',
  'Security Training & Awareness',
  'Configuration & Change Management',
  'Mobile & Remote Work Security',
  'Cloud & Virtualization Security',
  'Other',
];

export default function RegulatoryKnowledgeSection() {
  const { activeOrg } = useAuth();

  // State
  const [frameworks, setFrameworks] = useState([]);
  const [selectedFramework, setSelectedFramework] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [requirements, setRequirements] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExtracting, setIsExtracting] = useState(false);
  const [extractionJob, setExtractionJob] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Modals
  const [showNewFrameworkModal, setShowNewFrameworkModal] = useState(false);
  const [showUploadDocModal, setShowUploadDocModal] = useState(false);
  const [editReqModal, setEditReqModal] = useState(null);
  const [actionReasonModal, setActionReasonModal] = useState(null); // { type: 'reject' | 'revision', req: ... }
  const [historyModalReq, setHistoryModalReq] = useState(null);
  const [reqHistory, setReqHistory] = useState([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Forms
  const [fwForm, setFwForm] = useState({
    name: '',
    short_name: '',
    issuing_authority: '',
    jurisdiction: 'Global',
    framework_type: 'standard',
    version: '1.0',
    description: '',
  });

  const [docUploadForm, setDocUploadForm] = useState({
    file: null,
    title: '',
    document_number: '',
    version: '1.0',
  });

  // Load Frameworks
  const loadFrameworks = async () => {
    setIsLoading(true);
    try {
      const data = await regulatoryApi.listFrameworks();
      setFrameworks(data || []);
      if (data && data.length > 0 && !selectedFramework) {
        setSelectedFramework(data[0]);
      }
    } catch (err) {
      console.error('Failed to load frameworks', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadFrameworks();
  }, []);

  // Load Documents for selected Framework
  useEffect(() => {
    if (!selectedFramework) {
      setDocuments([]);
      setSelectedDoc(null);
      return;
    }
    const loadDocs = async () => {
      try {
        const docs = await regulatoryApi.listDocuments(selectedFramework.id);
        setDocuments(docs || []);
        if (docs && docs.length > 0) {
          setSelectedDoc(docs[0]);
        } else {
          setSelectedDoc(null);
        }
      } catch (err) {
        console.error('Failed to load regulatory documents', err);
      }
    };
    loadDocs();
  }, [selectedFramework]);

  // Load Requirements
  const loadRequirements = async () => {
    try {
      const params = {
        limit: 100,
      };
      if (selectedFramework) params.framework_id = selectedFramework.id;
      if (selectedDoc) params.document_id = selectedDoc.id;
      if (statusFilter !== 'all') params.review_status = statusFilter;
      if (categoryFilter !== 'all') params.category = categoryFilter;
      if (searchQuery) params.search = searchQuery;

      const res = await regulatoryApi.listRequirements(params);
      setRequirements(res?.items || []);
    } catch (err) {
      console.error('Failed to load requirements', err);
    }
  };

  useEffect(() => {
    loadRequirements();
  }, [selectedFramework, selectedDoc, statusFilter, categoryFilter, searchQuery]);

  // Handle Create Framework
  const handleCreateFramework = async (e) => {
    e.preventDefault();
    try {
      const newFw = await regulatoryApi.createFramework(fwForm);
      setShowNewFrameworkModal(false);
      setFwForm({
        name: '',
        short_name: '',
        issuing_authority: '',
        jurisdiction: 'Global',
        framework_type: 'standard',
        version: '1.0',
        description: '',
      });
      await loadFrameworks();
      setSelectedFramework(newFw);
    } catch (err) {
      alert(err.message || 'Failed to create framework');
    }
  };

  // Handle Upload Document
  const handleUploadDocument = async (e) => {
    e.preventDefault();
    if (!docUploadForm.file || !selectedFramework) return;
    try {
      const newDoc = await regulatoryApi.uploadDocument(selectedFramework.id, docUploadForm.file, {
        title: docUploadForm.title,
        document_number: docUploadForm.document_number,
        version: docUploadForm.version,
      });
      setShowUploadDocModal(false);
      setDocUploadForm({ file: null, title: '', document_number: '', version: '1.0' });
      const docs = await regulatoryApi.listDocuments(selectedFramework.id);
      setDocuments(docs || []);
      setSelectedDoc(newDoc);
    } catch (err) {
      alert(err.message || 'Failed to upload document');
    }
  };

  // Trigger Legal Analyst AI Extraction
  const handleTriggerExtraction = async () => {
    if (!selectedDoc) return;
    setIsExtracting(true);
    try {
      const job = await regulatoryApi.triggerExtraction(selectedDoc.id, true);
      setExtractionJob(job);
      await loadRequirements();
    } catch (err) {
      alert(err.message || 'Extraction failed');
    } finally {
      setIsExtracting(false);
    }
  };

  // Human Review Actions
  const handleApprove = async (reqId) => {
    try {
      await regulatoryApi.approveRequirement(reqId, 'Approved by compliance auditor.');
      await loadRequirements();
    } catch (err) {
      alert(err.message || 'Approval failed');
    }
  };

  const handleActionWithReason = async (e) => {
    e.preventDefault();
    const reason = e.target.reason.value;
    if (!reason) return;
    try {
      if (actionReasonModal.type === 'reject') {
        await regulatoryApi.rejectRequirement(actionReasonModal.req.id, reason);
      } else {
        await regulatoryApi.requestRevision(actionReasonModal.req.id, reason);
      }
      setActionReasonModal(null);
      await loadRequirements();
    } catch (err) {
      alert(err.message || 'Action failed');
    }
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      await regulatoryApi.editRequirement(editReqModal.id, {
        title: editReqModal.title,
        requirement_statement: editReqModal.requirement_statement,
        detailed_description: editReqModal.detailed_description,
        obligation_type: editReqModal.obligation_type,
        category: editReqModal.category,
        reason: editReqModal.reason || 'Manual revision of requirement metadata.',
      });
      setEditReqModal(null);
      await loadRequirements();
    } catch (err) {
      alert(err.message || 'Update failed');
    }
  };

  const handleOpenHistory = async (req) => {
    setHistoryModalReq(req);
    setIsLoadingHistory(true);
    try {
      const history = await regulatoryApi.getRequirementHistory(req.id);
      setReqHistory(history || []);
    } catch (err) {
      console.error(err);
      setReqHistory([]);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header Card */}
      <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-blue-50 border border-blue-200 flex items-center justify-center text-blue-600">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-900">Regulatory Knowledge Base</h2>
                <span className="text-[10px] font-bold bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full border border-blue-200">
                  Milestone 4
                </span>
                <span className="text-[10px] font-bold bg-emerald-100 text-emerald-700 px-2 py-0.5 rounded-full border border-emerald-200">
                  Legal Analyst Agent
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Authoritative compliance frameworks, standards, and Gemini-powered normative requirement extraction.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={() => setShowNewFrameworkModal(true)}
              className="flex items-center gap-1.5 bg-slate-900 hover:bg-slate-800 text-white px-3.5 py-2 rounded-xl text-xs font-semibold shadow-xs transition-colors cursor-pointer"
            >
              <Plus className="h-4 w-4" />
              <span>New Framework</span>
            </button>
          </div>
        </div>

        {/* Framework Selector Pills */}
        <div className="mt-6 flex items-center gap-2 overflow-x-auto pb-1">
          {frameworks.map((fw) => {
            const isSelected = selectedFramework?.id === fw.id;
            return (
              <button
                key={fw.id}
                onClick={() => setSelectedFramework(fw)}
                className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                  isSelected
                    ? 'bg-blue-600 text-white shadow-2xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-700'
                }`}
              >
                <span>{fw.short_name}</span>
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded ${
                    isSelected ? 'bg-blue-500/80 text-white' : 'bg-slate-200/80 text-slate-600'
                  }`}
                >
                  v{fw.version}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {selectedFramework && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Column 1: Framework Info & Source Documents */}
          <div className="space-y-6">
            {/* Framework Info Card */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Framework Profile</span>
                <span className="text-[10px] bg-slate-100 font-mono text-slate-600 px-2 py-0.5 rounded">
                  {selectedFramework.framework_type}
                </span>
              </div>
              <h3 className="text-sm font-bold text-slate-900">{selectedFramework.name}</h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                {selectedFramework.description || 'No description provided.'}
              </p>
              <div className="pt-2 border-t border-slate-100 grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-400">Authority:</span>
                  <p className="font-semibold text-slate-700">{selectedFramework.issuing_authority}</p>
                </div>
                <div>
                  <span className="text-slate-400">Jurisdiction:</span>
                  <p className="font-semibold text-slate-700">{selectedFramework.jurisdiction}</p>
                </div>
              </div>
            </div>

            {/* Authoritative Source Documents */}
            <div className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-blue-600" />
                  <h4 className="text-xs font-bold text-slate-900">Source Documents ({documents.length})</h4>
                </div>
                <button
                  onClick={() => setShowUploadDocModal(true)}
                  className="flex items-center gap-1 text-[11px] font-semibold text-blue-600 hover:text-blue-800 cursor-pointer"
                >
                  <Plus className="h-3 w-3" />
                  <span>Upload PDF</span>
                </button>
              </div>

              {documents.length === 0 ? (
                <div className="py-6 text-center border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50">
                  <Upload className="h-6 w-6 text-slate-300 mx-auto mb-1.5" />
                  <p className="text-xs font-semibold text-slate-700">No regulatory documents</p>
                  <p className="text-[11px] text-slate-400 mt-0.5">Upload acts, guidelines, or standards PDF/DOCX.</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {documents.map((doc) => {
                    const isSelected = selectedDoc?.id === doc.id;
                    return (
                      <div
                        key={doc.id}
                        onClick={() => setSelectedDoc(doc)}
                        className={`p-3 rounded-xl border transition-all cursor-pointer ${
                          isSelected
                            ? 'bg-blue-50/60 border-blue-300 shadow-2xs'
                            : 'bg-white border-slate-200 hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="font-semibold text-xs text-slate-800 line-clamp-1">{doc.title}</p>
                            <div className="flex items-center gap-2 text-[10px] text-slate-500 mt-1">
                              <span>{doc.file_extension.toUpperCase()}</span>
                              <span>•</span>
                              <span>{doc.page_count || 1} pages</span>
                              <span>•</span>
                              <span>{doc.chunk_count} chunks</span>
                            </div>
                          </div>
                          <span
                            className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                              doc.status === 'completed'
                                ? 'bg-emerald-100 text-emerald-700'
                                : 'bg-amber-100 text-amber-700'
                            }`}
                          >
                            {doc.status}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Legal Analyst Agent Control Card */}
            <div className="bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 text-white rounded-2xl p-5 shadow-sm space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Bot className="h-5 w-5 text-indigo-400" />
                  <h4 className="text-xs font-bold">Legal Analyst AI</h4>
                </div>
                <span className="text-[10px] font-mono bg-indigo-500/20 text-indigo-300 border border-indigo-400/30 px-2 py-0.5 rounded">
                  Gemini Flash 1.5
                </span>
              </div>

              <p className="text-[11px] text-slate-300 leading-relaxed">
                Normative extraction engine. Parses regulatory chunks into testable obligations with exact verbatim citations and zero hallucination guardrails.
              </p>

              {selectedDoc && (
                <div className="bg-white/10 rounded-xl p-3 space-y-2 border border-white/10 text-[11px]">
                  <div className="flex justify-between text-slate-300">
                    <span>Target Document:</span>
                    <span className="font-semibold text-white truncate max-w-[150px]">{selectedDoc.title}</span>
                  </div>
                  <div className="flex justify-between text-slate-300">
                    <span>Available Chunks:</span>
                    <span className="font-semibold text-white">{selectedDoc.chunk_count}</span>
                  </div>
                  {extractionJob && (
                    <div className="flex justify-between text-emerald-400 font-semibold pt-1 border-t border-white/10">
                      <span>Last Extraction:</span>
                      <span>{extractionJob.requirements_extracted} requirements</span>
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={handleTriggerExtraction}
                disabled={!selectedDoc || isExtracting || selectedDoc.status !== 'completed'}
                className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold py-2.5 px-4 rounded-xl text-xs transition-all shadow-md cursor-pointer"
              >
                {isExtracting ? (
                  <>
                    <RefreshCw className="h-4 w-4 animate-spin" />
                    <span>Extracting Obligations...</span>
                  </>
                ) : (
                  <>
                    <Play className="h-4 w-4" />
                    <span>Run Legal Analyst Extraction</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Column 2 & 3: Requirements Review & Management Board */}
          <div className="lg:col-span-2 space-y-4">
            {/* Filter and Search Bar */}
            <div className="bg-white rounded-2xl border border-slate-200 p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="relative w-full sm:w-64">
                <Search className="h-3.5 w-3.5 text-slate-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  placeholder="Search requirements or quotes..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center gap-2 w-full sm:w-auto">
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none cursor-pointer"
                >
                  <option value="all">All Statuses</option>
                  <option value="pending_review">Pending Review</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                  <option value="needs_revision">Needs Revision</option>
                </select>

                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="bg-slate-50 border border-slate-200 text-slate-700 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none cursor-pointer max-w-[160px]"
                >
                  <option value="all">All Categories</option>
                  {STANDARD_CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Requirements List */}
            {requirements.length === 0 ? (
              <div className="bg-white rounded-2xl border border-slate-200 p-12 text-center shadow-xs">
                <ShieldCheck className="h-10 w-10 text-slate-300 mx-auto mb-2" />
                <h4 className="text-xs font-bold text-slate-700">No Extracted Requirements Found</h4>
                <p className="text-[11px] text-slate-400 mt-1 max-w-sm mx-auto">
                  Run the Legal Analyst agent on an authoritative document chunk to automatically extract structured compliance requirements.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {requirements.map((req) => {
                  const isPending = req.review_status === 'pending_review';
                  const isApproved = req.review_status === 'approved';
                  const isRejected = req.review_status === 'rejected';
                  const isRevision = req.review_status === 'needs_revision';

                  return (
                    <div
                      key={req.id}
                      className="bg-white rounded-2xl border border-slate-200 p-5 shadow-xs space-y-3 hover:border-slate-300 transition-colors"
                    >
                      {/* Top Bar: Code, Category, Obligation, Review Status */}
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-xs font-bold text-blue-700 bg-blue-50 px-2 py-0.5 rounded border border-blue-200">
                            {req.requirement_code || req.identifier}
                          </span>
                          <span className="font-bold text-slate-900 text-xs">{req.title}</span>
                          <span className="text-[10px] bg-slate-100 text-slate-700 px-2 py-0.5 rounded font-medium">
                            {req.category || 'Other'}
                          </span>
                          <span
                            className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${
                              req.obligation_type === 'mandatory'
                                ? 'bg-rose-50 text-rose-700 border border-rose-200'
                                : 'bg-amber-50 text-amber-700 border border-amber-200'
                            }`}
                          >
                            {req.obligation_type}
                          </span>
                        </div>

                        <div className="flex items-center gap-2">
                          <span
                            className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${
                              isApproved
                                ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                : isRejected
                                ? 'bg-rose-50 text-rose-700 border-rose-200'
                                : isRevision
                                ? 'bg-amber-50 text-amber-700 border-amber-200'
                                : 'bg-blue-50 text-blue-700 border-blue-200'
                            }`}
                          >
                            {req.review_status.replace('_', ' ')}
                          </span>
                          <button
                            onClick={() => handleOpenHistory(req)}
                            className="p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
                            title="View Change Audit History"
                          >
                            <Clock className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>

                      {/* Testable Statement */}
                      <p className="text-xs text-slate-700 font-medium leading-relaxed">
                        {req.requirement_statement || req.description}
                      </p>

                      {/* Verbatim Source Excerpt */}
                      {req.source_excerpt && (
                        <div className="bg-slate-50 border-l-2 border-indigo-400 p-2.5 rounded-r-lg space-y-1">
                          <div className="flex items-center justify-between text-[10px] text-indigo-700 font-semibold">
                            <span>Exact Source Citation</span>
                            <span>
                              {req.source_section ? `${req.source_section} • ` : ''}
                              Page {req.source_page || 'N/A'}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-600 italic font-serif leading-relaxed">
                            "{req.source_excerpt}"
                          </p>
                        </div>
                      )}

                      {/* Human Review Actions */}
                      <div className="pt-2 border-t border-slate-100 flex items-center justify-between">
                        <span className="text-[10px] text-slate-400">
                          Confidence: {Math.round((req.confidence_score || 0.9) * 100)}%
                        </span>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => setEditReqModal(req)}
                            className="flex items-center gap-1 text-[11px] text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 px-2.5 py-1 rounded-lg font-medium transition-colors cursor-pointer"
                          >
                            <Edit3 className="h-3 w-3" />
                            <span>Edit</span>
                          </button>

                          <button
                            onClick={() => setActionReasonModal({ type: 'revision', req })}
                            className="flex items-center gap-1 text-[11px] text-amber-700 hover:text-amber-800 bg-amber-50 hover:bg-amber-100 px-2.5 py-1 rounded-lg font-medium transition-colors cursor-pointer border border-amber-200"
                          >
                            <AlertTriangle className="h-3 w-3" />
                            <span>Request Revision</span>
                          </button>

                          <button
                            onClick={() => setActionReasonModal({ type: 'reject', req })}
                            className="flex items-center gap-1 text-[11px] text-rose-700 hover:text-rose-800 bg-rose-50 hover:bg-rose-100 px-2.5 py-1 rounded-lg font-medium transition-colors cursor-pointer border border-rose-200"
                          >
                            <XCircle className="h-3 w-3" />
                            <span>Reject</span>
                          </button>

                          <button
                            onClick={() => handleApprove(req.id)}
                            className="flex items-center gap-1 text-[11px] text-white bg-emerald-600 hover:bg-emerald-700 px-3 py-1 rounded-lg font-semibold transition-colors cursor-pointer shadow-2xs"
                          >
                            <CheckCircle2 className="h-3 w-3" />
                            <span>Approve</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* New Framework Modal */}
      {showNewFrameworkModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <form
            onSubmit={handleCreateFramework}
            className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg overflow-hidden animate-in fade-in zoom-in-95"
          >
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-sm font-bold text-slate-900">Add Regulatory Framework</h3>
              <button
                type="button"
                onClick={() => setShowNewFrameworkModal(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>
            <div className="p-6 space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700">Framework Full Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. NIST Cybersecurity Framework 2.0"
                  value={fwForm.name}
                  onChange={(e) => setFwForm({ ...fwForm, name: e.target.value })}
                  className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700">Short Code *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. NIST-CSF-2.0"
                    value={fwForm.short_name}
                    onChange={(e) => setFwForm({ ...fwForm, short_name: e.target.value })}
                    className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700">Issuing Authority *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. NIST / Dept of Commerce"
                    value={fwForm.issuing_authority}
                    onChange={(e) => setFwForm({ ...fwForm, issuing_authority: e.target.value })}
                    className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700">Jurisdiction</label>
                  <input
                    type="text"
                    value={fwForm.jurisdiction}
                    onChange={(e) => setFwForm({ ...fwForm, jurisdiction: e.target.value })}
                    className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700">Type</label>
                  <select
                    value={fwForm.framework_type}
                    onChange={(e) => setFwForm({ ...fwForm, framework_type: e.target.value })}
                    className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                  >
                    <option value="standard">Standard</option>
                    <option value="regulation">Regulation</option>
                    <option value="legislation">Legislation</option>
                    <option value="guideline">Guideline</option>
                    <option value="circular">Circular</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="font-semibold text-slate-700">Description</label>
                <textarea
                  rows={2}
                  value={fwForm.description}
                  onChange={(e) => setFwForm({ ...fwForm, description: e.target.value })}
                  className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                />
              </div>
            </div>
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowNewFrameworkModal(false)}
                className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700"
              >
                Create Framework
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Upload Document Modal */}
      {showUploadDocModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <form
            onSubmit={handleUploadDocument}
            className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95"
          >
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-sm font-bold text-slate-900">Upload Regulatory Document</h3>
              <button
                type="button"
                onClick={() => setShowUploadDocModal(false)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>
            <div className="p-6 space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700">Document Title *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Official Gazette Act No 22"
                  value={docUploadForm.title}
                  onChange={(e) => setDocUploadForm({ ...docUploadForm, title: e.target.value })}
                  className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700">Document Ref/No.</label>
                  <input
                    type="text"
                    placeholder="e.g. DPDPA-SEC-2023"
                    value={docUploadForm.document_number}
                    onChange={(e) => setDocUploadForm({ ...docUploadForm, document_number: e.target.value })}
                    className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                  />
                </div>
                <div>
                  <label className="font-semibold text-slate-700">Version</label>
                  <input
                    type="text"
                    value={docUploadForm.version}
                    onChange={(e) => setDocUploadForm({ ...docUploadForm, version: e.target.value })}
                    className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                  />
                </div>
              </div>
              <div>
                <label className="font-semibold text-slate-700">PDF / DOCX File *</label>
                <input
                  type="file"
                  required
                  accept=".pdf,.docx,.doc"
                  onChange={(e) => setDocUploadForm({ ...docUploadForm, file: e.target.files[0] })}
                  className="mt-1 w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                />
              </div>
            </div>
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowUploadDocModal(false)}
                className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700"
              >
                Ingest &amp; Chunk
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Edit Requirement Modal */}
      {editReqModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <form
            onSubmit={handleEditSubmit}
            className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-xl overflow-hidden animate-in fade-in zoom-in-95"
          >
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Edit Requirement</h3>
                <span className="font-mono text-[10px] text-blue-600">
                  {editReqModal.requirement_code || editReqModal.identifier}
                </span>
              </div>
              <button
                type="button"
                onClick={() => setEditReqModal(null)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>
            <div className="p-6 space-y-3 text-xs">
              <div>
                <label className="font-semibold text-slate-700">Title</label>
                <input
                  type="text"
                  required
                  value={editReqModal.title}
                  onChange={(e) => setEditReqModal({ ...editReqModal, title: e.target.value })}
                  className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                />
              </div>
              <div>
                <label className="font-semibold text-slate-700">Requirement Statement (Normalized)</label>
                <textarea
                  rows={3}
                  required
                  value={editReqModal.requirement_statement || ''}
                  onChange={(e) =>
                    setEditReqModal({ ...editReqModal, requirement_statement: e.target.value })
                  }
                  className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-semibold text-slate-700">Category</label>
                  <select
                    value={editReqModal.category || 'Other'}
                    onChange={(e) => setEditReqModal({ ...editReqModal, category: e.target.value })}
                    className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                  >
                    {STANDARD_CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {c}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="font-semibold text-slate-700">Obligation Type</label>
                  <select
                    value={editReqModal.obligation_type || 'mandatory'}
                    onChange={(e) =>
                      setEditReqModal({ ...editReqModal, obligation_type: e.target.value })
                    }
                    className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                  >
                    <option value="mandatory">Mandatory</option>
                    <option value="conditional">Conditional</option>
                    <option value="recommended">Recommended</option>
                    <option value="informational">Informational</option>
                    <option value="unclear">Unclear</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="font-semibold text-slate-700">Reason for Edit (recorded in audit history)</label>
                <input
                  type="text"
                  placeholder="e.g. Fixed grammar and aligned with compliance definition"
                  value={editReqModal.reason || ''}
                  onChange={(e) => setEditReqModal({ ...editReqModal, reason: e.target.value })}
                  className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                />
              </div>
            </div>
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditReqModal(null)}
                className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-4 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-semibold hover:bg-blue-700"
              >
                Save Changes
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Reject / Revision Reason Modal */}
      {actionReasonModal && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <form
            onSubmit={handleActionWithReason}
            className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in-95"
          >
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
              <h3 className="text-sm font-bold text-slate-900">
                {actionReasonModal.type === 'reject' ? 'Reject Requirement' : 'Request Revision'}
              </h3>
              <button
                type="button"
                onClick={() => setActionReasonModal(null)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>
            <div className="p-6 space-y-3 text-xs">
              <p className="text-slate-600">
                Please provide a formal justification. This will be preserved in the requirement's immutable audit history.
              </p>
              <div>
                <label className="font-semibold text-slate-700">Justification / Feedback *</label>
                <textarea
                  name="reason"
                  required
                  rows={3}
                  placeholder="Explain why this requirement is rejected or what needs correction..."
                  className="mt-1 w-full p-2 bg-slate-50 border border-slate-200 rounded-lg focus:outline-none"
                />
              </div>
            </div>
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setActionReasonModal(null)}
                className="px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700"
              >
                Cancel
              </button>
              <button
                type="submit"
                className={`px-4 py-1.5 rounded-lg text-white text-xs font-semibold ${
                  actionReasonModal.type === 'reject'
                    ? 'bg-rose-600 hover:bg-rose-700'
                    : 'bg-amber-600 hover:bg-amber-700'
                }`}
              >
                Confirm
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Audit History Modal */}
      {historyModalReq && (
        <div className="fixed inset-0 z-60 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-lg max-h-[80vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95">
            <div className="px-6 py-4 border-b border-slate-200 flex justify-between items-center">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Requirement Audit Trail</h3>
                <span className="font-mono text-[10px] text-blue-600">
                  {historyModalReq.requirement_code || historyModalReq.identifier}
                </span>
              </div>
              <button
                onClick={() => setHistoryModalReq(null)}
                className="text-slate-400 hover:text-slate-600 text-xs font-bold"
              >
                ✕
              </button>
            </div>
            <div className="p-6 overflow-y-auto space-y-4">
              {isLoadingHistory ? (
                <div className="py-8 text-center text-slate-400 text-xs">Loading history...</div>
              ) : reqHistory.length === 0 ? (
                <div className="py-8 text-center text-slate-400 text-xs">No historical entries found.</div>
              ) : (
                reqHistory.map((h) => (
                  <div key={h.id} className="border-l-2 border-blue-400 pl-3 space-y-1 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-800 capitalize">{h.action.replace('_', ' ')}</span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {new Date(h.created_at).toLocaleString()}
                      </span>
                    </div>
                    {h.reason && <p className="text-slate-600 italic">"{h.reason}"</p>}
                    {h.previous_status && h.new_status && (
                      <p className="text-[11px] text-slate-500 font-mono">
                        Status: {h.previous_status} → {h.new_status}
                      </p>
                    )}
                  </div>
                ))
              )}
            </div>
            <div className="px-6 py-3 border-t border-slate-200 bg-slate-50 flex justify-end">
              <button
                onClick={() => setHistoryModalReq(null)}
                className="px-4 py-1.5 rounded-lg bg-slate-800 text-white text-xs font-semibold hover:bg-slate-900"
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

