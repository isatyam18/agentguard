"""Forwarding module for direct core namespace imports."""

from agentguard.core.decision_engine import (
    DecisionEngine,
    DecisionOutput,
)

__all__ = [
    "DecisionEngine",
    "DecisionOutput",
]
