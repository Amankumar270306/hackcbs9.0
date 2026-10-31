import React, { useState } from 'react';
import { X, Shield, Server, Check, ArrowRight, Play, Loader2, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { auditApi } from '../api/client';

export default function NewAuditModal({ isOpen, onClose, onAuditCreated }) {
  const { activeOrg } = useAuth();
  const [cluster, setCluster] = useState('us-east1-gke-4');
  const [targetAsset, setTargetAsset] = useState('Payment Gateway Cluster v2.4');
  const [framework, setFramework] = useState('PCI-DSS v4.0');
  const [depth, setDepth] = useState('Deep Multi-Agent (5 Agents)');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!activeOrg?.organization_id) {
      setError('Please select an active organization first.');
      return;
    }

    setError('');
    setIsSubmitting(true);

    try {
      // 1. Create Audit Case in YSQL
      const audit = await auditApi.create(activeOrg.organization_id, {
        name: targetAsset.trim(),
        application_name: cluster.trim(),
        description: `Compliance assessment under ${framework} framework`,
      });

      // 2. Dispatch First Sequential Run
      const run = await auditApi.createRun(activeOrg.organization_id, audit.id, {
        summary: `Autonomous consensus execution across ${depth}`,
        config: { framework, depth, cluster },
      });

      onAuditCreated?.({
        ...audit,
        id: audit.id,
        rawId: audit.id,
        displayId: `AUD-2024-${audit.id.slice(0, 4).toUpperCase()}`,
        targetName: audit.name,
        targetSub: audit.application_name,
        framework: framework,
        findings: [{ label: 'Running', type: 'med' }],
        riskScore: 85,
        riskLevel: 'Moderate',
        status: 'Running (1/5)',
        statusType: 'running',
        date: 'Just now',
      });

      onClose();
    } catch (err) {
      setError(err.message || 'Failed to dispatch audit');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
      <div className="w-full max-w-lg rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div className="flex items-center space-x-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
              <Shield className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Initiate New Audit</h3>
              <p className="text-[11px] text-slate-500">Dispatch autonomous LLM consensus verification</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors cursor-pointer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="flex items-start space-x-2.5 rounded-lg bg-rose-50 p-2.5 text-xs text-rose-800 border border-rose-200">
              <AlertCircle className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Target System or Workload Name
            </label>
            <input
              type="text"
              required
              value={targetAsset}
              onChange={(e) => setTargetAsset(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="e.g. Core Banking Payment Gateway"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Cluster / VPC Target
              </label>
              <input
                type="text"
                required
                value={cluster}
                onChange={(e) => setCluster(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                placeholder="e.g. us-east1-gke-4"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Framework Rulepack
              </label>
              <select
                value={framework}
                onChange={(e) => setFramework(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 px-3 py-2 text-xs text-slate-800 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500"
              >
                <option value="PCI-DSS v4.0">PCI-DSS v4.0</option>
                <option value="SOC 2 Type II">SOC 2 Type II</option>
                <option value="ISO 27001:2022">ISO 27001:2022</option>
                <option value="HIPAA Security Rule">HIPAA Security Rule</option>
                <option value="NIST CSF 2.0">NIST CSF 2.0</option>
                <option value="EU AI Act High-Risk">EU AI Act High-Risk</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Multi-Agent Verification Depth
            </label>
            <div className="grid grid-cols-2 gap-2 text-xs">
              {[
                { title: 'Standard Fast', desc: 'Legal + Defense (2 Agents)' },
                { title: 'Deep Multi-Agent (5 Agents)', desc: 'Adversary + Adjudicator consensus' },
              ].map((opt) => (
                <div
                  key={opt.title}
                  onClick={() => setDepth(opt.title)}
                  className={`p-2.5 rounded-lg border cursor-pointer transition-all ${
                    depth === opt.title
                      ? 'border-blue-600 bg-blue-50/50 ring-1 ring-blue-600'
                      : 'border-slate-200 hover:border-slate-300'
                  }`}
                >
                  <div className="font-semibold text-slate-800 text-[11px]">{opt.title}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{opt.desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Action buttons */}
          <div className="pt-3 flex items-center justify-end space-x-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-600 hover:bg-slate-50 cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center space-x-1.5 px-4 py-1.5 rounded-lg bg-blue-600 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 active:scale-[0.98] transition-all cursor-pointer disabled:opacity-70"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Provisioning & Dispatching...</span>
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5 fill-white" />
                  <span>Dispatch Consensus Audit</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
