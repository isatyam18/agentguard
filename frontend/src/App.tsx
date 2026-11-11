import React, { Suspense, lazy, useCallback, useEffect, useState } from 'react';
import { Breadcrumbs } from './components/layout/Breadcrumbs';
import { Header } from './components/layout/Header';
import { Sidebar } from './components/layout/Sidebar';
import { RouteMetadataManager } from './components/seo/RouteMetadataManager';
import { OverviewPage } from './pages/OverviewPage';
import { normalizePathname, resolveRoute, ROUTES } from './routes';
import { api } from './services/api';
import type { Approval, OverviewStats, Transaction } from './types';

// Lazy-load secondary & heavy views (such as AG Grid Transaction Explorer) to minimize initial bundle size
const TransactionExplorerPage = lazy(() =>
  import('./pages/TransactionExplorerPage').then((m) => ({ default: m.TransactionExplorerPage }))
);
const ApprovalCenterPage = lazy(() =>
  import('./pages/ApprovalCenterPage').then((m) => ({ default: m.ApprovalCenterPage }))
);
const PolicyManagementPage = lazy(() =>
  import('./pages/PolicyManagementPage').then((m) => ({ default: m.PolicyManagementPage }))
);
const SecurityAnalyticsPage = lazy(() =>
  import('./pages/SecurityAnalyticsPage').then((m) => ({ default: m.SecurityAnalyticsPage }))
);
const TransactionDetailPage = lazy(() =>
  import('./pages/TransactionDetailPage').then((m) => ({ default: m.TransactionDetailPage }))
);
const NotFoundPage = lazy(() =>
  import('./pages/NotFoundPage').then((m) => ({ default: m.NotFoundPage }))
);

const LazyFallback: React.FC = () => (
  <div className="flex items-center justify-center h-64 text-slate-400">
    <div className="text-center space-y-2">
      <div className="w-7 h-7 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto"></div>
      <p className="text-xs font-medium">Loading view...</p>
    </div>
  </div>
);

export const App: React.FC = () => {
  const [pathname, setPathname] = useState<string>(() =>
    normalizePathname(window.location.pathname)
  );
  const [overviewStats, setOverviewStats] = useState<OverviewStats | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [selectedTransactionId, setSelectedTransactionId] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const activeRoute = resolveRoute(pathname);

  useEffect(() => {
    const handlePopState = () => {
      setPathname(normalizePathname(window.location.pathname));
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleNavigate = useCallback(
    (targetPath: string, event?: React.MouseEvent<HTMLAnchorElement>) => {
      if (event) {
        // Preserve native browser new-tab behavior for Ctrl/Cmd/Shift/Middle click
        if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
          return;
        }
        event.preventDefault();
      }
      const cleanTarget = normalizePathname(targetPath);
      if (cleanTarget !== pathname) {
        window.history.pushState({}, '', cleanTarget);
        setPathname(cleanTarget);
      }
    },
    [pathname]
  );

  const fetchData = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const [statsRes, txsRes, approvalsRes] = await Promise.all([
        api.getOverview(),
        api.getTransactions(),
        api.getApprovals(),
      ]);

      setOverviewStats(statsRes);
      setTransactions(txsRes);
      setApprovals(approvalsRes);
    } catch (err: any) {
      setFetchError(err?.message || 'Failed to load telemetry from AgentGuard API.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      api.getOverview(),
      api.getTransactions(),
      api.getApprovals(),
    ])
      .then(([statsRes, txsRes, approvalsRes]) => {
        if (!active) return;
        setOverviewStats(statsRes);
        setTransactions(txsRes);
        setApprovals(approvalsRes);
      })
      .catch((err: any) => {
        if (active) setFetchError(err?.message || 'Failed to load telemetry from AgentGuard API.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleSeedDemoData = async () => {
    try {
      setFetchError(null);
      await api.seedDemoData(true);
      await fetchData();
    } catch (err: any) {
      setFetchError(err?.message || 'Failed to seed demo data.');
    }
  };

  const pendingApprovalsCount = approvals.filter((a) => a.status === 'PENDING').length;

  return (
    <div className="flex h-screen bg-slate-50 overflow-hidden font-sans antialiased text-slate-900">
      <RouteMetadataManager route={activeRoute} currentPath={pathname} />

      {/* Dark Navy Sidebar */}
      <Sidebar
        activeRouteId={activeRoute.id}
        onNavigate={handleNavigate}
        pendingCount={pendingApprovalsCount}
      />

      {/* Main Workspace */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header (contains the sole <h1> per page) */}
        <Header
          title={activeRoute.h1Title}
          subtitle={activeRoute.subtitle}
          onRefresh={fetchData}
          onSeedData={handleSeedDemoData}
          isLoading={loading}
        />

        {/* Scrollable Page Body */}
        <main className="flex-1 overflow-y-auto p-8 flex flex-col justify-between">
          <div className="max-w-7xl w-full mx-auto">
            <Breadcrumbs route={activeRoute} onNavigate={handleNavigate} />

            {activeRoute.id === 'overview' && (
              <OverviewPage
                stats={overviewStats}
                isLoading={loading}
                error={fetchError}
                onRetry={fetchData}
                onSelectTransaction={(id) => setSelectedTransactionId(id)}
                onNavigate={handleNavigate}
              />
            )}

            {activeRoute.id !== 'overview' && (
              <Suspense fallback={<LazyFallback />}>
                {activeRoute.id === 'transactions' && (
                  <TransactionExplorerPage
                    transactions={transactions}
                    onSelectTransaction={(id) => setSelectedTransactionId(id)}
                    isLoading={loading}
                  />
                )}

                {activeRoute.id === 'approvals' && (
                  <ApprovalCenterPage
                    approvals={approvals}
                    onRefresh={fetchData}
                    onSelectTransaction={(id) => setSelectedTransactionId(id)}
                    isLoading={loading}
                  />
                )}

                {activeRoute.id === 'policies' && <PolicyManagementPage />}

                {activeRoute.id === 'analytics' && <SecurityAnalyticsPage />}

                {activeRoute.id === 'not_found' && (
                  <NotFoundPage requestedPath={pathname} onNavigate={handleNavigate} />
                )}
              </Suspense>
            )}
          </div>

          {/* Internal Navigation Footer */}
          <footer className="max-w-7xl w-full mx-auto mt-10 pt-4 border-t border-slate-200/80 flex flex-wrap items-center justify-between gap-4 text-xs text-slate-500">
            <div className="flex items-center gap-2">
              <img
                src="/favicon.svg"
                alt="AgentGuard emblem"
                width={16}
                height={16}
                className="w-4 h-4 rounded-xs"
              />
              <span>AgentGuard Policy Firewall &amp; PayPal AUTHORIZE Escrow</span>
            </div>
            <nav aria-label="Footer Navigation" className="flex flex-wrap items-center gap-4">
              {Object.values(ROUTES).map((r) => (
                <a
                  key={r.id}
                  href={r.path}
                  onClick={(e) => handleNavigate(r.path, e)}
                  className={`hover:text-blue-600 transition-colors ${
                    activeRoute.id === r.id ? 'font-semibold text-slate-900' : ''
                  }`}
                >
                  {r.label}
                </a>
              ))}
            </nav>
          </footer>
        </main>
      </div>

      {/* Slide-out Transaction Detail Drawer */}
      {selectedTransactionId && (
        <Suspense fallback={null}>
          <TransactionDetailPage
            transactionId={selectedTransactionId}
            onClose={() => setSelectedTransactionId(null)}
          />
        </Suspense>
      )}
    </div>
  );
};

export default App;
