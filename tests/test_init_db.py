"""Tests for database initialization, schema creation, and database constraints."""

from decimal import Decimal
import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from agentguard.core.database import configure_sqlite_pragmas, init_db
from agentguard.models.base import Base
from agentguard.models.transaction import Transaction


def test_init_db_creates_all_tables() -> None:
    """Verify init_db initializes all expected tables in SQLite."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(target_engine=engine)

    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    assert "transactions" in table_names
    assert "policies" in table_names
    assert "approvals" in table_names
    assert "audit_logs" in table_names
    engine.dispose()


def test_sqlite_foreign_keys_pragmas_enabled(test_engine) -> None:
    """Verify that foreign keys pragma is active on SQLite connections."""
    with test_engine.connect() as conn:
        fk_status = conn.execute(text("PRAGMA foreign_keys")).scalar()
        assert fk_status == 1


def test_transaction_amount_positive_constraint(db_session: Session) -> None:
    """Verify CheckConstraint rejects transactions with amount <= 0."""
    invalid_txn = Transaction(
        external_reference="ref-negative-amount",
        merchant_name="Test Merchant",
        merchant_id="m-123",
        amount=Decimal("-10.00"),
        currency="USD",
        description="Invalid negative amount",
    )
    db_session.add(invalid_txn)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_transaction_risk_score_bounds_constraint(db_session: Session) -> None:
    """Verify CheckConstraint rejects risk scores outside [0.0, 1.0]."""
    invalid_txn = Transaction(
        external_reference="ref-invalid-risk",
        merchant_name="Test Merchant",
        merchant_id="m-123",
        amount=Decimal("15.00"),
        currency="USD",
        description="Invalid risk score",
        risk_score=Decimal("1.50"),
    )
    db_session.add(invalid_txn)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_unique_external_reference_constraint(db_session: Session) -> None:
    """Verify external_reference uniqueness constraint prevents duplicate agent IDs."""
    txn1 = Transaction(
        external_reference="duplicate-ref-123",
        merchant_name="Merchant A",
        merchant_id="m-a",
        amount=Decimal("20.00"),
        currency="USD",
        description="First attempt",
    )
    db_session.add(txn1)
    db_session.flush()

    txn2 = Transaction(
        external_reference="duplicate-ref-123",
        merchant_name="Merchant B",
        merchant_id="m-b",
        amount=Decimal("30.00"),
        currency="USD",
        description="Duplicate reference attempt",
    )
    db_session.add(txn2)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()
