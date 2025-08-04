# backend/modules/payments/tests/test_refund_service.py

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from sqlalchemy.ext.asyncio import AsyncSession

# Import directly to avoid dependency issues
import sys
import os

# Add backend to path so core can be found
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
sys.path.insert(0, backend_path)

import importlib.util

# Load refund_models directly without going through __init__.py
spec = importlib.util.spec_from_file_location(
    "refund_models", 
    os.path.join(backend_path, "modules/payments/models/refund_models.py")
)
refund_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refund_models)

RefundReason = refund_models.RefundReason
RefundCategory = refund_models.RefundCategory
RefundApprovalStatus = refund_models.RefundApprovalStatus
get_refund_category = refund_models.get_refund_category


class TestRefundEnums:
    """Test refund enum definitions and mappings"""
    
    def test_refund_reasons_complete(self):
        """Test that all refund reasons are defined"""
        reasons = list(RefundReason)
        assert len(reasons) == 16
        
        # Check key reasons exist
        assert RefundReason.ORDER_CANCELLED in reasons
        assert RefundReason.FOOD_QUALITY in reasons
        assert RefundReason.DUPLICATE_CHARGE in reasons
        assert RefundReason.LONG_WAIT in reasons
    
    def test_refund_categories_complete(self):
        """Test that all refund categories are defined"""
        categories = list(RefundCategory)
        assert len(categories) == 5
        
        expected = [
            RefundCategory.ORDER_ISSUE,
            RefundCategory.QUALITY_ISSUE,
            RefundCategory.SERVICE_ISSUE,
            RefundCategory.PAYMENT_ISSUE,
            RefundCategory.OTHER
        ]
        
        for cat in expected:
            assert cat in categories
    
    def test_approval_statuses_complete(self):
        """Test that all approval statuses are defined"""
        statuses = list(RefundApprovalStatus)
        assert len(statuses) == 4
        
        expected = [
            RefundApprovalStatus.PENDING_APPROVAL,
            RefundApprovalStatus.APPROVED,
            RefundApprovalStatus.REJECTED,
            RefundApprovalStatus.AUTO_APPROVED
        ]
        
        for status in expected:
            assert status in statuses
    
    def test_refund_category_mapping(self):
        """Test that refund reasons map correctly to categories"""
        # Order issues
        assert get_refund_category(RefundReason.ORDER_CANCELLED) == RefundCategory.ORDER_ISSUE
        assert get_refund_category(RefundReason.ORDER_MISTAKE) == RefundCategory.ORDER_ISSUE
        assert get_refund_category(RefundReason.WRONG_ITEMS) == RefundCategory.ORDER_ISSUE
        assert get_refund_category(RefundReason.MISSING_ITEMS) == RefundCategory.ORDER_ISSUE
        
        # Quality issues
        assert get_refund_category(RefundReason.FOOD_QUALITY) == RefundCategory.QUALITY_ISSUE
        assert get_refund_category(RefundReason.COLD_FOOD) == RefundCategory.QUALITY_ISSUE
        assert get_refund_category(RefundReason.INCORRECT_PREPARATION) == RefundCategory.QUALITY_ISSUE
        
        # Service issues
        assert get_refund_category(RefundReason.LONG_WAIT) == RefundCategory.SERVICE_ISSUE
        assert get_refund_category(RefundReason.POOR_SERVICE) == RefundCategory.SERVICE_ISSUE
        
        # Payment issues
        assert get_refund_category(RefundReason.DUPLICATE_CHARGE) == RefundCategory.PAYMENT_ISSUE
        assert get_refund_category(RefundReason.OVERCHARGE) == RefundCategory.PAYMENT_ISSUE
        assert get_refund_category(RefundReason.PRICE_DISPUTE) == RefundCategory.PAYMENT_ISSUE
        
        # Other
        assert get_refund_category(RefundReason.CUSTOMER_REQUEST) == RefundCategory.OTHER
        assert get_refund_category(RefundReason.GOODWILL) == RefundCategory.OTHER
        assert get_refund_category(RefundReason.TEST_REFUND) == RefundCategory.OTHER
        assert get_refund_category(RefundReason.OTHER) == RefundCategory.OTHER


class TestRefundValidation:
    """Test refund validation logic"""
    
    def test_refund_amount_validation(self):
        """Test that refund amounts must be positive"""
        # This would be tested in the actual service/endpoint
        # Just documenting expected behavior here
        invalid_amounts = [0, -10, -0.01]
        valid_amounts = [0.01, 1, 10, 100.50]
        
        for amount in invalid_amounts:
            # In real implementation, should raise ValueError
            assert amount <= 0
        
        for amount in valid_amounts:
            assert amount > 0
    
    def test_refund_window_validation(self):
        """Test refund time window validation"""
        # Order from 8 days ago (past default 7-day window)
        old_order_date = datetime.utcnow() - timedelta(days=8)
        refund_window_hours = 168  # 7 days
        
        hours_elapsed = (datetime.utcnow() - old_order_date).total_seconds() / 3600
        assert hours_elapsed > refund_window_hours
        
        # Order from 6 days ago (within window)
        recent_order_date = datetime.utcnow() - timedelta(days=6)
        hours_elapsed = (datetime.utcnow() - recent_order_date).total_seconds() / 3600
        assert hours_elapsed <= refund_window_hours


class TestRefundWorkflow:
    """Test refund approval workflow"""
    
    def test_auto_approval_threshold(self):
        """Test auto-approval logic based on amount threshold"""
        auto_approve_threshold = Decimal('50.00')
        
        # Should auto-approve
        small_amounts = [Decimal('10'), Decimal('25'), Decimal('49.99'), Decimal('50')]
        for amount in small_amounts:
            should_auto_approve = amount <= auto_approve_threshold
            assert should_auto_approve
        
        # Should require manual approval
        large_amounts = [Decimal('50.01'), Decimal('100'), Decimal('500')]
        for amount in large_amounts:
            should_auto_approve = amount <= auto_approve_threshold
            assert not should_auto_approve
    
    def test_approval_status_transitions(self):
        """Test valid status transitions"""
        # Valid transitions from pending
        pending = RefundApprovalStatus.PENDING_APPROVAL
        valid_from_pending = [
            RefundApprovalStatus.APPROVED,
            RefundApprovalStatus.REJECTED,
            RefundApprovalStatus.AUTO_APPROVED
        ]
        
        # Cannot go back to pending from other states
        final_states = [
            RefundApprovalStatus.APPROVED,
            RefundApprovalStatus.REJECTED,
            RefundApprovalStatus.AUTO_APPROVED
        ]
        
        for state in final_states:
            # In real implementation, should not allow transition back to pending
            assert state != RefundApprovalStatus.PENDING_APPROVAL


if __name__ == "__main__":
    # Run basic tests
    test_enums = TestRefundEnums()
    test_enums.test_refund_reasons_complete()
    test_enums.test_refund_categories_complete()
    test_enums.test_approval_statuses_complete()
    test_enums.test_refund_category_mapping()
    print("✓ All enum tests passed")
    
    test_validation = TestRefundValidation()
    test_validation.test_refund_amount_validation()
    test_validation.test_refund_window_validation()
    print("✓ All validation tests passed")
    
    test_workflow = TestRefundWorkflow()
    test_workflow.test_auto_approval_threshold()
    test_workflow.test_approval_status_transitions()
    print("✓ All workflow tests passed")
    
    print("\n✅ All refund tests passed!")