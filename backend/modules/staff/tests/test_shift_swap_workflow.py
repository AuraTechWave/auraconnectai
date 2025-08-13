import pytest
from datetime import datetime, timedelta, date, timezone
from sqlalchemy.orm import Session
from unittest.mock import Mock, patch

from modules.staff.models.scheduling_models import (
    ShiftSwap, EnhancedShift, SwapApprovalRule
)
from modules.staff.models.staff_models import StaffMember, Role
from modules.staff.enums.scheduling_enums import (
    ShiftStatus, SwapStatus, ShiftType
)
from modules.staff.services.shift_swap_service import ShiftSwapService
from modules.core.models import Restaurant, Location
from .factories import (
    RestaurantFactory, LocationFactory, RoleFactory,
    StaffMemberFactory, ShiftFactory, SwapApprovalRuleFactory,
    ShiftSwapFactory
)


class TestShiftSwapWorkflow:
    """Test cases for enhanced shift swap workflow"""
    
    @pytest.fixture
    def db_session(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def test_restaurant(self):
        """Create test restaurant"""
        return RestaurantFactory().create()
    
    @pytest.fixture
    def test_location(self, test_restaurant):
        """Create test location"""
        return LocationFactory(restaurant=test_restaurant).create()
    
    @pytest.fixture
    def test_role(self):
        """Create test role"""
        return RoleFactory().create()
    
    @pytest.fixture
    def test_staff(self, test_role):
        """Create test staff members"""
        staff1 = StaffMemberFactory(
            id=1,
            name="John Doe",
            role=test_role,
            tenure_days=120  # 4 months tenure
        ).create()
        
        staff2 = StaffMemberFactory(
            id=2,
            name="Jane Smith",
            role=test_role,
            tenure_days=180  # 6 months tenure
        ).create()
        
        return staff1, staff2
    
    @pytest.fixture
    def test_shifts(self, test_staff, test_location, test_role):
        """Create test shifts"""
        staff1, staff2 = test_staff
        return ShiftFactory.create_pair(staff1, staff2, test_location, test_role)
            role_id=test_role.id,
            role=test_role,
            location_id=test_location.id,
            location=test_location,
            date=tomorrow.date(),
            start_time=tomorrow.replace(hour=10, minute=0),
            end_time=tomorrow.replace(hour=18, minute=0),
            shift_type=ShiftType.REGULAR,
            status=ShiftStatus.SCHEDULED
        )
        
        return shift1, shift2
    
    @pytest.fixture
    def test_swap(self, test_staff, test_shifts):
        """Create test swap request"""
        staff1, staff2 = test_staff
        shift1, shift2 = test_shifts
        
        return ShiftSwap(
            id=1,
            requester_id=staff1.id,
            requester=staff1,
            from_shift_id=shift1.id,
            from_shift=shift1,
            to_shift_id=shift2.id,
            to_shift=shift2,
            status=SwapStatus.PENDING,
            reason="Personal emergency",
            created_at=datetime.utcnow()
        )
    
    @pytest.fixture
    def approval_rule(self, test_restaurant):
        """Create test approval rule"""
        return SwapApprovalRuleFactory(
            restaurant_id=test_restaurant.id,
            rule_name="Standard Auto-Approval",
            priority=10,
            requires_manager_approval=False
        ).create()
    
    def test_auto_approval_eligible(self, db_session, test_swap, approval_rule):
        """Test auto-approval eligibility check"""
        # Setup
        service = ShiftSwapService(db_session)
        db_session.query(SwapApprovalRule).filter.return_value.order_by.return_value.all.return_value = [approval_rule]
        db_session.query(ShiftSwap).filter.return_value.count.return_value = 1  # One swap this month
        
        # Test
        eligible, reason = service.check_auto_approval_eligibility(test_swap, 1)
        
        # Assert
        assert eligible is True
        assert "Auto-approved by rule" in reason
    
    def test_auto_approval_insufficient_notice(self, db_session, test_swap, approval_rule):
        """Test auto-approval fails with insufficient notice"""
        # Setup - shift starting in 12 hours
        test_swap.from_shift.start_time = datetime.now(timezone.utc) + timedelta(hours=12)
        service = ShiftSwapService(db_session)
        db_session.query(SwapApprovalRule).filter.return_value.order_by.return_value.all.return_value = [approval_rule]
        
        # Test
        eligible, reason = service.check_auto_approval_eligibility(test_swap, 1)
        
        # Assert
        assert eligible is False
        assert "No matching auto-approval rules" in reason
    
    def test_auto_approval_monthly_limit(self, db_session, test_swap, approval_rule):
        """Test auto-approval fails when monthly limit reached"""
        # Setup
        service = ShiftSwapService(db_session)
        db_session.query(SwapApprovalRule).filter.return_value.order_by.return_value.all.return_value = [approval_rule]
        db_session.query(ShiftSwap).filter.return_value.count.return_value = 3  # Already at limit
        
        # Test
        eligible, reason = service.check_auto_approval_eligibility(test_swap, 1)
        
        # Assert
        assert eligible is False
    
    def test_process_swap_request_auto_approved(self, db_session, test_swap):
        """Test processing swap request that gets auto-approved"""
        # Setup
        service = ShiftSwapService(db_session)
        db_session.query(ShiftSwap).filter.return_value.first.return_value = test_swap
        
        with patch.object(service, 'check_auto_approval_eligibility', return_value=(True, "Auto-approved")):
            with patch.object(service, '_execute_swap') as mock_execute:
                with patch.object(service, '_send_approval_notification') as mock_notify:
                    # Test
                    result = service.process_swap_request(1, 1)
                    
                    # Assert
                    assert result.status == SwapStatus.APPROVED
                    assert result.approval_level == "auto"
                    assert result.auto_approval_eligible is True
                    mock_execute.assert_called_once()
                    mock_notify.assert_called_once()
    
    def test_process_swap_request_needs_approval(self, db_session, test_swap):
        """Test processing swap request that needs manager approval"""
        # Setup
        service = ShiftSwapService(db_session)
        db_session.query(ShiftSwap).filter.return_value.first.return_value = test_swap
        
        with patch.object(service, 'check_auto_approval_eligibility', return_value=(False, "Needs approval")):
            with patch.object(service, '_send_approval_request_notification') as mock_notify:
                # Test
                result = service.process_swap_request(1, 1)
                
                # Assert
                assert result.status == SwapStatus.PENDING
                assert result.auto_approval_eligible is False
                assert result.response_deadline is not None
                mock_notify.assert_called_once()
    
    def test_approve_swap(self, db_session, test_swap):
        """Test manual swap approval"""
        # Setup
        service = ShiftSwapService(db_session)
        db_session.query(ShiftSwap).filter.return_value.first.return_value = test_swap
        
        with patch.object(service, '_execute_swap') as mock_execute:
            with patch.object(service, '_send_approval_notification') as mock_notify:
                # Test
                result = service.approve_swap(1, 99, "Approved by manager")
                
                # Assert
                assert result.status == SwapStatus.APPROVED
                assert result.approved_by_id == 99
                assert result.approval_level == "manager"
                assert result.manager_notes == "Approved by manager"
                mock_execute.assert_called_once()
                mock_notify.assert_called_once()
    
    def test_reject_swap(self, db_session, test_swap):
        """Test swap rejection"""
        # Setup
        service = ShiftSwapService(db_session)
        db_session.query(ShiftSwap).filter.return_value.first.return_value = test_swap
        
        with patch.object(service, '_send_rejection_notification') as mock_notify:
            # Test
            result = service.reject_swap(1, 99, "Not enough coverage")
            
            # Assert
            assert result.status == SwapStatus.REJECTED
            assert result.approved_by_id == 99
            assert result.rejection_reason == "Not enough coverage"
            mock_notify.assert_called_once()
    
    def test_cancel_swap(self, db_session, test_swap):
        """Test swap cancellation by requester"""
        # Setup
        service = ShiftSwapService(db_session)
        db_session.query(ShiftSwap).filter.return_value.first.return_value = test_swap
        
        with patch.object(service, '_send_cancellation_notification') as mock_notify:
            # Test
            result = service.cancel_swap(1, test_swap.requester_id)
            
            # Assert
            assert result.status == SwapStatus.CANCELLED
            mock_notify.assert_called_once()
    
    def test_cancel_swap_wrong_user(self, db_session, test_swap):
        """Test swap cancellation fails for wrong user"""
        # Setup
        service = ShiftSwapService(db_session)
        db_session.query(ShiftSwap).filter.return_value.first.return_value = test_swap
        
        # Test & Assert
        with pytest.raises(ValueError, match="Only the requester can cancel"):
            service.cancel_swap(1, 999)
    
    def test_execute_swap_shifts(self, db_session, test_swap, test_shifts):
        """Test executing swap between two shifts"""
        # Setup
        service = ShiftSwapService(db_session)
        shift1, shift2 = test_shifts
        original_staff1 = shift1.staff_id
        original_staff2 = shift2.staff_id
        
        # Test
        service._execute_swap(test_swap)
        
        # Assert - staff IDs should be swapped
        assert shift1.staff_id == original_staff2
        assert shift2.staff_id == original_staff1
    
    def test_execute_swap_to_staff(self, db_session, test_staff, test_shifts):
        """Test executing swap to specific staff"""
        # Setup
        staff1, staff2 = test_staff
        shift1, _ = test_shifts
        swap = ShiftSwap(
            from_shift=shift1,
            to_staff_id=staff2.id
        )
        service = ShiftSwapService(db_session)
        
        # Test
        service._execute_swap(swap)
        
        # Assert
        assert shift1.staff_id == staff2.id
    
    def test_get_pending_swaps_for_approval(self, db_session):
        """Test getting pending swaps for manager approval"""
        # Setup
        service = ShiftSwapService(db_session)
        mock_swaps = [Mock(spec=ShiftSwap), Mock(spec=ShiftSwap)]
        
        query_mock = Mock()
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = mock_swaps
        
        db_session.query.return_value = query_mock
        
        # Test
        result = service.get_pending_swaps_for_approval(1, 1)
        
        # Assert
        assert len(result) == 2
        db_session.query.assert_called_with(ShiftSwap)
    
    def test_get_swap_history(self, db_session):
        """Test getting swap history statistics"""
        # Setup
        service = ShiftSwapService(db_session)
        
        # Create mock swaps
        mock_swaps = [
            Mock(status=SwapStatus.APPROVED, approved_at=datetime.utcnow(), 
                 created_at=datetime.utcnow() - timedelta(hours=2), 
                 approval_level="auto", reason="Sick"),
            Mock(status=SwapStatus.APPROVED, approved_at=datetime.utcnow(), 
                 created_at=datetime.utcnow() - timedelta(hours=4), 
                 approval_level="manager", reason="Family emergency"),
            Mock(status=SwapStatus.REJECTED, created_at=datetime.utcnow(), 
                 reason="Sick"),
            Mock(status=SwapStatus.PENDING, created_at=datetime.utcnow(), 
                 reason="Personal"),
        ]
        
        query_mock = Mock()
        query_mock.join.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.all.return_value = mock_swaps
        
        db_session.query.return_value = query_mock
        
        # Test
        result = service.get_swap_history(1)
        
        # Assert
        assert result["total_swaps"] == 4
        assert result["approved_swaps"] == 2
        assert result["rejected_swaps"] == 1
        assert result["pending_swaps"] == 1
        assert result["average_approval_time_hours"] == 3.0  # (2 + 4) / 2
        assert len(result["most_common_reasons"]) > 0
    
    def test_check_rule_hours_difference(self, db_session):
        """Test rule check for hours difference"""
        # Setup
        service = ShiftSwapService(db_session)
        
        from_shift = Mock(
            start_time=datetime.utcnow() + timedelta(days=2, hours=9),
            end_time=datetime.utcnow() + timedelta(days=2, hours=17),
            role_id=1,
            location_id=1
        )
        
        to_shift = Mock(
            start_time=datetime.utcnow() + timedelta(days=2, hours=8),
            end_time=datetime.utcnow() + timedelta(days=2, hours=18),  # 10 hour shift
            role_id=1,
            location_id=1
        )
        
        swap = Mock(
            requester=Mock(created_at=datetime.utcnow() - timedelta(days=100)),
            requester_id=1
        )
        
        rule = Mock(
            max_hours_difference=1.5,  # Max 1.5 hour difference
            same_role_required=True,
            same_location_required=True,
            min_advance_notice_hours=24,
            max_advance_notice_hours=None,
            blackout_dates=[],
            min_tenure_days=90,
            max_swaps_per_month=3,
            peak_hours_restricted=False,
            restricted_shifts=[]
        )
        
        db_session.query(ShiftSwap).filter.return_value.count.return_value = 0
        
        # Test
        eligible, reason = service._check_rule(swap, from_shift, to_shift, None, rule)
        
        # Assert
        assert eligible is False
        assert "Shift hours difference exceeds limit" in reason


class TestShiftSwapAPI:
    """Test API endpoints for shift swap workflow"""
    
    @pytest.fixture
    def client(self, test_app):
        """Test client"""
        return test_app
    
    def test_request_shift_swap(self, client, auth_headers):
        """Test requesting a shift swap"""
        # Setup
        swap_data = {
            "from_shift_id": 1,
            "to_shift_id": 2,
            "reason": "Personal emergency",
            "urgency": "urgent"
        }
        
        # Test
        response = client.post(
            "/api/v1/staff/swaps",
            json=swap_data,
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["from_shift_id"] == 1
        assert data["to_shift_id"] == 2
        assert data["reason"] == "Personal emergency"
    
    def test_list_shift_swaps(self, client, auth_headers):
        """Test listing shift swaps with filters"""
        # Test
        response = client.get(
            "/api/v1/staff/swaps?status=pending&page=1&per_page=10",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_approve_shift_swap(self, client, manager_auth_headers):
        """Test approving a shift swap"""
        # Setup
        approval_data = {
            "status": "approved",
            "manager_notes": "Approved - coverage available"
        }
        
        # Test
        response = client.put(
            "/api/v1/staff/swaps/1/approve",
            json=approval_data,
            headers=manager_auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "approved" in data["message"].lower()
    
    def test_reject_shift_swap(self, client, manager_auth_headers):
        """Test rejecting a shift swap"""
        # Setup
        rejection_data = {
            "status": "rejected",
            "rejection_reason": "Insufficient coverage"
        }
        
        # Test
        response = client.put(
            "/api/v1/staff/swaps/1/approve",
            json=rejection_data,
            headers=manager_auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "rejected" in data["message"].lower()
    
    def test_cancel_shift_swap(self, client, auth_headers):
        """Test cancelling a shift swap"""
        # Test
        response = client.delete(
            "/api/v1/staff/swaps/1",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "cancelled" in data["message"].lower()
    
    def test_get_swap_history(self, client, auth_headers):
        """Test getting swap history statistics"""
        # Test
        response = client.get(
            "/api/v1/staff/swaps/history/stats",
            headers=auth_headers
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "total_swaps" in data
        assert "approved_swaps" in data
        assert "average_approval_time_hours" in data
        assert "most_common_reasons" in data