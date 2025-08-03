# backend/tests/factories/base.py

import factory
from factory.alchemy import SQLAlchemyModelFactory
from core.database import get_test_db


class BaseFactory(SQLAlchemyModelFactory):
    """Base factory with session management for all test factories."""
    
    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "commit"
    
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to use test database session."""
        if cls._meta.sqlalchemy_session is None:
            cls._meta.sqlalchemy_session = next(get_test_db())
        return super()._create(model_class, *args, **kwargs)
    
    @classmethod
    def reset_session(cls):
        """Reset the session (useful between tests)."""
        cls._meta.sqlalchemy_session = None