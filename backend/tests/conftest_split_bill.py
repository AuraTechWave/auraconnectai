# backend/tests/conftest_split_bill.py

import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from modules.orders.models.order_models import Order, OrderItem, OrderStatus
from modules.customers.models.customer_models import Customer
from modules.staff.models.staff_models import Staff, StaffRole
from modules.menu.models.menu_models import MenuItem
from modules.payments.models.payment_models import Payment, PaymentStatus, PaymentGateway


@pytest.fixture
async def test_customer(db: AsyncSession) -> Customer:
    """Create a test customer"""
    customer = Customer(
        name="Test Customer",
        email="test@example.com",
        phone="+1234567890"
    )
    db.add(customer)
    await db.commit()
    return customer


@pytest.fixture
async def test_menu_items(db: AsyncSession) -> list[MenuItem]:
    """Create test menu items"""
    items = [
        MenuItem(
            name="Burger",
            description="Delicious burger",
            price=Decimal("15.00"),
            category="Main",
            is_active=True
        ),
        MenuItem(
            name="Pizza",
            description="Classic pizza",
            price=Decimal("20.00"),
            category="Main",
            is_active=True
        ),
        MenuItem(
            name="Salad",
            description="Fresh salad",
            price=Decimal("10.00"),
            category="Appetizer",
            is_active=True
        ),
        MenuItem(
            name="Soda",
            description="Soft drink",
            price=Decimal("3.00"),
            category="Beverage",
            is_active=True
        )
    ]
    
    for item in items:
        db.add(item)
    
    await db.commit()
    return items


@pytest.fixture
async def test_order(db: AsyncSession, test_customer: Customer) -> Order:
    """Create a test order without items"""
    order = Order(
        order_number="ORD-001",
        customer_id=test_customer.id,
        customer_name=test_customer.name,
        customer_email=test_customer.email,
        status=OrderStatus.COMPLETED,
        subtotal_amount=Decimal("100.00"),
        tax_amount=Decimal("8.00"),
        service_charge=Decimal("5.00"),
        total_amount=Decimal("113.00"),
        payment_status="pending"
    )
    db.add(order)
    await db.commit()
    return order


@pytest.fixture
async def test_order_with_items(
    db: AsyncSession, 
    test_customer: Customer,
    test_menu_items: list[MenuItem]
) -> Order:
    """Create a test order with items"""
    order = Order(
        order_number="ORD-002",
        customer_id=test_customer.id,
        customer_name=test_customer.name,
        customer_email=test_customer.email,
        status=OrderStatus.COMPLETED,
        payment_status="pending"
    )
    db.add(order)
    await db.flush()
    
    # Add order items
    items = [
        OrderItem(
            order_id=order.id,
            menu_item_id=test_menu_items[0].id,  # Burger
            name=test_menu_items[0].name,
            quantity=2,
            unit_price=test_menu_items[0].price,
            total_price=test_menu_items[0].price * 2,
            notes=""
        ),
        OrderItem(
            order_id=order.id,
            menu_item_id=test_menu_items[1].id,  # Pizza
            name=test_menu_items[1].name,
            quantity=1,
            unit_price=test_menu_items[1].price,
            total_price=test_menu_items[1].price,
            notes=""
        ),
        OrderItem(
            order_id=order.id,
            menu_item_id=test_menu_items[2].id,  # Salad
            name=test_menu_items[2].name,
            quantity=2,
            unit_price=test_menu_items[2].price,
            total_price=test_menu_items[2].price * 2,
            notes=""
        )
    ]
    
    for item in items:
        db.add(item)
    
    # Calculate totals
    order.subtotal_amount = sum(item.total_price for item in items)
    order.tax_amount = order.subtotal_amount * Decimal("0.08")  # 8% tax
    order.service_charge = Decimal("0")
    order.total_amount = order.subtotal_amount + order.tax_amount
    
    await db.commit()
    return order


@pytest.fixture
async def test_payment(db: AsyncSession, test_order: Order) -> Payment:
    """Create a test payment"""
    payment = Payment(
        order_id=test_order.id,
        gateway=PaymentGateway.STRIPE,
        amount=test_order.total_amount,
        currency="USD",
        status=PaymentStatus.COMPLETED,
        customer_id=test_order.customer_id,
        customer_email=test_order.customer_email,
        customer_name=test_order.customer_name
    )
    db.add(payment)
    await db.commit()
    return payment


@pytest.fixture
async def test_staff_list(db: AsyncSession) -> list[Staff]:
    """Create test staff members"""
    staff_members = [
        Staff(
            first_name="John",
            last_name="Server",
            email="john@restaurant.com",
            role=StaffRole.SERVER,
            is_active=True,
            receives_tips=True
        ),
        Staff(
            first_name="Jane",
            last_name="Bartender",
            email="jane@restaurant.com",
            role=StaffRole.BARTENDER,
            is_active=True,
            receives_tips=True
        ),
        Staff(
            first_name="Mike",
            last_name="Busser",
            email="mike@restaurant.com",
            role=StaffRole.BUSSER,
            is_active=True,
            receives_tips=True
        )
    ]
    
    for staff in staff_members:
        db.add(staff)
    
    await db.commit()
    return staff_members


@pytest.fixture
async def test_staff_by_role(db: AsyncSession) -> dict[str, list[Staff]]:
    """Create staff members organized by role"""
    staff_by_role = {
        'server': [
            Staff(
                first_name="Server1",
                last_name="Staff",
                email="server1@restaurant.com",
                role=StaffRole.SERVER,
                is_active=True,
                receives_tips=True
            ),
            Staff(
                first_name="Server2",
                last_name="Staff",
                email="server2@restaurant.com",
                role=StaffRole.SERVER,
                is_active=True,
                receives_tips=True
            )
        ],
        'bartender': [
            Staff(
                first_name="Bartender1",
                last_name="Staff",
                email="bartender1@restaurant.com",
                role=StaffRole.BARTENDER,
                is_active=True,
                receives_tips=True
            )
        ],
        'busser': [
            Staff(
                first_name="Busser1",
                last_name="Staff",
                email="busser1@restaurant.com",
                role=StaffRole.BUSSER,
                is_active=True,
                receives_tips=True
            )
        ]
    }
    
    for role_staff in staff_by_role.values():
        for staff in role_staff:
            db.add(staff)
    
    await db.commit()
    return staff_by_role