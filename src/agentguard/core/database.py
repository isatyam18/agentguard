"""Database connectivity, engine configuration, and SQLite WAL lifecycle."""

from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from agentguard.core.config import Settings, get_settings
from agentguard.core.logging import logger
from agentguard.models.base import Base
# Import all models to ensure they are registered with Base.metadata
import agentguard.models  # noqa: F401


def configure_sqlite_pragmas(dbapi_connection: object, connection_record: object) -> None:
    """Enforce SQLite WAL mode and foreign key constraint validation."""
    cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def create_db_engine(settings: Settings | None = None) -> Engine:
    """Instantiate and configure SQLAlchemy database engine."""
    app_settings = settings or get_settings()

    connect_args = {}
    if app_settings.is_sqlite:
        connect_args["check_same_thread"] = False

    engine = create_engine(
        app_settings.database_url,
        echo=app_settings.database_echo,
        connect_args=connect_args,
        future=True,
    )

    if app_settings.is_sqlite:
        event.listen(engine, "connect", configure_sqlite_pragmas)

    return engine


engine = create_db_engine()
SessionFactory = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def init_db(target_engine: Engine | None = None) -> None:
    """Initialize database schemas and guarantee filesystem directory exists."""
    active_engine = target_engine or engine
    settings = get_settings()

    if settings.sqlite_file_path:
        settings.sqlite_file_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Initializing database tables",
        extra={"event": "DB_INIT", "url": str(active_engine.url)},
    )
    Base.metadata.create_all(bind=active_engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a managed database session."""
    session = SessionFactory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
