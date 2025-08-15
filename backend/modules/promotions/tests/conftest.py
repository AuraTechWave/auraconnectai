# backend/modules/promotions/tests/conftest.py

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import tempfile
import os

from core.database import Base
from modules.promotions.models.promotion_models import *
from modules.customers.models.customer_models import Customer
from modules.orders.models.order_models import Order


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine"""
    # Use in-memory SQLite for testing
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(test_engine):
    """Create a database session for testing"""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def sample_customer(db_session):
    """Create a sample customer for testing"""
    customer = Customer(
        id=1,
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        phone="123-456-7890",
        date_of_birth=datetime(1990, 1, 1),
        is_active=True,
        loyalty_points=100,
        total_spent=500.0,
        total_orders=5,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def sample_order(db_session, sample_customer):
    """Create a sample order for testing"""
    order = Order(
        id=1,
        customer_id=sample_customer.id,
        order_number="ORD-001",
        status="completed",
        subtotal=100.0,
        tax_amount=10.0,
        total_amount=110.0,
        final_amount=110.0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


@pytest.fixture
def sample_promotion(db_session):
    """Create a sample promotion for testing"""
    promotion = Promotion(
        name="Test Promotion",
        description="A test promotion",
        promotion_type=PromotionType.PERCENTAGE_DISCOUNT,
        discount_type=DiscountType.PERCENTAGE,
        discount_value=10.0,
        status=PromotionStatus.ACTIVE,
        start_date=datetime.utcnow() - timedelta(days=1),
        end_date=datetime.utcnow() + timedelta(days=30),
        max_uses=100,
        current_uses=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(promotion)
    db_session.commit()
    db_session.refresh(promotion)
    return promotion


@pytest.fixture
def sample_coupon(db_session, sample_promotion):
    """Create a sample coupon for testing"""
    coupon = Coupon(
        promotion_id=sample_promotion.id,
        code="TEST10",
        status=CouponStatus.ACTIVE,
        max_uses=10,
        current_uses=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(coupon)
    db_session.commit()
    db_session.refresh(coupon)
    return coupon


@pytest.fixture
def sample_referral_program(db_session):
    """Create a sample referral program for testing"""
    program = ReferralProgram(
        name="Test Referral Program",
        description="A test referral program",
        referrer_reward_type=RewardType.DISCOUNT,
        referrer_reward_value=20.0,
        referee_reward_type=RewardType.DISCOUNT,
        referee_reward_value=10.0,
        status=ReferralProgramStatus.ACTIVE,
        max_referrals_per_customer=5,
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(program)
    db_session.commit()
    db_session.refresh(program)
    return program


@pytest.fixture
def sample_customer_referral(db_session, sample_customer, sample_referral_program):
    """Create a sample customer referral for testing"""
    referral = CustomerReferral(
        referral_program_id=sample_referral_program.id,
        referrer_customer_id=sample_customer.id,
        referral_code="REF123",
        status=ReferralStatus.ACTIVE,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db_session.add(referral)
    db_session.commit()
    db_session.refresh(referral)
    return referral


@pytest.fixture
def promotion_service(db_session):
    """Create a promotion service instance for testing"""
    from modules.promotions.services.promotion_service import PromotionService

    return PromotionService(db_session)


@pytest.fixture
def coupon_service(db_session):
    """Create a coupon service instance for testing"""
    from modules.promotions.services.coupon_service import CouponService

    return CouponService(db_session)


@pytest.fixture
def referral_service(db_session):
    """Create a referral service instance for testing"""
    from modules.promotions.services.referral_service import ReferralService

    return ReferralService(db_session)


@pytest.fixture
def discount_service(db_session):
    """Create a discount service instance for testing"""
    from modules.promotions.services.discount_service import DiscountCalculationService

    return DiscountCalculationService(db_session)


@pytest.fixture
def ab_testing_service(db_session):
    """Create an A/B testing service instance for testing"""
    from modules.promotions.services.ab_testing_service import ABTestingService

    return ABTestingService(db_session)


# Test data factories
class PromotionFactory:
    """Factory for creating test promotions"""

    @staticmethod
    def create_percentage_promotion(db_session, **kwargs):
        defaults = {
            "name": "Test Percentage Promotion",
            "description": "Test promotion with percentage discount",
            "promotion_type": PromotionType.PERCENTAGE_DISCOUNT,
            "discount_type": DiscountType.PERCENTAGE,
            "discount_value": 15.0,
            "status": PromotionStatus.ACTIVE,
            "start_date": datetime.utcnow() - timedelta(days=1),
            "end_date": datetime.utcnow() + timedelta(days=30),
            "max_uses": 100,
            "current_uses": 0,
        }
        defaults.update(kwargs)

        promotion = Promotion(**defaults)
        db_session.add(promotion)
        db_session.commit()
        db_session.refresh(promotion)
        return promotion

    @staticmethod
    def create_fixed_amount_promotion(db_session, **kwargs):
        defaults = {
            "name": "Test Fixed Amount Promotion",
            "description": "Test promotion with fixed amount discount",
            "promotion_type": PromotionType.FIXED_AMOUNT_DISCOUNT,
            "discount_type": DiscountType.FIXED_AMOUNT,
            "discount_value": 25.0,
            "status": PromotionStatus.ACTIVE,
            "start_date": datetime.utcnow() - timedelta(days=1),
            "end_date": datetime.utcnow() + timedelta(days=30),
            "max_uses": 50,
            "current_uses": 0,
            "minimum_order_amount": 100.0,
        }
        defaults.update(kwargs)

        promotion = Promotion(**defaults)
        db_session.add(promotion)
        db_session.commit()
        db_session.refresh(promotion)
        return promotion

    @staticmethod
    def create_bogo_promotion(db_session, **kwargs):
        defaults = {
            "name": "Test BOGO Promotion",
            "description": "Test buy-one-get-one promotion",
            "promotion_type": PromotionType.BUY_ONE_GET_ONE,
            "discount_type": DiscountType.PERCENTAGE,
            "discount_value": 100.0,  # 100% off on second item
            "status": PromotionStatus.ACTIVE,
            "start_date": datetime.utcnow() - timedelta(days=1),
            "end_date": datetime.utcnow() + timedelta(days=30),
            "max_uses": 25,
            "current_uses": 0,
        }
        defaults.update(kwargs)

        promotion = Promotion(**defaults)
        db_session.add(promotion)
        db_session.commit()
        db_session.refresh(promotion)
        return promotion


class CouponFactory:
    """Factory for creating test coupons"""

    @staticmethod
    def create_coupon(db_session, promotion, **kwargs):
        defaults = {
            "promotion_id": promotion.id,
            "code": "TESTCODE",
            "status": CouponStatus.ACTIVE,
            "max_uses": 10,
            "current_uses": 0,
        }
        defaults.update(kwargs)

        coupon = Coupon(**defaults)
        db_session.add(coupon)
        db_session.commit()
        db_session.refresh(coupon)
        return coupon


class OrderFactory:
    """Factory for creating test orders"""

    @staticmethod
    def create_order(db_session, customer, **kwargs):
        defaults = {
            "customer_id": customer.id,
            "order_number": f"ORD-{datetime.utcnow().timestamp()}",
            "status": "completed",
            "subtotal": 100.0,
            "tax_amount": 10.0,
            "total_amount": 110.0,
            "final_amount": 110.0,
        }
        defaults.update(kwargs)

        order = Order(**defaults)
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        return order


# Export factories for use in tests
@pytest.fixture
def promotion_factory():
    return PromotionFactory


@pytest.fixture
def coupon_factory():
    return CouponFactory


@pytest.fixture
def order_factory():
    return OrderFactory
