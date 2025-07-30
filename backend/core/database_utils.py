# backend/core/database_utils.py

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from sqlalchemy.orm import Session
from .database import SessionLocal


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[Session, None]:
    """
    Async context manager for database sessions.
    Use this for background tasks and non-request contexts.
    
    Example:
        async with get_db_context() as db:
            # Use db session
            pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# For backwards compatibility
get_db_context = get_db_context