import React, { useState } from 'react';
import { X, Shield, Server, Check, ArrowRight, Play, Loader2 } from 'lucide-react';

export default function NewAuditModal({ isOpen, onClose, onAuditCreated }) {
  const [cluster, setCluster] = useState('us-east1-gke-4');
  const [targetAsset, setTargetAsset] = useState('Payment Gateway Cluster v2.4');
  const [framework, setFramework] = useState('PCI-DSS v4.0');
  const [depth, setDepth] = useState('Deep Multi-Agent (5 Agents)');
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      onAuditCreated?.({
        id: `AUD-2024-${Math.floor(1000 + Math.random() * 9000)}`,
        targetName: targetAsset,
        targetSub: cluster,
        framework: framework,
        findings: [{ label: 'Running', type: 'med' }],
        riskScore: 85,
        riskLevel: 'Moderate',
        status: 'Running (1/5)',
        statusType: 'running',
        date: 'Just now'
      });
      onClose();
    }, 1000);
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
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Target System or Workload Name
            </label>
            <input
              type="text"
              value={targetAsset}
              onChange={(e) => setTargetAsset(e.target.value)}
              required
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              placeholder="e.g. Core Banking Payment Gateway v2.4"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Cluster Node / VPC
              </label>
              <select
                value={cluster}
                onChange={(e) => setCluster(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
              >
                <option value="us-east1-gke-4">us-east1-gke-4</option>
                <option value="eu-west1-prod-vpc">eu-west1-prod-vpc</option>
                <option value="aws-us-hipaa-cluster">aws-us-hipaa-cluster</option>
                <option value="h100-inference-fleet">h100-inference-fleet</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Primary Framework
              </label>
              <select
                value={framework}
                onChange={(e) => setFramework(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 bg-white"
              >
                <option value="PCI-DSS v4.0">PCI-DSS v4.0</option>
                <option value="SOC 2 Type II">SOC 2 Type II</option>
                <option value="ISO/IEC 27001">ISO/IEC 27001</option>
                <option value="HIPAA Security">HIPAA Security</option>
                <option value="NIST CSF 2.0">NIST CSF 2.0</option>
                <option value="EU AI Act">EU AI Act</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Audit Pipeline Mode
            </label>
            <div className="grid grid-cols-2 gap-2">
              {[
                { title: 'Standard Fast Scan', sub: '3 policy checks • ~2m' },
                { title: 'Deep Multi-Agent (5 Agents)', sub: 'Full adversarial & consensus • ~8m' },
              ].map((opt) => (
                <div
                  key={opt.title}
                  onClick={() => setDepth(opt.title)}
                  className={`cursor-pointer rounded-lg border p-2.5 text-xs transition-all ${
                    depth === opt.title
                      ? 'border-blue-600 bg-blue-50/60 text-blue-900 ring-1 ring-blue-600'
                      : 'border-slate-200 bg-white hover:bg-slate-50'
                  }`}
                >
                  <div className="font-bold">{opt.title}</div>
                  <div className="text-[10px] text-slate-500">{opt.sub}</div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-lg bg-slate-50 p-3 text-[11px] text-slate-600 border border-slate-200/80">
            <span className="font-bold text-slate-800">Orchestrator Notice:</span> This will dispatch 5 autonomous auditor models: Legal Analyst, Adversarial Tester, Baseline Verifier, Policy Diff Engine, and Adjudicator AI.
          </div>

          {/* Footer Actions */}
          <div className="mt-5 flex items-center justify-end space-x-2 pt-2 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-200 px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="inline-flex items-center space-x-1.5 rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-blue-700 disabled:opacity-60 transition-all cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Dispatching...</span>
                </>
              ) : (
                <>
                  <Play className="h-3.5 w-3.5" />
                  <span>Launch Audit Run</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

