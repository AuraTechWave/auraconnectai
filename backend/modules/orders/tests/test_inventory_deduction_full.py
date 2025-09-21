"""Unit tests for the order inventory integration service."""

import os
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Dict, Iterable

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from core.inventory_models import Inventory
from core.menu_models import MenuCategory, MenuItem
from modules.menu.models.recipe_models import (
    Recipe,
    RecipeIngredient,
    RecipeStatus,
    UnitType,
)
from modules.customers.models.customer_models import Customer
from modules.orders.enums.order_enums import OrderStatus
from modules.orders.models.order_models import Order, OrderItem, Tag
from modules.orders.models.order_tracking_models import OrderTrackingEvent
from modules.orders.models.payment_reconciliation_models import PaymentReconciliation
from modules.orders.services.order_inventory_integration import (
    OrderInventoryIntegrationService,
)
from modules.staff.models.staff_models import Role, StaffMember
from modules.auth.models.user_models import AuthUser


# Provide minimal secrets so importing modules that rely on configuration succeeds
os.environ.setdefault("PYTEST_CURRENT_TEST", "1")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("JWT_SECRET_KEY", "unit-test")
os.environ.setdefault("SESSION_SECRET", "unit-test")
os.environ.setdefault("SECRET_KEY", "unit-test")


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw):
    """Treat PostgreSQL JSONB columns as generic JSON when using SQLite."""

    return "JSON"


@pytest.fixture(scope="function")
def db_session() -> Iterable[Session]:
    """Isolated in-memory SQLite session with the tables required for these tests."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(bind=engine)

    tables = [
        AuthUser.__table__,
        Role.__table__,
        StaffMember.__table__,
        Tag.__table__,
        Customer.__table__,
        MenuCategory.__table__,
        MenuItem.__table__,
        Inventory.__table__,
        Recipe.__table__,
        RecipeIngredient.__table__,
        Order.__table__,
        OrderItem.__table__,
        OrderTrackingEvent.__table__,
        PaymentReconciliation.__table__,
    ]

    Base.metadata.create_all(bind=engine, tables=tables)

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine, tables=list(reversed(tables)))
        engine.dispose()


@pytest.fixture
def sample_data(db_session: Session) -> Dict[str, int]:
    """Seed the database with a minimal order/recipe/inventory setup."""

    user = AuthUser(id=1, email="admin@example.com", username="admin")
    role = Role(id=1, restaurant_id=1, name="Manager", description="")
    staff = StaffMember(
        id=1,
        restaurant_id=1,
        name="Test Manager",
        email="manager@example.com",
        role_id=role.id,
        is_active=True,
    )

    category = MenuCategory(id=1, name="Pizza", display_order=0, restaurant_id=1)

    menu_item = MenuItem(
        id=1,
        name="Margherita Pizza",
        description="Classic pizza",
        price=Decimal("12.50"),
        category_id=category.id,
        is_active=True,
        is_available=True,
        restaurant_id=1,
    )

    flour = Inventory(item_name="Flour", quantity=100.0, unit="kg", threshold=20.0)
    cheese = Inventory(item_name="Cheese", quantity=50.0, unit="kg", threshold=10.0)
    sauce = Inventory(item_name="Tomato Sauce", quantity=30.0, unit="L", threshold=5.0)

    recipe = Recipe(
        menu_item_id=menu_item.id,
        name="Margherita Recipe",
        created_by=staff.id,
        status=RecipeStatus.ACTIVE,
        yield_quantity=1.0,
        yield_unit="pizza",
    )

    ingredients = [
        RecipeIngredient(
            recipe=recipe,
            inventory_item=flour,
            quantity=0.3,
            unit=UnitType.KILOGRAM,
        ),
        RecipeIngredient(
            recipe=recipe,
            inventory_item=cheese,
            quantity=0.2,
            unit=UnitType.KILOGRAM,
        ),
        RecipeIngredient(
            recipe=recipe,
            inventory_item=sauce,
            quantity=0.1,
            unit=UnitType.LITER,
        ),
    ]

    order = Order(
        staff_id=staff.id,
        status=OrderStatus.PENDING.value,
        subtotal=Decimal("25.00"),
        total_amount=Decimal("25.00"),
        final_amount=Decimal("25.00"),
    )

    order_item = OrderItem(
        order=order,
        menu_item_id=menu_item.id,
        quantity=2,
        price=Decimal("12.50"),
    )

    db_session.add_all(
        [user, role, staff, category, menu_item, flour, cheese, sauce, recipe, order, order_item]
        + ingredients
    )
    db_session.commit()

    return {
        "order_id": order.id,
        "inventory_ids": [flour.id, cheese.id, sauce.id],
        "menu_item_id": menu_item.id,
    }


class StubRecipeInventoryService:
    """Minimal implementation that mutates inventory based on recipe definitions."""

    def __init__(self, db: Session):
        self.db = db

    async def deduct_inventory_for_order(self, order_items, order_id, user_id, deduction_type):
        return self._apply_inventory_change(order_items, multiplier=-1, context="deduct")

    async def reverse_inventory_deduction(self, order_id, user_id, reason: str):
        order_items = self.db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
        return self._apply_inventory_change(order_items, multiplier=1, context="reverse")

    async def handle_partial_fulfillment(self, order_items, order_id, user_id):
        partial_items = [
            SimpleNamespace(menu_item_id=item["menu_item_id"], quantity=item["fulfilled_quantity"])
            for item in order_items
        ]
        return self._apply_inventory_change(partial_items, multiplier=-1, context="partial")

    async def get_inventory_impact_preview(self, order_items):
        impact = []
        for item in order_items:
            for ingredient, required in self._ingredient_requirements(item):
                inventory = self.db.get(Inventory, ingredient.inventory_id)
                impact.append(
                    {
                        "item_name": inventory.item_name,
                        "inventory_id": inventory.id,
                        "required_quantity": required,
                        "available_quantity": float(inventory.quantity),
                        "sufficient_stock": float(inventory.quantity) >= required,
                    }
                )

        return {
            "can_fulfill": all(entry["sufficient_stock"] for entry in impact),
            "impact_preview": impact,
        }

    def _apply_inventory_change(self, order_items, multiplier: int, context: str):
        adjustments = []
        for item in order_items:
            for ingredient, required_quantity in self._ingredient_requirements(item):
                inventory = self.db.get(Inventory, ingredient.inventory_id)
                inventory.quantity = float(inventory.quantity) + (required_quantity * multiplier)
                adjustments.append(
                    {
                        "inventory_id": inventory.id,
                        "item_name": inventory.item_name,
                        "quantity_changed": required_quantity * multiplier,
                        "context": context,
                    }
                )

        self.db.flush()
        return {"success": True, "deducted_items": adjustments}

    def _ingredient_requirements(self, order_item: OrderItem):
        recipe = (
            self.db.query(Recipe)
            .filter(Recipe.menu_item_id == order_item.menu_item_id)
            .one()
        )
        for ingredient in recipe.ingredients:
            required = float(ingredient.quantity) * order_item.quantity
            yield ingredient, required


def _build_service(db_session: Session) -> OrderInventoryIntegrationService:
    service = OrderInventoryIntegrationService(db_session)
    service.recipe_inventory_service = StubRecipeInventoryService(db_session)
    service.log_deduction_audit = lambda *args, **kwargs: None
    service.log_reversal_audit = lambda *args, **kwargs: None
    return service


@pytest.mark.asyncio
async def test_complete_order_with_inventory_deduction(db_session: Session, sample_data: Dict[str, int]):
    service = _build_service(db_session)

    flour = db_session.get(Inventory, sample_data["inventory_ids"][0])
    flour_before = float(flour.quantity)

    result = await service.complete_order_with_inventory(sample_data["order_id"], user_id=1)

    assert result["success"] is True

    db_session.refresh(flour)
    order = db_session.get(Order, sample_data["order_id"])

    assert order.status == OrderStatus.COMPLETED.value
    assert order.completed_at is not None
    assert order.is_cancelled is False
    assert float(flour.quantity) == pytest.approx(flour_before - 0.6)


@pytest.mark.asyncio
async def test_cancel_order_with_inventory_reversal(db_session: Session, sample_data: Dict[str, int]):
    service = _build_service(db_session)

    await service.complete_order_with_inventory(sample_data["order_id"], user_id=1)

    flour = db_session.get(Inventory, sample_data["inventory_ids"][0])
    flour_after_completion = float(flour.quantity)

    result = await service.handle_order_cancellation(
        sample_data["order_id"], user_id=1, reason="Customer cancelled", reverse_inventory=True
    )

    assert result["success"] is True

    db_session.refresh(flour)
    order = db_session.get(Order, sample_data["order_id"])

    assert order.status == OrderStatus.CANCELLED.value
    assert order.cancelled_at is not None
    assert order.cancellation_reason == "Customer cancelled"
    assert order.is_cancelled
    assert float(flour.quantity) == pytest.approx(flour_after_completion + 0.6)


@pytest.mark.asyncio
async def test_check_inventory_availability(db_session: Session, sample_data: Dict[str, int]):
    service = _build_service(db_session)

    result = await service.validate_inventory_availability(sample_data["order_id"])

    assert result["can_fulfill"] is True
    assert len(result["impact_preview"]) == 3
    flour_preview = next(p for p in result["impact_preview"] if p["item_name"] == "Flour")
    assert flour_preview["required_quantity"] == pytest.approx(0.6)
    assert flour_preview["sufficient_stock"] is True


@pytest.mark.asyncio
async def test_partial_fulfillment_updates_metadata(db_session: Session, sample_data: Dict[str, int]):
    service = _build_service(db_session)

    await service.handle_partial_fulfillment(
        sample_data["order_id"],
        fulfilled_items=[{"menu_item_id": sample_data["menu_item_id"], "fulfilled_quantity": 1}],
        user_id=1,
    )

    order = db_session.get(Order, sample_data["order_id"])

    metadata = order.metadata_json or {}
    assert "partial_fulfillments" in metadata
    assert len(metadata["partial_fulfillments"]) == 1
