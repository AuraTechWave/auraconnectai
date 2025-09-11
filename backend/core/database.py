# backend/core/database.py

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy import Column, DateTime
from datetime import datetime
from sqlalchemy.orm import sessionmaker
import os
from .query_logger import setup_query_logging

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://postgres:aurapass@localhost:5432/postgres"
)

# Create engine with optional echo for development
engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("LOG_SQL_QUERIES", "false").lower() == "true",
    pool_pre_ping=True,  # Verify connections before using them
    pool_size=10,  # Connection pool size
    max_overflow=20,  # Maximum overflow connections
)

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


class TimestampMixin:
    """Reusable timestamp mixin for SQLAlchemy models.

    Provides created_at and updated_at columns with sensible defaults.
    Some models in the codebase expect this mixin to exist in core.database.
    """

    @declared_attr
    def created_at(cls):  # type: ignore[no-redef]
        return Column(DateTime, default=datetime.utcnow, nullable=False)

    @declared_attr
    def updated_at(cls):  # type: ignore[no-redef]
        return Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
