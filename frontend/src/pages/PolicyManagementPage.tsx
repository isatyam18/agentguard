import React, { useEffect, useState } from 'react';
import {
  Check,
  CheckCircle2,
  Plus,
  Sliders,
  X,
} from 'lucide-react';
import { api } from '../services/api';
import type { Policy } from '../types';

export const PolicyManagementPage: React.FC = () => {
  const [activePolicy, setActivePolicy] = useState<Policy | null>(null);
  const [maxAmount, setMaxAmount] = useState('100.00');
  const [dailyLimit, setDailyLimit] = useState('500.00');
  const [requireHumanApproval, setRequireHumanApproval] = useState(false);
  const [merchants, setMerchants] = useState<string[]>([]);
  const [newMerchantInput, setNewMerchantInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const applyPolicyData = (data: Policy[]) => {
    const active = data.find((p) => p.is_active) || data[0];
    if (active) {
      setActivePolicy(active);
      setMaxAmount(active.max_transaction_amount);
      setDailyLimit(active.daily_spending_limit);
      setRequireHumanApproval(active.require_human_approval);
      setMerchants(active.allowed_merchants || []);
    }
  };

  const loadPolicies = async () => {
    try {
      const data = await api.getPolicies();
      applyPolicyData(data);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch policies.');
    }
  };

  useEffect(() => {
    let active = true;
    api
      .getPolicies()
      .then((data) => {
        if (active) applyPolicyData(data);
      })
      .catch((err: any) => {
        if (active) setErrorMsg(err.message || 'Failed to fetch policies.');
      });
    return () => {
      active = false;
    };
  }, []);

  const handleAddMerchant = () => {
    const val = newMerchantInput.trim().toLowerCase();
    if (!val || merchants.includes(val)) return;
    setMerchants([...merchants, val]);
    setNewMerchantInput('');
  };

  const handleRemoveMerchant = (merchantToRemove: string) => {
    setMerchants(merchants.filter((m) => m !== merchantToRemove));
  };

  const handleSavePolicy = async () => {
    setSaving(true);
    setSuccessMsg(null);
    setErrorMsg(null);

    try {
      const payload = {
        max_transaction_amount: maxAmount,
        daily_spending_limit: dailyLimit,
        require_human_approval: requireHumanApproval,
        allowed_merchants: merchants,
        is_active: true,
      };

      if (activePolicy) {
        await api.updatePolicy(activePolicy.id, payload);
      } else {
        await api.createPolicy(payload);
      }

      setSuccessMsg('Firewall spending policy successfully saved and actively enforced!');
      await loadPolicies();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update policy.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Banner */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
            <Sliders className="w-5 h-5 text-blue-600" />
            Spending Authority & Firewall Policy Rules
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Buyer-defined deterministic thresholds evaluated by AgentGuard before any PayPal API authorization call.
          </p>
        </div>

        <span className="px-3 py-1 text-xs font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          Policy Active
        </span>
      </div>

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-xs font-semibold text-emerald-800 flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>{successMsg}</span>
        </div>
      )}

      {errorMsg && (
        <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-xs font-semibold text-rose-800">
          {errorMsg}
        </div>
      )}

      {/* Main Policy Form Card */}
      <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-xs space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Rule 1: Max Transaction */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-800 uppercase tracking-wide">
              Rule 1: Maximum Single Transaction Amount ($)
            </label>
            <p className="text-[11px] text-slate-500">
              Purchases exceeding this single amount are strictly blocked before reaching PayPal.
            </p>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 font-mono text-slate-400 text-sm">
                $
              </span>
              <input
                type="number"
                step="0.01"
                value={maxAmount}
                onChange={(e) => setMaxAmount(e.target.value)}
                className="w-full pl-8 pr-4 py-2 text-sm font-mono font-bold text-slate-900 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          {/* Rule 2: Daily Budget */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-800 uppercase tracking-wide">
              Rule 2: Daily Cumulative Spending Limit ($)
            </label>
            <p className="text-[11px] text-slate-500">
              Cumulative rolling 24-hour limit across all agent actions.
            </p>
            <div className="relative">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 font-mono text-slate-400 text-sm">
                $
              </span>
              <input
                type="number"
                step="0.01"
                value={dailyLimit}
                onChange={(e) => setDailyLimit(e.target.value)}
                className="w-full pl-8 pr-4 py-2 text-sm font-mono font-bold text-slate-900 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>
        </div>

        {/* Rule 3: Allowed Merchants List */}
        <div className="space-y-3 pt-4 border-t border-slate-100">
          <label className="text-xs font-bold text-slate-800 uppercase tracking-wide">
            Rule 3: Trusted Merchant Allowlist
          </label>
          <p className="text-[11px] text-slate-500">
            Agents may only execute purchases with registered merchant identifiers. Unlisted merchants trigger mandatory review or block.
          </p>

          {/* Add input */}
          <div className="flex gap-2">
            <input
              type="text"
              value={newMerchantInput}
              onChange={(e) => setNewMerchantInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddMerchant())}
              placeholder="e.g. anthropic, stripe, google_cloud..."
              className="flex-1 px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono"
            />
            <button
              onClick={handleAddMerchant}
              type="button"
              className="px-4 py-2 text-xs font-semibold text-white bg-slate-800 hover:bg-slate-900 rounded-lg flex items-center gap-1.5 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Add Merchant</span>
            </button>
          </div>

          {/* Tags */}
          <div className="flex flex-wrap gap-2 pt-2">
            {merchants.map((m) => (
              <span
                key={m}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-mono font-medium bg-slate-100 text-slate-800 border border-slate-200"
              >
                <span>{m}</span>
                <button
                  onClick={() => handleRemoveMerchant(m)}
                  className="text-slate-400 hover:text-rose-600 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
          </div>
        </div>

        {/* Global Human Approval Toggle */}
        <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
          <div>
            <div className="text-xs font-bold text-slate-800 uppercase tracking-wide">
              Mandatory Human Escrow for All Transactions
            </div>
            <div className="text-[11px] text-slate-500">
              When enabled, every transaction enters the human approval queue before capture, regardless of amount.
            </div>
          </div>

          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              checked={requireHumanApproval}
              onChange={(e) => setRequireHumanApproval(e.target.checked)}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-slate-200 peer-focus:outline-hidden rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
          </label>
        </div>

        {/* Save Action */}
        <div className="pt-4 border-t border-slate-100 flex justify-end">
          <button
            onClick={handleSavePolicy}
            disabled={saving}
            className="px-6 py-2.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors flex items-center gap-2 disabled:opacity-50"
          >
            <Check className="w-4 h-4" />
            <span>{saving ? 'Enforcing...' : 'Enforce & Save Policy'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
