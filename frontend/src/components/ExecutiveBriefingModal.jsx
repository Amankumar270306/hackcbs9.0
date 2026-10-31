import React from 'react';
import { X, Download, FileText, CheckCircle2, ShieldCheck, Printer } from 'lucide-react';

export default function ExecutiveBriefingModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
      <div className="w-full max-w-xl rounded-2xl border border-slate-200 bg-white shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
          <div className="flex items-center space-x-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
              <FileText className="h-4 w-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Executive Compliance Briefing</h3>
              <p className="text-[11px] text-slate-400">Generated for Board &amp; Audit Committee</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-4 text-xs">
          <div className="rounded-xl border border-slate-200 p-4 bg-slate-50/50">
            <div className="flex items-center justify-between border-b border-slate-200 pb-2">
              <span className="font-bold text-slate-800">Acme Financial Global • Q3 2024 Audit Memo</span>
              <span className="text-[11px] font-mono text-slate-500">Oct 31, 2024</span>
            </div>
            <div className="mt-3 space-y-2 text-slate-600 text-[11px] leading-relaxed">
              <p>
                <strong>Overall Posture:</strong> 94.2% compliance index across 8 monitored frameworks. Zero high-impact drift detected in core production clusters.
              </p>
              <p>
                <strong>Automated Mitigation:</strong> 7 of 22 active findings have auto-remediation playbooks verified and queued for deployment.
              </p>
              <p>
                <strong>Certification Readiness:</strong> SOC2 Type II and ISO/IEC 27001 readiness scores remain at 96% and 91% respectively.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg border border-slate-200 p-2.5 bg-white">
              <div className="text-[10px] text-slate-400 font-bold uppercase">Audits Executed</div>
              <div className="text-lg font-bold text-slate-900 mt-0.5">142</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-2.5 bg-white">
              <div className="text-[10px] text-slate-400 font-bold uppercase">Pass Rate</div>
              <div className="text-lg font-bold text-emerald-600 mt-0.5">90.1%</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-2.5 bg-white">
              <div className="text-[10px] text-slate-400 font-bold uppercase">Resolved CVEs</div>
              <div className="text-lg font-bold text-blue-600 mt-0.5">48</div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-slate-100 px-6 py-3 bg-slate-50">
          <button
            onClick={() => window.print()}
            className="inline-flex items-center space-x-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900 cursor-pointer"
          >
            <Printer className="h-4 w-4" />
            <span>Print Report</span>
          </button>
          <div className="flex items-center space-x-2">
            <button
              onClick={onClose}
              className="rounded-lg border border-slate-200 px-3.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 cursor-pointer"
            >
              Close
            </button>
            <button
              onClick={() => {
                alert("Executive briefing PDF downloaded!");
                onClose();
              }}
              className="inline-flex items-center space-x-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-bold text-white hover:bg-blue-700 shadow-sm cursor-pointer"
            >
              <Download className="h-3.5 w-3.5" />
              <span>Download PDF Briefing</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

