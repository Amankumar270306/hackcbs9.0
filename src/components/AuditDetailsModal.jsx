import React from 'react';
import { 
  X, 
  ShieldAlert, 
  CheckCircle2, 
  Bot, 
  Terminal, 
  GitPullRequest, 
  Clock, 
  Server,
  Layers,
  ArrowRight
} from 'lucide-react';

export default function AuditDetailsModal({ audit, onClose }) {
  if (!audit) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 sticky top-0 bg-white z-10">
          <div className="flex items-center space-x-3">
            <span className="font-mono text-sm font-bold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-md border border-blue-200">
              {audit.id}
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">{audit.targetName}</h3>
              <p className="text-[11px] text-slate-400 font-mono">{audit.targetSub}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 space-y-5 text-xs">
          {/* Top Summary Bar */}
          <div className="grid grid-cols-3 gap-3 rounded-xl border border-slate-200 bg-slate-50/60 p-3.5">
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Framework</div>
              <div className="mt-1 font-bold text-slate-800 text-xs">{audit.framework}</div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Risk Score</div>
              <div className="mt-1 font-bold text-rose-600 text-xs">{audit.riskScore}/100 ({audit.riskLevel})</div>
            </div>
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Status</div>
              <div className="mt-1 font-semibold text-emerald-600 flex items-center space-x-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
                <span>{audit.status}</span>
              </div>
            </div>
          </div>

          {/* Agent Consensus Verification */}
          <div>
            <h4 className="font-bold text-slate-900 mb-2 flex items-center space-x-1.5">
              <Bot className="h-4 w-4 text-blue-600" />
              <span>Multi-Agent Consensus Report (5/5 Agents)</span>
            </h4>
            <div className="space-y-2">
              <div className="rounded-lg border border-slate-200 p-3 bg-white">
                <div className="flex items-center justify-between font-semibold text-slate-800">
                  <span>1. Adversarial Prober Agent</span>
                  <span className="text-rose-600 font-bold">1 Exploit Path Confirmed</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Attempted unauthenticated payload into cardholder endpoint. Bypassed WAF rule #882 due to wildcard header forwarding.
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 p-3 bg-white">
                <div className="flex items-center justify-between font-semibold text-slate-800">
                  <span>2. Legal &amp; Regulatory Auditor</span>
                  <span className="text-amber-600 font-bold">PCI-DSS 3.4 Non-Compliant</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Primary PAN storage at rest was detected with AES-128 instead of required AES-256 with KMS Hardware Security Module (HSM).
                </p>
              </div>

              <div className="rounded-lg border border-slate-200 p-3 bg-white">
                <div className="flex items-center justify-between font-semibold text-slate-800">
                  <span>3. Adjudicator AI Arbiter</span>
                  <span className="text-emerald-600 font-bold">Consensus Reached (Score: 72/100)</span>
                </div>
                <p className="mt-1 text-[11px] text-slate-500">
                  Formal verification checks completed. Synthesized remediation playbook created with 0 regression impact.
                </p>
              </div>
            </div>
          </div>

          {/* Auto Remediation Playbook */}
          <div className="rounded-xl border border-blue-200 bg-blue-50/50 p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <GitPullRequest className="h-4 w-4 text-blue-600" />
                <span className="font-bold text-blue-900">Recommended Auto-Remediation Playbook</span>
              </div>
              <span className="rounded bg-blue-600 text-white font-bold text-[10px] px-2 py-0.5">Ready to Merge</span>
            </div>
            <p className="mt-2 text-[11px] text-blue-800">
              Apply Terraform automated patch to enforce strict AWS KMS CMK key rotation and update VPC Security Group rule #12.
            </p>
            <div className="mt-3 flex items-center justify-between pt-2 border-t border-blue-200/60">
              <span className="font-mono text-[10px] text-blue-700">PR #8841-fix-pci-cmk-encryption</span>
              <button 
                onClick={() => alert("Playbook dispatched to CI/CD pipeline!")}
                className="inline-flex items-center space-x-1 rounded bg-blue-600 px-3 py-1 font-bold text-white text-[11px] hover:bg-blue-700 cursor-pointer"
              >
                <span>Dispatch Patch</span>
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end border-t border-slate-100 px-6 py-3 bg-slate-50">
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

