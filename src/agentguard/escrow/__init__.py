"""Escrow state machine and human-in-the-loop approval package."""

from agentguard.escrow.state_machine import TransactionState, can_transition, validate_transition
from agentguard.escrow.exceptions import (
    EscrowError,
    InvalidStateTransitionError,
    DuplicateApprovalError,
    UnauthorizedReviewerError,
    AlreadyCapturedError,
    AlreadyVoidedError,
    EscrowExecutionError,
)
from agentguard.escrow.service import EscrowWorkflowService

__all__ = [
    "TransactionState",
    "can_transition",
    "validate_transition",
    "EscrowError",
    "InvalidStateTransitionError",
    "DuplicateApprovalError",
    "UnauthorizedReviewerError",
    "AlreadyCapturedError",
    "AlreadyVoidedError",
    "EscrowExecutionError",
    "EscrowWorkflowService",
]
