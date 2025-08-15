# backend/modules/menu/tests/test_recipe_api.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from core.menu_models import MenuItem, MenuCategory
from core.inventory_models import Inventory
from ..models.recipe_models import Recipe, RecipeStatus, RecipeComplexity, UnitType


class TestRecipeAPI:

    @pytest.fixture
    def auth_headers(self, test_client: TestClient):
        """Get authentication headers for testing"""
        # This would typically login and get a token
        # For now, return mock headers
        return {"Authorization": "Bearer test_token"}

    @pytest.fixture
    def sample_menu_item(self, db_session: Session):
        """Create a sample menu item for testing"""
        category = MenuCategory(
            name="Test Category", description="Test", is_active=True
        )
        db_session.add(category)
        db_session.commit()

        item = MenuItem(
            name="Test Dish",
            price=15.99,
            category_id=category.id,
            is_active=True,
            is_available=True,
        )
        db_session.add(item)
        db_session.commit()
        return item

    @pytest.fixture
    def sample_inventory(self, db_session: Session):
        """Create sample inventory items"""
        items = [
            Inventory(
                item_name="Ingredient 1",
                quantity=100,
                unit="kg",
                threshold=10,
                cost_per_unit=5.00,
                is_active=True,
            ),
            Inventory(
                item_name="Ingredient 2",
                quantity=50,
                unit="liter",
                threshold=5,
                cost_per_unit=3.00,
                is_active=True,
            ),
        ]
        for item in items:
            db_session.add(item)
        db_session.commit()
        return items

    def test_create_recipe(
        self, test_client: TestClient, auth_headers, sample_menu_item, sample_inventory
    ):
        """Test creating a recipe via API"""
        recipe_data = {
            "menu_item_id": sample_menu_item.id,
            "name": "Test Recipe",
            "status": "draft",
            "yield_quantity": 1,
            "yield_unit": "portion",
            "prep_time_minutes": 15,
            "cook_time_minutes": 30,
            "complexity": "moderate",
            "instructions": ["Step 1", "Step 2", "Step 3"],
            "notes": "Test notes",
            "ingredients": [
                {
                    "inventory_id": sample_inventory[0].id,
                    "quantity": 0.5,
                    "unit": "kg",
                    "preparation": "diced",
                    "is_optional": False,
                },
                {
                    "inventory_id": sample_inventory[1].id,
                    "quantity": 0.25,
                    "unit": "l",
                    "preparation": "room temperature",
                    "is_optional": False,
                },
            ],
        }

        response = test_client.post(
            "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Recipe"
        assert data["total_time_minutes"] == 45
        assert len(data["ingredients"]) == 2
        assert data["total_cost"] is not None
        assert data["food_cost_percentage"] is not None

    def test_get_recipe(
        self, test_client: TestClient, auth_headers, sample_menu_item, sample_inventory
    ):
        """Test getting a recipe by ID"""
        # First create a recipe
        recipe_data = {
            "menu_item_id": sample_menu_item.id,
            "name": "Get Test Recipe",
            "ingredients": [
                {"inventory_id": sample_inventory[0].id, "quantity": 1, "unit": "kg"}
            ],
        }

        create_response = test_client.post(
            "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
        )
        recipe_id = create_response.json()["id"]

        # Get the recipe
        response = test_client.get(
            f"/api/v1/menu/recipes/{recipe_id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == recipe_id
        assert data["name"] == "Get Test Recipe"
        assert "menu_item" in data
        assert "ingredients" in data

    def test_get_recipe_by_menu_item(
        self, test_client: TestClient, auth_headers, sample_menu_item, sample_inventory
    ):
        """Test getting recipe by menu item ID"""
        # Create a recipe
        recipe_data = {
            "menu_item_id": sample_menu_item.id,
            "name": "Menu Item Recipe",
            "ingredients": [
                {"inventory_id": sample_inventory[0].id, "quantity": 1, "unit": "kg"}
            ],
        }

        test_client.post("/api/v1/menu/recipes", json=recipe_data, headers=auth_headers)

        # Get by menu item
        response = test_client.get(
            f"/api/v1/menu/recipes/menu-item/{sample_menu_item.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["menu_item_id"] == sample_menu_item.id

    def test_update_recipe(
        self, test_client: TestClient, auth_headers, sample_menu_item, sample_inventory
    ):
        """Test updating a recipe"""
        # Create a recipe
        recipe_data = {
            "menu_item_id": sample_menu_item.id,
            "name": "Original Recipe",
            "status": "draft",
            "ingredients": [
                {"inventory_id": sample_inventory[0].id, "quantity": 1, "unit": "kg"}
            ],
        }

        create_response = test_client.post(
            "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
        )
        recipe_id = create_response.json()["id"]

        # Update the recipe
        update_data = {
            "name": "Updated Recipe",
            "status": "active",
            "prep_time_minutes": 20,
            "notes": "Updated notes",
        }

        response = test_client.put(
            f"/api/v1/menu/recipes/{recipe_id}", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Recipe"
        assert data["status"] == "active"
        assert data["prep_time_minutes"] == 20
        assert data["version"] > 1

    def test_update_recipe_ingredients(
        self, test_client: TestClient, auth_headers, sample_menu_item, sample_inventory
    ):
        """Test updating recipe ingredients"""
        # Create a recipe
        recipe_data = {
            "menu_item_id": sample_menu_item.id,
            "name": "Ingredient Test Recipe",
            "ingredients": [
                {"inventory_id": sample_inventory[0].id, "quantity": 1, "unit": "kg"}
            ],
        }

        create_response = test_client.post(
            "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
        )
        recipe_id = create_response.json()["id"]

        # Update ingredients
        new_ingredients = [
            {"inventory_id": sample_inventory[0].id, "quantity": 2, "unit": "kg"},
            {"inventory_id": sample_inventory[1].id, "quantity": 0.5, "unit": "l"},
        ]

        response = test_client.put(
            f"/api/v1/menu/recipes/{recipe_id}/ingredients",
            json=new_ingredients,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["ingredients"]) == 2
        assert data["version"] > 1

    def test_search_recipes(
        self,
        test_client: TestClient,
        auth_headers,
        sample_menu_item,
        sample_inventory,
        db_session,
    ):
        """Test searching recipes"""
        # Create multiple recipes
        for i in range(3):
            item = MenuItem(
                name=f"Item {i}",
                price=10.00 + i,
                category_id=sample_menu_item.category_id,
                is_active=True,
            )
            db_session.add(item)
            db_session.commit()

            recipe_data = {
                "menu_item_id": item.id,
                "name": f"Recipe {i}",
                "status": "active" if i % 2 == 0 else "draft",
                "complexity": "simple" if i == 0 else "moderate",
                "ingredients": [
                    {
                        "inventory_id": sample_inventory[i % 2].id,
                        "quantity": 1,
                        "unit": "kg",
                    }
                ],
            }

            test_client.post(
                "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
            )

        # Search by status
        response = test_client.get(
            "/api/v1/menu/recipes?status=active", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2

        # Search by complexity
        response = test_client.get(
            "/api/v1/menu/recipes?complexity=simple", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    def test_recipe_cost_analysis(
        self, test_client: TestClient, auth_headers, sample_menu_item, sample_inventory
    ):
        """Test getting recipe cost analysis"""
        # Create a recipe
        recipe_data = {
            "menu_item_id": sample_menu_item.id,
            "name": "Cost Analysis Recipe",
            "ingredients": [
                {"inventory_id": sample_inventory[0].id, "quantity": 2, "unit": "kg"},
                {"inventory_id": sample_inventory[1].id, "quantity": 1, "unit": "l"},
            ],
        }

        create_response = test_client.post(
            "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
        )
        recipe_id = create_response.json()["id"]

        # Get cost analysis
        response = test_client.get(
            f"/api/v1/menu/recipes/{recipe_id}/cost-analysis", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_cost" in data
        assert "food_cost_percentage" in data
        assert "profit_margin" in data
        assert "ingredient_costs" in data
        assert len(data["ingredient_costs"]) == 2

    def test_recipe_validation(
        self, test_client: TestClient, auth_headers, sample_menu_item
    ):
        """Test recipe validation"""
        # Create an incomplete recipe
        recipe_data = {
            "menu_item_id": sample_menu_item.id,
            "name": "Incomplete Recipe",
            "ingredients": [],  # No ingredients
        }

        create_response = test_client.post(
            "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
        )
        recipe_id = create_response.json()["id"]

        # Validate recipe
        response = test_client.get(
            f"/api/v1/menu/recipes/{recipe_id}/validate", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert not data["is_valid"]
        assert not data["has_ingredients"]
        assert len(data["validation_errors"]) > 0

    def test_compliance_report(self, test_client: TestClient, auth_headers):
        """Test getting compliance report"""
        response = test_client.get(
            "/api/v1/menu/recipes/compliance/report", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_menu_items" in data
        assert "items_with_recipes" in data
        assert "compliance_percentage" in data
        assert "missing_recipes" in data

    def test_clone_recipe(
        self,
        test_client: TestClient,
        auth_headers,
        sample_menu_item,
        sample_inventory,
        db_session,
    ):
        """Test cloning a recipe"""
        # Create source recipe
        recipe_data = {
            "menu_item_id": sample_menu_item.id,
            "name": "Source Recipe",
            "yield_quantity": 1,
            "ingredients": [
                {"inventory_id": sample_inventory[0].id, "quantity": 1, "unit": "kg"}
            ],
        }

        create_response = test_client.post(
            "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
        )
        source_recipe_id = create_response.json()["id"]

        # Create target menu item
        target_item = MenuItem(
            name="Target Dish",
            price=20.99,
            category_id=sample_menu_item.category_id,
            is_active=True,
        )
        db_session.add(target_item)
        db_session.commit()

        # Clone recipe
        clone_data = {
            "source_recipe_id": source_recipe_id,
            "target_menu_item_id": target_item.id,
            "name": "Cloned Recipe",
            "adjust_portions": 2.0,
        }

        response = test_client.post(
            "/api/v1/menu/recipes/clone", json=clone_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Cloned Recipe"
        assert data["menu_item_id"] == target_item.id
        assert data["yield_quantity"] == 2.0
        assert data["status"] == "draft"

    def test_bulk_operations(
        self,
        test_client: TestClient,
        auth_headers,
        sample_menu_item,
        sample_inventory,
        db_session,
    ):
        """Test bulk recipe operations"""
        # Create multiple recipes
        recipe_ids = []
        for i in range(3):
            item = MenuItem(
                name=f"Bulk Item {i}",
                price=15.00,
                category_id=sample_menu_item.category_id,
                is_active=True,
            )
            db_session.add(item)
            db_session.commit()

            recipe_data = {
                "menu_item_id": item.id,
                "name": f"Bulk Recipe {i}",
                "status": "draft",
                "ingredients": [
                    {
                        "inventory_id": sample_inventory[0].id,
                        "quantity": 1,
                        "unit": "kg",
                    }
                ],
            }

            response = test_client.post(
                "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
            )
            recipe_ids.append(response.json()["id"])

        # Bulk activate
        response = test_client.put(
            "/api/v1/menu/recipes/bulk/activate",
            json={"recipe_ids": recipe_ids, "active": True},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated"] == 3
        assert data["action"] == "activated"

    def test_delete_recipe(
        self, test_client: TestClient, auth_headers, sample_menu_item, sample_inventory
    ):
        """Test deleting a recipe"""
        # Create a recipe
        recipe_data = {
            "menu_item_id": sample_menu_item.id,
            "name": "Delete Test Recipe",
            "ingredients": [
                {"inventory_id": sample_inventory[0].id, "quantity": 1, "unit": "kg"}
            ],
        }

        create_response = test_client.post(
            "/api/v1/menu/recipes", json=recipe_data, headers=auth_headers
        )
        recipe_id = create_response.json()["id"]

        # Delete the recipe
        response = test_client.delete(
            f"/api/v1/menu/recipes/{recipe_id}", headers=auth_headers
        )

        assert response.status_code == 204

        # Verify it's deleted
        response = test_client.get(
            f"/api/v1/menu/recipes/{recipe_id}", headers=auth_headers
        )

        assert response.status_code == 404
