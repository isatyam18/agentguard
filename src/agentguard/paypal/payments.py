"""PayPal Payments v2 integration module for capturing or voiding authorized escrow holds."""

from decimal import Decimal
from typing import Any, Dict, Optional, Set
import uuid

from agentguard.core.logging import logger
from agentguard.paypal.client import PayPalClient
from agentguard.paypal.exceptions import (
    PayPalApiError,
    PayPalDeclinedError,
    PayPalDuplicateCaptureError,
    PayPalTimeoutError,
)


class PayPalPayments:
    """Manages authorization capture, voiding, and timeout reconciliation via Payments v2."""

    def __init__(self, client: PayPalClient) -> None:
        self.client = client
        # In-process cache of captured authorization IDs to prevent duplicate capture operations
        self._captured_authorizations: Set[str] = set()

    def get_authorization(self, authorization_id: str) -> Dict[str, Any]:
        """Retrieve live authorization details from PayPal Payments v2."""
        clean_id = authorization_id.strip()
        resp = self.client.request(
            method="GET",
            path=f"/v2/payments/authorizations/{clean_id}",
            operation_name="GET_AUTHORIZATION",
            resource_id=clean_id,
        )
        return resp

    def capture_authorization(
        self,
        authorization_id: str,
        amount: Optional[Decimal] = None,
        currency: str = "USD",
        final_capture: bool = True,
        note_to_payer: str = "AgentGuard verified release condition satisfied.",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Capture an authorized payment after AgentGuard approval.

        Enforces payment rules:
        - Never capture automatically before AgentGuard approval.
        - Prevent duplicate capture operations.
        - Check actual capture status and amount.
        - Never retry blindly after an ambiguous timeout; reconcile state first.
        """
        clean_id = authorization_id.strip()

        # Rule: Prevent duplicate capture operations locally
        if clean_id in self._captured_authorizations:
            raise PayPalDuplicateCaptureError(
                f"Duplicate capture prevented: authorization '{clean_id}' was already captured.",
                status_code=422,
                error_name="AUTHORIZATION_ALREADY_CAPTURED",
            )

        idempotency = idempotency_key or str(uuid.uuid4())

        payload: Dict[str, Any] = {
            "final_capture": final_capture,
            "note_to_payer": note_to_payer[:255],
        }
        if amount is not None:
            if amount <= Decimal("0.00"):
                raise ValueError(f"Capture amount must be positive, got {amount}.")
            payload["amount"] = {
                "currency_code": currency.upper(),
                "value": f"{amount:.2f}",
            }

        logger.info(
            f"Initiating capture on PayPal authorization '{clean_id}'",
            extra={"event": "PAYPAL_CAPTURE", "authorization_id": clean_id, "idempotency_key": idempotency},
        )

        try:
            resp = self.client.request(
                method="POST",
                path=f"/v2/payments/authorizations/{clean_id}/capture",
                json_body=payload,
                idempotency_key=idempotency,
                operation_name="CAPTURE_AUTHORIZATION",
                resource_id=clean_id,
            )
        except PayPalTimeoutError:
            # Rule: Never retry a money-moving request blindly after an ambiguous timeout!
            logger.warning(
                f"Capture request on '{clean_id}' timed out; performing state reconciliation before retry.",
                extra={"event": "PAYPAL_RECONCILE_TIMEOUT", "authorization_id": clean_id},
            )
            # Query authorization status to check if capture landed on PayPal
            reconciled = self.get_authorization(clean_id)
            reconciled_status = reconciled.get("status")
            if reconciled_status == "CAPTURED":
                self._captured_authorizations.add(clean_id)
                return {
                    "capture_id": reconciled.get("id", clean_id),
                    "status": "COMPLETED",
                    "authorization_id": clean_id,
                    "reconciled": True,
                    "raw_response": reconciled,
                }
            # Still not captured or in unknown state: raise timeout error to prevent blind double-charging
            raise PayPalTimeoutError(
                f"Ambiguous timeout on capture for '{clean_id}'. Current status is '{reconciled_status}'. Manual review required.",
                operation="CAPTURE_AUTHORIZATION",
                resource_id=clean_id,
            )

        capture_id = resp.get("id")
        status = resp.get("status")

        # Payment Rule: Check actual status. Do not rely on HTTP 2xx alone!
        if status in ("DECLINED", "FAILED"):
            raise PayPalDeclinedError(
                f"PayPal capture was {status}.",
                error_name="CAPTURE_DECLINED",
                raw_response=resp,
            )
        if status not in ("COMPLETED", "PENDING"):
            raise PayPalApiError(
                f"Unexpected capture status: '{status}'. Expected 'COMPLETED' or 'PENDING'.",
                raw_response=resp,
            )

        # Mark as captured locally to prevent duplicates
        self._captured_authorizations.add(clean_id)

        captured_amount_str = resp.get("amount", {}).get("value")
        captured_amount = Decimal(captured_amount_str) if captured_amount_str else amount

        return {
            "capture_id": capture_id,
            "status": status,
            "authorization_id": clean_id,
            "amount": captured_amount,
            "currency": resp.get("amount", {}).get("currency_code", currency.upper()),
            "idempotency_key": idempotency,
            "raw_response": resp,
        }

    def void_authorization(
        self,
        authorization_id: str,
        note_to_payer: str = "AgentGuard released hold back to buyer.",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Void an active authorization, releasing held funds back to the buyer."""
        clean_id = authorization_id.strip()
        idempotency = idempotency_key or str(uuid.uuid4())

        logger.info(
            f"Voiding authorization hold '{clean_id}'",
            extra={"event": "PAYPAL_VOID", "authorization_id": clean_id},
        )

        resp = self.client.request(
            method="POST",
            path=f"/v2/payments/authorizations/{clean_id}/void",
            json_body={"note_to_payer": note_to_payer[:255]},
            idempotency_key=idempotency,
            operation_name="VOID_AUTHORIZATION",
            resource_id=clean_id,
        )

        return {
            "authorization_id": clean_id,
            "status": "VOIDED",
            "idempotency_key": idempotency,
            "raw_response": resp,
        }


def capture_authorization(client: PayPalClient, **kwargs: Any) -> Dict[str, Any]:
    """Convenience functional wrapper for PayPalPayments.capture_authorization."""
    return PayPalPayments(client).capture_authorization(**kwargs)


def void_authorization(client: PayPalClient, **kwargs: Any) -> Dict[str, Any]:
    """Convenience functional wrapper for PayPalPayments.void_authorization."""
    return PayPalPayments(client).void_authorization(**kwargs)


def get_authorization(client: PayPalClient, authorization_id: str) -> Dict[str, Any]:
    """Convenience functional wrapper for PayPalPayments.get_authorization."""
    return PayPalPayments(client).get_authorization(authorization_id)

