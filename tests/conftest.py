"""Test configuration, fixtures, and database lifecycle for pytest."""

from decimal import Decimal
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from agentguard.core.database import configure_sqlite_pragmas, get_db
from agentguard.main import create_app
from agentguard.models.base import Base


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """Provide an in-memory SQLite engine configured with SQLite pragmas for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    event.listen(engine, "connect", configure_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Provide an isolated database session rolled back after every individual test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a FastAPI TestClient with the database dependency overridden."""
    app = create_app()

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_transaction_data() -> dict:
    """Provide valid payload for creating a sample transaction."""
    return {
        "external_reference": "agent-txn-test-001",
        "merchant_name": "Anthropic API",
        "merchant_id": "merchant-anthropic-prod",
        "amount": Decimal("49.99"),
        "currency": "USD",
        "description": "API tokens for code execution pipeline",
        "risk_score": Decimal("0.10"),
        "decision": "PENDING",
        "payment_status": "PENDING",
    }
