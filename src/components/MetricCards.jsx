import React from 'react';
import { 
  CheckCircle2, 
  ShieldAlert, 
  AlertTriangle, 
  FileText, 
  TrendingUp, 
  AlertCircle,
  FileCheck
} from 'lucide-react';

export default function MetricCards() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
      {/* Card 1: Total Audits */}
      <div className="flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-4 shadow-2xs hover:shadow-xs transition-shadow">
        <div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Total Audits
            </span>
          </div>
          <div className="text-[11px] font-medium text-blue-600">
            8/8 Compliance Scopes
          </div>

          <div className="mt-2.5 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold tracking-tight text-slate-900">
              142
            </span>
            <span className="inline-flex items-center space-x-0.5 rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 border border-emerald-200/60">
              <TrendingUp className="h-3 w-3 mr-0.5" />
              +12%
            </span>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between pt-2 border-t border-slate-100">
          <span className="text-xs text-slate-500 font-medium">8 active in-flight</span>
          {/* Blue Sparkline */}
          <svg className="h-5 w-16" viewBox="0 0 60 20" fill="none">
            <path
              d="M1 15 L 12 14 L 24 16 L 36 8 L 48 10 L 59 3"
              stroke="#2563EB"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>

      {/* Card 2: Completed Audits */}
      <div className="flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-4 shadow-2xs hover:shadow-xs transition-shadow">
        <div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Completed Audits
            </span>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
          </div>
          <div className="text-[11px] font-medium text-slate-400">
            Certification Runs
          </div>

          <div className="mt-2.5 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold tracking-tight text-slate-900">
              128
            </span>
            <span className="inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-bold text-emerald-700 border border-emerald-200/60">
              90.1% Pass
            </span>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between pt-2 border-t border-slate-100">
          <span className="text-xs text-slate-500 font-medium">Zero drift detected</span>
          {/* Green Sparkline */}
          <svg className="h-5 w-16" viewBox="0 0 60 20" fill="none">
            <path
              d="M1 18 L 15 16 L 30 11 L 45 12 L 59 4"
              stroke="#10B981"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>

      {/* Card 3: Critical Findings */}
      <div className="flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-4 shadow-2xs hover:shadow-xs transition-shadow">
        <div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Critical Findings
            </span>
            <ShieldAlert className="h-4 w-4 text-rose-500" />
          </div>
          <div className="text-[11px] font-medium text-slate-400">
            Tier 1 Severity
          </div>

          <div className="mt-2.5 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold tracking-tight text-slate-900">
              3
            </span>
            <span className="inline-flex items-center rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-bold text-rose-700 border border-rose-200/60">
              -2 vs last wk
            </span>
          </div>
        </div>

        <div className="mt-4 pt-2 border-t border-slate-100">
          <div className="flex items-center justify-center space-x-1 rounded-md bg-rose-50/80 px-2 py-1 text-[11px] font-semibold text-rose-700 border border-rose-200/60 cursor-pointer hover:bg-rose-100 transition-colors">
            <AlertCircle className="h-3 w-3" />
            <span>Immediate CISO action needed</span>
          </div>
        </div>
      </div>

      {/* Card 4: High-Risk Findings */}
      <div className="flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-4 shadow-2xs hover:shadow-xs transition-shadow">
        <div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              High-Risk Findings
            </span>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </div>
          <div className="text-[11px] font-medium text-slate-400">
            CVSS &gt; 7.0 Issues
          </div>

          <div className="mt-2.5 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold tracking-tight text-slate-900">
              11
            </span>
            <span className="inline-flex items-center rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-bold text-amber-700 border border-amber-200/60">
              6 in triage
            </span>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between pt-2 border-t border-slate-100">
          <span className="text-xs text-slate-500 font-medium">Active engineering tasks</span>
          {/* Orange/Red Sparkline */}
          <svg className="h-5 w-16" viewBox="0 0 60 20" fill="none">
            <path
              d="M1 10 L 15 15 L 28 8 L 42 16 L 59 7"
              stroke="#F97316"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
      </div>

      {/* Card 5: Documents Analyzed */}
      <div className="flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-4 shadow-2xs hover:shadow-xs transition-shadow">
        <div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Documents Analyzed
            </span>
            <FileCheck className="h-4 w-4 text-blue-500" />
          </div>
          <div className="text-[11px] font-medium text-slate-400">
            OCR & Vector Digest
          </div>

          <div className="mt-2.5 flex items-baseline justify-between">
            <span className="text-3xl font-extrabold tracking-tight text-slate-900">
              1,489
            </span>
            <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-bold text-blue-700 border border-blue-200/60">
              +2.8k doc
            </span>
          </div>
        </div>

        <div className="mt-4 flex items-center justify-between pt-2 border-t border-slate-100">
          <span className="text-xs text-slate-400 font-mono truncate" title="PKCS, Specs & SOC...">
            PKCS, Specs &amp; SOC...
          </span>
          <span className="text-[10px] font-semibold text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded">
            PROD
          </span>
        </div>
      </div>
    </div>
  );
}

