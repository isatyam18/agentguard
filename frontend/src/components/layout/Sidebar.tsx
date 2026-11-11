import React from 'react';
import {
  BarChart3,
  CheckCircle2,
  Lock,
  Receipt,
  Shield,
  ShieldCheck,
  Sliders,
  Wallet,
} from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  pendingCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  setActiveTab,
  pendingCount,
}) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: BarChart3 },
    { id: 'transactions', label: 'Transaction Explorer', icon: Receipt },
    {
      id: 'approvals',
      label: 'Approval Center',
      icon: ShieldCheck,
      badge: pendingCount > 0 ? pendingCount : null,
    },
    { id: 'policies', label: 'Policy Management', icon: Sliders },
    { id: 'analytics', label: 'Security Analytics', icon: Shield },
  ];

  return (
    <aside className="w-64 bg-navy-900 border-r border-navy-800 flex flex-col justify-between shrink-0 select-none text-slate-300">
      <div>
        {/* Brand Header */}
        <div className="h-16 px-6 flex items-center gap-3 border-b border-navy-800 bg-navy-950/40">
          <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <div className="text-white font-bold text-base tracking-wide flex items-center gap-1.5">
              AgentGuard
              <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                PRO
              </span>
            </div>
            <div className="text-[11px] text-slate-400 tracking-tight">
              Policy Firewall & Escrow
            </div>
          </div>
        </div>

        {/* Navigation Section */}
        <div className="px-3 py-6">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-slate-500 px-3 mb-2">
            Control Console
          </div>
          <nav className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-navy-800/60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge !== null && (
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                        isActive
                          ? 'bg-white text-blue-700'
                          : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Integration & Security Status Box */}
      <div className="p-4 border-t border-navy-800 bg-navy-950/60 m-3 rounded-xl space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
          <div className="flex items-center gap-1.5">
            <Wallet className="w-3.5 h-3.5 text-blue-400" />
            <span>PayPal Sandbox</span>
          </div>
          <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            AUTHORIZE
          </span>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
          <div className="flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5 text-indigo-400" />
            <span>MCP Firewall</span>
          </div>
          <span className="text-[11px] text-blue-400 font-semibold flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-blue-400" />
            Enforcing
          </span>
        </div>

        <div className="pt-2 border-t border-navy-800/80 text-[10px] text-slate-500 flex justify-between items-center">
          <span>Solo PayPal Hackathon</span>
          <span className="font-mono">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
};
