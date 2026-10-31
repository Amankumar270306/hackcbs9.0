import React from 'react';
import { Cpu, ArrowRight, ShieldCheck } from 'lucide-react';

export default function EngineFooter({ onOpenDebugger }) {
  return (
    <div className="rounded-xl border border-blue-200/60 bg-gradient-to-r from-blue-50/70 via-slate-50 to-emerald-50/40 p-4 shadow-2xs">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        {/* Left Info */}
        <div className="flex items-start sm:items-center space-x-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-600 text-white shadow-2xs">
            <Cpu className="h-5 w-5" />
          </div>

          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-bold text-slate-900 text-xs sm:text-sm">
                Compliance Sentinel Engine v4.0
              </span>
              <span className="inline-flex items-center space-x-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                <span>All Agents Online</span>
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Continuous cross-framework evidence triangulation running against NIST SP 800-53, SOC2, and EU AI Act baselines.
            </p>
          </div>
        </div>

        {/* Right CTA */}
        <button
          onClick={onOpenDebugger}
          className="inline-flex items-center space-x-1.5 rounded-lg border border-blue-300 bg-white px-3.5 py-1.5 text-xs font-bold text-blue-700 shadow-2xs hover:bg-blue-50 transition-all shrink-0 cursor-pointer"
        >
          <span>Agent Debugger Console</span>
          <ArrowRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

