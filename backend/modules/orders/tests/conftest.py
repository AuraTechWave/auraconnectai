import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from httpx import AsyncClient
from core.database import Base, get_db
from app.main import app
from modules.orders.models.order_models import Order, OrderItem
from core.inventory_models import Inventory
from core.menu_models import MenuItemInventory
from modules.orders.enums.order_enums import OrderStatus
from modules.staff.models.staff_models import StaffMember, Role  # noqa

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def async_client(db_session):
    """Create an async test client."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def sample_order(db_session):
    """Create a sample order for testing."""
    order = Order(
        staff_id=1,
        table_no=5,
        status=OrderStatus.PENDING.value
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_order_with_items(db_session):
    """Create a sample order with order items."""
    order = Order(
        staff_id=1,
        table_no=3,
        status=OrderStatus.IN_PROGRESS.value
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)

    item1 = OrderItem(
        order_id=order.id,
        menu_item_id=101,
        quantity=2,
        price=15.99,
        notes="Extra spicy"
    )
    item2 = OrderItem(
        order_id=order.id,
        menu_item_id=102,
        quantity=1,
        price=8.50
    )
    db_session.add_all([item1, item2])
    db_session.commit()
    return order


@pytest.fixture
def sample_inventory(db_session):
    inventory = Inventory(
        item_name="Test Ingredient",
        quantity=50.0,
        unit="kg",
        threshold=10.0,
        vendor_id=1
    )
    db_session.add(inventory)
    db_session.commit()
    db_session.refresh(inventory)
    return inventory


@pytest.fixture
def sample_inventory_with_mapping(db_session):
    inventory = Inventory(
        item_name="Test Ingredient",
        quantity=50.0,
        unit="kg",
        threshold=10.0
    )
    db_session.add(inventory)
    db_session.commit()
    db_session.refresh(inventory)

    mapping = MenuItemInventory(
        menu_item_id=101,
        inventory_id=inventory.id,
        quantity_needed=2.5
    )
    db_session.add(mapping)
    db_session.commit()
    db_session.refresh(mapping)
    return inventory, mapping
