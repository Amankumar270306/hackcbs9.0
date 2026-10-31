import React, { useState, useMemo } from 'react';
import { 
  Search, 
  ChevronDown, 
  Eye, 
  ExternalLink, 
  RefreshCw, 
  ChevronLeft, 
  ChevronRight,
  Shield,
  Loader2,
  CheckCircle2,
  AlertOctagon,
  Clock
} from 'lucide-react';

export default function RecentAuditsTable({ onSelectAudit }) {
  const [search, setSearch] = useState('');
  const [frameworkFilter, setFrameworkFilter] = useState('All Frameworks');
  const [severityFilter, setSeverityFilter] = useState('All Severities');
  const [currentPage, setCurrentPage] = useState(1);

  const initialAudits = [
    {
      id: 'AUD-2024-8841',
      targetName: 'Core Banking Payment Gateway v2.4',
      targetSub: 'Tier-0 Production VPC',
      framework: 'PCI-DSS v4.0',
      extraFw: '+1',
      findings: [
        { label: '1 Crit', type: 'crit' },
        { label: '2 High', type: 'high' }
      ],
      riskScore: 72,
      riskLevel: 'High Risk',
      status: 'Completed',
      statusType: 'completed',
      date: 'Today, 14:22 EST',
    },
    {
      id: 'AUD-2024-8839',
      targetName: 'Patient Health Telemetry Pipeline',
      targetSub: 'AWS US-HIPAA-Cluster',
      framework: 'HIPAA & HITRUST',
      findings: [
        { label: '2 High', type: 'high' },
        { label: '1 Med', type: 'med' }
      ],
      riskScore: 88,
      riskLevel: 'Moderate',
      status: 'Running (4/5)',
      statusType: 'running',
      date: 'Today, 11:05 EST',
    },
    {
      id: 'AUD-2024-8835',
      targetName: 'Customer Identity & SSO Microservice',
      targetSub: 'Auth0 Federation Gateway',
      framework: 'NIST 800-53 R5',
      findings: [
        { label: '2 Med', type: 'med' },
        { label: '0 High', type: 'neutral' }
      ],
      riskScore: 94,
      riskLevel: 'Low Risk',
      status: 'Completed',
      statusType: 'completed',
      date: 'Yesterday',
    },
    {
      id: 'AUD-2024-8830',
      targetName: 'AI Model Inference Training Cluster',
      targetSub: 'NVIDIA H100 Fleet - Innovation Fit',
      framework: 'EU AI Act',
      extraFw: '+1',
      findings: [
        { label: '2 Crit', type: 'crit' },
        { label: '4 High', type: 'high' }
      ],
      riskScore: 58,
      riskLevel: 'Critical',
      status: 'In Review',
      statusType: 'review',
      date: 'Oct 17, 2024',
    },
    {
      id: 'AUD-2024-8824',
      targetName: 'Cloud Infrastructure Terraform Stack',
      targetSub: 'AWS Multi-Region DevCloud',
      framework: 'CIS AWS v3.0',
      findings: [
        { label: '1 High', type: 'high' },
        { label: '3 Med', type: 'med' }
      ],
      riskScore: 92,
      riskLevel: 'Low Risk',
      status: 'Completed',
      statusType: 'completed',
      date: 'Oct 16, 2024',
    },
  ];

  const filteredAudits = useMemo(() => {
    return initialAudits.filter((audit) => {
      const matchSearch =
        audit.id.toLowerCase().includes(search.toLowerCase()) ||
        audit.targetName.toLowerCase().includes(search.toLowerCase()) ||
        audit.targetSub.toLowerCase().includes(search.toLowerCase()) ||
        audit.framework.toLowerCase().includes(search.toLowerCase());

      const matchFw =
        frameworkFilter === 'All Frameworks' || audit.framework.includes(frameworkFilter);

      const matchSev =
        severityFilter === 'All Severities' ||
        (severityFilter === 'Critical' && audit.riskLevel === 'Critical') ||
        (severityFilter === 'High' && audit.riskLevel === 'High Risk') ||
        (severityFilter === 'Moderate' && audit.riskLevel === 'Moderate') ||
        (severityFilter === 'Low' && audit.riskLevel === 'Low Risk');

      return matchSearch && matchFw && matchSev;
    });
  }, [search, frameworkFilter, severityFilter]);

  return (
    <div className="rounded-xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
      {/* Table Header & Controls */}
      <div className="flex flex-col gap-4 border-b border-slate-200 p-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-900">
            Recent Audits &amp; Automated Assessments
          </h2>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Live telemetry from multi-agent orchestration workers
          </p>
        </div>

        {/* Filters and search */}
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="rounded-md bg-blue-50 border border-blue-200 px-2.5 py-1 text-[11px] font-bold text-blue-700">
            Production Mode
          </span>

          {/* Search */}
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by ID, target..."
              className="h-8 rounded-lg border border-slate-200 bg-slate-50 pl-8 pr-3 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition-colors"
            />
          </div>

          {/* Framework Dropdown */}
          <div className="relative">
            <select
              value={frameworkFilter}
              onChange={(e) => setFrameworkFilter(e.target.value)}
              className="h-8 appearance-none rounded-lg border border-slate-200 bg-white pl-2.5 pr-7 text-xs font-medium text-slate-700 focus:border-blue-500 focus:outline-none cursor-pointer"
            >
              <option value="All Frameworks">All Frameworks</option>
              <option value="PCI-DSS">PCI-DSS</option>
              <option value="HIPAA">HIPAA</option>
              <option value="NIST">NIST 800-53</option>
              <option value="EU AI">EU AI Act</option>
              <option value="CIS">CIS AWS</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          </div>

          {/* Severity Dropdown */}
          <div className="relative">
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="h-8 appearance-none rounded-lg border border-slate-200 bg-white pl-2.5 pr-7 text-xs font-medium text-slate-700 focus:border-blue-500 focus:outline-none cursor-pointer"
            >
              <option value="All Severities">All Severities</option>
              <option value="Critical">Critical</option>
              <option value="High">High Risk</option>
              <option value="Moderate">Moderate</option>
              <option value="Low">Low Risk</option>
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
          </div>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50/70 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              <th className="py-3 pl-5 pr-3">Audit ID</th>
              <th className="px-3 py-3">Target System / Asset</th>
              <th className="px-3 py-3">Framework</th>
              <th className="px-3 py-3">Finding Summary</th>
              <th className="px-3 py-3">Risk Score</th>
              <th className="px-3 py-3">Argus Status</th>
              <th className="px-3 py-3">Execution Date</th>
              <th className="py-3 pl-3 pr-5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filteredAudits.map((item) => (
              <tr
                key={item.id}
                className="group hover:bg-slate-50/80 transition-colors"
              >
                {/* Audit ID */}
                <td className="py-3.5 pl-5 pr-3 font-mono font-semibold text-blue-600 hover:underline cursor-pointer">
                  <span onClick={() => onSelectAudit?.(item)}>{item.id}</span>
                </td>

                {/* Target System */}
                <td className="px-3 py-3.5">
                  <div className="font-bold text-slate-800">{item.targetName}</div>
                  <div className="text-[11px] text-slate-400 font-mono">{item.targetSub}</div>
                </td>

                {/* Framework */}
                <td className="px-3 py-3.5">
                  <div className="inline-flex items-center space-x-1">
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 border border-slate-200">
                      {item.framework}
                    </span>
                    {item.extraFw && (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 border border-slate-200">
                        {item.extraFw}
                      </span>
                    )}
                  </div>
                </td>

                {/* Finding Summary */}
                <td className="px-3 py-3.5">
                  <div className="flex items-center space-x-1.5">
                    {item.findings.map((f, i) => (
                      <span
                        key={i}
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                          f.type === 'crit'
                            ? 'bg-rose-50 text-rose-700 border border-rose-200'
                            : f.type === 'high'
                            ? 'bg-amber-50 text-amber-700 border border-amber-200'
                            : f.type === 'med'
                            ? 'bg-yellow-50 text-yellow-700 border border-yellow-200'
                            : 'bg-slate-100 text-slate-500 border border-slate-200'
                        }`}
                      >
                        {f.label}
                      </span>
                    ))}
                  </div>
                </td>

                {/* Risk Score */}
                <td className="px-3 py-3.5 font-semibold">
                  <span
                    className={
                      item.riskScore < 60
                        ? 'text-rose-600 font-bold'
                        : item.riskScore < 75
                        ? 'text-rose-600 font-bold'
                        : item.riskScore < 90
                        ? 'text-amber-600 font-bold'
                        : 'text-emerald-600 font-bold'
                    }
                  >
                    {item.riskScore}/100 ({item.riskLevel})
                  </span>
                </td>

                {/* Status */}
                <td className="px-3 py-3.5">
                  {item.statusType === 'completed' && (
                    <span className="inline-flex items-center space-x-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700 border border-emerald-200">
                      <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      <span>Completed</span>
                    </span>
                  )}
                  {item.statusType === 'running' && (
                    <span className="inline-flex items-center space-x-1.5 rounded-full bg-blue-50 px-2.5 py-0.5 text-[11px] font-semibold text-blue-700 border border-blue-200 animate-pulse">
                      <Loader2 className="h-3 w-3 animate-spin text-blue-600" />
                      <span>{item.status}</span>
                    </span>
                  )}
                  {item.statusType === 'review' && (
                    <span className="inline-flex items-center space-x-1.5 rounded-full bg-amber-50 px-2.5 py-0.5 text-[11px] font-semibold text-amber-700 border border-amber-200">
                      <span className="h-1.5 w-1.5 rounded-full bg-amber-500" />
                      <span>In Review</span>
                    </span>
                  )}
                </td>

                {/* Execution Date */}
                <td className="px-3 py-3.5 text-slate-500 text-[11px]">
                  {item.date}
                </td>

                {/* Actions */}
                <td className="py-3.5 pl-3 pr-5 text-right">
                  <div className="flex items-center justify-end space-x-2">
                    <button
                      onClick={() => onSelectAudit?.(item)}
                      title="Inspect Audit Trace"
                      className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors cursor-pointer"
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                    <button
                      title="External Ledger Verification"
                      className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition-colors cursor-pointer"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Table Pagination & Footer */}
      <div className="flex flex-col sm:flex-row items-center justify-between border-t border-slate-200 px-5 py-3 gap-3">
        {/* Left: Counter & Auto-refresh status */}
        <div className="flex items-center space-x-3 text-xs text-slate-500">
          <span>Showing 1 to {filteredAudits.length} of 142 audit runs</span>
          <span>•</span>
          <div className="flex items-center space-x-1.5 text-[11px] text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>Auto-refresh every 30s</span>
          </div>
        </div>

        {/* Right: Page Navigation */}
        <div className="flex items-center space-x-1 text-xs font-semibold">
          <button 
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
            className="flex h-7 w-7 items-center justify-center rounded border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button 
            onClick={() => setCurrentPage(1)}
            className={`flex h-7 w-7 items-center justify-center rounded cursor-pointer ${
              currentPage === 1 ? 'bg-blue-600 text-white font-bold' : 'border border-slate-200 text-slate-700 hover:bg-slate-50'
            }`}
          >
            1
          </button>
          <button 
            onClick={() => setCurrentPage(2)}
            className={`flex h-7 w-7 items-center justify-center rounded cursor-pointer ${
              currentPage === 2 ? 'bg-blue-600 text-white font-bold' : 'border border-slate-200 text-slate-700 hover:bg-slate-50'
            }`}
          >
            2
          </button>
          <button 
            onClick={() => setCurrentPage(3)}
            className={`flex h-7 w-7 items-center justify-center rounded cursor-pointer ${
              currentPage === 3 ? 'bg-blue-600 text-white font-bold' : 'border border-slate-200 text-slate-700 hover:bg-slate-50'
            }`}
          >
            3
          </button>
          <span className="px-1 text-slate-400">...</span>
          <button 
            onClick={() => setCurrentPage(29)}
            className="flex h-7 w-7 items-center justify-center rounded border border-slate-200 text-slate-700 hover:bg-slate-50 cursor-pointer"
          >
            29
          </button>
          <button 
            onClick={() => setCurrentPage(prev => Math.min(29, prev + 1))}
            className="flex h-7 w-7 items-center justify-center rounded border border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

