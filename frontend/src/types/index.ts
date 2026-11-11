export type Decision = 'APPROVE' | 'REVIEW' | 'BLOCK' | 'PENDING';

export type PaymentStatus =
  | 'PENDING'
  | 'EVALUATING'
  | 'BLOCKED'
  | 'REVIEW_REQUIRED'
  | 'PAYPAL_ORDER_CREATED'
  | 'AUTHORIZED'
  | 'APPROVED_FOR_CAPTURE'
  | 'CAPTURED'
  | 'VOIDED'
  | 'FAILED';

export interface Transaction {
  id: string;
  external_reference: string;
  merchant_name: string;
  merchant_id: string;
  amount: string;
  currency: string;
  description: string;
  risk_score: string;
  decision: Decision;
  payment_status: PaymentStatus;
  paypal_order_id: string | null;
  paypal_authorization_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface Approval {
  id: string;
  transaction_id: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  reviewer: string | null;
  reason: string | null;
  created_at: string;
  resolved_at: string | null;
  transaction?: Transaction;
}

export interface Policy {
  id: string;
  max_transaction_amount: string;
  daily_spending_limit: string;
  allowed_merchants: string[];
  require_human_approval: boolean;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface AuditLog {
  id: string;
  transaction_id: string | null;
  event_type: string;
  actor: string;
  details: Record<string, any>;
  timestamp: string;
}

export interface OverviewStats {
  total_transactions: number;
  approved_transactions: number;
  blocked_transactions: number;
  pending_approvals: number;
  total_authorized_amount: string;
  total_captured_amount: string;
  currency: string;
  risk_distribution: {
    low: number;
    medium: number;
    high: number;
  };
  recent_activity: Array<{
    id: string;
    external_reference: string;
    merchant_name: string;
    amount: string;
    currency: string;
    risk_score: number;
    decision: string;
    payment_status: string;
    created_at: string;
  }>;
}

export interface SecurityStats {
  threat_summary: Record<string, number>;
  metrics: {
    prompt_injection_defense_rate: number;
    false_positive_rate: number;
    average_inspection_latency_ms: number;
    benchmark_cases_evaluated: number;
    active_firewall_policies: number;
    sandbox_mode: string;
  };
  risk_histogram: Array<{ bucket: string; count: number }>;
  top_blocked_reasons: Array<{ reason: string; count: number }>;
}
