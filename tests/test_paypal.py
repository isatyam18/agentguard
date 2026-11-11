"""Tests for PayPal Orders v2 and Payments v2 client, authorization holds, capture, void, and error handling."""

from decimal import Decimal
import time
import pytest

from paypal.client import PayPalClient
from paypal.exceptions import (
    PayPalApiError,
    PayPalAuthError,
    PayPalDeclinedError,
    PayPalDuplicateCaptureError,
    PayPalInvalidResourceError,
    PayPalTimeoutError,
)
from paypal.orders import PayPalOrders
from paypal.payments import PayPalPayments


@pytest.fixture
def mock_client() -> PayPalClient:
    """Provide a PayPalClient configured in mock sandbox mode."""
    return PayPalClient(
        client_id="mock_client_id",
        client_secret="mock_client_secret",
        mode="mock",
    )


@pytest.fixture
def orders(mock_client: PayPalClient) -> PayPalOrders:
    """Provide PayPalOrders service instance."""
    return PayPalOrders(mock_client)


@pytest.fixture
def payments(mock_client: PayPalClient) -> PayPalPayments:
    """Provide PayPalPayments service instance."""
    return PayPalPayments(mock_client)


# ---------------------------------------------------------------------------
# 1. AUTHENTICATION & TOKEN CACHING TESTS
# ---------------------------------------------------------------------------

def test_oauth_token_retrieval_and_caching(mock_client: PayPalClient) -> None:
    """Verify OAuth2 token is retrieved and cached in memory across subsequent calls."""
    token1 = mock_client.get_access_token()
    assert token1.startswith("A21AA-MOCK-")

    # Second call should return the exact same cached token without re-fetching
    token2 = mock_client.get_access_token()
    assert token1 == token2

    # Forced refresh generates a fresh token
    token3 = mock_client.get_access_token(force_refresh=True)
    assert token3 != token1


def test_invalid_credentials(mock_client: PayPalClient) -> None:
    """Verify invalid client credentials raise PayPalAuthError."""
    bad_client = PayPalClient(
        client_id="invalid_client_id",
        client_secret="invalid_client_secret",
        mode="mock",
    )
    with pytest.raises(PayPalAuthError) as exc_info:
        bad_client.get_access_token()
    assert "INVALID_CLIENT" in exc_info.value.error_name


# ---------------------------------------------------------------------------
# 2. ORDERS V2: CREATE & INTENT: AUTHORIZE TESTS
# ---------------------------------------------------------------------------

def test_create_order_enforces_authorize_intent(orders: PayPalOrders) -> None:
    """Verify that orders are created strictly with 'intent: AUTHORIZE'."""
    amount = Decimal("75.00")
    order = orders.create_order(
        amount=amount,
        currency="USD",
        description="Compute engine reservation",
    )

    assert order["order_id"].startswith("MOCK-ORD-")
    assert order["status"] == "CREATED"
    assert order["intent"] == "AUTHORIZE"
    assert order["amount"] == amount
    assert order["approve_url"] is not None
    assert "token=" in order["approve_url"]


def test_create_order_rejects_non_positive_amounts(orders: PayPalOrders) -> None:
    """Verify order creation fails if amount <= 0."""
    with pytest.raises(ValueError):
        orders.create_order(amount=Decimal("0.00"))

    with pytest.raises(ValueError):
        orders.create_order(amount=Decimal("-10.00"))


def test_get_order_details(orders: PayPalOrders) -> None:
    """Verify retrieving order details by ID."""
    created = orders.create_order(amount=Decimal("30.00"))
    order_id = created["order_id"]

    details = orders.get_order(order_id)
    assert details["id"] == order_id
    assert details["status"] == "CREATED"
    assert details["intent"] == "AUTHORIZE"


def test_invalid_order_id(orders: PayPalOrders) -> None:
    """Verify non-existent order ID raises PayPalInvalidResourceError."""
    with pytest.raises(PayPalInvalidResourceError) as exc_info:
        orders.get_order("NON_EXISTENT_ORDER_ID_12345")
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# 3. AUTHORIZATION, CAPTURE & VOID LIFECYCLE TESTS
# ---------------------------------------------------------------------------

def test_successful_authorization(orders: PayPalOrders) -> None:
    """Verify successful authorization on an approved order."""
    amount = Decimal("50.00")
    created = orders.create_order(amount=amount)
    order_id = created["order_id"]

    auth_result = orders.authorize_order(order_id=order_id, expected_amount=amount)
    assert auth_result["order_id"] == order_id
    assert auth_result["authorization_id"].startswith("MOCK-AUTH-")
    assert auth_result["authorization_status"] == "CREATED"
    assert auth_result["amount"] == amount
    assert auth_result["currency"] == "USD"
    assert auth_result["expiration_time"] is not None


def test_successful_capture(orders: PayPalOrders, payments: PayPalPayments) -> None:
    """Verify successful capture against an authorized hold."""
    amount = Decimal("60.00")
    created = orders.create_order(amount=amount)
    auth_result = orders.authorize_order(created["order_id"], expected_amount=amount)
    auth_id = auth_result["authorization_id"]

    capture_result = payments.capture_authorization(
        authorization_id=auth_id,
        amount=amount,
        final_capture=True,
    )
    assert capture_result["capture_id"].startswith("MOCK-CAP-")
    assert capture_result["status"] == "COMPLETED"
    assert capture_result["authorization_id"] == auth_id
    assert capture_result["amount"] == amount


def test_successful_void(orders: PayPalOrders, payments: PayPalPayments) -> None:
    """Verify successful voiding of an authorization, releasing held funds."""
    amount = Decimal("40.00")
    created = orders.create_order(amount=amount)
    auth_result = orders.authorize_order(created["order_id"], expected_amount=amount)
    auth_id = auth_result["authorization_id"]

    void_result = payments.void_authorization(authorization_id=auth_id)
    assert void_result["authorization_id"] == auth_id
    assert void_result["status"] == "VOIDED"

    # Attempting to capture a voided authorization must fail
    with pytest.raises(PayPalApiError) as exc_info:
        payments.capture_authorization(authorization_id=auth_id)
    assert "voided" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# 4. SECURITY & PAYMENT RULES ENFORCEMENT TESTS
# ---------------------------------------------------------------------------

def test_declined_payment(orders: PayPalOrders) -> None:
    """Verify that a payment declined by PayPal raises PayPalDeclinedError."""
    # Amount 999.99 triggers simulated decline in mock sandbox
    with pytest.raises(PayPalDeclinedError) as exc_info:
        orders.create_order(amount=Decimal("999.99"))
    assert "declined" in str(exc_info.value).lower()


def test_duplicate_capture_prevention(orders: PayPalOrders, payments: PayPalPayments) -> None:
    """Verify that attempting to capture an authorization twice is prevented."""
    amount = Decimal("25.00")
    created = orders.create_order(amount=amount)
    auth_result = orders.authorize_order(created["order_id"], expected_amount=amount)
    auth_id = auth_result["authorization_id"]

    # First capture succeeds
    payments.capture_authorization(authorization_id=auth_id, amount=amount)

    # Second capture must be blocked with PayPalDuplicateCaptureError
    with pytest.raises(PayPalDuplicateCaptureError) as exc_info:
        payments.capture_authorization(authorization_id=auth_id, amount=amount)
    assert "already captured" in str(exc_info.value).lower()


def test_timeout_and_reconciliation(orders: PayPalOrders, payments: PayPalPayments, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that an ambiguous timeout triggers state reconciliation before retrying."""
    amount = Decimal("30.00")
    created = orders.create_order(amount=amount)
    auth_result = orders.authorize_order(created["order_id"], expected_amount=amount)
    auth_id = auth_result["authorization_id"]

    # Scenario A: Capture succeeded on PayPal server, but the network response timed out
    # Simulate timeout on the client request method
    def mock_request_with_timeout(*args, **kwargs):
        if kwargs.get("operation_name") == "CAPTURE_AUTHORIZATION":
            # Manually advance server state to simulate capture completing on PayPal side before timeout
            payments.client._mock_authorizations[auth_id]["status"] = "CAPTURED"
            raise PayPalTimeoutError("Network dropped during capture response", operation="CAPTURE", resource_id=auth_id)
        # Fall through to standard mock request
        return payments.client._handle_mock_request(kwargs["method"], kwargs["path"], kwargs.get("json_body", {}), kwargs.get("idempotency_key"))

    monkeypatch.setattr(payments.client, "request", mock_request_with_timeout)

    # Calling capture must reconcile state, see that it was captured, and return success without double-charging
    reconciled_capture = payments.capture_authorization(authorization_id=auth_id, amount=amount)
    assert reconciled_capture["status"] == "COMPLETED"
    assert reconciled_capture.get("reconciled") is True


def test_idempotency_key_returns_cached_response(orders: PayPalOrders) -> None:
    """Verify identical PayPal-Request-Id returns identical order."""
    idempotency_key = "idemp-test-uuid-999"
    order1 = orders.create_order(amount=Decimal("15.00"), idempotency_key=idempotency_key)
    order2 = orders.create_order(amount=Decimal("15.00"), idempotency_key=idempotency_key)

    assert order1["order_id"] == order2["order_id"]
