#!/usr/bin/env python3

"""
Standalone test for circular dependency validation
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest.mock import Mock, MagicMock, patch
from modules.menu.services.recipe_circular_validation import (
    RecipeCircularValidator, CircularDependencyError
)

def test_self_reference():
    """Test that a recipe cannot reference itself"""
    print("\n=== Testing Self-Reference Prevention ===")
    
    db = Mock()
    validator = RecipeCircularValidator(db)
    
    try:
        validator.validate_no_circular_reference(1, 1)
        print("❌ FAILED: Should have raised CircularDependencyError")
    except CircularDependencyError as e:
        print(f"✅ PASSED: {e}")
        print(f"   Cycle path: {e.cycle_path}")


def test_simple_cycle():
    """Test A -> B -> A cycle detection"""
    print("\n=== Testing Simple Cycle (A -> B -> A) ===")
    
    db = Mock()
    validator = RecipeCircularValidator(db)
    
    # Mock database queries
    def mock_query_side_effect(*args, **kwargs):
        query_mock = MagicMock()
        
        # Configure the filter chain
        def filter_side_effect(*filter_args, **filter_kwargs):
            filter_mock = MagicMock()
            
            # Check what's being queried
            if hasattr(filter_args[0], 'left') and hasattr(filter_args[0].left, 'key'):
                if filter_args[0].left.key == 'parent_recipe_id':
                    parent_id = filter_args[0].right.value
                    
                    # Recipe 1 has no sub-recipes initially
                    if parent_id == 1:
                        filter_mock.all.return_value = []
                    # Recipe 2 has Recipe 1 as sub-recipe (creating B -> A)
                    elif parent_id == 2:
                        sub_recipe = Mock()
                        sub_recipe.parent_recipe_id = 2
                        sub_recipe.sub_recipe_id = 1
                        sub_recipe.is_active = True
                        filter_mock.all.return_value = [sub_recipe]
                    else:
                        filter_mock.all.return_value = []
            
            return filter_mock
        
        query_mock.filter.side_effect = filter_side_effect
        return query_mock
    
    db.query.side_effect = mock_query_side_effect
    
    try:
        # Try to add Recipe 2 as sub-recipe to Recipe 1 (would create A -> B -> A)
        validator.validate_no_circular_reference(1, 2)
        print("❌ FAILED: Should have raised CircularDependencyError")
    except CircularDependencyError as e:
        print(f"✅ PASSED: {e}")
        print(f"   Cycle path: {e.cycle_path}")


def test_complex_cycle():
    """Test A -> B -> C -> A cycle detection"""
    print("\n=== Testing Complex Cycle (A -> B -> C -> A) ===")
    
    db = Mock()
    validator = RecipeCircularValidator(db)
    
    # Define the existing relationships:
    # Recipe 1 -> Recipe 2
    # Recipe 2 -> Recipe 3
    # We'll try to add Recipe 3 -> Recipe 1 (which would create a cycle)
    
    def mock_query_side_effect(*args, **kwargs):
        query_mock = MagicMock()
        
        def filter_side_effect(*filter_args, **filter_kwargs):
            filter_mock = MagicMock()
            
            if hasattr(filter_args[0], 'left') and hasattr(filter_args[0].left, 'key'):
                if filter_args[0].left.key == 'parent_recipe_id':
                    parent_id = filter_args[0].right.value
                    
                    if parent_id == 1:
                        # Recipe 1 has Recipe 2 as sub-recipe
                        sub = Mock(parent_recipe_id=1, sub_recipe_id=2, is_active=True)
                        filter_mock.all.return_value = [sub]
                    elif parent_id == 2:
                        # Recipe 2 has Recipe 3 as sub-recipe
                        sub = Mock(parent_recipe_id=2, sub_recipe_id=3, is_active=True)
                        filter_mock.all.return_value = [sub]
                    elif parent_id == 3:
                        # Recipe 3 has Recipe 1 as sub-recipe (creating the cycle)
                        sub = Mock(parent_recipe_id=3, sub_recipe_id=1, is_active=True)
                        filter_mock.all.return_value = [sub]
                    else:
                        filter_mock.all.return_value = []
            
            return filter_mock
        
        query_mock.filter.side_effect = filter_side_effect
        return query_mock
    
    db.query.side_effect = mock_query_side_effect
    
    try:
        # Try to add Recipe 1 as sub-recipe to Recipe 3 (would create cycle)
        validator.validate_no_circular_reference(3, 1)
        print("❌ FAILED: Should have raised CircularDependencyError")
    except CircularDependencyError as e:
        print(f"✅ PASSED: {e}")
        print(f"   Cycle path: {e.cycle_path}")


def test_valid_shared_sub_recipe():
    """Test that multiple recipes can share the same sub-recipe"""
    print("\n=== Testing Valid Shared Sub-Recipe ===")
    
    db = Mock()
    validator = RecipeCircularValidator(db)
    
    # Setup: 
    # Recipe 1 (base sauce)
    # Recipe 2 -> Recipe 1
    # Recipe 3 -> Recipe 1 (this should be allowed)
    
    def mock_query_side_effect(*args, **kwargs):
        query_mock = MagicMock()
        
        def filter_side_effect(*filter_args, **filter_kwargs):
            filter_mock = MagicMock()
            
            if hasattr(filter_args[0], 'left') and hasattr(filter_args[0].left, 'key'):
                if filter_args[0].left.key == 'parent_recipe_id':
                    parent_id = filter_args[0].right.value
                    
                    if parent_id == 1:
                        # Recipe 1 has no sub-recipes (it's the base)
                        filter_mock.all.return_value = []
                    elif parent_id == 2:
                        # Recipe 2 already has Recipe 1
                        sub = Mock(parent_recipe_id=2, sub_recipe_id=1, is_active=True)
                        filter_mock.all.return_value = [sub]
                    else:
                        filter_mock.all.return_value = []
            
            return filter_mock
        
        query_mock.filter.side_effect = filter_side_effect
        return query_mock
    
    db.query.side_effect = mock_query_side_effect
    
    try:
        # This should NOT raise an error - sharing sub-recipes is allowed
        validator.validate_no_circular_reference(3, 1)
        print("✅ PASSED: No circular dependency detected (as expected)")
    except CircularDependencyError as e:
        print(f"❌ FAILED: Should not have raised error. Error: {e}")


def test_recipe_names_in_error():
    """Test that error messages include recipe names"""
    print("\n=== Testing Recipe Names in Error Messages ===")
    
    db = Mock()
    validator = RecipeCircularValidator(db)
    
    # Mock recipe name lookup
    def mock_query_side_effect(model):
        if model.__name__ == 'RecipeSubRecipe':
            query_mock = MagicMock()
            
            def filter_side_effect(*filter_args, **filter_kwargs):
                filter_mock = MagicMock()
                parent_id = filter_args[0].right.value
                
                if parent_id == 2:
                    sub = Mock(parent_recipe_id=2, sub_recipe_id=1, is_active=True)
                    filter_mock.all.return_value = [sub]
                else:
                    filter_mock.all.return_value = []
                
                return filter_mock
            
            query_mock.filter.side_effect = filter_side_effect
            return query_mock
        
        elif model.__name__ == 'Recipe':
            # Mock recipe names query
            query_mock = MagicMock()
            
            def filter_side_effect(*args, **kwargs):
                filter_mock = MagicMock()
                
                # Mock recipes with names
                recipe1 = Mock(id=1, name="Tomato Sauce")
                recipe2 = Mock(id=2, name="Pasta Dish")
                recipe1.name = "Tomato Sauce"  # Ensure name is accessible
                recipe2.name = "Pasta Dish"    # Ensure name is accessible
                filter_mock.all.return_value = [recipe1, recipe2]
                
                return filter_mock
            
            query_mock.filter.side_effect = filter_side_effect
            return query_mock
        
        return MagicMock()
    
    db.query.side_effect = mock_query_side_effect
    
    try:
        validator.validate_no_circular_reference(1, 2)
        print("❌ FAILED: Should have raised CircularDependencyError")
    except CircularDependencyError as e:
        error_msg = str(e)
        print(f"✅ PASSED: {error_msg}")
        # Check if recipe names are in the message
        if "Tomato Sauce" in error_msg or "Pasta Dish" in error_msg:
            print("   ✅ Recipe names included in error message")
        else:
            print("   ⚠️  Recipe names not found in error message")


if __name__ == "__main__":
    print("Running Circular Dependency Validation Tests...")
    print("=" * 50)
    
    test_self_reference()
    test_simple_cycle()
    test_complex_cycle()
    test_valid_shared_sub_recipe()
    test_recipe_names_in_error()
    
    print("\n" + "=" * 50)
    print("All tests completed!")