import React, { useState } from 'react';
import { SlidersHorizontal, Download, Share2, Server, CheckCircle2 } from 'lucide-react';

export default function OverviewHeader({ onExportBriefing }) {
  const [selectedRange, setSelectedRange] = useState('Last 30 Days');
  const ranges = ['Last 30 Days', 'Q3 2024', 'YTD'];

  return (
    <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between pb-2">
      {/* Left: Sensor badge, Title, Subtitle */}
      <div>
        {/* Kubernetes sensor status badge */}
        <div className="inline-flex items-center space-x-2 rounded-full bg-emerald-50/80 border border-emerald-200/60 px-2.5 py-0.5 text-[11px] font-medium text-emerald-800 mb-2">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
          </span>
          <span className="font-bold tracking-wider text-[10px] uppercase text-emerald-900">
            ACTIVE KUBERNETES SENSOR
          </span>
          <span className="text-emerald-300">|</span>
          <span className="text-emerald-700 font-mono text-[10px]">
            Cluster node: us-east1-gke-4
          </span>
        </div>

        {/* Title */}
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          Security Posture & Compliance Overview
        </h1>

        {/* Subtitle */}
        <p className="mt-1 text-xs sm:text-sm text-slate-500 max-w-2xl">
          Continuous multi-agent audit monitoring across 8 regulatory frameworks & 14 automated policy engines
        </p>
      </div>

      {/* Right: Date selector, Filter button, Export briefing */}
      <div className="flex flex-wrap items-center gap-2 sm:gap-2.5">
        {/* Date Segmented Control */}
        <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 shadow-2xs">
          {ranges.map((range) => (
            <button
              key={range}
              onClick={() => setSelectedRange(range)}
              className={`rounded-md px-2.5 py-1.5 text-xs font-semibold transition-all cursor-pointer ${
                selectedRange === range
                  ? 'bg-slate-100 text-slate-900 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-900'
              }`}
            >
              {range}
            </button>
          ))}
        </div>

        {/* Filters button */}
        <button className="inline-flex items-center space-x-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 hover:text-slate-900 transition-colors cursor-pointer">
          <SlidersHorizontal className="h-3.5 w-3.5 text-slate-500" />
          <span>Filters</span>
        </button>

        {/* Export Executive Briefing Button */}
        <button
          onClick={onExportBriefing}
          className="inline-flex items-center space-x-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-2xs hover:bg-blue-700 active:scale-[0.98] transition-all cursor-pointer"
        >
          <Download className="h-3.5 w-3.5" />
          <span>Export Executive Briefing</span>
        </button>
      </div>
    </div>
  );
}

