# AgentGuard: System Architecture

> **System**: AgentGuard - Policy Firewall & Escrow for Autonomous AI Payments  
> **Status**: Accepted / Baseline  
> **Date**: 2026-11-10  
> **Author**: Lead Software Architect & Senior Python Engineer  
> **Protocol**: Yuntra 2.0  

---

## 1. Executive Summary & Problem Space

As autonomous AI agents acquire tool-use capabilities to purchase computational resources, cloud APIs, digital assets, and subagent services, the risk of unconstrained, non-deterministic, or compromised spending escalates dramatically.

**AgentGuard** is an institutional-grade Policy Firewall and Escrow Gateway positioned between autonomous AI agents (the "Buyers") and the PayPal payment rail.

### Core Guarantees:
1. **Zero Credential Exposure**: AI agents and frontend clients never touch PayPal Client Secrets, Access Tokens, or raw payment rails.
2. **Deterministic Firewalling**: All payment policies (velocity limits, budget caps, vendor allowlists, anomaly detection) are executed by immutable, deterministic code—completely isolated from non-deterministic LLM reasoning or prompt injection vulnerabilities.
3. **True Escrow via PayPal Authorization**: High-risk or milestone-based payments leverage PayPal Orders v2 `intent: "AUTHORIZE"` to lock funds securely on PayPal infrastructure without capturing until agent verification or human milestone approval is satisfied.
4. **Agent-Native Protocol**: AI agents interact exclusively via the open Model Context Protocol (MCP) or an authenticated REST proxy, enforcing complete sandbox confinement.

---

## 2. High-Level System Architecture

AgentGuard is designed as a **modular monolith** with clean architectural boundaries, low operational overhead, and high auditability.

```mermaid
flowchart TD
    subgraph AutonomousAI ["Autonomous AI Agent Domain"]
        Agent["Autonomous Buyer Agent\n(Claude, AutoGPT, LangChain)"]
    end

    subgraph InterfaceLayer ["AgentGuard Interface Layer"]
        MCP["MCP Gateway\n(Model Context Protocol Stdio/SSE)"]
        REST["AgentGuard REST API\n(FastAPI /v1/agent/*)"]
        AdminAPI["Admin & HITL API\n(FastAPI /v1/admin/*)"]
    end

    subgraph CoreEngine ["AgentGuard Core Engine (Modular Monolith)"]
        Auth["Agent Auth & Token Verifier"]
        Firewall["Deterministic Policy Firewall\n- Budget & Velocity Engine\n- Vendor Whitelist/Blacklist\n- Anomaly & Risk Scorer"]
        Escrow["Escrow State Machine\n- Hold / Condition Logic\n- Auto-Timeout & Release"]
        Audit["Immutable Audit Logger"]
    end

    subgraph StorageLayer ["Persistence & State"]
        DB[(SQLite WAL Engine\n- Agents & Policies\n- Transactions & Escrows\n- Audit Trail)]
    end

    subgraph AdapterLayer ["Isolated Payment Adapter"]
        Adapter["PayPal Orders v2 Adapter\n- OAuth Token Caching\n- Intent: AUTHORIZE & CAPTURE\n- Void / Release Engine\n- Webhook Verifier"]
    end

    subgraph ExternalRail ["PayPal Sandbox / Production Rail"]
        PayPalAPI["PayPal Orders v2 & Payments API\n(api-m.sandbox.paypal.com)"]
        PayPalWebhook["PayPal Webhook Notifications"]
    end

    subgraph UI ["Human-in-the-Loop Frontend"]
        Dashboard["AgentGuard React + Vite Dashboard\n- Real-Time Transaction Monitor\n- Policy Configuration UI\n- HITL Approval Queue"]
    end

    %% Data Flows
    Agent -->|JSON-RPC Tools| MCP
    Agent -->|HTTP REST| REST
    MCP --> Auth
    REST --> Auth
    Auth --> Firewall
    
    Firewall -->|Policy Evaluated| Escrow
    Escrow -->|State Persisted| DB
    Audit --> DB

    Escrow -->|Clear to Execute| Adapter
    Adapter -->|HTTPS Basic Auth / Bearer| PayPalAPI
    PayPalWebhook -->|Signed Events| Adapter

    AdminAPI --> DB
    AdminAPI --> Escrow
    Dashboard -->|REST & SSE| AdminAPI
```

---

## 3. Modular Monolith Subsystems & Domain Boundaries

The backend is strictly partitioned into domain packages under `src/agentguard/`:

| Module | Purpose | Allowed Inbound Dependencies | Prohibited Direct Access |
| :--- | :--- | :--- | :--- |
| **`core`** | Configuration, Pydantic base models, SQLite connection lifecycle, security primitives. | All modules | Must not import domain modules |
| **`firewall`** | Deterministic evaluation of transaction rules: spending caps, velocity limits, vendor allowlists/blocklists, regex content filters, anomaly scoring. | `api`, `mcp` | Must not import `paypal` adapter |
| **`escrow`** | Escrow lifecycle management (`PENDING_REVIEW`, `HELD`, `APPROVED`, `CAPTURED`, `VOIDED`, `REFUNDED`). | `api`, `mcp`, `firewall` | External agents cannot directly trigger state transitions |
| **`paypal`** | **Isolated Payment Adapter**. Handles OAuth2 client credentials, token caching, Orders v2 creation (`AUTHORIZE`/`CAPTURE`), authorization captures, voids, and webhook verification. | `escrow` exclusively | **Strictly prohibited** from direct invocation by `api`, `mcp`, or frontend |
| **`mcp`** | Model Context Protocol gateway. Exposes tools (`request_payment`, `check_payment_status`, `simulate_transaction`, `list_approved_vendors`) to AI agents over stdio/SSE. | External AI processes | Cannot access PayPal adapter directly; routes strictly through `firewall` |
| **`api`** | FastAPI routing layer (`/v1/agent`, `/v1/admin`, `/v1/webhooks`, `/health`). | HTTP clients, Dashboard | Cannot execute PayPal payments without traversing `firewall` and `escrow` |

---

## 4. End-to-End Transaction Lifecycle

### Flow A: Autonomous Low-Risk Transaction (Direct Policy Pass & Auto-Capture)
```mermaid
sequenceDiagram
    autonumber
    actor Agent as Autonomous AI Agent
    participant MCP as MCP Gateway / REST API
    participant Firewall as Policy Firewall
    participant Escrow as Escrow Engine
    participant DB as SQLite DB
    participant Adapter as PayPal Adapter
    participant PayPal as PayPal API (Orders v2)

    Agent->>MCP: request_payment(amount=15.00, vendor="OpenAI API", purpose="Compute")
    MCP->>Firewall: evaluate_policy(agent_id, amount, vendor)
    Firewall->>DB: Check agent budget, daily velocity & vendor allowlist
    DB-->>Firewall: Limits OK, Risk Score = 0.05 (LOW)
    Firewall-->>Escrow: Policy Approved (Action: AUTO_EXECUTE)
    
    Escrow->>Adapter: create_and_capture_order(amount=15.00, custom_id=TXN-101)
    Adapter->>PayPal: POST /v2/checkout/orders (intent: CAPTURE)
    PayPal-->>Adapter: 201 Created (Order ID: 5O19..., status: COMPLETED)
    Adapter-->>Escrow: Capture Success (Capture ID: 9V87...)
    Escrow->>DB: Commit TXN-101 as CAPTURED, update velocity tally
    Escrow-->>MCP: Payment Approved & Captured
    MCP-->>Agent: { status: "SUCCESS", transaction_id: "TXN-101", capture_id: "9V87..." }
```

### Flow B: High-Risk / Milestone Escrow (Intent: AUTHORIZE + Human-in-the-Loop)
```mermaid
sequenceDiagram
    autonumber
    actor Agent as Autonomous AI Agent
    participant MCP as MCP Gateway
    participant Firewall as Policy Firewall
    participant Escrow as Escrow Engine
    participant DB as SQLite DB
    participant Adapter as PayPal Adapter
    participant PayPal as PayPal API
    actor Human as Human Operator (Dashboard)

    Agent->>MCP: request_payment(amount=450.00, vendor="Freelance Dev", milestone="Phase 1")
    MCP->>Firewall: evaluate_policy(agent_id, amount=450.00, vendor)
    Firewall->>DB: Check threshold (Max Autonomous = $100.00)
    DB-->>Firewall: Threshold Exceeded (Requires Escrow Hold + HITL)
    Firewall-->>Escrow: Policy Decision: HOLD_ESCROW_HITL
    
    Escrow->>Adapter: create_authorized_order(amount=450.00)
    Adapter->>PayPal: POST /v2/checkout/orders (intent: AUTHORIZE)
    PayPal-->>Adapter: Order Created (ID: 7K21..., status: CREATED, approve_link)
    Adapter->>PayPal: POST /v2/checkout/orders/7K21.../authorize
    PayPal-->>Adapter: Funds Authorized (Auth ID: 3X99..., status: CREATED)
    
    Escrow->>DB: Store TXN as HELD (Auth ID: 3X99..., Token: tok_sec_89f...)
    Escrow-->>MCP: { status: "HELD_IN_ESCROW", hold_reason: "AMOUNT_EXCEEDS_AUTONOMOUS_LIMIT", approval_id: "APPR-42" }
    
    Note over Human,Escrow: Human inspects transaction in AgentGuard Dashboard
    Human->>Dashboard: Review deliverables & Click "Release Escrow"
    Dashboard->>Escrow: POST /v1/admin/approvals/APPR-42/release (Admin Session)
    Escrow->>Adapter: capture_authorization(authorization_id="3X99...", final_capture=true)
    Adapter->>PayPal: POST /v2/payments/authorizations/3X99.../capture
    PayPal-->>Adapter: Capture Completed (Capture ID: 8C44...)
    Escrow->>DB: Update TXN to CAPTURED, log audit event
    Dashboard-->>Human: Escrow Successfully Disbursed
```

---

## 5. PayPal Orders v2 API Integration Contract

All external payment operations are strictly encapsulated inside `agentguard.paypal.adapter.PayPalAdapter`:

1. **OAuth2 Token Manager**:
   - `POST /v1/oauth2/token`
   - Cache token in-memory with expiration guard (refresh 5 minutes prior to TTL).
   - Thread-safe / async-safe mutex prevents token fetch race conditions.
2. **Order Creation (`intent: AUTHORIZE` or `intent: CAPTURE`)**:
   - Endpoint: `POST /v2/checkout/orders`
   - Headers:
     - `Authorization: Bearer [REDACTED]`
     - `PayPal-Request-Id: <idempotency_key>`
     - `Content-Type: application/json`
   - Standard payload:
     ```json
     {
       "intent": "AUTHORIZE",
       "purchase_units": [
         {
           "reference_id": "default",
           "custom_id": "AGENTGUARD_TXN_UUID",
           "description": "Agent Payment for: Compute Engine",
           "amount": {
             "currency_code": "USD",
             "value": "150.00"
           }
         }
       ]
     }
     ```
3. **Authorize Order**:
   - Endpoint: `POST /v2/checkout/orders/{order_id}/authorize`
   - Extracts and persists `purchase_units[0].payments.authorizations[0].id`.
4. **Capture Authorization (Escrow Settlement)**:
   - Endpoint: `POST /v2/payments/authorizations/{authorization_id}/capture`
   - Payload:
     ```json
     {
       "amount": { "currency_code": "USD", "value": "150.00" },
       "final_capture": true,
       "note_to_payer": "AgentGuard verified release condition satisfied."
     }
     ```
5. **Void Authorization (Escrow Cancellation / Refund)**:
   - Endpoint: `POST /v2/payments/authorizations/{authorization_id}/void`
   - Releases held buyer funds if policy is violated or task fails.
6. **Webhook Signature Verification**:
   - Endpoint: `POST /v1/notifications/verify-webhook-signature`
   - Verifies incoming payloads against PayPal transmission headers:
     `paypal-auth-algo`, `paypal-cert-url`, `paypal-transmission-id`, `paypal-transmission-sig`, `paypal-transmission-time`.

---

## 6. Database Schema (SQLite with WAL Mode)

```mermaid
erDiagram
    AGENTS ||--o{ POLICIES : owns
    AGENTS ||--o{ TRANSACTIONS : initiates
    TRANSACTIONS ||--o| ESCROW_RECORDS : holds
    TRANSACTIONS ||--o| APPROVAL_REQUESTS : requires
    TRANSACTIONS ||--o{ AUDIT_LOGS : audits

    AGENTS {
        string agent_id PK
        string name
        string api_key_hash
        real max_single_budget
        real daily_velocity_limit
        real current_daily_spent
        string status
        datetime created_at
    }

    POLICIES {
        string policy_id PK
        string agent_id FK
        string rule_type
        json rule_config
        boolean is_active
        datetime created_at
    }

    TRANSACTIONS {
        string txn_id PK
        string agent_id FK
        string vendor_name
        real amount
        string currency
        string status
        string policy_decision
        real risk_score
        string paypal_order_id
        string paypal_auth_id
        string paypal_capture_id
        string idempotency_key UK
        datetime created_at
        datetime updated_at
    }

    ESCROW_RECORDS {
        string escrow_id PK
        string txn_id FK
        string status
        string hold_reason
        string release_condition
        datetime expires_at
        datetime released_at
    }

    APPROVAL_REQUESTS {
        string approval_id PK
        string txn_id FK
        string approval_token_hash
        string status
        string reviewer_notes
        datetime requested_at
        datetime decided_at
    }

    AUDIT_LOGS {
        integer log_id PK
        string entity_type
        string entity_id
        string action
        string actor
        json details
        datetime timestamp
    }
```

---

## 7. Model Context Protocol (MCP) Gateway

AgentGuard provides a native MCP server for seamless integration with modern agent runtimes (Claude Code, Cursor, AutoGPT, LangChain, custom agents).

### Exposed MCP Tools:
1. **`request_payment`**:
   - Parameters: `amount` (float), `currency` (ISO-4217, default "USD"), `vendor` (string), `purpose` (string), `milestone_id` (optional string), `idempotency_key` (UUID string).
   - Behavior: Enters policy firewall. Returns immediate approval & capture or escrow hold details.
2. **`check_payment_status`**:
   - Parameters: `transaction_id` (string).
   - Behavior: Queries live state of transaction/escrow.
3. **`simulate_transaction`**:
   - Parameters: `amount` (float), `vendor` (string).
   - Behavior: Dry-runs through policy firewall without triggering PayPal APIs, reporting what policies would fire.
4. **`list_approved_vendors`**:
   - Parameters: none.
   - Behavior: Returns allowlisted vendors and approved merchant categories.

---

## 8. Frontend Architecture (React, Vite, TypeScript, Tailwind)

The operator dashboard provides single-pane-of-glass observability and human-in-the-loop control:
1. **Firewall Live Monitor**: Real-time ticker of agent payment requests, status badges (`CAPTURED`, `HELD`, `REJECTED`, `VOIDED`), risk score radar.
2. **Escrow Vault & HITL Approval Queue**: Active authorizations held on PayPal. Single-click "Approve & Capture" or "Reject & Void" with cryptographic token verification.
3. **Policy Rules Manager**: Interactive configuration of per-agent budget caps, rolling 24-hour velocity windows, and vendor whitelists.
4. **Agent Simulator / Sandbox**: Built-in test console to dispatch synthetic agent payment payloads and verify policy enforcement live.

---

## 9. Security Boundary Invariants

1. **Isolation Invariant**: The PayPal adapter credentials (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`) never leave the backend process environment.
2. **Determinism Invariant**: No LLM prompt or output is ever permitted to override a deterministic firewall rejection.
3. **Idempotency Invariant**: Every transaction carries an idempotency key mapped to PayPal's `PayPal-Request-Id` to guarantee zero double-charging under network retries.
4. **Audit Immutability**: All decisions (firewall evaluations, approvals, holds, captures, voids) generate append-only audit records.
