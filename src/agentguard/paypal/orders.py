"""PayPal Orders v2 integration module enforcing 'intent: AUTHORIZE' for escrow holds."""

from decimal import Decimal
from typing import Any, Dict, Optional
import uuid

from agentguard.core.logging import logger
from agentguard.paypal.client import PayPalClient
from agentguard.paypal.exceptions import PayPalApiError, PayPalDeclinedError


class PayPalOrders:
    """Manages order creation and authorization holds via PayPal Orders v2 API."""

    def __init__(self, client: PayPalClient) -> None:
        self.client = client

    def create_order(
        self,
        amount: Decimal,
        currency: str = "USD",
        reference_id: Optional[str] = None,
        custom_id: Optional[str] = None,
        description: str = "Guarded AI Agent Payment",
        return_url: str = "https://agentguard.local/checkout/success",
        cancel_url: str = "https://agentguard.local/checkout/cancel",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a PayPal order with 'intent: AUTHORIZE'.

        Enforces payment rule: Never use CAPTURE intent for the guarded purchase workflow.
        """
        if amount <= Decimal("0.00"):
            raise ValueError(f"Order amount must be positive, got {amount}.")

        order_ref = reference_id or str(uuid.uuid4())
        idempotency = idempotency_key or str(uuid.uuid4())

        payload = {
            "intent": "AUTHORIZE",  # Strictly AUTHORIZE, never CAPTURE
            "purchase_units": [
                {
                    "reference_id": order_ref,
                    "custom_id": custom_id or order_ref,
                    "description": description[:127],
                    "amount": {
                        "currency_code": currency.upper(),
                        "value": f"{amount:.2f}",
                    },
                }
            ],
            "application_context": {
                "return_url": return_url,
                "cancel_url": cancel_url,
                "user_action": "CONTINUE",
                "brand_name": "AgentGuard Escrow",
            },
        }

        logger.info(
            f"Creating PayPal order with intent: AUTHORIZE for amount ${amount:.2f} {currency}",
            extra={"event": "PAYPAL_CREATE_ORDER", "amount": str(amount), "reference_id": order_ref},
        )

        resp = self.client.request(
            method="POST",
            path="/v2/checkout/orders",
            json_body=payload,
            idempotency_key=idempotency,
            operation_name="CREATE_ORDER",
            resource_id=order_ref,
        )

        order_id = resp.get("id")
        status = resp.get("status")

        # Extract approval URL for buyer redirection
        approve_url = None
        for link in resp.get("links", []):
            if link.get("rel") == "approve":
                approve_url = link.get("href")

        return {
            "order_id": order_id,
            "status": status,
            "intent": resp.get("intent", "AUTHORIZE"),
            "amount": amount,
            "currency": currency.upper(),
            "approve_url": approve_url,
            "idempotency_key": idempotency,
            "raw_response": resp,
        }

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """Retrieve live order status from PayPal Orders v2."""
        clean_id = order_id.strip()
        resp = self.client.request(
            method="GET",
            path=f"/v2/checkout/orders/{clean_id}",
            operation_name="GET_ORDER",
            resource_id=clean_id,
        )
        return resp

    def authorize_order(
        self,
        order_id: str,
        expected_amount: Optional[Decimal] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Authorize the order after required buyer approval.

        Enforces payment rules:
        - Check actual authorization status and amount.
        - Do not interpret HTTP 2xx alone as proof of successful authorization.
        """
        clean_id = order_id.strip()
        idempotency = idempotency_key or str(uuid.uuid4())

        logger.info(
            f"Executing authorization on PayPal order '{clean_id}'",
            extra={"event": "PAYPAL_AUTHORIZE_ORDER", "order_id": clean_id},
        )

        resp = self.client.request(
            method="POST",
            path=f"/v2/checkout/orders/{clean_id}/authorize",
            json_body={},
            idempotency_key=idempotency,
            operation_name="AUTHORIZE_ORDER",
            resource_id=clean_id,
        )

        # Validate order-level status
        order_status = resp.get("status")
        purchase_units = resp.get("purchase_units", [])
        if not purchase_units:
            raise PayPalApiError(
                f"PayPal returned no purchase units for order '{clean_id}'.",
                raw_response=resp,
            )

        payments = purchase_units[0].get("payments", {})
        authorizations = payments.get("authorizations", [])

        if not authorizations:
            raise PayPalApiError(
                f"No authorization resource was returned for order '{clean_id}'.",
                raw_response=resp,
            )

        auth_resource = authorizations[0]
        auth_id = auth_resource.get("id")
        auth_status = auth_resource.get("status")
        auth_amount_val = auth_resource.get("amount", {}).get("value")
        auth_currency = auth_resource.get("amount", {}).get("currency_code")
        expiration_time = auth_resource.get("expiration_time")

        # Payment rule: Do not interpret HTTP 2xx alone as proof. Check status!
        if auth_status in ("DENIED", "FAILED", "DECLINED"):
            raise PayPalDeclinedError(
                f"PayPal authorization was {auth_status}.",
                error_name="AUTHORIZATION_DECLINED",
                raw_response=resp,
            )
        if auth_status not in ("CREATED", "PENDING"):
            raise PayPalApiError(
                f"Unexpected authorization status: '{auth_status}'. Expected 'CREATED' or 'PENDING'.",
                raw_response=resp,
            )

        # Check actual authorization amount against expected amount if provided
        if expected_amount is not None:
            actual_amount = Decimal(auth_amount_val)
            if actual_amount != expected_amount:
                raise PayPalApiError(
                    f"Authorized amount mismatch: expected ${expected_amount:.2f}, but authorized amount is ${actual_amount:.2f}.",
                    raw_response=resp,
                )

        return {
            "order_id": clean_id,
            "order_status": order_status,
            "authorization_id": auth_id,
            "authorization_status": auth_status,
            "amount": Decimal(auth_amount_val),
            "currency": auth_currency,
            "expiration_time": expiration_time,
            "raw_response": resp,
        }


def create_order(client: PayPalClient, **kwargs: Any) -> Dict[str, Any]:
    """Convenience functional wrapper for PayPalOrders.create_order."""
    return PayPalOrders(client).create_order(**kwargs)


def authorize_order(client: PayPalClient, **kwargs: Any) -> Dict[str, Any]:
    """Convenience functional wrapper for PayPalOrders.authorize_order."""
    return PayPalOrders(client).authorize_order(**kwargs)


def get_order(client: PayPalClient, order_id: str) -> Dict[str, Any]:
    """Convenience functional wrapper for PayPalOrders.get_order."""
    return PayPalOrders(client).get_order(order_id)

