# backend/modules/promotions/tests/test_integration_e2e.py

import pytest
import asyncio
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.database import Base, get_db
from backend.main import app
from backend.modules.promotions.models.promotion_models import *
from backend.modules.customers.models.customer_models import Customer
from backend.modules.orders.models.order_models import Order


class TestPromotionSystemE2E:
    """End-to-end integration tests for the complete promotion system"""
    
    @pytest.fixture(scope="class")
    def test_app(self):
        """Create test application with database"""
        # Create test database
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        def override_get_db():
            try:
                db = TestingSessionLocal()
                yield db
            finally:
                db.close()
        
        app.dependency_overrides[get_db] = override_get_db
        
        with TestClient(app) as client:
            yield client, TestingSessionLocal()
        
        app.dependency_overrides.clear()
    
    def test_complete_promotion_lifecycle(self, test_app):
        """Test complete promotion lifecycle from creation to analytics"""
        client, db_session = test_app
        
        # Step 1: Create a customer
        customer = Customer(
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            loyalty_points=100,
            total_spent=0.0,
            total_orders=0
        )
        db_session.add(customer)
        db_session.commit()
        
        # Step 2: Create promotion via API
        promotion_data = {
            "name": "E2E Test Promotion",
            "description": "End-to-end test promotion",
            "promotion_type": "percentage_discount",
            "discount_type": "percentage",
            "discount_value": 20.0,
            "start_date": datetime.utcnow().isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "max_uses": 100,
            "is_active": True
        }
        
        # Mock authentication for admin user
        headers = {"Authorization": "Bearer admin_token"}
        
        # Create promotion
        response = client.post("/api/v1/promotions/", json=promotion_data, headers=headers)
        assert response.status_code == 201
        promotion = response.json()
        promotion_id = promotion["id"]
        
        # Step 3: Activate promotion
        response = client.post(f"/api/v1/promotions/{promotion_id}/activate", headers=headers)
        assert response.status_code == 200
        
        # Step 4: Create coupons for the promotion
        coupon_data = {
            "count": 5,
            "coupon_config": {
                "max_uses": 1,
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
        }
        
        response = client.post(f"/api/v1/coupons/bulk/{promotion_id}", json=coupon_data, headers=headers)
        assert response.status_code == 201
        coupons = response.json()["coupons"]
        test_coupon_code = coupons[0]["code"]
        
        # Step 5: Validate coupon
        response = client.post(
            f"/api/v1/coupons/validate/{test_coupon_code}",
            json={"customer_id": customer.id},
            headers=headers
        )
        assert response.status_code == 200
        assert response.json()["is_valid"] is True
        
        # Step 6: Calculate discount for order
        order_items = [
            {"product_id": 1, "quantity": 2, "unit_price": 50.0, "subtotal": 100.0}
        ]
        
        discount_data = {
            "order_items": order_items,
            "customer_id": customer.id
        }
        
        response = client.post(
            f"/api/v1/promotions/{promotion_id}/calculate-discount",
            json=discount_data,
            headers=headers
        )
        assert response.status_code == 200
        discount_amount = response.json()["discount_amount"]
        assert discount_amount == 20.0  # 20% of 100
        
        # Step 7: Create order and apply discount
        order = Order(
            customer_id=customer.id,
            order_number="E2E-001",
            status="pending",
            subtotal=100.0,
            tax_amount=10.0,
            total_amount=110.0,
            final_amount=110.0
        )
        db_session.add(order)
        db_session.commit()
        
        # Apply discount to order
        apply_data = {
            "order_items": order_items,
            "coupon_code": test_coupon_code
        }
        
        response = client.post(
            f"/api/v1/orders/{order.id}/apply-discount",
            json=apply_data,
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 8: Verify discount was applied
        response = client.get(f"/api/v1/orders/{order.id}", headers=headers)
        updated_order = response.json()
        assert updated_order["discount_amount"] == 20.0
        assert updated_order["final_amount"] == 90.0  # 110 - 20
        
        # Step 9: Check promotion usage statistics
        response = client.get(f"/api/v1/promotions/{promotion_id}/statistics", headers=headers)
        assert response.status_code == 200
        stats = response.json()
        assert stats["total_usage"] == 1
        assert stats["total_discount_amount"] == 20.0
        
        # Step 10: Generate analytics report
        response = client.get("/api/v1/analytics/performance-report", headers=headers)
        assert response.status_code == 200
        report = response.json()
        assert len(report["promotion_details"]) >= 1
    
    def test_referral_program_complete_flow(self, test_app):
        """Test complete referral program flow"""
        client, db_session = test_app
        
        # Create referrer and referee customers
        referrer = Customer(
            email="referrer@example.com",
            first_name="Alice",
            last_name="Referrer",
            loyalty_points=0,
            total_spent=0.0,
            total_orders=0
        )
        referee = Customer(
            email="referee@example.com",
            first_name="Bob",
            last_name="Referee",
            loyalty_points=0,
            total_spent=0.0,
            total_orders=0
        )
        db_session.add_all([referrer, referee])
        db_session.commit()
        
        headers = {"Authorization": "Bearer admin_token"}
        
        # Step 1: Create referral program
        program_data = {
            "name": "E2E Referral Program",
            "description": "Test referral program",
            "referrer_reward_type": "points",
            "referrer_reward_value": 100,
            "referee_reward_type": "discount",
            "referee_reward_value": 10.0,
            "status": "active",
            "max_referrals_per_customer": 5
        }
        
        response = client.post("/api/v1/referrals/programs/", json=program_data, headers=headers)
        assert response.status_code == 201
        program = response.json()
        program_id = program["id"]
        
        # Step 2: Generate referral code for referrer
        response = client.post(
            f"/api/v1/referrals/programs/{program_id}/generate-code/{referrer.id}",
            headers=headers
        )
        assert response.status_code == 201
        referral_data = response.json()
        referral_code = referral_data["referral_code"]
        
        # Step 3: Validate referral code
        response = client.get(f"/api/v1/referrals/validate/{referral_code}", headers=headers)
        assert response.status_code == 200
        assert response.json()["is_valid"] is True
        
        # Step 4: Process referral (referee signs up using code)
        referral_process_data = {
            "referral_code": referral_code,
            "referee_customer_id": referee.id
        }
        
        response = client.post("/api/v1/referrals/process", json=referral_process_data, headers=headers)
        assert response.status_code == 200
        
        # Step 5: Complete referral by having referee make a purchase
        order = Order(
            customer_id=referee.id,
            order_number="REF-001",
            status="completed",
            subtotal=50.0,
            tax_amount=5.0,
            total_amount=55.0,
            final_amount=55.0
        )
        db_session.add(order)
        db_session.commit()
        
        completion_data = {
            "referral_code": referral_code,
            "order_id": order.id
        }
        
        response = client.post("/api/v1/referrals/complete", json=completion_data, headers=headers)
        assert response.status_code == 200
        
        # Step 6: Verify rewards were issued
        response = client.get(f"/api/v1/referrals/customer/{referrer.id}/summary", headers=headers)
        assert response.status_code == 200
        referrer_summary = response.json()
        assert referrer_summary["total_successful_referrals"] == 1
        assert referrer_summary["total_rewards_earned"] > 0
        
        # Step 7: Check referral analytics
        response = client.get("/api/v1/analytics/referral-analytics", headers=headers)
        assert response.status_code == 200
        analytics = response.json()
        assert analytics["total_referrals"] >= 1
    
    def test_ab_testing_complete_flow(self, test_app):
        """Test complete A/B testing flow"""
        client, db_session = test_app
        
        headers = {"Authorization": "Bearer admin_token"}
        
        # Step 1: Create A/B test
        control_promotion = {
            "name": "Control - 10% Off",
            "description": "Control promotion",
            "promotion_type": "percentage_discount",
            "discount_type": "percentage",
            "discount_value": 10.0,
            "start_date": datetime.utcnow().isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "max_uses": 1000
        }
        
        variant_promotions = [{
            "name": "Variant - 15% Off",
            "description": "Variant promotion",
            "promotion_type": "percentage_discount",
            "discount_type": "percentage",
            "discount_value": 15.0,
            "start_date": datetime.utcnow().isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "max_uses": 1000
        }]
        
        test_config = {
            "control_traffic_percentage": 50,
            "variant_traffic_percentages": [50],
            "duration_days": 14,
            "minimum_sample_size": 100
        }
        
        ab_test_data = {
            "test_name": "E2E A/B Test",
            "control_promotion": control_promotion,
            "variant_promotions": variant_promotions,
            "test_config": test_config
        }
        
        response = client.post("/api/v1/ab-testing/create", json=ab_test_data, headers=headers)
        assert response.status_code == 200
        test_result = response.json()
        test_id = test_result["test_id"]
        
        # Step 2: Start A/B test
        response = client.post(f"/api/v1/ab-testing/{test_id}/start", headers=headers)
        assert response.status_code == 200
        
        # Step 3: Assign users to variants
        assignments = []
        for customer_id in range(1, 21):  # Test 20 users
            assignment_data = {"customer_id": customer_id}
            response = client.post(
                f"/api/v1/ab-testing/{test_id}/assign",
                json=assignment_data,
                headers=headers
            )
            assert response.status_code == 200
            assignments.append(response.json())
        
        # Step 4: Verify consistent assignment
        first_assignment = client.post(
            f"/api/v1/ab-testing/{test_id}/assign",
            json={"customer_id": 1},
            headers=headers
        ).json()
        
        second_assignment = client.post(
            f"/api/v1/ab-testing/{test_id}/assign",
            json={"customer_id": 1},
            headers=headers
        ).json()
        
        assert first_assignment["assigned_variant"] == second_assignment["assigned_variant"]
        
        # Step 5: Get test results
        response = client.get(f"/api/v1/ab-testing/{test_id}/results", headers=headers)
        assert response.status_code == 200
        results = response.json()
        assert results["test_id"] == test_id
        assert len(results["variant_results"]) == 2
        
        # Step 6: Stop test
        response = client.post(
            f"/api/v1/ab-testing/{test_id}/stop",
            json={"winning_variant": "control"},
            headers=headers
        )
        assert response.status_code == 200
    
    def test_automation_triggers_flow(self, test_app):
        """Test automation triggers complete flow"""
        client, db_session = test_app
        
        headers = {"Authorization": "Bearer admin_token"}
        
        # Step 1: Create automated promotion
        automation_data = {
            "name": "Birthday Promotion",
            "trigger_type": "customer_lifecycle",
            "trigger_conditions": {
                "event_type": "birthday"
            },
            "promotion_config": {
                "name": "Happy Birthday",
                "description": "Birthday special discount",
                "promotion_type": "percentage_discount",
                "discount_type": "percentage",
                "discount_value": 25.0,
                "start_date": datetime.utcnow().isoformat(),
                "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
                "max_uses": 500
            },
            "automation_options": {
                "duration_hours": 48,
                "max_triggers": 1
            }
        }
        
        response = client.post("/api/v1/automation/create", json=automation_data, headers=headers)
        assert response.status_code == 200
        automated_promotion = response.json()
        
        # Step 2: Test trigger processing
        response = client.post(
            "/api/v1/automation/process-triggers",
            json={"trigger_type": "customer_lifecycle"},
            headers=headers
        )
        assert response.status_code == 200
        
        # Step 3: Get automation performance
        response = client.get("/api/v1/automation/performance", headers=headers)
        assert response.status_code == 200
        performance = response.json()
        assert "total_automated_promotions" in performance
    
    def test_bulk_operations_performance(self, test_app):
        """Test bulk operations and performance"""
        client, db_session = test_app
        
        headers = {"Authorization": "Bearer admin_token"}
        
        # Step 1: Create promotion for bulk coupons
        promotion_data = {
            "name": "Bulk Test Promotion",
            "description": "Promotion for bulk coupon testing",
            "promotion_type": "percentage_discount",
            "discount_type": "percentage",
            "discount_value": 10.0,
            "start_date": datetime.utcnow().isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "max_uses": 10000
        }
        
        response = client.post("/api/v1/promotions/", json=promotion_data, headers=headers)
        assert response.status_code == 201
        promotion = response.json()
        promotion_id = promotion["id"]
        
        # Step 2: Test bulk coupon creation (performance test)
        import time
        start_time = time.time()
        
        coupon_data = {
            "count": 1000,  # Create 1000 coupons
            "coupon_config": {
                "max_uses": 1,
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
        }
        
        response = client.post(f"/api/v1/coupons/bulk/{promotion_id}", json=coupon_data, headers=headers)
        creation_time = time.time() - start_time
        
        assert response.status_code == 201
        assert len(response.json()["coupons"]) == 1000
        # Should complete within reasonable time (adjust threshold as needed)
        assert creation_time < 30.0  # 30 seconds max
        
        # Step 3: Test bulk promotion status update
        promotion_ids = [promotion_id]
        start_time = time.time()
        
        bulk_update_data = {
            "promotion_ids": promotion_ids,
            "status": "active"
        }
        
        response = client.post("/api/v1/promotions/bulk-update-status", json=bulk_update_data, headers=headers)
        update_time = time.time() - start_time
        
        assert response.status_code == 200
        assert update_time < 5.0  # Should be very fast
        
        # Step 4: Test analytics with large dataset
        start_time = time.time()
        response = client.get("/api/v1/analytics/performance-report", headers=headers)
        analytics_time = time.time() - start_time
        
        assert response.status_code == 200
        assert analytics_time < 10.0  # Analytics should be reasonably fast
    
    def test_concurrent_usage_handling(self, test_app):
        """Test concurrent coupon/promotion usage handling"""
        client, db_session = test_app
        
        headers = {"Authorization": "Bearer admin_token"}
        
        # Create promotion with limited uses
        promotion_data = {
            "name": "Limited Use Promotion",
            "description": "Promotion with limited uses for concurrency testing",
            "promotion_type": "percentage_discount",
            "discount_type": "percentage",
            "discount_value": 50.0,
            "start_date": datetime.utcnow().isoformat(),
            "end_date": (datetime.utcnow() + timedelta(days=30)).isoformat(),
            "max_uses": 3  # Very limited
        }
        
        response = client.post("/api/v1/promotions/", json=promotion_data, headers=headers)
        promotion = response.json()
        promotion_id = promotion["id"]
        
        # Activate promotion
        client.post(f"/api/v1/promotions/{promotion_id}/activate", headers=headers)
        
        # Create coupon with limited uses
        coupon_data = {
            "count": 1,
            "coupon_config": {
                "max_uses": 2,  # Limited uses
                "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
            }
        }
        
        response = client.post(f"/api/v1/coupons/bulk/{promotion_id}", json=coupon_data, headers=headers)
        coupon_code = response.json()["coupons"][0]["code"]
        
        # Create multiple customers and orders
        customers = []
        orders = []
        for i in range(5):
            customer = Customer(
                email=f"customer{i}@example.com",
                first_name=f"Customer{i}",
                last_name="Test"
            )
            db_session.add(customer)
            db_session.commit()
            customers.append(customer)
            
            order = Order(
                customer_id=customer.id,
                order_number=f"CONC-{i:03d}",
                status="pending",
                subtotal=100.0,
                total_amount=100.0,
                final_amount=100.0
            )
            db_session.add(order)
            db_session.commit()
            orders.append(order)
        
        # Test concurrent coupon usage
        successful_uses = 0
        failed_uses = 0
        
        for i, order in enumerate(orders):
            try:
                order_items = [{"product_id": 1, "quantity": 1, "unit_price": 100.0, "subtotal": 100.0}]
                apply_data = {
                    "order_items": order_items,
                    "coupon_code": coupon_code
                }
                
                response = client.post(
                    f"/api/v1/orders/{order.id}/apply-discount",
                    json=apply_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    successful_uses += 1
                else:
                    failed_uses += 1
                    
            except Exception:
                failed_uses += 1
        
        # Should respect usage limits
        assert successful_uses <= 2  # Coupon max_uses = 2
        assert failed_uses >= 3  # Remaining attempts should fail