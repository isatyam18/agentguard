import React, { useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Lock,
  ShieldCheck,
  XCircle,
} from 'lucide-react';
import { api } from '../services/api';
import type { Approval } from '../types';
import { RiskBadge } from '../components/common/StatusBadge';

interface ApprovalCenterPageProps {
  approvals: Approval[];
  onRefresh: () => void;
  onSelectTransaction: (id: string) => void;
  isLoading?: boolean;
}

export const ApprovalCenterPage: React.FC<ApprovalCenterPageProps> = ({
  approvals,
  onRefresh,
  onSelectTransaction,
}) => {
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null);
  const [actionType, setActionType] = useState<'approve' | 'reject' | null>(null);
  const [reviewerName, setReviewerName] = useState('SecOps Officer');
  const [reasonNotes, setReasonNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const pendingApprovals = approvals.filter((a) => a.status === 'PENDING');

  const handleOpenModal = (approval: Approval, type: 'approve' | 'reject') => {
    setSelectedApproval(approval);
    setActionType(type);
    setReasonNotes(
      type === 'approve'
        ? 'Verified merchant invoice integrity; cleared for capture.'
        : 'Disallowed expenditure: outside corporate autonomous agent procurement limits.'
    );
  };

  const handleConfirmAction = async () => {
    if (!selectedApproval || !actionType) return;

    setSubmitting(true);
    setFeedbackMessage(null);

    try {
      if (actionType === 'approve') {
        const res = await api.approveEscrow(selectedApproval.id, reviewerName, reasonNotes);
        setFeedbackMessage({
          type: 'success',
          text: `Transaction approved & captured successfully! PayPal Capture ID: ${res.capture_id || 'CAPTURED'}`,
        });
      } else {
        const res = await api.rejectEscrow(selectedApproval.id, reviewerName, reasonNotes);
        setFeedbackMessage({
          type: 'success',
          text: `Transaction rejected & authorization voided! Status: ${res.status || 'VOIDED'}`,
        });
      }
      setSelectedApproval(null);
      setActionType(null);
      onRefresh();
    } catch (err: any) {
      setFeedbackMessage({
        type: 'error',
        text: err.message || 'Escrow state transition failed.',
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Title & Status Banner */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-blue-600" />
            Human-in-the-Loop Escrow Settlement
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Review ambiguous or flagged AI purchases held in PayPal <code>intent: AUTHORIZE</code> escrow. Autonomous AI buyer agents are strictly prohibited from approving their own transactions.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="px-3.5 py-1.5 rounded-lg bg-amber-50 border border-amber-200 text-xs font-semibold text-amber-800 flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <span>{pendingApprovals.length} Pending Review</span>
          </div>
        </div>
      </div>

      {feedbackMessage && (
        <div
          className={`p-4 rounded-xl border text-xs font-medium flex items-center justify-between animate-in fade-in duration-150 ${
            feedbackMessage.type === 'success'
              ? 'bg-emerald-50 text-emerald-800 border-emerald-200'
              : 'bg-rose-50 text-rose-800 border-rose-200'
          }`}
        >
          <span>{feedbackMessage.text}</span>
          <button
            onClick={() => setFeedbackMessage(null)}
            className="text-slate-400 hover:text-slate-700 font-bold"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Pending Approvals Grid */}
      <div className="space-y-4">
        <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wide">
          Pending Escrow Queue ({pendingApprovals.length})
        </h3>

        {pendingApprovals.length === 0 ? (
          <div className="bg-white p-12 rounded-xl border border-slate-200 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h4 className="font-bold text-slate-800 text-sm">Escrow Queue Clear</h4>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              All transactions have either cleared automatic deterministic policies or have been verified by a security officer.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {pendingApprovals.map((approval) => {
              const tx = approval.transaction;
              return (
                <div
                  key={approval.id}
                  className="bg-white rounded-xl border border-slate-200 shadow-xs p-5 flex flex-col justify-between space-y-4 hover:border-blue-300 transition-colors"
                >
                  <div className="space-y-3">
                    {/* Header */}
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-xs font-bold text-slate-800">
                        {tx?.external_reference || approval.transaction_id}
                      </span>
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                        PENDING HUMAN CHECK
                      </span>
                    </div>

                    {/* Financial details */}
                    <div className="flex items-baseline justify-between">
                      <div>
                        <div className="text-2xl font-black text-slate-900 font-mono">
                          ${tx ? tx.amount : '---'}
                          <span className="text-xs font-medium text-slate-400 ml-1">
                            {tx ? tx.currency : 'USD'}
                          </span>
                        </div>
                        <div className="text-xs font-medium text-slate-700 mt-0.5">
                          {tx ? tx.merchant_name : 'Merchant Unknown'}
                        </div>
                      </div>

                      {tx && <RiskBadge score={tx.risk_score} />}
                    </div>

                    {/* Escrow & Flag Reason */}
                    <div className="p-3 rounded-lg bg-amber-50/60 border border-amber-200/80 text-xs space-y-1">
                      <div className="font-semibold text-amber-900 flex items-center gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5 text-amber-600" />
                        <span>Firewall Flag Reason</span>
                      </div>
                      <p className="text-amber-800/90 leading-relaxed text-[11px]">
                        {approval.reason || 'Escrow hold requested by policy firewall.'}
                      </p>
                    </div>

                    {/* PayPal Auth Info */}
                    <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1">
                      <span className="flex items-center gap-1">
                        <Lock className="w-3 h-3 text-blue-500" />
                        <span>PayPal Hold:</span>
                      </span>
                      <span className="font-mono text-slate-700">
                        {tx?.paypal_authorization_id || 'MOCK-AUTH-PENDING'}
                      </span>
                    </div>
                  </div>

                  {/* Operator Actions */}
                  <div className="pt-3 border-t border-slate-100 flex items-center justify-between gap-3">
                    <button
                      onClick={() => onSelectTransaction(approval.transaction_id)}
                      className="text-xs text-blue-600 hover:text-blue-800 font-semibold"
                    >
                      Inspect Evidence
                    </button>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleOpenModal(approval, 'reject')}
                        className="px-3 py-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 border border-rose-200 rounded-lg transition-colors"
                      >
                        Reject & Void
                      </button>
                      <button
                        onClick={() => handleOpenModal(approval, 'approve')}
                        className="px-3.5 py-1.5 text-xs font-semibold text-white bg-emerald-600 hover:bg-emerald-700 rounded-lg shadow-xs transition-colors"
                      >
                        Approve & Capture
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Confirmation Modal */}
      {selectedApproval && actionType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-150">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-lg p-6 space-y-4">
            <div className="flex items-center gap-3">
              <div
                className={`p-2.5 rounded-xl ${
                  actionType === 'approve'
                    ? 'bg-emerald-50 text-emerald-600'
                    : 'bg-rose-50 text-rose-600'
                }`}
              >
                {actionType === 'approve' ? (
                  <CheckCircle2 className="w-6 h-6" />
                ) : (
                  <XCircle className="w-6 h-6" />
                )}
              </div>
              <div>
                <h3 className="font-bold text-base text-slate-900">
                  {actionType === 'approve'
                    ? 'Confirm Escrow Release & PayPal Capture'
                    : 'Confirm Escrow Rejection & PayPal Void'}
                </h3>
                <p className="text-xs text-slate-500">
                  {actionType === 'approve'
                    ? 'This action will finalize settlement and execute the PayPal capture.'
                    : 'This action will void the PayPal authorization hold and cancel transaction.'}
                </p>
              </div>
            </div>

            <div className="space-y-3 pt-2">
              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Reviewer Identity</label>
                <input
                  type="text"
                  value={reviewerName}
                  onChange={(e) => setReviewerName(e.target.value)}
                  placeholder="e.g. security-officer@agentguard.internal"
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-slate-700">Audit Justification Notes</label>
                <textarea
                  value={reasonNotes}
                  onChange={(e) => setReasonNotes(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                disabled={submitting}
                onClick={() => {
                  setSelectedApproval(null);
                  setActionType(null);
                }}
                className="px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                disabled={submitting}
                onClick={handleConfirmAction}
                className={`px-4 py-2 text-xs font-semibold text-white rounded-lg shadow-sm transition-colors ${
                  actionType === 'approve'
                    ? 'bg-emerald-600 hover:bg-emerald-700'
                    : 'bg-rose-600 hover:bg-rose-700'
                }`}
              >
                {submitting
                  ? 'Executing...'
                  : actionType === 'approve'
                  ? 'Execute PayPal Capture'
                  : 'Execute PayPal Void'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
