export type RouteId =
  | 'overview'
  | 'transactions'
  | 'approvals'
  | 'policies'
  | 'analytics'
  | 'not_found';

export interface RouteMetadata {
  id: RouteId;
  path: string;
  label: string;
  h1Title: string;
  subtitle: string;
  documentTitle: string;
  metaDescription: string;
}

export const ROUTES: Record<Exclude<RouteId, 'not_found'>, RouteMetadata> = {
  overview: {
    id: 'overview',
    path: '/',
    label: 'Overview',
    h1Title: 'Firewall & Escrow Overview',
    subtitle: 'Real-time agent payment authorization telemetry and firewall defenses',
    documentTitle: 'Firewall & Escrow Overview — AgentGuard',
    metaDescription:
      'Monitor real-time AI agent payment requests, authorized holds, blocked attacks, risk score distributions, and recent escrow settlement activity.',
  },
  transactions: {
    id: 'transactions',
    path: '/transactions',
    label: 'Transaction Explorer',
    h1Title: 'Transaction Explorer',
    subtitle: 'Searchable audit registry of all autonomous purchase requests and PayPal holds',
    documentTitle: 'Transaction Explorer — AgentGuard',
    metaDescription:
      'Search, filter, and inspect every autonomous AI purchase request evaluated by AgentGuard with firewall decisions, risk scores, and PayPal order IDs.',
  },
  approvals: {
    id: 'approvals',
    path: '/approvals',
    label: 'Approval Center',
    h1Title: 'Human Approval Center',
    subtitle: 'Operator verification and delay-capture settlement of held escrow requests',
    documentTitle: 'Human Approval Center — AgentGuard',
    metaDescription:
      'Review flagged AI buyer transactions, inspect invoice security evidence, and approve PayPal captures or reject and void active authorization holds.',
  },
  policies: {
    id: 'policies',
    path: '/policies',
    label: 'Policy Management',
    h1Title: 'Policy Firewall Configuration',
    subtitle: 'Deterministic spending caps, daily budgets, and trusted merchant allowlists',
    documentTitle: 'Policy Firewall Configuration — AgentGuard',
    metaDescription:
      'Configure single-transaction limits, rolling 24-hour spending limits, merchant allowlists, and mandatory human approval controls enforced before PayPal calls.',
  },
  analytics: {
    id: 'analytics',
    path: '/security-analytics',
    label: 'Security Analytics',
    h1Title: 'Adversarial Threat Intelligence',
    subtitle: 'Prompt injection interception metrics, attack categories, and risk histograms',
    documentTitle: 'Security Analytics & Threat Intelligence — AgentGuard',
    metaDescription:
      'Analyze blocked prompt injections, budget limit violations, merchant impersonation attempts, and empirical benchmark metrics across AgentGuard.',
  },
};

export const NOT_FOUND_ROUTE: RouteMetadata = {
  id: 'not_found',
  path: '/404',
  label: '404 Not Found',
  h1Title: 'Page Not Found (404)',
  subtitle: 'The requested AgentGuard console route does not exist',
  documentTitle: '404 Page Not Found — AgentGuard',
  metaDescription:
    'The requested AgentGuard console page could not be found. Return to the Firewall & Escrow Overview or navigate using internal console links.',
};

export function normalizePathname(rawPathname: string): string {
  if (!rawPathname || rawPathname === '/') return '/';
  return rawPathname.endsWith('/') ? rawPathname.slice(0, -1) : rawPathname;
}

export function resolveRoute(rawPathname: string): RouteMetadata {
  const path = normalizePathname(rawPathname);
  const match = Object.values(ROUTES).find((r) => r.path === path);
  return match || NOT_FOUND_ROUTE;
}
