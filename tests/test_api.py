"""Integration tests for FastAPI endpoints, health checks, error responses, and CRUD routes."""

from decimal import Decimal
import uuid
from fastapi.testclient import TestClient


def test_health_check_endpoints(client: TestClient) -> None:
    """Verify both root and versioned health-check endpoints report healthy status."""
    for path in ("/health", "/api/v1/health"):
        response = client.get(path)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "version" in data
        assert "timestamp" in data


def test_create_and_get_transaction_api(client: TestClient) -> None:
    """Verify transaction creation and lookup via REST API."""
    payload = {
        "external_reference": "ref-api-txn-001",
        "merchant_name": "OpenAI Platform",
        "merchant_id": "m-openai-org-42",
        "amount": "29.99",
        "currency": "USD",
        "description": "GPT-4o fine-tuning tokens",
        "risk_score": "0.05",
        "decision": "ALLOW",
        "payment_status": "PENDING",
    }

    # Create transaction
    create_resp = client.post("/api/v1/transactions", json=payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()

    assert "id" in created_data
    txn_id = created_data["id"]
    assert uuid.UUID(txn_id)
    assert created_data["amount"] == "29.99"
    assert created_data["merchant_name"] == "OpenAI Platform"

    # Get transaction by ID
    get_resp = client.get(f"/api/v1/transactions/{txn_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == txn_id

    # Non-existent ID returns 404
    missing_id = str(uuid.uuid4())
    missing_resp = client.get(f"/api/v1/transactions/{missing_id}")
    assert missing_resp.status_code == 404
    assert missing_resp.json()["error"]["code"] == "NOT_FOUND"


def test_invalid_transaction_requests(client: TestClient) -> None:
    """Verify invalid payloads trigger structured 422 validation errors."""
    # Negative amount
    resp_negative = client.post(
        "/api/v1/transactions",
        json={
            "external_reference": "ref-neg",
            "merchant_name": "Merchant",
            "merchant_id": "m-1",
            "amount": "-50.00",
            "currency": "USD",
            "description": "Negative amount",
        },
    )
    assert resp_negative.status_code == 422
    assert resp_negative.json()["error"]["code"] == "REQUEST_VALIDATION_ERROR"

    # Invalid currency code
    resp_bad_currency = client.post(
        "/api/v1/transactions",
        json={
            "external_reference": "ref-bad-curr",
            "merchant_name": "Merchant",
            "merchant_id": "m-1",
            "amount": "50.00",
            "currency": "USDOLLARS",
            "description": "Bad currency code",
        },
    )
    assert resp_bad_currency.status_code == 422

    # Missing required field
    resp_missing = client.post(
        "/api/v1/transactions",
        json={
            "external_reference": "ref-missing-fields",
            "amount": "10.00",
        },
    )
    assert resp_missing.status_code == 422


def test_duplicate_external_reference_conflict(client: TestClient) -> None:
    """Verify duplicate external reference returns 409 Conflict."""
    payload = {
        "external_reference": "ref-unique-dup-check",
        "merchant_name": "Cloudflare",
        "merchant_id": "m-cf-1",
        "amount": "12.00",
        "currency": "USD",
        "description": "Worker subscription",
    }

    first = client.post("/api/v1/transactions", json=payload)
    assert first.status_code == 201

    second = client.post("/api/v1/transactions", json=payload)
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "CONFLICT"


def test_policy_api_lifecycle(client: TestClient) -> None:
    """Verify policy creation, listing, and partial update."""
    payload = {
        "max_transaction_amount": "50.00",
        "daily_spending_limit": "200.00",
        "allowed_merchants": ["GitHub", "AWS"],
        "require_human_approval": True,
        "is_active": True,
    }

    create_resp = client.post("/api/v1/policies", json=payload)
    assert create_resp.status_code == 201
    policy_id = create_resp.json()["id"]

    # Patch policy
    patch_resp = client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"max_transaction_amount": "75.00", "is_active": False},
    )
    assert patch_resp.status_code == 200
    patched_data = patch_resp.json()
    assert patched_data["max_transaction_amount"] == "75.00"
    assert patched_data["is_active"] is False


def test_approval_api_lifecycle(client: TestClient) -> None:
    """Verify approval creation, decision resolution, and duplicate checks."""
    # Create transaction first
    txn_resp = client.post(
        "/api/v1/transactions",
        json={
            "external_reference": "ref-approval-test-01",
            "merchant_name": "Upwork Freelancer",
            "merchant_id": "m-upwork-dev",
            "amount": "250.00",
            "currency": "USD",
            "description": "Contractor milestone",
            "decision": "HOLD",
            "payment_status": "PENDING",
        },
    )
    txn_id = txn_resp.json()["id"]

    # Request approval
    appr_resp = client.post(
        "/api/v1/approvals",
        json={"transaction_id": txn_id, "reason": "Amount exceeds autonomous budget"},
    )
    assert appr_resp.status_code == 201
    approval_id = appr_resp.json()["id"]

    # Duplicate pending approval should be rejected
    dup_appr = client.post(
        "/api/v1/approvals",
        json={"transaction_id": txn_id, "reason": "Second request"},
    )
    assert dup_appr.status_code == 409

    # Decide approval: APPROVE
    decide_resp = client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json={
            "status": "APPROVED",
            "reviewer": "finance_lead",
            "reason": "Milestone verified against GitHub PR",
        },
    )
    assert decide_resp.status_code == 200
    decided_data = decide_resp.json()
    assert decided_data["status"] == "APPROVED"
    assert decided_data["reviewer"] == "finance_lead"
    assert decided_data["resolved_at"] is not None

    # Verify transaction decision was updated to ALLOW
    txn_after = client.get(f"/api/v1/transactions/{txn_id}").json()
    assert txn_after["decision"] == "ALLOW"

    # Resolving already resolved approval should return 409
    re_resolve = client.post(
        f"/api/v1/approvals/{approval_id}/decide",
        json={"status": "REJECTED", "reviewer": "other"},
    )
    assert re_resolve.status_code == 409


def test_audit_logs_api(client: TestClient) -> None:
    """Verify audit log creation and query endpoints."""
    # Create an audit entry
    resp_create = client.post(
        "/api/v1/audit-logs",
        json={
            "event_type": "MANUAL_SECURITY_AUDIT",
            "actor": "admin:secops",
            "details": {"action": "inspected_rules", "status": "all_clear"},
        },
    )
    assert resp_create.status_code == 201
    assert resp_create.json()["event_type"] == "MANUAL_SECURITY_AUDIT"

    # Query audit logs
    resp_list = client.get("/api/v1/audit-logs?event_type=MANUAL_SECURITY_AUDIT")
    assert resp_list.status_code == 200
    logs = resp_list.json()
    assert len(logs) >= 1
    assert logs[0]["event_type"] == "MANUAL_SECURITY_AUDIT"


def test_analytics_and_seed_endpoints(client: TestClient) -> None:
    """Verify analytics endpoints and demo seed generator."""
    # Test seed
    seed_resp = client.post("/api/v1/demo/seed?force=true")
    assert seed_resp.status_code == 201
    seed_data = seed_resp.json()
    assert seed_data["status"] == "success"
    assert len(seed_data["seeded_ids"]) >= 5

    # Test overview analytics
    overview_resp = client.get("/api/v1/analytics/overview")
    assert overview_resp.status_code == 200
    overview_data = overview_resp.json()
    assert overview_data["total_transactions"] >= 5
    assert "risk_distribution" in overview_data
    assert "total_authorized_amount" in overview_data
    assert "total_captured_amount" in overview_data
    assert len(overview_data["recent_activity"]) >= 1

    # Test security analytics
    security_resp = client.get("/api/v1/analytics/security")
    assert security_resp.status_code == 200
    security_data = security_resp.json()
    assert "threat_summary" in security_data
    assert security_data["metrics"]["prompt_injection_defense_rate"] == 100.0
    assert security_data["metrics"]["false_positive_rate"] == 0.0
    assert len(security_data["risk_histogram"]) == 5
    assert len(security_data["top_blocked_reasons"]) >= 1

