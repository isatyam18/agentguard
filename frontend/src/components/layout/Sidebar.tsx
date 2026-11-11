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
import { ROUTES, type RouteId } from '../../routes';

interface SidebarProps {
  activeRouteId: RouteId;
  onNavigate: (path: string, event?: React.MouseEvent<HTMLAnchorElement>) => void;
  pendingCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeRouteId,
  onNavigate,
  pendingCount,
}) => {
  const navItems = [
    { ...ROUTES.overview, icon: BarChart3, badge: null as number | null },
    { ...ROUTES.transactions, icon: Receipt, badge: null as number | null },
    {
      ...ROUTES.approvals,
      icon: ShieldCheck,
      badge: pendingCount > 0 ? pendingCount : null,
    },
    { ...ROUTES.policies, icon: Sliders, badge: null as number | null },
    { ...ROUTES.analytics, icon: Shield, badge: null as number | null },
  ];

  return (
    <aside className="w-64 bg-navy-900 border-r border-navy-800 flex flex-col justify-between shrink-0 select-none text-slate-300">
      <div>
        {/* Brand Header */}
        <a
          href="/"
          onClick={(e) => onNavigate('/', e)}
          className="h-16 px-6 flex items-center gap-3 border-b border-navy-800 bg-navy-950/40 hover:bg-navy-950/70 transition-colors"
        >
          <img
            src="/favicon.svg"
            alt="AgentGuard Policy Firewall and Escrow logo"
            width={36}
            height={36}
            className="w-9 h-9 rounded-lg shadow-lg shadow-blue-500/20 shrink-0"
          />
          <div>
            <div className="text-white font-bold text-base tracking-wide flex items-center gap-1.5">
              AgentGuard
              <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                PRO
              </span>
            </div>
            <div className="text-[11px] text-slate-400 tracking-tight">
              Policy Firewall &amp; Escrow
            </div>
          </div>
        </a>

        {/* Navigation Section */}
        <div className="px-3 py-6">
          <div className="text-[11px] uppercase tracking-wider font-semibold text-slate-500 px-3 mb-2">
            Control Console
          </div>
          <nav aria-label="Primary Navigation" className="space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeRouteId === item.id;
              return (
                <a
                  key={item.id}
                  href={item.path}
                  onClick={(e) => onNavigate(item.path, e)}
                  aria-current={isActive ? 'page' : undefined}
                  className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-navy-800/60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon
                      className={`w-4 h-4 ${isActive ? 'text-white' : 'text-slate-400'}`}
                      aria-hidden="true"
                    />
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
                </a>
              );
            })}
          </nav>
        </div>
      </div>

      {/* Integration & Security Status Box */}
      <div className="p-4 border-t border-navy-800 bg-navy-950/60 m-3 rounded-xl space-y-3">
        <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
          <div className="flex items-center gap-1.5">
            <Wallet className="w-3.5 h-3.5 text-blue-400" aria-hidden="true" />
            <span>PayPal Escrow</span>
          </div>
          <span className="flex items-center gap-1 text-[11px] text-emerald-400 font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            AUTHORIZE
          </span>
        </div>

        <div className="flex items-center justify-between text-xs text-slate-400 font-medium">
          <div className="flex items-center gap-1.5">
            <Lock className="w-3.5 h-3.5 text-indigo-400" aria-hidden="true" />
            <span>MCP Firewall</span>
          </div>
          <span className="text-[11px] text-blue-400 font-semibold flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3 text-blue-400" aria-hidden="true" />
            Enforcing
          </span>
        </div>

        <div className="pt-2 border-t border-navy-800/80 text-[10px] text-slate-500 flex justify-between items-center">
          <span>AgentGuard Console</span>
          <span className="font-mono">v1.0.0</span>
        </div>
      </div>
    </aside>
  );
};
