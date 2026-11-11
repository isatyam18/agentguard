import React, { useState } from 'react';
import {
  Database,
  KeyRound,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { getAdminToken, setAdminToken } from '../../services/api';

interface HeaderProps {
  title: string;
  subtitle: string;
  onRefresh: () => void;
  onSeedData: () => Promise<void>;
  isLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  title,
  subtitle,
  onRefresh,
  onSeedData,
  isLoading,
}) => {
  const [showTokenModal, setShowTokenModal] = useState(false);
  const [tokenInput, setTokenInput] = useState(getAdminToken());
  const [seeding, setSeeding] = useState(false);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await onSeedData();
    } finally {
      setSeeding(false);
    }
  };

  const handleSaveToken = () => {
    setAdminToken(tokenInput.trim());
    setShowTokenModal(false);
  };

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between shrink-0 shadow-xs">
      <div>
        <h1 className="text-xl font-bold text-slate-900 tracking-tight">{title}</h1>
        <p className="text-xs text-slate-500 font-medium">{subtitle}</p>
      </div>

      <div className="flex items-center gap-3">
        {/* Environment Status Pill */}
        <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-200 text-xs font-medium text-slate-600">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
          <span>PayPal Sandbox (Delay-Capture Mode)</span>
        </div>

        {/* Admin Token Modal Trigger */}
        <button
          onClick={() => setShowTokenModal(true)}
          title="Configure Admin Authorization Key"
          className="p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg border border-slate-200 transition-colors"
        >
          <KeyRound className="w-4 h-4" />
        </button>

        {/* Refresh Button */}
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-3 py-1.5 text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin text-blue-600' : ''}`} />
          <span>Sync</span>
        </button>

        {/* Seed Demo Data Button */}
        <button
          onClick={handleSeed}
          disabled={seeding || isLoading}
          className="flex items-center gap-2 px-3.5 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm transition-colors disabled:opacity-50"
        >
          <Sparkles className={`w-3.5 h-3.5 ${seeding ? 'animate-spin' : ''}`} />
          <span>{seeding ? 'Populating...' : 'Seed Demo Data'}</span>
        </button>
      </div>

      {/* Admin Key Modal */}
      {showTokenModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-md p-6 space-y-4">
            <div className="flex items-center gap-3 text-slate-900">
              <div className="p-2 rounded-lg bg-blue-50 text-blue-600">
                <Database className="w-5 h-5" />
              </div>
              <div>
                <h3 className="font-bold text-base">Human Operator Key</h3>
                <p className="text-xs text-slate-500">
                  Required to authorize escrow capture or void operations.
                </p>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-700">
                X-Admin-Token Secret
              </label>
              <input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="Enter AGENTGUARD_ADMIN_KEY..."
                className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-blue-500 font-mono"
              />
              <p className="text-[11px] text-slate-400">
                Default sandbox test key: <code className="text-slate-600">admin-secret-key-2026</code>
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowTokenModal(false)}
                className="px-3.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveToken}
                className="px-4 py-1.5 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg shadow-sm"
              >
                Save Credential
              </button>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};
