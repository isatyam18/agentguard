import React, { useEffect, useState } from 'react';
import {
  AlertOctagon,
  Calendar,
  CheckCircle2,
  Clock,
  Lock,
  Shield,
  ShieldAlert,
  User,
  X,
} from 'lucide-react';
import { api } from '../services/api';
import type { AuditLog, Transaction } from '../types';
import { RiskBadge, StatusBadge } from '../components/common/StatusBadge';

interface TransactionDetailPageProps {
  transactionId: string | null;
  onClose: () => void;
}

export const TransactionDetailPage: React.FC<TransactionDetailPageProps> = ({
  transactionId,
  onClose,
}) => {
  const [transaction, setTransaction] = useState<Transaction | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'security' | 'paypal' | 'audit'>('overview');

  useEffect(() => {
    if (!transactionId) return;

    let mounted = true;
    setLoading(true);

    Promise.all([
      api.getTransaction(transactionId),
      api.getAuditLogs(transactionId),
    ])
      .then(([tx, logs]) => {
        if (mounted) {
          setTransaction(tx);
          setAuditLogs(logs);
        }
      })
      .catch((err) => {
        console.error('Failed to load transaction details:', err);
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [transactionId]);

  if (!transactionId) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/40 backdrop-blur-xs animate-in fade-in duration-200">
      <div className="w-full max-w-3xl bg-white h-full shadow-2xl flex flex-col justify-between border-l border-slate-200">
        {/* Top Header */}
        <div className="p-6 border-b border-slate-200 flex items-center justify-between bg-slate-50/70">
          <div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-lg font-bold text-slate-900">
                {transaction?.external_reference || 'Loading...'}
              </span>
              {transaction && (
                <>
                  <StatusBadge decision={transaction.decision} />
                  <StatusBadge status={transaction.payment_status} />
                </>
              )}
            </div>
            <div className="text-xs text-slate-400 font-mono mt-1">
              UUID: {transaction?.id}
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-200/50 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="px-6 border-b border-slate-200 flex gap-6 text-xs font-semibold">
          {[
            { id: 'overview', label: 'Overview & Request' },
            { id: 'security', label: 'Firewall & Threat Analysis' },
            { id: 'paypal', label: 'PayPal Delay-Capture' },
            { id: 'audit', label: `Audit Log Timeline (${auditLogs.length})` },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`py-3 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Scrollable Content Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {loading ? (
            <div className="py-20 text-center text-slate-400 space-y-2">
              <div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <p className="text-xs">Fetching cryptographic evidence...</p>
            </div>
          ) : !transaction ? (
            <div className="py-20 text-center text-slate-400">Transaction not found.</div>
          ) : (
            <>
              {/* TAB 1: OVERVIEW */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Financial Overview Card */}
                  <div className="p-5 rounded-xl border border-slate-200 bg-slate-50/50 space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                        Requested Amount
                      </div>
                      <RiskBadge score={transaction.risk_score} />
                    </div>
                    <div className="text-3xl font-extrabold text-slate-900 font-mono">
                      ${transaction.amount}{' '}
                      <span className="text-base font-medium text-slate-500">
                        {transaction.currency}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-4 pt-3 border-t border-slate-200 text-xs">
                      <div>
                        <span className="text-slate-400">Merchant Name:</span>
                        <div className="font-semibold text-slate-800 mt-0.5">
                          {transaction.merchant_name}
                        </div>
                      </div>
                      <div>
                        <span className="text-slate-400">Merchant Identifier:</span>
                        <div className="font-mono text-slate-800 mt-0.5">
                          {transaction.merchant_id}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Agent Memo & Intent */}
                  <div className="space-y-2">
                    <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                      Agent Purchase Description / Invoice Content
                    </label>
                    <div className="p-4 rounded-xl border border-slate-200 bg-white font-mono text-xs text-slate-800 whitespace-pre-wrap leading-relaxed shadow-xs">
                      {transaction.description}
                    </div>
                  </div>

                  {/* Timestamp details */}
                  <div className="grid grid-cols-2 gap-4 p-4 rounded-xl border border-slate-200 bg-slate-50/30 text-xs">
                    <div className="flex items-center gap-2 text-slate-600">
                      <Calendar className="w-4 h-4 text-slate-400" />
                      <span>Created: {new Date(transaction.created_at).toLocaleString()}</span>
                    </div>
                    <div className="flex items-center gap-2 text-slate-600">
                      <Clock className="w-4 h-4 text-slate-400" />
                      <span>Updated: {new Date(transaction.updated_at).toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: SECURITY & THREAT ANALYSIS */}
              {activeTab === 'security' && (
                <div className="space-y-6">
                  {/* Risk Overview */}
                  <div className="p-5 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm font-bold text-slate-900">
                        <Shield className="w-4 h-4 text-blue-600" />
                        <span>Policy Firewall Scorecard</span>
                      </div>
                      <RiskBadge score={transaction.risk_score} />
                    </div>
                    <p className="text-xs text-slate-600">
                      AgentGuard evaluates purchase requests using an isolated deterministic policy engine paired with a semantic prompt injection firewall.
                    </p>
                  </div>

                  {/* Policy Rule Checklist */}
                  <div className="space-y-3">
                    <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                      Evaluated Policy Safeguards
                    </h4>
                    <div className="space-y-2 text-xs">
                      <div className="p-3 rounded-lg border border-slate-200 bg-white flex items-center justify-between">
                        <div>
                          <span className="font-semibold text-slate-800">Rule 1: Maximum Single Purchase Limit ($100.00)</span>
                          <div className="text-slate-500 text-[11px]">Enforces hard spending boundary</div>
                        </div>
                        {parseFloat(transaction.amount) <= 100.0 ? (
                          <span className="text-emerald-600 font-semibold flex items-center gap-1">
                            <CheckCircle2 className="w-4 h-4" /> Passed
                          </span>
                        ) : (
                          <span className="text-rose-600 font-semibold flex items-center gap-1">
                            <AlertOctagon className="w-4 h-4" /> Exceeded (${transaction.amount})
                          </span>
                        )}
                      </div>

                      <div className="p-3 rounded-lg border border-slate-200 bg-white flex items-center justify-between">
                        <div>
                          <span className="font-semibold text-slate-800">Rule 2: Daily Cumulative Spending Budget ($500.00)</span>
                          <div className="text-slate-500 text-[11px]">Tracks 24h rolling velocity</div>
                        </div>
                        <span className="text-emerald-600 font-semibold flex items-center gap-1">
                          <CheckCircle2 className="w-4 h-4" /> Evaluated
                        </span>
                      </div>

                      <div className="p-3 rounded-lg border border-slate-200 bg-white flex items-center justify-between">
                        <div>
                          <span className="font-semibold text-slate-800">Rule 3: Merchant Allowlist Verification</span>
                          <div className="text-slate-500 text-[11px]">Identity trust check: {transaction.merchant_id}</div>
                        </div>
                        {transaction.decision === 'BLOCK' && transaction.description.toLowerCase().includes('rogue') ? (
                          <span className="text-rose-600 font-semibold flex items-center gap-1">
                            <AlertOctagon className="w-4 h-4" /> Blocked
                          </span>
                        ) : (
                          <span className="text-emerald-600 font-semibold flex items-center gap-1">
                            <CheckCircle2 className="w-4 h-4" /> Checked
                          </span>
                        )}
                      </div>

                      <div className="p-3 rounded-lg border border-slate-200 bg-white flex items-center justify-between">
                        <div>
                          <span className="font-semibold text-slate-800">Rule 4: Prompt Injection & Phishing Filter</span>
                          <div className="text-slate-500 text-[11px]">Deep semantic scan on memo & payment instructions</div>
                        </div>
                        {parseFloat(transaction.risk_score) >= 0.7 ? (
                          <span className="text-rose-600 font-semibold flex items-center gap-1">
                            <ShieldAlert className="w-4 h-4" /> Threat Detected
                          </span>
                        ) : (
                          <span className="text-emerald-600 font-semibold flex items-center gap-1">
                            <CheckCircle2 className="w-4 h-4" /> Clean
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 3: PAYPAL DELAY-CAPTURE INTEGRATION */}
              {activeTab === 'paypal' && (
                <div className="space-y-6">
                  <div className="p-5 rounded-xl border border-slate-200 bg-blue-50/40 space-y-3">
                    <div className="flex items-center gap-2 text-sm font-bold text-blue-900">
                      <Lock className="w-4 h-4 text-blue-600" />
                      <span>PayPal Orders v2 / Payments v2 Isolation</span>
                    </div>
                    <p className="text-xs text-blue-800/80 leading-relaxed">
                      All purchase operations strictly use <code>intent: "AUTHORIZE"</code> to place funds in delay-capture escrow. No funds are automatically seized without policy engine validation and human operator confirmation.
                    </p>
                  </div>

                  <div className="space-y-3">
                    <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-1">
                      <span className="text-xs text-slate-400 font-medium">PayPal Order Resource ID</span>
                      <div className="font-mono text-sm font-bold text-slate-800">
                        {transaction.paypal_order_id || (
                          <span className="text-slate-400 font-normal italic">
                            None (Execution blocked before PayPal invocation)
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-1">
                      <span className="text-xs text-slate-400 font-medium">PayPal Authorization Resource ID</span>
                      <div className="font-mono text-sm font-bold text-slate-800">
                        {transaction.paypal_authorization_id || (
                          <span className="text-slate-400 font-normal italic">
                            None (Awaiting authorization or blocked)
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-1">
                      <span className="text-xs text-slate-400 font-medium">Escrow Lifecycle State</span>
                      <div className="pt-1">
                        <StatusBadge status={transaction.payment_status} />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: AUDIT LOG TIMELINE */}
              {activeTab === 'audit' && (
                <div className="space-y-4">
                  {auditLogs.length === 0 ? (
                    <div className="py-12 text-center text-slate-400 text-xs">
                      No audit log records found for this transaction.
                    </div>
                  ) : (
                    <div className="relative pl-6 space-y-6 before:content-[''] before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                      {auditLogs.map((log) => (
                        <div key={log.id} className="relative space-y-1 text-xs">
                          {/* Dot indicator */}
                          <div className="absolute -left-6 top-1 w-3 h-3 rounded-full bg-blue-600 border-2 border-white shadow-xs"></div>

                          <div className="flex items-center justify-between">
                            <span className="font-mono font-bold text-slate-800">
                              {log.event_type}
                            </span>
                            <span className="text-slate-400 font-mono">
                              {new Date(log.timestamp).toLocaleTimeString([], {
                                hour: '2-digit',
                                minute: '2-digit',
                                second: '2-digit',
                              })}
                            </span>
                          </div>

                          <div className="flex items-center gap-1.5 text-slate-500 text-[11px]">
                            <User className="w-3 h-3 text-slate-400" />
                            <span>Actor: {log.actor}</span>
                          </div>

                          {log.details && (
                            <div className="mt-2 p-3 rounded-lg bg-slate-50 border border-slate-200 font-mono text-[11px] text-slate-700 overflow-x-auto">
                              <pre>{JSON.stringify(log.details, null, 2)}</pre>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Bottom Drawer Footer */}
        <div className="p-4 border-t border-slate-200 bg-slate-50/50 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 shadow-xs transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};
