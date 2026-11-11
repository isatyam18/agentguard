"""Deterministic state machine governing AgentGuard escrow and human approval transitions."""

from enum import Enum
from typing import Dict, Set

from agentguard.escrow.exceptions import (
    AlreadyCapturedError,
    AlreadyVoidedError,
    InvalidStateTransitionError,
)


class TransactionState(str, Enum):
    """Canonical transaction lifecycle states required by AgentGuard specifications."""

    PENDING = "PENDING"
    EVALUATING = "EVALUATING"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    PAYPAL_ORDER_CREATED = "PAYPAL_ORDER_CREATED"
    AUTHORIZED = "AUTHORIZED"
    APPROVED_FOR_CAPTURE = "APPROVED_FOR_CAPTURE"
    CAPTURED = "CAPTURED"
    VOIDED = "VOIDED"
    FAILED = "FAILED"

    # Support legacy alias for backwards compatibility
    HELD = "HELD"


# Directed state transition graph enforcing escrow invariants
LEGAL_TRANSITIONS: Dict[str, Set[str]] = {
    TransactionState.PENDING.value: {
        TransactionState.EVALUATING.value,
        TransactionState.REVIEW_REQUIRED.value,
        TransactionState.APPROVED_FOR_CAPTURE.value,
        TransactionState.BLOCKED.value,
        TransactionState.HELD.value,
        TransactionState.FAILED.value,
    },
    TransactionState.EVALUATING.value: {
        TransactionState.BLOCKED.value,
        TransactionState.REVIEW_REQUIRED.value,
        TransactionState.PAYPAL_ORDER_CREATED.value,
        TransactionState.AUTHORIZED.value,
        TransactionState.APPROVED_FOR_CAPTURE.value,
        TransactionState.HELD.value,
        TransactionState.FAILED.value,
    },
    TransactionState.BLOCKED.value: set(),  # Terminal: Blocked requests never reach payment rails
    TransactionState.PAYPAL_ORDER_CREATED.value: {
        TransactionState.AUTHORIZED.value,
        TransactionState.VOIDED.value,
        TransactionState.FAILED.value,
    },
    TransactionState.AUTHORIZED.value: {
        TransactionState.REVIEW_REQUIRED.value,
        TransactionState.APPROVED_FOR_CAPTURE.value,
        TransactionState.CAPTURED.value,
        TransactionState.VOIDED.value,
        TransactionState.HELD.value,
        TransactionState.FAILED.value,
    },
    TransactionState.REVIEW_REQUIRED.value: {
        TransactionState.APPROVED_FOR_CAPTURE.value,
        TransactionState.AUTHORIZED.value,
        TransactionState.VOIDED.value,
        TransactionState.FAILED.value,
    },
    TransactionState.HELD.value: {  # Equivalent alias for REVIEW_REQUIRED
        TransactionState.APPROVED_FOR_CAPTURE.value,
        TransactionState.AUTHORIZED.value,
        TransactionState.VOIDED.value,
        TransactionState.FAILED.value,
    },
    TransactionState.APPROVED_FOR_CAPTURE.value: {
        TransactionState.CAPTURED.value,
        TransactionState.VOIDED.value,
        TransactionState.FAILED.value,
    },
    TransactionState.CAPTURED.value: set(),  # Terminal: Never capture an already captured transaction
    TransactionState.VOIDED.value: set(),  # Terminal: Never capture a voided authorization
    TransactionState.FAILED.value: set(),  # Terminal
}


def normalize_state(state: str | TransactionState) -> str:
    """Extract string value of transaction state."""
    if isinstance(state, TransactionState):
        return state.value
    return str(state).strip().upper()


def can_transition(from_state: str | TransactionState, to_state: str | TransactionState) -> bool:
    """Check if state transition is permissible according to the escrow graph."""
    origin = normalize_state(from_state)
    target = normalize_state(to_state)
    valid_targets = LEGAL_TRANSITIONS.get(origin, set())
    return target in valid_targets


def validate_transition(from_state: str | TransactionState, to_state: str | TransactionState) -> None:
    """Validate transition and raise targeted domain exception on failure."""
    origin = normalize_state(from_state)
    target = normalize_state(to_state)

    if origin == TransactionState.CAPTURED.value:
        raise AlreadyCapturedError(
            f"Illegal state transition: Transaction is already CAPTURED and cannot transition to '{target}'."
        )

    if origin == TransactionState.VOIDED.value:
        raise AlreadyVoidedError(
            f"Illegal state transition: Authorization is VOIDED and cannot transition to '{target}'.",
            from_state=origin,
            to_state=target,
        )

    if origin == TransactionState.BLOCKED.value:
        raise InvalidStateTransitionError(
            f"Illegal state transition: Transaction was BLOCKED by policy firewall and cannot transition to '{target}'.",
            from_state=origin,
            to_state=target,
        )

    if not can_transition(origin, target):
        raise InvalidStateTransitionError(
            f"Illegal escrow state transition from '{origin}' to '{target}'.",
            from_state=origin,
            to_state=target,
        )
