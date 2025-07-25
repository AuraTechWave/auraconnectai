"""
Basic CI test to verify the pipeline works correctly.
This file can be deleted once the main tests are working.
"""
import pytest
from decimal import Decimal


def test_basic_imports():
    """Test that basic imports work."""
    # Test standard library imports
    from datetime import datetime, date
    from typing import List, Optional
    
    assert datetime.now() is not None
    assert isinstance([], List.__origin__)


def test_decimal_operations():
    """Test decimal operations work correctly."""
    a = Decimal('100.00')
    b = Decimal('25.50')
    
    assert a + b == Decimal('125.50')
    assert a - b == Decimal('74.50')
    assert a * Decimal('0.1') == Decimal('10.00')


def test_pydantic_import():
    """Test that Pydantic works."""
    try:
        from pydantic import BaseModel, Field
        
        class TestModel(BaseModel):
            name: str = Field(..., description="Test field")
            value: int = Field(default=0, ge=0)
        
        model = TestModel(name="test")
        assert model.name == "test"
        assert model.value == 0
        
    except ImportError:
        pytest.skip("Pydantic not available")


def test_sqlalchemy_import():
    """Test that SQLAlchemy imports work."""
    try:
        from sqlalchemy import Column, Integer, String
        from sqlalchemy.orm import Session
        
        # Basic SQLAlchemy imports should work
        assert Column is not None
        assert Integer is not None
        assert String is not None
        assert Session is not None
        
    except ImportError:
        pytest.skip("SQLAlchemy not available")


def test_project_structure():
    """Test that project structure is correct."""
    import os
    import sys
    
    # Check that we're in the backend directory
    current_dir = os.getcwd()
    assert 'backend' in current_dir or 'modules' in os.listdir('.')
    
    # Check that important directories exist
    if os.path.exists('modules'):
        assert os.path.exists('modules/payroll')
        assert os.path.exists('core')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])