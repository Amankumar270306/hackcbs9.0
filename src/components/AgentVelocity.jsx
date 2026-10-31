import React, { useState } from 'react';
import { 
  FileCheck2, 
  Crosshair, 
  ShieldCheck, 
  Sparkles, 
  Activity, 
  Bot, 
  Info 
} from 'lucide-react';

export default function AgentVelocity({ onSelectAgent }) {
  const [hoveredPoint, setHoveredPoint] = useState(null);

  const days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
  const chartData = [
    { day: 'Mon', primary: 230, secondary: 210 },
    { day: 'Tue', primary: 275, secondary: 250 },
    { day: 'Wed', primary: 215, secondary: 195 },
    { day: 'Thu', primary: 320, secondary: 290 },
    { day: 'Fri', primary: 285, secondary: 260 },
  ];

  const agents = [
    {
      id: 'legal',
      name: 'Legal Analyst',
      status: 'Docs Latency: ~98.4%',
      icon: FileCheck2,
      iconBg: 'bg-blue-50 text-blue-600',
      badge: 'Active',
      badgeColor: 'text-emerald-600',
    },
    {
      id: 'adversarial',
      name: 'Adversarial Tester',
      status: 'Active Probing',
      icon: Crosshair,
      iconBg: 'bg-purple-50 text-purple-600',
      badge: 'Probing',
      badgeColor: 'text-purple-600',
    },
    {
      id: 'defence',
      name: 'Defence Auditor',
      status: 'Baseline verifying',
      icon: ShieldCheck,
      iconBg: 'bg-emerald-50 text-emerald-600',
      badge: 'Verifying',
      badgeColor: 'text-emerald-600',
    },
    {
      id: 'adjudicator',
      name: 'Adjudicator & Gov...',
      status: 'Consensus achieved',
      icon: Sparkles,
      iconBg: 'bg-cyan-50 text-cyan-600',
      badge: 'Synced',
      badgeColor: 'text-cyan-600',
    },
  ];

  return (
    <div className="flex flex-col justify-between rounded-xl border border-slate-200/90 bg-white p-5 shadow-2xs">
      <div>
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <h2 className="text-sm font-bold text-slate-900">
              Agent Velocity &amp; Cadence
            </h2>
            <span className="h-2 w-2 rounded-full bg-blue-600 animate-pulse"></span>
          </div>
          <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-0.5 text-[10px] font-bold tracking-wider text-blue-700">
            REAL-TIME
          </span>
        </div>

        <p className="text-[11px] text-slate-500 mt-0.5">
          Execution throughput across 5 autonomous LLM auditors
        </p>

        {/* Chart Subheader */}
        <div className="mt-4 flex items-center justify-between text-xs">
          <span className="text-[11px] font-semibold text-slate-600">
            Agent Inference Cycles (Weekly)
          </span>
          <span className="text-[11px] font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded">
            Avg: 284/day
          </span>
        </div>

        {/* Spline Area Chart */}
        <div className="relative mt-2 h-32 w-full">
          <svg
            className="h-full w-full overflow-visible"
            viewBox="0 0 400 100"
            preserveAspectRatio="none"
          >
            <defs>
              <linearGradient id="blueGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2563EB" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#2563EB" stopOpacity="0.0" />
              </linearGradient>
              <linearGradient id="cyanGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#06B6D4" stopOpacity="0.2" />
                <stop offset="100%" stopColor="#06B6D4" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* Grid horizontal lines */}
            <line x1="0" y1="20" x2="400" y2="20" stroke="#f1f5f9" strokeWidth="1" strokeDasharray="3 3" />
            <line x1="0" y1="50" x2="400" y2="50" stroke="#f1f5f9" strokeWidth="1" strokeDasharray="3 3" />
            <line x1="0" y1="80" x2="400" y2="80" stroke="#f1f5f9" strokeWidth="1" strokeDasharray="3 3" />

            {/* Secondary Cyan Area & Line */}
            <path
              d="M 20 70 C 60 70, 80 50, 110 45 C 150 38, 170 75, 210 70 C 250 65, 270 25, 310 20 C 350 15, 370 40, 390 35 L 390 95 L 20 95 Z"
              fill="url(#cyanGradient)"
            />
            <path
              d="M 20 70 C 60 70, 80 50, 110 45 C 150 38, 170 75, 210 70 C 250 65, 270 25, 310 20 C 350 15, 370 40, 390 35"
              fill="none"
              stroke="#06B6D4"
              strokeWidth="2"
              strokeDasharray="4 2"
            />

            {/* Primary Blue Area & Line */}
            <path
              d="M 20 60 C 60 60, 80 35, 110 30 C 150 25, 170 65, 210 58 C 250 50, 270 18, 310 12 C 350 6, 370 32, 390 25 L 390 95 L 20 95 Z"
              fill="url(#blueGradient)"
            />
            <path
              d="M 20 60 C 60 60, 80 35, 110 30 C 150 25, 170 65, 210 58 C 250 50, 270 18, 310 12 C 350 6, 370 32, 390 25"
              fill="none"
              stroke="#2563EB"
              strokeWidth="2.5"
            />

            {/* Active Data Points on Primary Line */}
            {[
              { cx: 20, cy: 60, val: '230' },
              { cx: 110, cy: 30, val: '275' },
              { cx: 210, cy: 58, val: '215' },
              { cx: 310, cy: 12, val: '320' },
              { cx: 390, cy: 25, val: '285' },
            ].map((p, i) => (
              <circle
                key={i}
                cx={p.cx}
                cy={p.cy}
                r={hoveredPoint === i ? "5" : "3.5"}
                fill="#ffffff"
                stroke="#2563EB"
                strokeWidth="2"
                className="cursor-pointer transition-all"
                onMouseEnter={() => setHoveredPoint(i)}
                onMouseLeave={() => setHoveredPoint(null)}
              />
            ))}
          </svg>

          {/* X Axis Labels */}
          <div className="mt-1 flex justify-between px-3 text-[10px] font-semibold text-slate-400">
            {days.map((d) => (
              <span key={d}>{d}</span>
            ))}
          </div>
        </div>

        {/* 2x2 Agent Status Sub-Cards */}
        <div className="mt-4 grid grid-cols-2 gap-2.5">
          {agents.map((agent) => {
            const Icon = agent.icon;
            return (
              <div
                key={agent.id}
                onClick={() => onSelectAgent?.(agent)}
                className="flex items-center space-x-2.5 rounded-lg border border-slate-200/80 bg-slate-50/50 p-2.5 hover:bg-white hover:shadow-2xs transition-all cursor-pointer"
              >
                <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${agent.iconBg}`}>
                  <Icon className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="truncate text-xs font-bold text-slate-800">
                    {agent.name}
                  </div>
                  <div className="truncate text-[10px] font-medium text-slate-500">
                    {agent.status}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

