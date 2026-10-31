import React from 'react';
import { useAuth } from '../context/AuthContext';
import {
  LayoutDashboard,
  PlusCircle,
  PlayCircle,
  AlertTriangle,
  Bot,
  FileText,
  FolderLock,
  Settings,
  ChevronDown,
  ExternalLink,
  ShieldAlert,
  Sparkles,
  BookOpen,
} from 'lucide-react';

export default function Sidebar({ activeNav, setActiveNav, onOpenNewAudit }) {
  const { activeOrg } = useAuth();
  const navItems = [
    { id: 'overview', label: 'Assessment & Reports', icon: LayoutDashboard },
    { id: 'regulatory', label: 'Regulatory KB', icon: BookOpen },
    { id: 'new-audit', label: 'New Audit', icon: PlusCircle, action: onOpenNewAudit },
  ];

  return (
    <aside className="w-60 shrink-0 border-r border-slate-200 bg-white flex flex-col justify-between min-h-[calc(100vh-4rem)] p-3">
      {/* Top Workspace & Menu */}
      <div className="space-y-4">
        {/* Workspace Card */}
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/70 p-2.5">
          <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Workspace
          </div>
          <div className="mt-1 flex items-center justify-between text-xs font-semibold text-slate-800">
            <span className="truncate">{activeOrg?.organization_name || 'Acme Financial Global • Production'}</span>
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-slate-400" />
          </div>
        </div>

        {/* Navigation list */}
        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeNav === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  if (item.action) {
                    item.action();
                  } else {
                    setActiveNav(item.id);
                  }
                }}
                className={`group flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-blue-50 text-blue-700 font-semibold shadow-2xs'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                }`}
              >
                <div className="flex items-center space-x-2.5">
                  <Icon
                    className={`h-4 w-4 transition-colors ${
                      isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-600'
                    }`}
                  />
                  <span>{item.label}</span>
                </div>

                {item.badge && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-[10px] font-medium tracking-wide ${item.badgeColor}`}
                  >
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom Section: Connected System Status */}
      <div className="space-y-3 pt-4 border-t border-slate-100">
        <div className="rounded-xl border border-slate-200/80 bg-slate-50/90 p-3">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              System Engine
            </span>
            <span className="flex items-center space-x-1 text-xs font-semibold text-emerald-600">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Online</span>
            </span>
          </div>

          <div className="mt-2 text-[11px] text-slate-600 space-y-0.5 font-mono">
            <div>DB: YugabyteDB (YSQL)</div>
            <div>AI: Gemini 3.5 Flash</div>
          </div>
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between px-1 text-[10px] text-slate-400 font-medium">
          <span>Compliance Sentinel</span>
          <span>v4.0 Enterprise</span>
        </div>
      </div>
    </aside>
  );
}

