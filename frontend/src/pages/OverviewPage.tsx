import React from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  DollarSign,
  Lock,
  Receipt,
  Shield,
  ShieldAlert,
  Zap,
} from 'lucide-react';
import type { OverviewStats } from '../types';
import { RiskBadge, StatusBadge } from '../components/common/StatusBadge';

interface OverviewPageProps {
  stats: OverviewStats | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onSelectTransaction: (id: string) => void;
  onNavigate: (path: string, event?: React.MouseEvent<HTMLAnchorElement>) => void;
}

export const OverviewPage: React.FC<OverviewPageProps> = ({
  stats,
  isLoading,
  error,
  onRetry,
  onSelectTransaction,
  onNavigate,
}) => {
  if (!stats) {
    if (isLoading) {
      return (
        <div className="flex items-center justify-center h-64 text-slate-400">
          <div className="text-center space-y-2">
            <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
            <p className="text-sm font-medium">Loading live telemetry from AgentGuard API...</p>
          </div>
        </div>
      );
    }

    return (
      <div className="bg-white p-8 rounded-xl border border-rose-200 shadow-xs text-center space-y-3">
        <p className="text-sm font-semibold text-rose-700">
          {error || 'Unable to retrieve telemetry from the AgentGuard backend API.'}
        </p>
        <p className="text-xs text-slate-500">
          Verify the backend service is awake and reachable, then retry synchronization.
        </p>
        <button
          onClick={onRetry}
          className="px-4 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors"
        >
          Retry Sync
        </button>
      </div>
    );
  }

  const lowRisk = stats.risk_distribution.low || 0;
  const medRisk = stats.risk_distribution.medium || 0;
  const highRisk = stats.risk_distribution.high || 0;
  const totalRiskCount = Math.max(lowRisk + medRisk + highRisk, 1);

  const lowPct = Math.round((lowRisk / totalRiskCount) * 100);
  const medPct = Math.round((medRisk / totalRiskCount) * 100);
  const highPct = Math.round((highRisk / totalRiskCount) * 100);

  return (
    <div className="space-y-6">
      {/* 6 Key Performance Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {/* 1. Total Transactions */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <span>Evaluated</span>
            <Receipt className="w-4 h-4 text-blue-600" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 font-mono">
              {stats.total_transactions}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Agent purchase requests</div>
          </div>
        </div>

        {/* 2. Approved Transactions */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <span>Approved</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-emerald-600 font-mono">
              {stats.approved_transactions}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Cleared policy firewall</div>
          </div>
        </div>

        {/* 3. Blocked Transactions */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <span>Blocked</span>
            <ShieldAlert className="w-4 h-4 text-rose-600" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-rose-600 font-mono">
              {stats.blocked_transactions}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Attacks & violations stopped</div>
          </div>
        </div>

        {/* 4. Pending Approvals */}
        <a
          href="/approvals"
          onClick={(e) => onNavigate('/approvals', e)}
          className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between hover:border-amber-400 transition-colors group"
        >
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <span>Pending Escrow</span>
            <AlertTriangle className="w-4 h-4 text-amber-500 group-hover:scale-110 transition-transform" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-amber-600 font-mono">
              {stats.pending_approvals}
            </div>
            <div className="text-[11px] text-amber-700/80 mt-0.5 font-medium flex items-center gap-1">
              <span>Requires human check</span>
              <ArrowRight className="w-3 h-3" />
            </div>
          </div>
        </a>

        {/* 5. Total Authorized Escrow */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <span>Authorized Hold</span>
            <Lock className="w-4 h-4 text-blue-500" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-blue-700 font-mono">
              ${stats.total_authorized_amount}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">PayPal delay-capture hold</div>
          </div>
        </div>

        {/* 6. Total Captured Settlement */}
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-500 text-xs font-semibold uppercase tracking-wider">
            <span>Captured Funds</span>
            <DollarSign className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900 font-mono">
              ${stats.total_captured_amount}
            </div>
            <div className="text-[11px] text-slate-500 mt-0.5">Successfully settled</div>
          </div>
        </div>
      </div>

      {/* Middle Grid: Risk Distribution & Pipeline Health */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Risk Distribution Breakdown */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
              Risk Score Distribution
            </h3>
            <span className="text-xs text-slate-400 font-mono">Deterministic Signals</span>
          </div>

          <p className="text-xs text-slate-500">
            Composite 0-100 score weighing budget velocity, merchant allowlist, invoice math, and prompt injection indicators.
          </p>

          {/* Stacked Progress Bar */}
          <div className="w-full h-3 rounded-full overflow-hidden flex bg-slate-100">
            <div
              style={{ width: `${lowPct}%` }}
              className="bg-emerald-500 h-full transition-all duration-500"
              title={`Low Risk: ${lowPct}%`}
            ></div>
            <div
              style={{ width: `${medPct}%` }}
              className="bg-amber-400 h-full transition-all duration-500"
              title={`Medium Risk: ${medPct}%`}
            ></div>
            <div
              style={{ width: `${highPct}%` }}
              className="bg-rose-500 h-full transition-all duration-500"
              title={`High Risk: ${highPct}%`}
            ></div>
          </div>

          <div className="grid grid-cols-3 gap-2 pt-2 border-t border-slate-100 text-center">
            <div className="p-2 rounded-lg bg-emerald-50 border border-emerald-100">
              <div className="text-xs font-semibold text-emerald-800">Low (&lt;35)</div>
              <div className="text-lg font-bold text-emerald-600 font-mono">{lowRisk}</div>
              <div className="text-[10px] text-emerald-700">{lowPct}%</div>
            </div>
            <div className="p-2 rounded-lg bg-amber-50 border border-amber-100">
              <div className="text-xs font-semibold text-amber-800">Medium (35-69)</div>
              <div className="text-lg font-bold text-amber-600 font-mono">{medRisk}</div>
              <div className="text-[10px] text-amber-700">{medPct}%</div>
            </div>
            <div className="p-2 rounded-lg bg-rose-50 border border-rose-100">
              <div className="text-xs font-semibold text-rose-800">High (70+)</div>
              <div className="text-lg font-bold text-rose-600 font-mono">{highRisk}</div>
              <div className="text-[10px] text-rose-700">{highPct}%</div>
            </div>
          </div>
        </div>

        {/* Security Pipeline Status */}
        <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-4 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
              Autonomous Defense Architecture
            </h3>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-semibold border border-emerald-300">
              Active Protection
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
                <Shield className="w-4 h-4 text-blue-600" />
                <span>Deterministic Rules</span>
              </div>
              <p className="text-xs text-slate-600">
                Hard spending limits ($100 max, $500 daily cap) and strict merchant allowlist verification evaluated before any API call.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
                <Zap className="w-4 h-4 text-amber-600" />
                <span>AI Prompt Injection Shield</span>
              </div>
              <p className="text-xs text-slate-600">
                Deep deterministic and fail-closed semantic inspection of invoice notes, line items, and payment destinations.
              </p>
            </div>

            <div className="p-4 rounded-lg bg-slate-50 border border-slate-200 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
                <Lock className="w-4 h-4 text-emerald-600" />
                <span>PayPal Escrow Hold</span>
              </div>
              <p className="text-xs text-slate-600">
                Orders v2 with <code>intent: AUTHORIZE</code>. Funds are never captured automatically; human approval triggers delayed capture.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs text-slate-500">
            <div className="flex items-center gap-4">
              <span>Zero-knowledge agent credential isolation</span>
              <span>•</span>
              <span>SQLite WAL ACID concurrency</span>
            </div>
            <a
              href="/transactions"
              onClick={(e) => onNavigate('/transactions', e)}
              className="text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1"
            >
              <span>Explore All Transactions</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </a>
          </div>
        </div>
      </div>

      {/* Recent Activity Stream */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-5 border-b border-slate-200 flex items-center justify-between">
          <div>
            <h3 className="font-bold text-slate-900 text-sm uppercase tracking-wide">
              Live Firewall &amp; Escrow Activity
            </h3>
            <p className="text-xs text-slate-500">Most recent transactions evaluated by AgentGuard</p>
          </div>
          <a
            href="/transactions"
            onClick={(e) => onNavigate('/transactions', e)}
            className="text-xs font-semibold text-blue-600 hover:text-blue-800 flex items-center gap-1"
          >
            <span>View All</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </a>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 font-semibold uppercase">
                <th className="py-3 px-4">Reference</th>
                <th className="py-3 px-4">Merchant</th>
                <th className="py-3 px-4">Amount</th>
                <th className="py-3 px-4">Firewall Decision</th>
                <th className="py-3 px-4">Escrow Status</th>
                <th className="py-3 px-4">Risk</th>
                <th className="py-3 px-4">Timestamp</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {stats.recent_activity.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-400">
                    No transactions recorded yet. Submit an MCP agent request or populate sample data using &ldquo;Seed Demo Data&rdquo;.
                  </td>
                </tr>
              ) : (
                stats.recent_activity.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => onSelectTransaction(item.id)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="py-3 px-4 font-mono font-medium text-slate-800">
                      {item.external_reference}
                    </td>
                    <td className="py-3 px-4 font-medium text-slate-900">
                      {item.merchant_name}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold text-slate-900">
                      ${item.amount} {item.currency}
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge decision={item.decision} />
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={item.payment_status} />
                    </td>
                    <td className="py-3 px-4">
                      <RiskBadge score={item.risk_score} />
                    </td>
                    <td className="py-3 px-4 text-slate-500 font-mono">
                      {new Date(item.created_at).toLocaleTimeString([], {
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      })}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectTransaction(item.id);
                        }}
                        className="text-blue-600 hover:text-blue-800 font-semibold"
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
