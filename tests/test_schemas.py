"""Tests for Pydantic schema validation, Decimal precision, and input sanitization."""

from decimal import Decimal
import pytest
from pydantic import ValidationError

from agentguard.schemas.approval import ApprovalDecision
from agentguard.schemas.policy import PolicyCreate
from agentguard.schemas.transaction import TransactionCreate, TransactionResponse


def test_valid_transaction_schema(sample_transaction_data: dict) -> None:
    """Verify valid transaction payload creates Pydantic model successfully."""
    model = TransactionCreate(**sample_transaction_data)
    assert model.amount == Decimal("49.99")
    assert model.currency == "USD"
    assert model.external_reference == sample_transaction_data["external_reference"]


def test_transaction_schema_rejects_negative_and_zero_amount() -> None:
    """Verify schema raises ValidationError for zero or negative amounts."""
    base_data = {
        "external_reference": "ref-zero",
        "merchant_name": "Test",
        "merchant_id": "m-1",
        "currency": "USD",
        "description": "Zero amount",
    }

    with pytest.raises(ValidationError) as exc_info:
        TransactionCreate(**base_data, amount=Decimal("0.00"))
    assert "strictly greater than 0" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        TransactionCreate(**base_data, amount=Decimal("-25.50"))
    assert "strictly greater than 0" in str(exc_info.value)


def test_transaction_schema_rejects_subcent_precision() -> None:
    """Verify schema raises ValidationError if amount has more than 2 decimal places."""
    with pytest.raises(ValidationError) as exc_info:
        TransactionCreate(
            external_reference="ref-subcent",
            merchant_name="Test",
            merchant_id="m-1",
            amount=Decimal("19.999"),
            currency="USD",
            description="Invalid subcent amount",
        )
    assert "cannot have more than 2 decimal places" in str(exc_info.value)


def test_transaction_schema_currency_normalization_and_validation() -> None:
    """Verify currency code is normalized to uppercase and invalid codes rejected."""
    # Lowercase gets converted to uppercase
    model = TransactionCreate(
        external_reference="ref-curr-lower",
        merchant_name="Test",
        merchant_id="m-1",
        amount=Decimal("10.00"),
        currency="usd",
        description="Lowercase currency",
    )
    assert model.currency == "USD"

    # Invalid length or non-alphabetical
    with pytest.raises(ValidationError):
        TransactionCreate(
            external_reference="ref-curr-invalid",
            merchant_name="Test",
            merchant_id="m-1",
            amount=Decimal("10.00"),
            currency="US",
            description="Invalid currency code length",
        )

    with pytest.raises(ValidationError):
        TransactionCreate(
            external_reference="ref-curr-invalid2",
            merchant_name="Test",
            merchant_id="m-1",
            amount=Decimal("10.00"),
            currency="U12",
            description="Invalid currency characters",
        )


def test_transaction_schema_rejects_blank_strings() -> None:
    """Verify whitespace-only or empty strings fail validation."""
    with pytest.raises(ValidationError):
        TransactionCreate(
            external_reference="   ",
            merchant_name="Test",
            merchant_id="m-1",
            amount=Decimal("10.00"),
            currency="USD",
            description="Valid description",
        )


def test_policy_schema_validation() -> None:
    """Verify PolicyCreate validates positive thresholds."""
    with pytest.raises(ValidationError):
        PolicyCreate(
            max_transaction_amount=Decimal("-5.00"),
            daily_spending_limit=Decimal("100.00"),
        )

    with pytest.raises(ValidationError):
        PolicyCreate(
            max_transaction_amount=Decimal("50.00"),
            daily_spending_limit=Decimal("0.00"),
        )


def test_approval_decision_schema_validation() -> None:
    """Verify ApprovalDecision enforces allowed outcomes."""
    decision = ApprovalDecision(
        status="APPROVED",
        reviewer="lead_dev",
        reason="Verified deliverables",
    )
    assert decision.status == "APPROVED"

    with pytest.raises(ValidationError):
        ApprovalDecision(
            status="MAYBE",  # type: ignore[arg-type]
            reviewer="lead_dev",
        )
