import type {
  Approval,
  AuditLog,
  OverviewStats,
  Policy,
  SecurityStats,
  Transaction,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

// Administrative token for human reviewer operations (defaults to dev key in development mode only)
export const DEFAULT_ADMIN_TOKEN =
  import.meta.env.VITE_ADMIN_TOKEN || (import.meta.env.DEV ? 'admin-secret-key-2026' : ''); // [REDACTED]

export function getAdminToken(): string {
  return localStorage.getItem('agentguard_admin_token') || DEFAULT_ADMIN_TOKEN;
}

export function setAdminToken(token: string): void {
  localStorage.setItem('agentguard_admin_token', token);
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options?.headers || {});

  if (!headers.has('Content-Type') && !(options?.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const token = getAdminToken(); // [REDACTED]
  if (token && !headers.has('X-Admin-Token')) {
    headers.set('X-Admin-Token', token);
  }

  const res = await fetch(url, { ...options, headers });

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    try {
      const errJson = await res.json();
      errorDetail = errJson.message || errJson.error?.message || JSON.stringify(errJson);
    } catch {
      // ignore non-json error body
    }
    throw new Error(errorDetail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  // Analytics
  getOverview: (): Promise<OverviewStats> => request<OverviewStats>('/analytics/overview'),
  getSecurity: (): Promise<SecurityStats> => request<SecurityStats>('/analytics/security'),
  seedDemoData: (force: boolean = true): Promise<{ status: string; message: string; seeded_ids: string[] }> =>
    request(`/demo/seed?force=${force}`, { method: 'POST' }),

  // Transactions
  getTransactions: (limit: number = 100, offset: number = 0): Promise<Transaction[]> =>
    request<Transaction[]>(`/transactions?limit=${limit}&offset=${offset}`),
  getTransaction: (id: string): Promise<Transaction> => request<Transaction>(`/transactions/${id}`),

  // Audit Logs
  getAuditLogs: (transactionId?: string): Promise<AuditLog[]> => {
    const query = transactionId ? `?transaction_id=${transactionId}` : '';
    return request<AuditLog[]>(`/audit-logs${query}`);
  },

  // Approvals (Human-in-the-Loop)
  getApprovals: (status?: string): Promise<Approval[]> => {
    const query = status ? `?status=${status}` : '';
    return request<Approval[]>(`/approvals${query}`);
  },
  getApprovalDetails: (id: string): Promise<any> => request<any>(`/approvals/${id}/details`),
  approveEscrow: (id: string, reviewer: string = 'Security Officer', reason: string = 'Approved after verification'): Promise<any> =>
    request<any>(`/approvals/${id}/approve`, {
      method: 'POST',
      body: JSON.stringify({ reviewer, reason, admin_token: getAdminToken() }),
    }),
  rejectEscrow: (id: string, reviewer: string = 'Security Officer', reason: string = 'Rejected by security review'): Promise<any> =>
    request<any>(`/approvals/${id}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reviewer, reason, admin_token: getAdminToken() }),
    }),

  // Policies
  getPolicies: (): Promise<Policy[]> => request<Policy[]>('/policies'),
  createPolicy: (policy: Partial<Policy>): Promise<Policy> =>
    request<Policy>('/policies', { method: 'POST', body: JSON.stringify(policy) }),
  updatePolicy: (id: string, policy: Partial<Policy>): Promise<Policy> =>
    request<Policy>(`/policies/${id}`, { method: 'PATCH', body: JSON.stringify(policy) }),
};
