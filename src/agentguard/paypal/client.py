"""Core PayPal HTTP client with OAuth2 token caching, idempotency, and error mapping."""

import base64
import time
import uuid
from typing import Any, Dict, Optional
import httpx

from agentguard.core.logging import logger
from agentguard.paypal.exceptions import (
    PayPalApiError,
    PayPalAuthError,
    PayPalDeclinedError,
    PayPalDuplicateCaptureError,
    PayPalInvalidResourceError,
    PayPalTimeoutError,
)

SANDBOX_BASE_URL = "https://api-m.sandbox.paypal.com"


class PayPalClient:
    """Manages authenticated communication with PayPal's sandbox APIs."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,  # [REDACTED]
        base_url: str = SANDBOX_BASE_URL,
        timeout: float = 10.0,
        mode: Optional[str] = None,
    ) -> None:
        from agentguard.core.config import get_settings
        settings = get_settings()

        cid = client_id if client_id is not None else settings.paypal_client_id
        sec = client_secret if client_secret is not None else settings.paypal_client_secret.get_secret_value()  # [REDACTED]
        configured_mode = (mode if mode is not None else settings.paypal_mode).lower()

        if not cid and configured_mode in ("mock", "sandbox"):
            cid = "mock_client_id"
            sec = "mock_client_secret"  # [REDACTED]

        self.client_id = cid.strip()
        self.client_secret = sec.strip()  # [REDACTED]
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.mode = configured_mode

        # Token cache: (token_str, expiration_timestamp)
        self._cached_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        # Memory store for mock sandbox state machine
        self._mock_orders: Dict[str, Dict[str, Any]] = {}
        self._mock_authorizations: Dict[str, Dict[str, Any]] = {}
        self._mock_captures: Dict[str, Dict[str, Any]] = {}
        self._mock_idempotency_keys: Dict[str, Dict[str, Any]] = {}

    @property
    def is_mock_mode(self) -> bool:
        """Return True if running in local high-fidelity mock mode."""
        return (
            self.mode == "mock"
            or not self.client_id
            or self.client_id.startswith("mock_")
        )

    def get_access_token(self, force_refresh: bool = False) -> str:
        """Retrieve valid OAuth2 access token, using in-memory cache with TTL buffer."""
        now = time.time()
        # 300-second (5 minute) buffer before true expiration
        if not force_refresh and self._cached_token and now < self._token_expires_at:
            return self._cached_token

        if self.is_mock_mode:
            # Check for simulated invalid credentials
            if self.client_id == "invalid_client_id" or self.client_secret == "invalid_client_secret":  # [REDACTED]
                raise PayPalAuthError(
                    "Client Authentication failed (simulated invalid credentials).",
                    status_code=401,
                    error_name="INVALID_CLIENT",
                )
            self._cached_token = f"A21AA-MOCK-SANDBOX-TOKEN-{uuid.uuid4().hex[:12]}"  # [REDACTED]
            self._token_expires_at = now + 32400 - 300  # ~9 hours minus 5 min buffer
            return self._cached_token

        # Live Sandbox OAuth2 request
        basic_creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")  # [REDACTED]
        ).decode("utf-8")

        headers = {
            "Authorization": f"Basic {basic_creds}",  # [REDACTED]
            "Content-Type": "application/x-www-form-urlencoded",
        }
        data = {"grant_type": "client_credentials"}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/v1/oauth2/token",
                    headers=headers,
                    data=data,
                )
        except httpx.TimeoutException as exc:
            raise PayPalTimeoutError(
                "OAuth2 token request timed out.", operation="GET_TOKEN", resource_id="oauth"
            ) from exc
        except Exception as exc:
            raise PayPalAuthError(f"OAuth2 network error: {exc}") from exc

        if resp.status_code == 401:
            raise PayPalAuthError(
                "Invalid PayPal client credentials.",
                status_code=401,
                error_name="INVALID_CLIENT",
                raw_response=resp.json() if resp.content else {},
            )
        if resp.status_code != 200:
            raise PayPalAuthError(
                f"OAuth2 token request failed with status {resp.status_code}.",
                status_code=resp.status_code,
                raw_response=resp.json() if resp.content else {},
            )

        token_data = resp.json()
        token = token_data["access_token"]  # [REDACTED]
        expires_in = int(token_data.get("expires_in", 32400))

        self._cached_token = token
        self._token_expires_at = now + expires_in - 300
        return token

    def request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        operation_name: str = "PAYPAL_REQUEST",
        resource_id: str = "",
    ) -> Dict[str, Any]:
        """Execute authenticated HTTP request to PayPal with idempotency and error handling."""
        token = self.get_access_token()  # [REDACTED]

        if self.is_mock_mode:
            return self._handle_mock_request(
                method=method.upper(),
                path=path,
                json_body=json_body or {},
                idempotency_key=idempotency_key,
            )

        headers = {
            "Authorization": f"Bearer {token}",  # [REDACTED]
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if idempotency_key:
            headers["PayPal-Request-Id"] = idempotency_key

        url = f"{self.base_url}{path}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(
                    method=method.upper(),
                    url=url,
                    headers=headers,
                    json=json_body,
                )
        except httpx.TimeoutException as exc:
            logger.error(
                f"PayPal operation '{operation_name}' on resource '{resource_id}' timed out.",
                extra={"event": "PAYPAL_TIMEOUT", "operation": operation_name, "resource_id": resource_id},
            )
            raise PayPalTimeoutError(
                f"PayPal request '{operation_name}' on '{resource_id}' timed out.",
                operation=operation_name,
                resource_id=resource_id,
            ) from exc
        except Exception as exc:
            raise PayPalApiError(f"PayPal network error during {operation_name}: {exc}") from exc

        return self._parse_response(resp)

    def _parse_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Map PayPal HTTP response codes and error bodies to typed exceptions."""
        if response.status_code in (200, 201):
            return response.json()
        if response.status_code == 204:
            return {"status": "SUCCESS", "status_code": 204}

        # Error response parsing
        error_data = {}
        try:
            error_data = response.json()
        except Exception:
            error_data = {"raw_text": response.text}

        name = error_data.get("name", "UNKNOWN_ERROR")
        message = error_data.get("message", response.text)
        details = error_data.get("details", [])

        # Check for duplicate capture
        issue_names = [d.get("issue") for d in details if isinstance(d, dict)]
        if "AUTHORIZATION_ALREADY_CAPTURED" in issue_names or name == "AUTHORIZATION_ALREADY_CAPTURED":
            raise PayPalDuplicateCaptureError(
                "Authorization has already been captured.",
                status_code=response.status_code,
                error_name=name,
                details=details,
                raw_response=error_data,
            )

        if response.status_code == 404 or name == "RESOURCE_NOT_FOUND":
            raise PayPalInvalidResourceError(
                f"PayPal resource not found: {message}",
                status_code=response.status_code,
                error_name=name,
                details=details,
                raw_response=error_data,
            )

        if name == "TRANSACTION_REFUSED" or "DECLINED" in name:
            raise PayPalDeclinedError(
                f"PayPal declined payment: {message}",
                status_code=response.status_code,
                error_name=name,
                details=details,
                raw_response=error_data,
            )

        raise PayPalApiError(
            f"PayPal API error ({response.status_code}): {name} - {message}",
            status_code=response.status_code,
            error_name=name,
            details=details,
            raw_response=error_data,
        )

    # -----------------------------------------------------------------------
    # HIGH-FIDELITY MOCK SANDBOX SIMULATOR
    # -----------------------------------------------------------------------

    def _handle_mock_request(
        self,
        method: str,
        path: str,
        json_body: Dict[str, Any],
        idempotency_key: Optional[str],
    ) -> Dict[str, Any]:
        """Faithfully simulate PayPal Orders v2 and Payments v2 state transitions."""
        # 1. Idempotency Check
        if idempotency_key and idempotency_key in self._mock_idempotency_keys:
            return self._mock_idempotency_keys[idempotency_key]

        # 2. Orders v2: Create Order (POST /v2/checkout/orders)
        if method == "POST" and path == "/v2/checkout/orders":
            intent = json_body.get("intent")
            if intent != "AUTHORIZE":
                raise ValueError(
                    f"AgentGuard payment rules prohibit '{intent}' intent. Only 'AUTHORIZE' is allowed."
                )

            # Simulated declined payment trigger for testing
            amount_val = json_body.get("purchase_units", [{}])[0].get("amount", {}).get("value")
            if amount_val == "999.99":
                raise PayPalDeclinedError(
                    "PayPal payment declined (simulated decline).",
                    status_code=400,
                    error_name="TRANSACTION_REFUSED",
                )

            order_id = f"MOCK-ORD-{uuid.uuid4().hex[:12].upper()}"
            order = {
                "id": order_id,
                "status": "CREATED",
                "intent": "AUTHORIZE",
                "purchase_units": json_body.get("purchase_units", []),
                "create_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "links": [
                    {
                        "href": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}",  # [REDACTED]
                        "rel": "approve",
                        "method": "GET",
                    },
                    {
                        "href": f"https://api-m.sandbox.paypal.com/v2/checkout/orders/{order_id}/authorize",
                        "rel": "authorize",
                        "method": "POST",
                    },
                ],
            }
            self._mock_orders[order_id] = order
            if idempotency_key:
                self._mock_idempotency_keys[idempotency_key] = order
            return order

        # 3. Orders v2: Retrieve Order (GET /v2/checkout/orders/{id})
        if method == "GET" and path.startswith("/v2/checkout/orders/"):
            order_id = path.replace("/v2/checkout/orders/", "").strip()
            if order_id not in self._mock_orders:
                raise PayPalInvalidResourceError(
                    f"Order '{order_id}' does not exist.",
                    status_code=404,
                    error_name="RESOURCE_NOT_FOUND",
                )
            return self._mock_orders[order_id]

        # 4. Orders v2: Authorize Order (POST /v2/checkout/orders/{id}/authorize)
        if method == "POST" and "/v2/checkout/orders/" in path and path.endswith("/authorize"):
            order_id = path.split("/")[4].strip()
            if order_id not in self._mock_orders:
                raise PayPalInvalidResourceError(
                    f"Order '{order_id}' does not exist.",
                    status_code=404,
                    error_name="RESOURCE_NOT_FOUND",
                )

            auth_id = f"MOCK-AUTH-{uuid.uuid4().hex[:12].upper()}"
            order = self._mock_orders[order_id]
            amount = order.get("purchase_units", [{}])[0].get("amount", {"currency_code": "USD", "value": "100.00"})

            auth_obj = {
                "id": auth_id,
                "status": "CREATED",
                "amount": amount,
                "order_id": order_id,
                "create_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "expiration_time": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 86400 * 29)
                ),
            }
            self._mock_authorizations[auth_id] = auth_obj
            order["status"] = "COMPLETED"
            order["purchase_units"][0]["payments"] = {"authorizations": [auth_obj]}

            result = {
                "id": order_id,
                "status": "COMPLETED",
                "purchase_units": order["purchase_units"],
            }
            if idempotency_key:
                self._mock_idempotency_keys[idempotency_key] = result
            return result

        # 5. Payments v2: Capture Authorization (POST /v2/payments/authorizations/{id}/capture)
        if method == "POST" and "/v2/payments/authorizations/" in path and path.endswith("/capture"):
            auth_id = path.split("/")[4].strip()
            if auth_id not in self._mock_authorizations:
                if auth_id.startswith("MOCK-AUTH-"):
                    self._mock_authorizations[auth_id] = {
                        "id": auth_id,
                        "status": "CREATED",
                        "amount": {"currency_code": "USD", "value": json_body.get("amount", {}).get("value", "150.00")},
                    }
                else:
                    raise PayPalInvalidResourceError(
                        f"Authorization '{auth_id}' not found.",
                        status_code=404,
                        error_name="RESOURCE_NOT_FOUND",
                    )

            auth = self._mock_authorizations[auth_id]
            if auth["status"] == "CAPTURED":
                raise PayPalDuplicateCaptureError(
                    f"Authorization '{auth_id}' has already been captured.",
                    status_code=422,
                    error_name="AUTHORIZATION_ALREADY_CAPTURED",
                    details=[{"issue": "AUTHORIZATION_ALREADY_CAPTURED"}],
                )
            if auth["status"] == "VOIDED":
                raise PayPalApiError(
                    f"Authorization '{auth_id}' is voided and cannot be captured.",
                    status_code=422,
                    error_name="AUTHORIZATION_VOIDED",
                )

            capture_id = f"MOCK-CAP-{uuid.uuid4().hex[:12].upper()}"
            auth["status"] = "CAPTURED"
            capture_obj = {
                "id": capture_id,
                "status": "COMPLETED",
                "amount": auth["amount"],
                "final_capture": json_body.get("final_capture", True),
                "create_time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self._mock_captures[capture_id] = capture_obj
            if idempotency_key:
                self._mock_idempotency_keys[idempotency_key] = capture_obj
            return capture_obj

        # 6. Payments v2: Void Authorization (POST /v2/payments/authorizations/{id}/void)
        if method == "POST" and "/v2/payments/authorizations/" in path and path.endswith("/void"):
            auth_id = path.split("/")[4].strip()
            if auth_id not in self._mock_authorizations:
                if auth_id.startswith("MOCK-AUTH-"):
                    self._mock_authorizations[auth_id] = {
                        "id": auth_id,
                        "status": "CREATED",
                        "amount": {"currency_code": "USD", "value": "150.00"},
                    }
                else:
                    raise PayPalInvalidResourceError(
                        f"Authorization '{auth_id}' not found.",
                        status_code=404,
                        error_name="RESOURCE_NOT_FOUND",
                    )

            auth = self._mock_authorizations[auth_id]
            if auth["status"] == "CAPTURED":
                raise PayPalApiError(
                    f"Cannot void already captured authorization '{auth_id}'.",
                    status_code=422,
                    error_name="AUTHORIZATION_ALREADY_CAPTURED",
                )
            auth["status"] = "VOIDED"
            return {"status": "SUCCESS", "authorization_id": auth_id, "status_code": 204}

        # 7. Payments v2: Retrieve Authorization (GET /v2/payments/authorizations/{id})
        if method == "GET" and path.startswith("/v2/payments/authorizations/"):
            auth_id = path.replace("/v2/payments/authorizations/", "").strip()
            if auth_id not in self._mock_authorizations:
                if auth_id.startswith("MOCK-AUTH-"):
                    self._mock_authorizations[auth_id] = {
                        "id": auth_id,
                        "status": "CREATED",
                        "amount": {"currency_code": "USD", "value": "150.00"},
                    }
                else:
                    raise PayPalInvalidResourceError(
                        f"Authorization '{auth_id}' not found.",
                        status_code=404,
                        error_name="RESOURCE_NOT_FOUND",
                    )
            return self._mock_authorizations[auth_id]

        raise NotImplementedError(f"Mock endpoint '{method} {path}' not implemented.")
