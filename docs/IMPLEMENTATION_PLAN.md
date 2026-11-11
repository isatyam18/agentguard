# AgentGuard: Comprehensive Implementation Plan

> **System**: AgentGuard - Policy Firewall & Escrow for Autonomous AI Payments  
> **Target Event**: Solo PayPal AI Hackathon  
> **Status**: Ready for User Review & Approval  
> **Author**: Lead Software Architect & Senior Python Engineer  
> **Protocol**: Yuntra 2.0  

---

## 1. Plan Overview & Engineering Philosophy

This implementation plan outlines the systematic, phased delivery of **AgentGuard**. Adhering strictly to Yuntra 2.0 and the hackathon development guidelines:
- Work is broken down into discrete, verifiable milestones.
- No production code is executed until this plan is formally approved by the user.
- Every milestone includes concrete acceptance criteria and automated test evidence.
- Zero credential leaks; deterministic policy isolation; no invented PayPal APIs.

---

## 2. Dependency & Environment Matrix

### 2.1 Host Runtime Environment (Verified During Discovery)
- **Python**: `3.14.3` (Standard library includes `sqlite3`, `secrets`, `hashlib`, `asyncio`, `json`, `dataclasses`)
- **Node.js**: `v24.14.0`
- **npm**: `11.11.0`
- **Operating System**: Windows 11 (pwsh shell)

### 2.2 Backend Dependencies (Python)
| Package | Version Range | Purpose & Rationale |
| :--- | :--- | :--- |
| `fastapi` | `^0.115.0` | High-performance asynchronous API framework for agent gateway, admin routes, and webhooks. |
| `uvicorn[standard]` | `^0.32.0` | ASGI server for asynchronous request handling. |
| `pydantic` | `^2.9.0` | Strict data validation and schema serialization for payment requests, policies, and PayPal payloads. |
| `pydantic-settings` | `^2.6.0` | Environment variable and configuration management from `.env`. |
| `httpx` | `^0.27.2` | Async HTTP client for low-latency calls to PayPal Orders v2 and Payments v2 endpoints. |
| `aiosqlite` | `^0.20.0` | Asynchronous SQLite wrapper enabling non-blocking database queries with WAL mode. |
| `mcp` | `^1.1.0` | Official Model Context Protocol Python SDK for AI agent tool server integration. |
| `pytest` | `^8.3.0` | Test runner for unit, integration, and security test suites. |
| `pytest-asyncio` | `^0.24.0` | Asynchronous testing fixtures for FastAPI and SQLite. |

### 2.3 Frontend Dependencies (React + Vite + TypeScript)
| Package | Purpose & Rationale |
| :--- | :--- |
| `react`, `react-dom` (v18 or v19) | Modern declarative UI for the operator dashboard. |
| `typescript` | Static type safety matching backend Pydantic models. |
| `vite` | Fast dev server and modern ES build tooling. |
| `lucide-react` | Clean icon library for transactions, firewall rules, and escrow statuses. |
| `tailwindcss` | Utility-first styling for clean, modern dashboard layout. |

### 2.4 External Integration Requirements
- **PayPal Developer Sandbox**:
  - `PAYPAL_CLIENT_ID`
  - `PAYPAL_CLIENT_SECRET`
  - `PAYPAL_BASE_URL` (`https://api-m.sandbox.paypal.com`)
  - `PAYPAL_WEBHOOK_ID` (for signature validation)
- Built-in Mock Mode: When live PayPal sandbox credentials are not present in `.env`, the PayPal adapter defaults to a deterministic, high-fidelity mock adapter simulating exact PayPal Orders v2 responses, error codes, and authorization tokens for offline verification.

---

## 3. Milestones & Task Breakdown

### Milestone 1: Core Foundation & Storage Engine
- **Objective**: Establish the modular repository structure, configuration system, SQLite database schema with WAL mode, and database migration/seed scripts.
- **Tasks**:
  1. Create directory tree under `src/agentguard/` (`core`, `firewall`, `escrow`, `paypal`, `mcp`, `api`).
  2. Implement `src/agentguard/core/config.py` with Pydantic settings (`PAYPAL_*`, `AGENTGUARD_*`).
  3. Implement `src/agentguard/core/database.py` with connection pooling, WAL mode, foreign keys, and atomic transaction helpers.
  4. Implement SQLite DDL schemas for `agents`, `policies`, `transactions`, `escrow_records`, `approval_requests`, and `audit_logs`.
  5. Create automated migration/initialization script and test database fixtures.
- **Acceptance Criteria**:
  - `pytest tests/test_database.py` passes with 100% green tests.
  - SQLite creates all tables with correct indexes and constraints.
  - WAL journal mode is active and verified via `PRAGMA journal_mode`.

---

### Milestone 2: Isolated PayPal Orders v2 Adapter
- **Objective**: Implement the isolated payment adapter communicating strictly with PayPal's Orders v2 and Payments v2 REST APIs.
- **Tasks**:
  1. Implement OAuth2 client credentials token caching with TTL buffer (`src/agentguard/paypal/auth.py`).
  2. Implement Order creation supporting both `intent: "CAPTURE"` and `intent: "AUTHORIZE"` (`src/agentguard/paypal/client.py`).
  3. Implement Order Authorization execution (`POST /v2/checkout/orders/{id}/authorize`).
  4. Implement Authorized Payment Capture (`POST /v2/payments/authorizations/{id}/capture`).
  5. Implement Authorized Payment Void/Release (`POST /v2/payments/authorizations/{id}/void`).
  6. Implement Webhook signature verification (`POST /v1/notifications/verify-webhook-signature`).
  7. Implement comprehensive Mock PayPal Adapter for local offline testing and CI.
- **Acceptance Criteria**:
  - `pytest tests/test_paypal_adapter.py` passes.
  - Verifies exact official PayPal v2 payloads against PayPal API documentation.
  - Idempotency keys (`PayPal-Request-Id`) correctly forwarded on all mutation requests.
  - No PayPal credentials or raw tokens exposed outside the adapter interface.

---

### Milestone 3: Deterministic Policy Firewall Engine
- **Objective**: Implement the rule evaluation engine that analyzes agent payment requests before execution.
- **Tasks**:
  1. Implement `SpendingLimitRule` (per-transaction maximums, e.g. cap at $50 for autonomous execution).
  2. Implement `VelocityLimitRule` (rolling 24-hour aggregate budget enforcement with atomic database locking).
  3. Implement `VendorPolicyRule` (domain allowlisting, merchant category matching, unverified vendor flagging).
  4. Implement `ContentFilterRule` (regex detection of suspicious payment purpose descriptions, e.g. exfiltration attempts).
  5. Implement `RiskScorer` (calculates composite risk score from 0.00 to 1.00; classifies as `AUTO_APPROVE`, `ESCROW_HOLD_HITL`, or `REJECT`).
  6. Connect policy engine to immutable audit log.
- **Acceptance Criteria**:
  - `pytest tests/test_firewall.py` passes with unit tests covering boundary limits, velocity overflow, and prompt injection attempts.
  - Deterministic evaluation executes in < 5ms without external network calls.
  - Guaranteed refusal: No agent prompt or payload can force an auto-approval if limits are exceeded.

---

### Milestone 4: Escrow State Machine & Human-in-the-Loop (HITL) Gateway
- **Objective**: Build the escrow holding, milestone verification, and human approval workflow.
- **Tasks**:
  1. Implement Escrow state machine (`HELD`, `APPROVED`, `CAPTURED`, `VOIDED`, `EXPIRED`).
  2. Implement cryptographically secure token generator for human approval URLs (`secrets.token_urlsafe(32)`).
  3. Implement HITL approval and rejection endpoints (`POST /v1/admin/approvals/{id}/decide`).
  4. Implement auto-expiration and release daemon/task (voiding expired PayPal authorizations before funds get stranded).
  5. Connect escrow transitions to PayPal adapter capture/void methods.
- **Acceptance Criteria**:
  - `pytest tests/test_escrow.py` passes.
  - High-value payments (> threshold) automatically transition to `HELD` with an `AUTHORIZE` call to PayPal.
  - Releasing escrow successfully triggers PayPal authorization capture.
  - Rejecting escrow triggers PayPal authorization void, releasing funds back to buyer.

---

### Milestone 5: Model Context Protocol (MCP) Server & Agent REST Gateway
- **Objective**: Expose typed, sandboxed tools to autonomous AI agents.
- **Tasks**:
  1. Implement MCP stdio/SSE server (`src/agentguard/mcp/server.py`).
  2. Implement MCP tools:
     - `request_payment`: Primary payment tool with schema validation.
     - `check_payment_status`: State lookup by transaction ID.
     - `simulate_transaction`: Dry-run policy check.
     - `list_approved_vendors`: Vendor directory query.
  3. Implement agent REST endpoints in FastAPI (`POST /v1/agent/payments`, `GET /v1/agent/payments/{id}`).
  4. Implement agent API key authentication and rate limiting.
- **Acceptance Criteria**:
  - `pytest tests/test_mcp.py` passes using the official MCP client protocol.
  - Agents receive clear, actionable JSON responses indicating whether payment was executed or placed in escrow with a tracking ID.
  - Zero sensitive server secrets or PayPal API keys present in MCP tool schemas or responses.

---

### Milestone 6: Operator Dashboard Frontend (React + Vite + TypeScript)
- **Objective**: Build an institutional dashboard for visualising agent activity, inspecting escrows, and human-in-the-loop decisions.
- **Tasks**:
  1. Initialize React + TypeScript + Vite project under `frontend/`.
  2. Configure Tailwind CSS with dark-mode aesthetic suited for fintech security tooling.
  3. Implement **Live Firewall Feed**: Real-time stream of incoming agent transactions with status pills and risk metrics.
  4. Implement **Escrow Vault & HITL Approval Queue**: List of held authorizations with one-click "Release Escrow" or "Refund / Void" buttons.
  5. Implement **Policy Rules Editor**: Interactive form to set per-agent transaction limits, daily caps, and vendor lists.
  6. Implement **Interactive Agent Simulator**: Playground where evaluators can trigger mock AI agent purchases and observe real-time firewall gating.
- **Acceptance Criteria**:
  - Frontend builds cleanly via `npm run build` with zero TypeScript errors.
  - Dashboard connects seamlessly to FastAPI backend via REST API.
  - Live approval action updates escrow status in real-time.

---

### Milestone 7: Verification, Security Audit & Yuntra Sign-Off
- **Objective**: Full end-to-end integration testing, automated security scan, and documentation finalization.
- **Tasks**:
  1. Run complete automated test suite (`pytest -v --tb=short`).
  2. Execute credential leak scan via `yuntra scan` to guarantee zero committed secrets.
  3. Verify end-to-end flow: AI Agent -> MCP Gateway -> Policy Firewall -> Escrow Hold -> PayPal Sandbox Authorize -> Human Dashboard Approval -> PayPal Sandbox Capture.
  4. Update `.yuntra/progress.md`, `.yuntra/context.md`, and `CHANGELOG.md` with explicit rationale.
  5. Create comprehensive `README.md` with quickstart instructions for hackathon judges.
- **Acceptance Criteria**:
  - 100% test pass rate across all test modules.
  - `yuntra scan` returns 0 exposed secrets or high-entropy tokens.
  - Full demo flow runnable in under 60 seconds with simple instructions.

---

## 4. Risk Assessment & Mitigations

| Risk | Impact | Likelihood | Mitigation Strategy |
| :--- | :--- | :--- | :--- |
| **PayPal Sandbox Rate Limits / Downtime** | High | Medium | Implement high-fidelity `MockPayPalAdapter` toggleable via `PAYPAL_MODE=mock`, allowing full end-to-end demo and testing without live internet reliance. |
| **Concurrency / Double-Spend via Agents** | High | Low | Use SQLite `BEGIN IMMEDIATE` transactions with unique `idempotency_key` constraint to serialize budget deductions atomically. |
| **Prompt Injection to Bypass Policy** | Critical | High | Completely decouple policy checks from LLM prompts; policy rules are pure Python mathematical checks that do not evaluate LLM text assertions. |
| **Token Expiry on Authorizations** | Medium | Medium | Include TTL timestamp on escrow records and automated warning in UI if an authorization approaches PayPal's expiration window. |
| **Credential Exfiltration by Agent** | Critical | Medium | Zero-knowledge architecture: Agents only have AgentGuard API keys; PayPal Client Secrets reside exclusively in server-side environment variables. |

---

## 5. Verification & Test Strategy

### Automated Test Pyramid:
1. **Unit Tests (`tests/unit/`)**:
   - `test_config.py`: Environment variable loading, validation of defaults.
   - `test_rules.py`: Spending limits, velocity tracking, vendor regex matching, prompt injection resilience.
   - `test_escrow_fsm.py`: Escrow state machine transitions and invalid transition rejections.
2. **Integration Tests (`tests/integration/`)**:
   - `test_paypal_adapter.py`: Mock and Sandbox PayPal API calls, token caching, order creation, authorization, capture, and void.
   - `test_api_endpoints.py`: FastAPI agent and admin endpoints, error handling, status codes.
   - `test_mcp_server.py`: MCP tool dispatch, parameter validation, JSON-RPC communication.
3. **Security & Protocol Verification**:
   - `yuntra scan`: Deterministic credential scanning on all repository files.
   - Automated boundary assertion: Verify no imports of `agentguard.paypal` exist outside `agentguard.escrow`.

---

## 6. Next Steps & Approval Gate

> [!IMPORTANT]
> In accordance with the prompt and Yuntra 2.0 Golden Rule:
> **Stop after completing discovery and planning. Wait for approval before implementation.**
> Once approved, implementation will proceed systematically starting with Milestone 1.
