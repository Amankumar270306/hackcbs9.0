import React, { useState } from 'react';
import { 
  X, 
  Terminal, 
  Radio, 
  Cpu, 
  CheckCircle, 
  Activity, 
  Zap, 
  RefreshCw,
  Sparkles,
  Bot
} from 'lucide-react';

export default function AgentDebuggerModal({ isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState('agents');

  if (!isOpen) return null;

  const agentStates = [
    {
      name: 'Legal & Regulatory Analyst',
      model: 'Gemini 1.5 Pro (Custom Fine-tuned)',
      status: 'Online • Standby',
      latency: '112ms',
      tokensSec: '1,420 t/s',
      accuracy: '99.4%',
      activeCheck: 'Cross-verifying 45 CFR 164.312(a)(2)(iv) against HIPAA cluster state.',
    },
    {
      name: 'Adversarial Prober',
      model: 'Claude 3.5 Sonnet / Red Team Fine-tune',
      status: 'Active Probing',
      latency: '240ms',
      tokensSec: '980 t/s',
      accuracy: '98.1%',
      activeCheck: 'Simulating OWASP API Top 10 against Payment Gateway VPC microservices.',
    },
    {
      name: 'Defence & Policy Verifier',
      model: 'GPT-4o (Reasoning Mode)',
      status: 'Verifying Baseline',
      latency: '180ms',
      tokensSec: '1,150 t/s',
      accuracy: '99.8%',
      activeCheck: 'Checking Terraform state drift vs AWS IAM least-privilege boundary.',
    },
    {
      name: 'Adjudicator & Arbiter AI',
      model: 'Ensemble Consensus Arbiter v4.2',
      status: 'Consensus Achieved',
      latency: '85ms',
      tokensSec: '2,100 t/s',
      accuracy: '99.9%',
      activeCheck: 'Synthesized consensus vector on AUD-2024-8841. Generated confidence rating 0.984.',
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs p-4">
      <div className="w-full max-w-2xl max-h-[90vh] overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl flex flex-col animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 bg-slate-50/70">
          <div className="flex items-center space-x-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white shadow-2xs">
              <Cpu className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-sm font-bold text-slate-900">Agent Debugger &amp; Telemetry Console</h3>
                <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-bold text-emerald-800">
                  Engine v4.0 Active
                </span>
              </div>
              <p className="text-[11px] text-slate-500">Live multi-agent orchestration workers and token telemetry</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-700 transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-6 overflow-y-auto space-y-4 text-xs">
          {/* Metrics header */}
          <div className="grid grid-cols-4 gap-2.5">
            <div className="rounded-lg border border-slate-200 p-2.5 bg-slate-50 text-center">
              <div className="text-[10px] text-slate-500 font-bold uppercase">Active Nodes</div>
              <div className="text-base font-extrabold text-blue-600">5 / 5</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-2.5 bg-slate-50 text-center">
              <div className="text-[10px] text-slate-500 font-bold uppercase">Avg Latency</div>
              <div className="text-base font-extrabold text-slate-800">142ms</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-2.5 bg-slate-50 text-center">
              <div className="text-[10px] text-slate-500 font-bold uppercase">Throughput</div>
              <div className="text-base font-extrabold text-emerald-600">5.6k t/s</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-2.5 bg-slate-50 text-center">
              <div className="text-[10px] text-slate-500 font-bold uppercase">Drift Loss</div>
              <div className="text-base font-extrabold text-slate-800">0.00%</div>
            </div>
          </div>

          {/* Agents List */}
          <div className="space-y-3">
            <div className="text-xs font-bold text-slate-900">Registered Auditor Agents</div>
            {agentStates.map((agent, i) => (
              <div key={i} className="rounded-xl border border-slate-200 p-3.5 bg-white hover:border-blue-300 transition-colors">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Bot className="h-4 w-4 text-blue-600" />
                    <span className="font-bold text-slate-800">{agent.name}</span>
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                      {agent.model}
                    </span>
                  </div>
                  <span className="rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.5 text-[10px] font-bold text-emerald-700">
                    {agent.status}
                  </span>
                </div>

                <div className="mt-2 text-[11px] text-slate-600 bg-slate-50 p-2 rounded border border-slate-100 font-mono">
                  {agent.activeCheck}
                </div>

                <div className="mt-2.5 flex items-center justify-between text-[11px] text-slate-400">
                  <span>Latency: <strong className="text-slate-700 font-mono">{agent.latency}</strong></span>
                  <span>Throughput: <strong className="text-slate-700 font-mono">{agent.tokensSec}</strong></span>
                  <span>Confidence: <strong className="text-emerald-600 font-mono">{agent.accuracy}</strong></span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between border-t border-slate-100 px-6 py-3 bg-slate-50">
          <span className="text-[11px] text-slate-500">Live WebSockets connected to ws://cluster-us-east1.audit.internal</span>
          <button
            onClick={onClose}
            className="rounded-lg bg-slate-200 px-4 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-300 transition-colors cursor-pointer"
          >
            Close Console
          </button>
        </div>
      </div>
    </div>
  );
}

