# backend/core/database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from typing import Generator
import logging
import os


if os.getenv("ENVIRONMENT", "development").lower() != "production":
    os.environ.setdefault("DATABASE_URL", "postgresql+psycopg2://postgres:aurapass@localhost:5432/postgres")
    os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret")
    os.environ.setdefault("SESSION_SECRET", "test-session-secret")
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("AURACONNECT_IMPORT_PAYROLL_ROUTERS", "0")
    os.environ.setdefault("AURACONNECT_ENABLE_TIP_RECORDS", "0")
    os.environ.setdefault("AURACONNECT_ENABLE_PAYMENT_MODELS", "0")
    os.environ.setdefault("AURACONNECT_ENABLE_RESERVATION_MODELS", "0")

from .query_logger import setup_query_logging

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:aurapass@localhost:5432/postgres"
)

def _create_engine(database_url: str, *, for_tests: bool = False):
    """Create a SQLAlchemy engine with sensible defaults."""
    engine_kwargs = {
        "echo": os.getenv("LOG_SQL_QUERIES", "false").lower() == "true",
        "pool_pre_ping": True,
    }

    if for_tests:
        # Keep test configuration lightweight and SQLite-friendly.
        engine_kwargs["echo"] = False
    else:
        engine_kwargs.update({"pool_size": 10, "max_overflow": 20})

    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
        engine_kwargs["connect_args"] = connect_args
        if for_tests and (":memory:" in database_url or database_url.endswith("?mode=memory&cache=shared")):
            engine_kwargs["poolclass"] = StaticPool

    return create_engine(database_url, **engine_kwargs)


# Create engine with optional echo for development
engine = _create_engine(DATABASE_URL)

# Setup query logging in development
setup_query_logging(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Test database helpers ---

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")

_test_engine = _create_engine(TEST_DATABASE_URL, for_tests=True)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)

_models_loaded = False
_MODEL_IMPORTS: tuple[str, ...] = (
    "modules.payroll.models.payroll_models",
)
_TEST_TABLE_EXCLUDE = {"tip_records"}


def _load_model_modules() -> None:
    """Import model modules so SQLAlchemy can resolve string-based relationships."""
    global _models_loaded
    if _models_loaded:
        return

    logger = logging.getLogger(__name__)

    for module_path in _MODEL_IMPORTS:
        try:
            __import__(module_path)
        except Exception as exc:  # pragma: no cover - optional modules may fail in tests
            logger.debug("Skipping model module %s due to import error: %s", module_path, exc)

    _models_loaded = True


def get_test_db() -> Generator[Session, None, None]:
    """Yield a database session backed by the test database engine."""
    _load_model_modules()
    for table_name in _TEST_TABLE_EXCLUDE:
        table = Base.metadata.tables.get(table_name)
        if table is not None:
            Base.metadata.remove(table)
    # Ensure a clean schema for each test invocation.
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
