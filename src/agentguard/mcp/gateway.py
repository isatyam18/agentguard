"""AgentGuard MCP Gateway implementation.

Coordinates schema validation, deterministic policy firewall evaluation,
invoice security scanning, database persistence, and PayPal authorization holding.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import threading
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from agentguard.core.config import get_settings
from agentguard.core.database import SessionFactory
from agentguard.core.decision_engine import DecisionEngine
from agentguard.core.logging import logger
from agentguard.core.policy_engine import (
    PolicyConfig,
    PurchaseRequest,
    SpendingContext,
)
from agentguard.mcp.schemas import (
    InvoiceData,
    PendingApprovalItem,
    PendingApprovalsResponse,
    PurchaseDecisionResponse,
    PurchaseRequestInput,
    TransactionStatusResponse,
)
from agentguard.models.approval import Approval
from agentguard.models.audit_log import AuditLog
from agentguard.models.policy import Policy
from agentguard.models.transaction import Transaction
from agentguard.paypal.client import PayPalClient
from agentguard.paypal.orders import authorize_order, create_order
from agentguard.security.invoice_scanner import InvoiceScanner
from agentguard.security.schemas import ContactDetails, InvoiceLineItem, NormalizedInvoice


# Process-wide lock guarding atomic velocity checks, spending limits, and transaction registration
_PURCHASE_LOCK = threading.Lock()


class AgentGuardMCPGateway:
    """Guarded gateway mediating between autonomous AI buyer agents and payment rails."""

    def __init__(self, session: Optional[Session] = None, paypal_client: Optional[PayPalClient] = None):
        self._external_session = session
        self._paypal_client = paypal_client

    def _get_session(self) -> Session:
        return self._external_session or SessionFactory()

    async def request_purchase(
        self,
        merchant_id: str,
        merchant_name: str,
        amount: str,
        currency: str = "USD",
        description: str = "",
        invoice: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process an untrusted purchase request through policy firewall and invoice scanner."""
        # 1. Validate request schema and bounds
        try:
            raw_input = {
                "merchant_id": merchant_id,
                "merchant_name": merchant_name,
                "amount": amount,
                "currency": currency,
                "description": description,
                "invoice": invoice,
                "idempotency_key": idempotency_key,
            }
            validated_input = PurchaseRequestInput.model_validate(raw_input)
        except Exception as val_err:
            logger.warning(f"MCP purchase validation rejected: {val_err}")
            return {
                "error": "SCHEMA_VALIDATION_ERROR",
                "message": str(val_err),
                "decision": "BLOCK",
                "payment_status": "BLOCKED",
            }

        amount_dec = Decimal(validated_input.amount)
        norm_currency = validated_input.currency.upper()

        # 2. Generate unique references and idempotency handles
        external_ref = validated_input.idempotency_key or f"TXN-AG-{uuid.uuid4().hex[:12].upper()}"
        transaction_id = str(uuid.uuid4())

        # Atomic lock serializing velocity checking, policy evaluation, and transaction registration
        _PURCHASE_LOCK.acquire()
        session = self._get_session()
        owns_session = self._external_session is None

        try:
            # 3. Prevent replayed requests / check existing idempotency
            existing_txn = (
                session.query(Transaction)
                .filter(Transaction.external_reference == external_ref)
                .first()
            )
            if existing_txn:
                logger.info(
                    f"Idempotent replay detected for external reference '{external_ref}'. Returning cached outcome."
                )
                appr = (
                    session.query(Approval)
                    .filter(Approval.transaction_id == existing_txn.id)
                    .first()
                )
                return PurchaseDecisionResponse(
                    decision=existing_txn.decision,  # type: ignore[arg-type]
                    payment_status=existing_txn.payment_status,
                    transaction_id=existing_txn.id,
                    external_reference=existing_txn.external_reference,
                    risk_score=int(existing_txn.risk_score * 100),
                    reasons=["IDEMPOTENT_REPLAY: Returning cached transaction outcome."],
                    policy_violations=[],
                    security_threats=[],
                    requires_human_approval=(existing_txn.payment_status == "HELD"),
                    approval_id=appr.id if appr else None,
                    paypal_order_id=existing_txn.paypal_order_id,
                    paypal_authorization_id=existing_txn.paypal_authorization_id,
                    created_at=existing_txn.created_at.isoformat(),
                ).model_dump()

            # 4. Fetch active buyer policies
            active_policy_model = (
                session.query(Policy).filter(Policy.is_active.is_(True)).first()
            )
            if active_policy_model:
                policy_config = PolicyConfig(
                    max_transaction_amount=active_policy_model.max_transaction_amount,
                    daily_spending_limit=active_policy_model.daily_spending_limit,
                    allowed_merchants=active_policy_model.allowed_merchants or [],
                    require_human_approval=active_policy_model.require_human_approval,
                    is_active=active_policy_model.is_active,
                    policy_version="1.0",
                )
            else:
                # Default buyer policy configuration per hackathon specification
                policy_config = PolicyConfig(
                    max_transaction_amount=Decimal("100.00"),
                    daily_spending_limit=Decimal("500.00"),
                    allowed_merchants=[],
                    require_human_approval=False,
                    is_active=True,
                    policy_version="1.0",
                )

            # 5. Compute velocity context (daily cumulative spending and recent attempt count)
            now = datetime.now(timezone.utc)
            start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
            spent_query = session.query(
                func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))
            ).filter(
                Transaction.decision != "BLOCK",
                Transaction.payment_status != "BLOCKED",
                Transaction.created_at >= start_of_day,
            )
            daily_spent = Decimal(spent_query.scalar() or "0.00")

            one_hour_ago = now - timedelta(hours=1)
            recent_attempts = (
                session.query(func.count(Transaction.id))
                .filter(Transaction.created_at >= one_hour_ago)
                .scalar()
                or 0
            )

            # 6. Run deterministic policy engine
            policy_request = PurchaseRequest(
                amount=amount_dec,
                currency=norm_currency,
                merchant_name=validated_input.merchant_name,
                merchant_id=validated_input.merchant_id,
                description=validated_input.description,
                external_reference=external_ref,
            )
            spending_context = SpendingContext(
                daily_cumulative_spent=daily_spent,
                recent_attempt_count=recent_attempts,
            )
            policy_decision = DecisionEngine.evaluate(
                request=policy_request,
                policy=policy_config,
                context=spending_context,
            )

            # 7. Run invoice security analysis
            invoice_dict = validated_input.invoice or {}
            if isinstance(invoice_dict, InvoiceData):
                invoice_dict = invoice_dict.model_dump()

            line_items_data: List[InvoiceLineItem] = []
            raw_items = invoice_dict.get("line_items") or []
            for item in raw_items:
                line_items_data.append(
                    InvoiceLineItem(
                        description=str(item.get("description", "Item")),
                        quantity=Decimal(str(item.get("quantity", "1"))),
                        unit_price=Decimal(str(item.get("unit_price", amount_dec))),
                        total=Decimal(str(item.get("total", amount_dec))),
                    )
                )

            raw_contact = invoice_dict.get("contact_details")
            contact_obj = None
            if isinstance(raw_contact, dict):
                contact_obj = ContactDetails(
                    email=raw_contact.get("email"),
                    phone=raw_contact.get("phone"),
                    support_url=raw_contact.get("support_url"),
                    address=raw_contact.get("address"),
                )

            normalized_invoice = NormalizedInvoice(
                invoice_id=invoice_dict.get("invoice_id")
                or f"INV-{uuid.uuid4().hex[:8].upper()}",
                merchant_name=validated_input.merchant_name,
                merchant_id=validated_input.merchant_id,
                amount=amount_dec,
                currency=norm_currency,
                description=validated_input.description
                or str(invoice_dict.get("description", "")),
                line_items=line_items_data,
                notes=str(invoice_dict.get("notes", "")),
                payment_instructions=str(invoice_dict.get("payment_instructions", "")),
                contact_details=contact_obj,
            )
            scan_result = InvoiceScanner.scan(normalized_invoice)

            # 8. Merge security findings without reducing policy restrictions
            # Invariant: An explicit policy BLOCK cannot be downgraded
            # Invariant: A security BLOCK cannot be downgraded
            # Invariant: A REVIEW decision cannot be converted to APPROVE
            final_decision: str = "APPROVE"
            requires_human_approval = False

            if policy_decision.decision == "BLOCK" or scan_result.recommended_action == "BLOCK":
                final_decision = "BLOCK"
            elif (
                policy_decision.decision == "REVIEW"
                or scan_result.recommended_action == "REVIEW"
                or scan_result.is_suspicious
                or policy_config.require_human_approval
            ):
                final_decision = "REVIEW"
                requires_human_approval = True
            else:
                final_decision = "APPROVE"

            # Compute composite risk score
            scanner_severity_weights = {
                "CRITICAL": 98,
                "HIGH": 80,
                "MEDIUM": 50,
                "LOW": 10,
            }
            scanner_implied_score = scanner_severity_weights.get(scan_result.severity, 10)
            final_risk_score = max(policy_decision.risk_score, scanner_implied_score)

            # Escalate high-risk unblocked transactions to human review
            if final_risk_score >= 50 and final_decision == "APPROVE":
                final_decision = "REVIEW"
                requires_human_approval = True

            merged_reasons = list(policy_decision.reasons)
            for ev in scan_result.evidence:
                merged_reasons.append(f"SECURITY_EVIDENCE: {ev}")

            merged_violations = list(policy_decision.policy_violations)
            security_threats = list(scan_result.threat_categories)

            # 9. Store transaction and audit records
            payment_status = (
                "BLOCKED"
                if final_decision == "BLOCK"
                else ("HELD" if final_decision == "REVIEW" else "PENDING")
            )

            txn_record = Transaction(
                id=transaction_id,
                external_reference=external_ref,
                merchant_name=validated_input.merchant_name,
                merchant_id=validated_input.merchant_id,
                amount=amount_dec,
                currency=norm_currency,
                description=validated_input.description,
                risk_score=Decimal(final_risk_score) / Decimal("100.00"),
                decision=final_decision,
                payment_status=payment_status,
            )
            session.add(txn_record)

            # Append initial audit trail events
            audit_events = [
                AuditLog(
                    transaction_id=transaction_id,
                    event_type="MCP_PURCHASE_REQUEST",
                    actor="mcp_buyer_agent",
                    details={
                        "merchant_id": validated_input.merchant_id,
                        "merchant_name": validated_input.merchant_name,
                        "amount": str(amount_dec),
                        "currency": norm_currency,
                        "description": validated_input.description,
                    },
                ),
                AuditLog(
                    transaction_id=transaction_id,
                    event_type="POLICY_FIREWALL_EVALUATION",
                    actor="policy_firewall",
                    details={
                        "policy_decision": policy_decision.decision,
                        "policy_violations": merged_violations,
                        "policy_risk_score": policy_decision.risk_score,
                    },
                ),
                AuditLog(
                    transaction_id=transaction_id,
                    event_type="INVOICE_SECURITY_SCAN",
                    actor="invoice_scanner",
                    details={
                        "scanner_action": scan_result.recommended_action,
                        "scanner_threats": security_threats,
                        "scanner_severity": scan_result.severity,
                        "scanner_confidence": scan_result.confidence,
                    },
                ),
                AuditLog(
                    transaction_id=transaction_id,
                    event_type="DECISION_FINALIZED",
                    actor="decision_engine",
                    details={
                        "final_decision": final_decision,
                        "final_risk_score": final_risk_score,
                        "requires_human_approval": requires_human_approval,
                    },
                ),
            ]
            session.add_all(audit_events)
            session.flush()

            # 10. Handle BLOCK outcome: Never call payment rails
            if final_decision == "BLOCK":
                session.commit()
                return PurchaseDecisionResponse(
                    decision="BLOCK",
                    payment_status="BLOCKED",
                    transaction_id=transaction_id,
                    external_reference=external_ref,
                    risk_score=final_risk_score,
                    reasons=merged_reasons,
                    policy_violations=merged_violations,
                    security_threats=security_threats,
                    requires_human_approval=False,
                    approval_id=None,
                    paypal_order_id=None,
                    paypal_authorization_id=None,
                    created_at=txn_record.created_at.isoformat(),
                ).model_dump()

            # 11. Handle REVIEW outcome: Create approval task
            approval_id: Optional[str] = None
            if final_decision == "REVIEW":
                approval_id = str(uuid.uuid4())
                reason_str = "; ".join(merged_reasons) or "Human review required by policy."
                approval_record = Approval(
                    id=approval_id,
                    transaction_id=transaction_id,
                    status="PENDING",
                    reason=reason_str[:500],
                )
                session.add(approval_record)
                session.commit()

                return PurchaseDecisionResponse(
                    decision="REVIEW",
                    payment_status="HELD",
                    transaction_id=transaction_id,
                    external_reference=external_ref,
                    risk_score=final_risk_score,
                    reasons=merged_reasons,
                    policy_violations=merged_violations,
                    security_threats=security_threats,
                    requires_human_approval=True,
                    approval_id=approval_id,
                    paypal_order_id=None,
                    paypal_authorization_id=None,
                    created_at=txn_record.created_at.isoformat(),
                ).model_dump()

            # 12. Handle APPROVE outcome: Execute PayPal AUTHORIZE workflow
            paypal_client = self._paypal_client or PayPalClient(timeout=10.0)
            order = create_order(
                client=paypal_client,
                amount=amount_dec,
                currency=norm_currency,
                description=validated_input.description or f"Payment for {validated_input.merchant_name}",
                custom_id=transaction_id,
                idempotency_key=f"AG-ORD-{transaction_id}",
            )
            paypal_order_id = order.get("order_id") or order.get("id")

            # Execute authorization to place native hold on buyer funds
            auth_resp = authorize_order(
                client=paypal_client,
                order_id=paypal_order_id,  # type: ignore[arg-type]
                expected_amount=amount_dec,
                idempotency_key=f"AG-AUTH-{transaction_id}",
            )
            paypal_auth_id = (
                auth_resp.get("authorization_id")
                or auth_resp.get("id")
                or (
                    auth_resp.get("purchase_units", [{}])[0]
                    .get("payments", {})
                    .get("authorizations", [{}])[0]
                    .get("id")
                )
            )

            txn_record.paypal_order_id = paypal_order_id
            txn_record.paypal_authorization_id = paypal_auth_id
            txn_record.payment_status = "AUTHORIZED"

            auth_audit = AuditLog(
                transaction_id=transaction_id,
                event_type="PAYPAL_AUTHORIZATION_HELD",
                actor="paypal_adapter",
                details={
                    "paypal_order_id": paypal_order_id,
                    "paypal_authorization_id": paypal_auth_id,
                    "status": "AUTHORIZED",
                },
            )
            session.add(auth_audit)
            session.commit()

            return PurchaseDecisionResponse(
                decision="APPROVE",
                payment_status="AUTHORIZED",
                transaction_id=transaction_id,
                external_reference=external_ref,
                risk_score=final_risk_score,
                reasons=merged_reasons,
                policy_violations=[],
                security_threats=[],
                requires_human_approval=False,
                approval_id=None,
                paypal_order_id=paypal_order_id,
                paypal_authorization_id=paypal_auth_id,
                created_at=txn_record.created_at.isoformat(),
            ).model_dump()

        except Exception as exc:
            session.rollback()
            logger.error(f"Error processing MCP purchase request: {exc}", exc_info=True)
            return {
                "error": "PROCESSING_FAILURE",
                "message": f"Transaction processing failed: {exc}",
                "decision": "BLOCK",
                "payment_status": "BLOCKED",
            }
        finally:
            _PURCHASE_LOCK.release()
            if owns_session:
                session.close()

    async def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Look up transaction status and audit history by internal UUID or external reference."""
        clean_id = (transaction_id or "").strip()
        if not clean_id:
            return {"error": "INVALID_ARGUMENT", "message": "Transaction ID is required."}

        session = self._get_session()
        owns_session = self._external_session is None

        try:
            txn = (
                session.query(Transaction)
                .filter(
                    (Transaction.id == clean_id)
                    | (Transaction.external_reference == clean_id)
                )
                .first()
            )
            if not txn:
                return {
                    "error": "NOT_FOUND",
                    "message": f"Transaction '{clean_id}' was not found in AgentGuard records.",
                }

            appr = (
                session.query(Approval)
                .filter(Approval.transaction_id == txn.id)
                .first()
            )
            logs = (
                session.query(AuditLog)
                .filter(AuditLog.transaction_id == txn.id)
                .order_by(AuditLog.timestamp.asc())
                .all()
            )

            return TransactionStatusResponse(
                transaction_id=txn.id,
                external_reference=txn.external_reference,
                merchant_name=txn.merchant_name,
                merchant_id=txn.merchant_id,
                amount=str(txn.amount),
                currency=txn.currency,
                description=txn.description,
                decision=txn.decision,
                payment_status=txn.payment_status,
                risk_score=int(txn.risk_score * 100),
                paypal_order_id=txn.paypal_order_id,
                paypal_authorization_id=txn.paypal_authorization_id,
                created_at=txn.created_at.isoformat(),
                updated_at=txn.updated_at.isoformat(),
                approval_status=appr.status if appr else None,
                audit_events=[log.event_type for log in logs],
            ).model_dump()

        finally:
            if owns_session:
                session.close()

    async def list_pending_approvals(self, admin_token: Optional[str] = None) -> Dict[str, Any]:
        """List transactions awaiting human-in-the-loop sign-off.
        
        Requires administrative authentication. Buyer agents are strictly prohibited
        from accessing approval management.
        """
        settings = get_settings()
        expected_secret = settings.admin_api_key.get_secret_value()

        if not admin_token or admin_token.strip() != expected_secret:
            logger.warning("Unauthorized attempt to access administrative approval queue.")
            return {
                "error": "UNAUTHORIZED",
                "message": (
                    "Administrative authentication required. Autonomous buyer agents are strictly "
                    "prohibited from inspecting or modifying the human approval queue."
                ),
            }

        session = self._get_session()
        owns_session = self._external_session is None

        try:
            pending_records = (
                session.query(Approval)
                .filter(Approval.status == "PENDING")
                .order_by(Approval.created_at.desc())
                .all()
            )

            items: List[PendingApprovalItem] = []
            for appr in pending_records:
                txn = appr.transaction
                if not txn:
                    continue
                items.append(
                    PendingApprovalItem(
                        approval_id=appr.id,
                        transaction_id=txn.id,
                        external_reference=txn.external_reference,
                        merchant_name=txn.merchant_name,
                        amount=str(txn.amount),
                        currency=txn.currency,
                        reason=appr.reason,
                        created_at=appr.created_at.isoformat(),
                        risk_score=int(txn.risk_score * 100),
                    )
                )

            return PendingApprovalsResponse(
                pending_count=len(items),
                approvals=items,
            ).model_dump()

        finally:
            if owns_session:
                session.close()
