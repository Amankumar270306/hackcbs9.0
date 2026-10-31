import React, { useState, useEffect, useMemo } from 'react';
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
  Clock,
  Plus
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { auditApi } from '../api/client';

export default function RecentAuditsTable({ onSelectAudit, onOpenNewAudit }) {
  const { activeOrg } = useAuth();
  const [search, setSearch] = useState('');
  const [frameworkFilter, setFrameworkFilter] = useState('All Frameworks');
  const [severityFilter, setSeverityFilter] = useState('All Severities');
  const [currentPage, setCurrentPage] = useState(1);
  const [dbAudits, setDbAudits] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const fetchAudits = () => {
    if (!activeOrg?.organization_id) return;
    setIsLoading(true);
    auditApi.list(activeOrg.organization_id, {
      search: search.trim() || undefined,
      page: currentPage,
      size: 10,
    })
      .then((res) => {
        setDbAudits(res.items || []);
        setTotalCount(res.total || 0);
      })
      .catch((err) => {
        console.warn('Could not fetch audits from API:', err);
      })
      .finally(() => {
        setIsLoading(false);
      });
  };

  useEffect(() => {
    fetchAudits();
  }, [activeOrg?.organization_id, search, currentPage]);

  const fallbackAudits = [
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
        { label: '3 High', type: 'high' }
      ],
      riskScore: 94,
      riskLevel: 'Low Risk',
      status: 'Completed',
      statusType: 'completed',
      date: 'Yesterday',
    },
  ];

  // Map database audits into display format
  const displayAudits = useMemo(() => {
    if (dbAudits.length > 0) {
      return dbAudits.map((a) => {
        const lr = a.latest_run;
        const statusType = lr?.status === 'running' ? 'running' : (a.status === 'completed' ? 'completed' : 'review');
        const statusLabel = lr ? (lr.status === 'running' ? 'Running (1/5)' : lr.status) : (a.status === 'draft' ? 'Draft Case' : a.status);
        const score = lr?.risk_score !== null && lr?.risk_score !== undefined ? lr.risk_score : 85;
        const riskLabel = score > 90 ? 'Low Risk' : (score > 70 ? 'Moderate' : 'Critical');
        const formattedDate = new Date(a.created_at).toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        });

        return {
          id: `AUD-2024-${a.id.slice(0, 4).toUpperCase()}`,
          rawId: a.id,
          targetName: a.name || a.title,
          targetSub: a.application_name || 'Production VPC',
          framework: a.description?.includes('PCI') ? 'PCI-DSS v4.0' : 'SOC 2 Type II',
          extraFw: a.runs_count > 1 ? `+${a.runs_count - 1}` : null,
          findings: [
            { label: `${a.finding_count || 0} Issues`, type: a.finding_count > 0 ? 'high' : 'med' }
          ],
          riskScore: score,
          riskLevel: riskLabel,
          status: statusLabel,
          statusType: statusType,
          date: formattedDate,
        };
      });
    }

    // If activeOrg is default demo workspace and no audits in DB yet, show fallback
    if (!activeOrg || activeOrg.organization_slug?.includes('acme') || activeOrg.organization_name?.includes('Acme')) {
      return fallbackAudits;
    }

    return [];
  }, [dbAudits, activeOrg]);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-xs overflow-hidden">
      {/* Table Header Section */}
      <div className="p-5 border-b border-slate-100 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <h3 className="text-sm font-bold text-slate-900 tracking-tight">
              Recent Audits & Automated Assessments
            </h3>
            <span className="rounded bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700 border border-blue-200">
              YSQL Live Partition
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Telemetry from multi-agent consensus orchestrations for {activeOrg?.organization_name || 'workspace'}
          </p>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="relative">
            <Search className="h-3.5 w-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter by ID, target..."
              className="rounded-lg border border-slate-200 bg-slate-50/70 py-1.5 pl-8 pr-3 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 w-44 sm:w-52 transition-all"
            />
          </div>

          <button
            onClick={() => fetchAudits()}
            title="Refresh from YugabyteDB"
            className="flex items-center space-x-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition-colors cursor-pointer"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? 'animate-spin text-blue-600' : ''}`} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Main Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[760px]">
          <thead>
            <tr className="border-b border-slate-100 bg-slate-50/75 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              <th className="py-3 pl-5 pr-3">Audit ID</th>
              <th className="py-3 px-3">Target System / Workload</th>
              <th className="py-3 px-3">Framework</th>
              <th className="py-3 px-3">Findings Summary</th>
              <th className="py-3 px-3">Risk Score</th>
              <th className="py-3 px-3">Engine Status</th>
              <th className="py-3 px-3">Execution Date</th>
              <th className="py-3 pl-3 pr-5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-xs">
            {isLoading ? (
              <tr>
                <td colSpan={8} className="py-12 text-center text-slate-500">
                  <div className="flex flex-col items-center justify-center space-y-2">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
                    <span className="text-xs font-medium">Querying YugabyteDB YSQL tenant partitions...</span>
                  </div>
                </td>
              </tr>
            ) : displayAudits.length === 0 ? (
              <tr>
                <td colSpan={8} className="py-14 text-center">
                  <div className="flex flex-col items-center justify-center space-y-3">
                    <div className="h-10 w-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                      <Shield className="h-5 w-5" />
                    </div>
                    <div className="text-slate-800 font-semibold text-sm">No Audits Found</div>
                    <p className="text-xs text-slate-500 max-w-sm">
                      There are no audit cases in this workspace yet. Initiate your first autonomous consensus audit.
                    </p>
                    <button
                      onClick={onOpenNewAudit}
                      className="inline-flex items-center space-x-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 transition-colors cursor-pointer"
                    >
                      <Plus className="h-4 w-4" />
                      <span>Initiate New Audit</span>
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              displayAudits.map((item) => (
                <tr key={item.id} className="hover:bg-slate-50/80 transition-colors">
                  {/* Audit ID */}
                  <td className="py-3.5 pl-5 pr-3 font-mono font-medium text-blue-600">
                    {item.id}
                  </td>

                  {/* Target System */}
                  <td className="py-3.5 px-3">
                    <div className="font-semibold text-slate-800">{item.targetName}</div>
                    <div className="text-[11px] text-slate-400">{item.targetSub}</div>
                  </td>

                  {/* Framework */}
                  <td className="py-3.5 px-3">
                    <div className="inline-flex items-center space-x-1">
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700 border border-slate-200">
                        {item.framework}
                      </span>
                      {item.extraFw && (
                        <span className="rounded bg-slate-100 px-1 py-0.5 text-[9px] font-bold text-slate-500">
                          {item.extraFw}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Findings */}
                  <td className="py-3.5 px-3">
                    <div className="flex items-center space-x-1.5">
                      {item.findings.map((f, i) => (
                        <span
                          key={i}
                          className={`rounded px-1.5 py-0.5 text-[10px] font-bold ${
                            f.type === 'crit'
                              ? 'bg-rose-50 text-rose-700 border border-rose-200'
                              : f.type === 'high'
                              ? 'bg-orange-50 text-orange-700 border border-orange-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {f.label}
                        </span>
                      ))}
                    </div>
                  </td>

                  {/* Risk Score */}
                  <td className="py-3.5 px-3">
                    <div className="flex items-center space-x-1.5">
                      <span className="font-bold text-slate-800">{item.riskScore}/100</span>
                      <span
                        className={`text-[10px] font-semibold ${
                          item.riskLevel.includes('Critical') || item.riskLevel.includes('High')
                            ? 'text-rose-600'
                            : item.riskLevel.includes('Moderate')
                            ? 'text-amber-600'
                            : 'text-emerald-600'
                        }`}
                      >
                        ({item.riskLevel})
                      </span>
                    </div>
                  </td>

                  {/* Status */}
                  <td className="py-3.5 px-3">
                    <div className="inline-flex items-center space-x-1.5">
                      {item.statusType === 'completed' ? (
                        <>
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                          <span className="text-emerald-700 font-medium">{item.status}</span>
                        </>
                      ) : item.statusType === 'running' ? (
                        <>
                          <Loader2 className="h-3.5 w-3.5 text-blue-500 animate-spin" />
                          <span className="text-blue-700 font-medium">{item.status}</span>
                        </>
                      ) : (
                        <>
                          <Clock className="h-3.5 w-3.5 text-amber-500" />
                          <span className="text-amber-700 font-medium">{item.status}</span>
                        </>
                      )}
                    </div>
                  </td>

                  {/* Date */}
                  <td className="py-3.5 px-3 text-slate-500 text-[11px]">
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
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Table Pagination & Footer */}
      <div className="flex flex-col sm:flex-row items-center justify-between border-t border-slate-200 px-5 py-3 gap-3">
        <div className="flex items-center space-x-3 text-xs text-slate-500">
          <span>Showing {displayAudits.length} of {totalCount || displayAudits.length} assessments</span>
          <span>•</span>
          <div className="flex items-center space-x-1.5 text-[11px] text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>Multi-tenant consensus sync</span>
          </div>
        </div>

        <div className="flex items-center space-x-1 text-xs font-semibold">
          <button 
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((prev) => Math.max(1, prev - 1))}
            className="flex h-7 w-7 items-center justify-center rounded border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button className="flex h-7 w-7 items-center justify-center rounded bg-blue-600 text-white font-bold cursor-pointer">
            {currentPage}
          </button>
          <button 
            disabled={displayAudits.length < 10}
            onClick={() => setCurrentPage((prev) => prev + 1)}
            className="flex h-7 w-7 items-center justify-center rounded border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-40 cursor-pointer"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
