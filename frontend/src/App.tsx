import React, { useEffect, useState } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { ApprovalCenterPage } from './pages/ApprovalCenterPage';
import { OverviewPage } from './pages/OverviewPage';
import { PolicyManagementPage } from './pages/PolicyManagementPage';
import { SecurityAnalyticsPage } from './pages/SecurityAnalyticsPage';
import { TransactionDetailPage } from './pages/TransactionDetailPage';
import { TransactionExplorerPage } from './pages/TransactionExplorerPage';
import { api } from './services/api';
import type { Approval, OverviewStats, Transaction } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [overviewStats, setOverviewStats] = useState<OverviewStats | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selectedTransactionId, setSelectedTransactionId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [statsRes, txsRes, approvalsRes] = await Promise.all([
        api.getOverview().catch(() => null),
        api.getTransactions().catch(() => []),
        api.getApprovals().catch(() => []),
      ]);

      if (statsRes) setOverviewStats(statsRes);
      setTransactions(txsRes);
      setApprovals(approvalsRes);
    } catch (err) {
      console.error('Error fetching AgentGuard console telemetry:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleSeedDemoData = async () => {
    try {
      await api.seedDemoData(true);
      await fetchData();
    } catch (err) {
      console.error('Failed to seed demo data:', err);
    }
  };

  const getPageHeaderInfo = () => {
    switch (activeTab) {
      case 'overview':
        return {
          title: 'Firewall & Escrow Overview',
          subtitle: 'Real-time agent payment authorization telemetry and firewall defenses',
        };
      case 'transactions':
        return {
          title: 'Transaction Explorer',
          subtitle: 'Comprehensive audit registry of all autonomous purchase requests',
        };
      case 'approvals':
        return {
          title: 'Human Approval Center',
          subtitle: 'Verification and delay-capture release of escrowed purchase requests',
        };
      case 'policies':
        return {
          title: 'Policy Firewall Configuration',
          subtitle: 'Buyer spending boundaries, velocity thresholds, and merchant allowlists',
        };
      case 'analytics':
        return {
          title: 'Adversarial Threat Intelligence',
          subtitle: 'Prompt injection defense verification and security benchmark metrics',
        };
      default:
        return {
          title: 'AgentGuard Console',
          subtitle: 'Policy Firewall & Escrow for Autonomous AI Payments',
        };
    }
  };

  const headerInfo = getPageHeaderInfo();
  const pendingApprovalsCount = approvals.filter((a) => a.status === 'PENDING').length;

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans antialiased text-slate-900">
      {/* Dark Navy Sidebar */}
      <Sidebar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        pendingCount={pendingApprovalsCount}
      />

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <Header
          title={headerInfo.title}
          subtitle={headerInfo.subtitle}
          onRefresh={fetchData}
          onSeedData={handleSeedDemoData}
          isLoading={loading}
        />

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-7xl mx-auto">
            {activeTab === 'overview' && (
              <OverviewPage
                stats={overviewStats}
                onSelectTransaction={(id) => setSelectedTransactionId(id)}
                onNavigateToApprovals={() => setActiveTab('approvals')}
                onNavigateToTransactions={() => setActiveTab('transactions')}
              />
            )}

            {activeTab === 'transactions' && (
              <TransactionExplorerPage
                transactions={transactions}
                onSelectTransaction={(id) => setSelectedTransactionId(id)}
                isLoading={loading}
              />
            )}

            {activeTab === 'approvals' && (
              <ApprovalCenterPage
                approvals={approvals}
                onRefresh={fetchData}
                onSelectTransaction={(id) => setSelectedTransactionId(id)}
                isLoading={loading}
              />
            )}

            {activeTab === 'policies' && <PolicyManagementPage />}

            {activeTab === 'analytics' && <SecurityAnalyticsPage />}
          </div>
        </main>
      </div>

      {/* Slide-out Transaction Detail Drawer */}
      <TransactionDetailPage
        transactionId={selectedTransactionId}
        onClose={() => setSelectedTransactionId(null)}
      />
    </div>
  );
};

export default App;
