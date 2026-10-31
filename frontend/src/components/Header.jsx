import React, { useState } from 'react';
import { 
  ShieldCheck, 
  Search, 
  Bell, 
  Plus, 
  ChevronDown, 
  Cpu, 
  Check, 
  Radio, 
  Sparkles,
  Command,
  SlidersHorizontal,
  ExternalLink,
  LogOut,
  Building,
  User as UserIcon
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Header({ onOpenNewAudit, onOpenDebugger }) {
  const { user, activeOrg, organizations, switchOrganization, logout } = useAuth();

  const [workspaceOpen, setWorkspaceOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showNotifications, setShowNotifications] = useState(false);

  const activeWorkspaceName = activeOrg?.organization_name || 'Acme Financial Global • Production';
  const userFullName = user?.full_name || 'Elena Vance';
  const userRole = activeOrg?.role ? `${activeOrg.role.toUpperCase()} • ${activeOrg.organization_name}` : 'CISO • Acme Financial Services';

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur-md sm:px-6">
      {/* Left section: Logo & Workspaces */}
      <div className="flex items-center space-x-3 sm:space-x-5">
        {/* Brand Logo */}
        <div className="flex items-center space-x-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-sm ring-2 ring-emerald-500/20">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center space-x-1.5">
              <span className="font-bold tracking-tight text-slate-900 text-sm sm:text-base">
                Compliance Sentinel
              </span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600 border border-slate-200 uppercase tracking-wide">
                Enterprise v4.0
              </span>
            </div>
          </div>
        </div>

        {/* Divider */}
        <div className="hidden h-5 w-px bg-slate-200 md:block" />

        {/* Workspace Quick Indicator */}
        <div className="relative hidden lg:block">
          <div className="flex items-center space-x-2 text-xs">
            <span className="text-slate-400 font-medium">Workspace:</span>
            <button 
              onClick={() => {
                setWorkspaceOpen(!workspaceOpen);
                setProfileOpen(false);
              }}
              className="flex items-center space-x-1.5 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 font-medium text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <Building className="h-3.5 w-3.5 text-blue-600 mr-0.5" />
              <span className="max-w-[200px] truncate">{activeWorkspaceName}</span>
              <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
            </button>
          </div>

          {workspaceOpen && (
            <div className="absolute left-16 top-full mt-1.5 w-72 rounded-lg border border-slate-200 bg-white p-1.5 shadow-lg z-50">
              <div className="px-2 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Switch Organization Workspace
              </div>
              <div className="max-h-60 overflow-y-auto space-y-0.5 mt-1">
                {organizations.length > 0 ? (
                  organizations.map((org) => {
                    const isSelected = activeOrg?.organization_id === org.organization_id;
                    return (
                      <button
                        key={org.organization_id}
                        onClick={() => {
                          switchOrganization(org.organization_id);
                          setWorkspaceOpen(false);
                        }}
                        className={`flex w-full items-center justify-between rounded-md px-2.5 py-2 text-xs text-left transition-colors cursor-pointer ${
                          isSelected ? 'bg-blue-50 text-blue-700 font-medium' : 'text-slate-700 hover:bg-slate-50'
                        }`}
                      >
                        <div className="flex flex-col truncate pr-2">
                          <span className="font-semibold text-slate-800">{org.organization_name}</span>
                          <span className="text-[10px] text-slate-400 capitalize">Role: {org.role}</span>
                        </div>
                        {isSelected && <Check className="h-4 w-4 text-blue-600 shrink-0" />}
                      </button>
                    );
                  })
                ) : (
                  <div className="p-2 text-xs text-slate-500">No organizations available</div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Center status indicators */}
      <div className="hidden 2xl:flex items-center space-x-3 text-xs bg-slate-50 border border-slate-200/80 rounded-lg px-3 py-1.5">
        <div className="flex items-center space-x-1.5">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-semibold text-slate-700">Multi-Agent Engine:</span>
          <span className="text-emerald-700 font-medium">Healthy</span>
        </div>
        <div className="h-3 w-px bg-slate-200" />
        <div className="flex items-center space-x-1.5 text-slate-600">
          <Cpu className="h-3.5 w-3.5 text-blue-600" />
          <span>5 Agents Active</span>
        </div>
        <div className="h-3 w-px bg-slate-200" />
        <button
          onClick={onOpenDebugger}
          className="text-blue-600 hover:text-blue-700 font-medium flex items-center space-x-1 text-[11px] cursor-pointer"
        >
          <span>Debugger</span>
          <ExternalLink className="h-3 w-3" />
        </button>
      </div>

      {/* Right section: Search, Notifications, Profile */}
      <div className="flex items-center space-x-2 sm:space-x-3">
        {/* Global Search */}
        <div className="relative hidden md:block w-48 sm:w-60 lg:w-72">
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-2.5 text-slate-400">
            <Search className="h-3.5 w-3.5" />
          </div>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search audits, CVEs... /"
            className="w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-7 text-xs text-slate-800 placeholder-slate-400 focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-1 focus:ring-blue-500 transition-all"
          />
          <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
            <kbd className="rounded border border-slate-200 bg-white px-1 text-[10px] font-medium text-slate-400 shadow-2xs">/</kbd>
          </div>
        </div>

        {/* Notifications */}
        <div className="relative">
          <button 
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700 transition-colors cursor-pointer"
            title="Notifications"
          >
            <Bell className="h-4.5 w-4.5" />
            <span className="absolute top-1.5 right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[10px] font-bold text-white ring-2 ring-white">
              2
            </span>
          </button>

          {showNotifications && (
            <div className="absolute right-0 top-full mt-2 w-80 rounded-xl border border-slate-200 bg-white p-3 shadow-xl z-50">
              <div className="flex items-center justify-between pb-2 border-b border-slate-100">
                <span className="text-xs font-bold text-slate-800">Telemetry Alerts</span>
                <span className="rounded bg-rose-50 text-[10px] font-semibold text-rose-600 px-1.5 py-0.5">2 Critical</span>
              </div>
              <div className="mt-2 space-y-2">
                <div className="rounded-lg bg-rose-50/60 p-2 text-xs border border-rose-100">
                  <div className="font-semibold text-rose-800">Critical: S3 Bucket Open</div>
                  <div className="text-[11px] text-slate-600">AUD-2024-8841 flagged unencrypted PII store in US-East.</div>
                  <div className="mt-1 text-[10px] text-slate-400">4 minutes ago</div>
                </div>
                <div className="rounded-lg bg-amber-50/60 p-2 text-xs border border-amber-100">
                  <div className="font-semibold text-amber-800">Drift Detected: HIPAA Policy</div>
                  <div className="text-[11px] text-slate-600">Audit execution running on AWS-US-HIPAA cluster.</div>
                  <div className="mt-1 text-[10px] text-slate-400">18 minutes ago</div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Primary Action Button: + New Audit */}
        <button
          onClick={onOpenNewAudit}
          className="inline-flex items-center space-x-1.5 rounded-lg bg-blue-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-xs hover:bg-blue-700 active:scale-[0.98] transition-all cursor-pointer"
        >
          <Plus className="h-4 w-4" />
          <span>New Audit</span>
        </button>

        {/* User Profile Menu */}
        <div className="relative">
          <button
            onClick={() => {
              setProfileOpen(!profileOpen);
              setWorkspaceOpen(false);
            }}
            className="flex items-center space-x-2.5 border-l border-slate-200 pl-3 sm:pl-3.5 hover:opacity-85 transition-opacity cursor-pointer text-left"
          >
            <div className="relative">
              <div className="h-8 w-8 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-xs ring-2 ring-slate-100">
                {userFullName.charAt(0)}
              </div>
              <span className="absolute bottom-0 right-0 h-2 w-2 rounded-full bg-emerald-500 ring-1.5 ring-white" />
            </div>
            <div className="hidden xl:flex flex-col text-left">
              <div className="flex items-center space-x-1">
                <span className="text-xs font-semibold text-slate-800 max-w-[140px] truncate">
                  {userFullName}
                </span>
                <ChevronDown className="h-3 w-3 text-slate-400" />
              </div>
              <span className="text-[10px] text-slate-400 font-medium max-w-[160px] truncate">
                {userRole}
              </span>
            </div>
          </button>

          {profileOpen && (
            <div className="absolute right-0 top-full mt-2 w-64 rounded-xl border border-slate-200 bg-white p-2 shadow-xl z-50">
              <div className="px-3 py-2.5 border-b border-slate-100">
                <div className="text-xs font-bold text-slate-900">{userFullName}</div>
                <div className="text-[11px] text-slate-500 truncate">{user?.email}</div>
                <div className="mt-1.5 inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 border border-emerald-200">
                  Role: {activeOrg?.role || 'Member'}
                </div>
              </div>

              <div className="py-1">
                <button
                  onClick={() => {
                    setProfileOpen(false);
                    logout();
                  }}
                  className="w-full flex items-center space-x-2 rounded-lg px-3 py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                >
                  <LogOut className="h-4 w-4 text-rose-500" />
                  <span>Sign Out</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
