import React from 'react';
import { Info, ArrowRight, ShieldCheck } from 'lucide-react';

export default function PostureStatusDonut({ onTriggerCheck }) {
  // SVG Donut calculation with r=40
  // Circumference = 251.327
  const r = 40;
  const c = 2 * Math.PI * r;

  // Percentages:
  // Green (Verified): 76%
  // Blue (Remediated): 11%
  // Amber (Open Discrepancies): 8%
  // Rose (Unresolved Question): 5%
  const p1 = 0.76;
  const p2 = 0.11;
  const p3 = 0.08;
  const p4 = 0.05;

  const len1 = p1 * c;
  const len2 = p2 * c;
  const len3 = p3 * c;
  const len4 = p4 * c;

  const off1 = 0;
  const off2 = -(len1);
  const off3 = -(len1 + len2);
  const off4 = -(len1 + len2 + len3);

  const legendItems = [
    { label: 'Verified Controls', value: '76%', color: 'bg-emerald-500', text: 'text-emerald-700' },
    { label: 'Remediated', value: '11%', color: 'bg-blue-600', text: 'text-blue-700' },
    { label: 'Open Discrepancies', value: '8%', color: 'bg-amber-500', text: 'text-amber-700' },
    { label: 'Unresolved Question', value: '5%', color: 'bg-rose-500', text: 'text-rose-700' },
  ];

  return (
    <div className="flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-5 shadow-2xs">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-sm font-bold text-slate-900">
              Posture Status Breakdown
            </h2>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Formal control verification health index
            </p>
          </div>
          <button 
            className="rounded-full p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            title="Formal verification information"
          >
            <Info className="h-4 w-4" />
          </button>
        </div>

        {/* Donut Chart & Legend Row */}
        <div className="mt-5 flex flex-col sm:flex-row items-center justify-center gap-6">
          {/* Donut graphic */}
          <div className="relative flex h-36 w-36 shrink-0 items-center justify-center">
            <svg className="h-full w-full -rotate-90 transform" viewBox="0 0 100 100">
              {/* Background circle track */}
              <circle
                cx="50"
                cy="50"
                r={r}
                fill="transparent"
                stroke="#f1f5f9"
                strokeWidth="11"
              />

              {/* Verified (Green) */}
              <circle
                cx="50"
                cy="50"
                r={r}
                fill="transparent"
                stroke="#10B981"
                strokeWidth="11"
                strokeDasharray={`${len1} ${c - len1}`}
                strokeDashoffset={off1}
                strokeLinecap="round"
                className="transition-all duration-700"
              />

              {/* Remediated (Blue) */}
              <circle
                cx="50"
                cy="50"
                r={r}
                fill="transparent"
                stroke="#2563EB"
                strokeWidth="11"
                strokeDasharray={`${len2} ${c - len2}`}
                strokeDashoffset={off2}
                strokeLinecap="round"
                className="transition-all duration-700"
              />

              {/* Open Discrepancies (Amber) */}
              <circle
                cx="50"
                cy="50"
                r={r}
                fill="transparent"
                stroke="#F59E0B"
                strokeWidth="11"
                strokeDasharray={`${len3} ${c - len3}`}
                strokeDashoffset={off3}
                strokeLinecap="round"
                className="transition-all duration-700"
              />

              {/* Unresolved Question (Rose) */}
              <circle
                cx="50"
                cy="50"
                r={r}
                fill="transparent"
                stroke="#EF4444"
                strokeWidth="11"
                strokeDasharray={`${len4} ${c - len4}`}
                strokeDashoffset={off4}
                strokeLinecap="round"
                className="transition-all duration-700"
              />
            </svg>

            {/* Donut Center text */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-2xl font-extrabold tracking-tight text-slate-900">
                76%
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                Verified
              </span>
            </div>
          </div>

          {/* Legend Items */}
          <div className="space-y-2.5 text-xs w-full sm:w-auto">
            {legendItems.map((item, idx) => (
              <div key={idx} className="flex items-center justify-between sm:justify-start sm:space-x-4">
                <div className="flex items-center space-x-2">
                  <span className={`h-2.5 w-2.5 rounded-full ${item.color}`} />
                  <span className="font-medium text-slate-700 text-[11px]">{item.label}</span>
                </div>
                <span className={`font-bold text-[11px] ${item.text}`}>{item.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-6 flex items-center justify-between pt-3 border-t border-slate-100 text-xs">
        <span className="text-slate-500 text-[11px]">
          Continuous Cycles: <span className="font-semibold text-slate-700">Next run in 11 min</span>
        </span>
        <button
          onClick={onTriggerCheck}
          className="inline-flex items-center space-x-1 font-semibold text-blue-600 hover:text-blue-700 hover:underline cursor-pointer text-[11px]"
        >
          <span>Automated Check</span>
          <ArrowRight className="h-3 w-3" />
        </button>
      </div>
    </div>
  );
}

