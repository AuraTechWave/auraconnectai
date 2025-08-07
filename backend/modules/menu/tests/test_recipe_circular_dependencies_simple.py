# backend/modules/menu/tests/test_recipe_circular_dependencies_simple.py

"""
Simple test to verify circular dependency validation is working.
This is a minimal test file to avoid import issues.
"""

import pytest
from sqlalchemy.orm import Session
from fastapi import HTTPException

from modules.menu.models.recipe_models import Recipe, RecipeSubRecipe, RecipeStatus
from modules.menu.services.recipe_circular_validation import (
    RecipeCircularValidator, CircularDependencyError
)


def test_self_reference_prevention(db: Session):
    """Test that a recipe cannot reference itself"""
    # Create a mock recipe
    recipe = Recipe(
        id=1,
        menu_item_id=1,
        name="Test Recipe",
        status=RecipeStatus.ACTIVE,
        yield_quantity=1.0,
        created_by=1
    )
    
    # Initialize validator
    validator = RecipeCircularValidator(db)
    
    # Test self-reference
    with pytest.raises(CircularDependencyError) as exc_info:
        validator.validate_no_circular_reference(1, 1)
    
    assert "cannot reference itself" in str(exc_info.value)
    assert exc_info.value.cycle_path == [1]


def test_simple_circular_dependency():
    """Test detection of simple A -> B -> A circular dependency"""
    # Mock database session
    from unittest.mock import Mock, MagicMock
    
    db = Mock()
    
    # Create validator
    validator = RecipeCircularValidator(db)
    
    # Mock the query results
    # First call: Recipe A has sub-recipe B
    mock_query1 = MagicMock()
    mock_query1.filter.return_value.all.return_value = [
        Mock(parent_recipe_id=2, sub_recipe_id=1, is_active=True)
    ]
    
    # Setup the query chain
    db.query.return_value = mock_query1
    
    # Test that adding B as sub-recipe to A would create cycle
    with pytest.raises(CircularDependencyError) as exc_info:
        validator.validate_no_circular_reference(1, 2)
    
    assert "circular dependency" in str(exc_info.value).lower()


if __name__ == "__main__":
    # Run tests manually
    print("Testing self-reference prevention...")
    try:
        from unittest.mock import Mock
        test_self_reference_prevention(Mock())
        print("❌ Test should have raised an exception")
    except CircularDependencyError as e:
        print(f"✅ Test passed: {e}")
    
    print("\nTesting simple circular dependency...")
    try:
        test_simple_circular_dependency()
        print("✅ Test passed")
    except Exception as e:
        print(f"❌ Test failed: {e}")