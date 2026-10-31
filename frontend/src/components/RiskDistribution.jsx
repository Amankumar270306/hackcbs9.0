import React from 'react';
import { ArrowUpRight } from 'lucide-react';

export default function RiskDistribution({ onExploreMatrix }) {
  const frameworks = [
    {
      name: 'SOC 2 Type II (Trust Services)',
      standard: 'AICPA 2023',
      status: '0 crit · 96% Compliant',
      safePct: 96,
      medPct: 4,
      critPct: 0,
      textColor: 'text-emerald-600',
    },
    {
      name: 'ISO/IEC 27001:2022',
      standard: 'ISMS Annex A',
      status: '3 High · 91% Compliant',
      safePct: 91,
      medPct: 9,
      critPct: 0,
      textColor: 'text-amber-600',
    },
    {
      name: 'HIPAA Security & Privacy Rule',
      standard: '45 CFR 164',
      status: '1 Crit · 89% Compliant',
      safePct: 89,
      medPct: 6,
      critPct: 5,
      textColor: 'text-rose-600',
    },
    {
      name: 'PCI-DSS v4.0 Level 1',
      standard: 'Cardholder Data',
      status: '0 Crit · 94% Compliant',
      safePct: 94,
      medPct: 6,
      critPct: 0,
      textColor: 'text-emerald-600',
    },
    {
      name: 'NIST CSF 2.0',
      standard: 'Govern / Protect',
      status: '2 Med · 89% Compliant',
      safePct: 89,
      medPct: 7,
      critPct: 4,
      textColor: 'text-amber-600',
    },
  ];

  return (
    <div className="flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-5 shadow-2xs">
      <div>
        {/* Header and Legend */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              Risk Distribution by Framework
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Control satisfaction indices indexed across global governance domains
            </p>
          </div>

          <div className="flex items-center space-x-3 text-[11px]">
            <span className="rounded-md bg-slate-100 px-2 py-0.5 font-medium text-slate-600 border border-slate-200">
              Normal Level
            </span>
            <div className="flex items-center space-x-2 text-slate-600">
              <span className="flex items-center space-x-1">
                <span className="h-2 w-2 rounded-full bg-emerald-500"></span>
                <span className="text-[10px]">Safe</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="h-2 w-2 rounded-full bg-amber-500"></span>
                <span className="text-[10px]">Med</span>
              </span>
              <span className="flex items-center space-x-1">
                <span className="h-2 w-2 rounded-full bg-rose-500"></span>
                <span className="text-[10px]">Crit</span>
              </span>
            </div>
          </div>
        </div>

        {/* Frameworks Bar List */}
        <div className="mt-5 space-y-4">
          {frameworks.map((fw, idx) => (
            <div key={idx} className="group">
              <div className="flex items-center justify-between text-xs mb-1.5">
                <div className="flex items-center space-x-1.5">
                  <span className="font-semibold text-slate-800">{fw.name}</span>
                  <span className="text-slate-300">|</span>
                  <span className="text-slate-400 font-mono text-[11px]">{fw.standard}</span>
                </div>
                <span className={`text-[11px] font-semibold ${fw.textColor}`}>
                  {fw.status}
                </span>
              </div>

              {/* Stacked segmented progress bar */}
              <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-slate-100 ring-1 ring-slate-200/50">
                <div
                  className="bg-emerald-500 transition-all duration-500 group-hover:brightness-105"
                  style={{ width: `${fw.safePct}%` }}
                  title={`Safe: ${fw.safePct}%`}
                />
                {fw.medPct > 0 && (
                  <div
                    className="bg-amber-500 transition-all duration-500"
                    style={{ width: `${fw.medPct}%` }}
                    title={`Medium: ${fw.medPct}%`}
                  />
                )}
                {fw.critPct > 0 && (
                  <div
                    className="bg-rose-500 transition-all duration-500"
                    style={{ width: `${fw.critPct}%` }}
                    title={`Critical: ${fw.critPct}%`}
                  />
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Footer bar */}
      <div className="mt-6 flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
        <div className="text-slate-600">
          Aggregated Governance Score: <span className="font-bold text-slate-900">91.6 / 100</span>
        </div>
        <button
          onClick={onExploreMatrix}
          className="inline-flex items-center space-x-1 font-semibold text-blue-600 hover:text-blue-700 hover:underline cursor-pointer"
        >
          <span>Explore Matrix</span>
          <ArrowUpRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

