import React from 'react';
import { 
  KeyRound, 
  Database, 
  FileClock, 
  Zap, 
  Globe2, 
  Wand2 
} from 'lucide-react';

export default function FindingsByCategory({ onConfigureGuardrails }) {
  const categories = [
    {
      name: 'Identity & Access Control',
      count: '5 (24%)',
      widthPct: 65,
      barColor: 'from-rose-500 to-amber-500',
      icon: KeyRound,
    },
    {
      name: 'Data Encryption at Rest',
      count: '5 (24%)',
      widthPct: 65,
      barColor: 'from-rose-500 to-amber-500',
      icon: Database,
    },
    {
      name: 'Audit Logging & Retention',
      count: '4 (19%)',
      widthPct: 52,
      barColor: 'from-amber-500 to-amber-400',
      icon: FileClock,
    },
    {
      name: 'Incident Response SLA',
      count: '3 (14%)',
      widthPct: 38,
      barColor: 'from-amber-500 to-orange-400',
      icon: Zap,
    },
    {
      name: 'Third-Party Risk (TPRM)',
      count: '2 (9%)',
      widthPct: 24,
      barColor: 'from-blue-500 to-cyan-400',
      icon: Globe2,
    },
  ];

  return (
    <div className="flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-5 shadow-2xs">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              Findings by Category
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Critical surface exposure mapped to control clusters
            </p>
          </div>
          <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-bold text-slate-700 border border-slate-200">
            22 Active
          </span>
        </div>

        {/* Categories List */}
        <div className="mt-5 space-y-3.5">
          {categories.map((cat, idx) => {
            const Icon = cat.icon;
            return (
              <div key={idx} className="group">
                <div className="flex items-center justify-between text-xs mb-1.5">
                  <div className="flex items-center space-x-2">
                    <Icon className="h-3.5 w-3.5 text-blue-500" />
                    <span className="font-semibold text-slate-800">{cat.name}</span>
                  </div>
                  <span className="text-[11px] font-bold text-slate-700">
                    {cat.count}
                  </span>
                </div>

                {/* Progress bar container */}
                <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100 ring-1 ring-slate-200/50">
                  <div
                    className={`h-full rounded-full bg-gradient-to-r ${cat.barColor} transition-all duration-500`}
                    style={{ width: `${cat.widthPct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Auto-remediation banner */}
      <div className="mt-6 flex flex-col sm:flex-row sm:items-center justify-between gap-2 rounded-lg bg-blue-50/70 border border-blue-200/60 p-2.5 text-xs text-blue-900">
        <div className="flex items-center space-x-2">
          <Wand2 className="h-4 w-4 text-blue-600 shrink-0" />
          <span className="font-medium text-[11px] text-blue-800">
            Auto-Remediation Playbooks applied to 7 findings
          </span>
        </div>
        <button
          onClick={onConfigureGuardrails}
          className="text-[11px] font-bold text-blue-600 hover:text-blue-800 hover:underline shrink-0 text-left sm:text-right cursor-pointer"
        >
          Configure Guardrails
        </button>
      </div>
    </div>
  );
}

