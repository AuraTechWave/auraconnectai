from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta, timezone, date
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
import logging

from ..models.scheduling_models import (
    ShiftSwap, EnhancedShift, StaffAvailability, SwapApprovalRule
)
from ..models.staff_models import StaffMember
from ..enums.scheduling_enums import (
    ShiftStatus, SwapStatus, AvailabilityStatus
)
from .scheduling_service import SchedulingService
from ..config.shift_swap_config import shift_swap_config

logger = logging.getLogger(__name__)


class ShiftSwapService:
    def __init__(self, db: Session):
        self.db = db
        self.scheduling_service = SchedulingService(db)
    
    def check_auto_approval_eligibility(
        self, 
        swap: ShiftSwap,
        restaurant_id: int
    ) -> Tuple[bool, str]:
        """Check if a swap request is eligible for auto-approval"""
        
        # Get active approval rules sorted by priority
        rules = self.db.query(SwapApprovalRule).filter(
            and_(
                SwapApprovalRule.restaurant_id == restaurant_id,
                SwapApprovalRule.is_active == True
            )
        ).order_by(SwapApprovalRule.priority.desc()).all()
        
        if not rules:
            return False, "No approval rules configured"
        
        # Get shift details
        from_shift = swap.from_shift
        to_shift = swap.to_shift if swap.to_shift_id else None
        to_staff = swap.to_staff if swap.to_staff_id else None
        
        # Check each rule
        for rule in rules:
            eligible, reason = self._check_rule(swap, from_shift, to_shift, to_staff, rule)
            if not eligible:
                continue
            
            # If we get here, the rule allows auto-approval
            return True, f"Auto-approved by rule: {rule.rule_name}"
        
        return False, "No matching auto-approval rules"
    
    def _check_rule(
        self,
        swap: ShiftSwap,
        from_shift: EnhancedShift,
        to_shift: Optional[EnhancedShift],
        to_staff: Optional[StaffMember],
        rule: SwapApprovalRule
    ) -> Tuple[bool, str]:
        """Check if swap meets a specific rule's criteria"""
        
        # Check advance notice
        # from_shift.start_time is already a datetime object
        shift_datetime = from_shift.start_time
        if shift_datetime.tzinfo is None:
            shift_datetime = shift_datetime.replace(tzinfo=timezone.utc)
        hours_until_shift = (shift_datetime - datetime.now(timezone.utc)).total_seconds() / 3600
        if hours_until_shift < rule.min_advance_notice_hours:
            return False, f"Insufficient advance notice (requires {rule.min_advance_notice_hours} hours)"
        
        if rule.max_advance_notice_hours and hours_until_shift > rule.max_advance_notice_hours:
            return False, f"Too far in advance (max {rule.max_advance_notice_hours} hours)"
        
        # Check blackout dates
        # from_shift.date is a datetime object, extract the date part
        shift_date = from_shift.date.date() if hasattr(from_shift.date, 'date') else from_shift.date
        if shift_date in rule.blackout_dates:
            return False, "Shift date is in blackout period"
        
        # Check staff tenure
        requester = swap.requester
        requester_tenure_days = (datetime.now(timezone.utc) - requester.created_at.replace(tzinfo=timezone.utc)).days
        if requester_tenure_days < rule.min_tenure_days:
            return False, f"Insufficient tenure (requires {rule.min_tenure_days} days)"
        
        # Check monthly swap limit
        if rule.max_swaps_per_month > 0:
            month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            swap_count = self.db.query(ShiftSwap).filter(
                and_(
                    ShiftSwap.requester_id == swap.requester_id,
                    ShiftSwap.created_at >= month_start,
                    ShiftSwap.status.in_([SwapStatus.APPROVED, SwapStatus.PENDING])
                )
            ).count()
            
            if swap_count >= rule.max_swaps_per_month:
                return False, f"Monthly swap limit reached ({rule.max_swaps_per_month})"
        
        # If swapping with another shift
        if to_shift:
            # Check hours difference
            if rule.max_hours_difference:
                from_hours = (from_shift.end_time - from_shift.start_time).total_seconds() / 3600
                to_hours = (to_shift.end_time - to_shift.start_time).total_seconds() / 3600
                if abs(from_hours - to_hours) > rule.max_hours_difference:
                    return False, f"Shift hours difference exceeds limit ({rule.max_hours_difference} hours)"
            
            # Check same role requirement
            if rule.same_role_required and from_shift.role_id != to_shift.role_id:
                return False, "Shifts must be for the same role"
            
            # Check same location requirement
            if rule.same_location_required and from_shift.location_id != to_shift.location_id:
                return False, "Shifts must be at the same location"
        
        # If assigning to specific staff
        elif to_staff:
            # Check role compatibility
            if rule.same_role_required and from_shift.role_id != to_staff.role_id:
                return False, "Target staff must have the same role"
        
        # Check peak hours restriction
        if rule.peak_hours_restricted:
            # Get peak hours from rule configuration or use defaults
            peak_ranges = (
                rule.peak_hour_ranges 
                if hasattr(rule, 'peak_hour_ranges') and rule.peak_hour_ranges 
                else shift_swap_config.DEFAULT_PEAK_HOURS
            )
            shift_hour = from_shift.start_time.hour
            
            for start_hour, end_hour in peak_ranges:
                if start_hour <= shift_hour < end_hour:
                    return False, "Shift is during peak hours"
        
        # Check restricted shift types
        if from_shift.shift_type and from_shift.shift_type.value in rule.restricted_shifts:
            return False, f"Shift type '{from_shift.shift_type.value}' cannot be auto-approved"
        
        # All checks passed
        return True, "All criteria met"
    
    def process_swap_request(
        self,
        swap_id: int,
        restaurant_id: int
    ) -> ShiftSwap:
        """Process a new swap request and check for auto-approval"""
        
        try:
            swap = self.db.query(ShiftSwap).filter(ShiftSwap.id == swap_id).first()
            if not swap:
                raise ValueError("Swap request not found")
            
            logger.info(f"Processing swap request {swap_id} for restaurant {restaurant_id}")
        
            # Check auto-approval eligibility
            eligible, reason = self.check_auto_approval_eligibility(swap, restaurant_id)
            
            swap.auto_approval_eligible = eligible
            swap.auto_approval_reason = reason
            
            if eligible:
                logger.info(f"Swap {swap_id} is eligible for auto-approval: {reason}")
                # Auto-approve the swap
                swap.status = SwapStatus.APPROVED
                swap.approved_at = datetime.now(timezone.utc)
                swap.approval_level = "auto"
                
                # Execute the swap
                self._execute_swap(swap)
                
                # Send notifications
                self._send_approval_notification(swap)
                logger.info(f"Swap {swap_id} auto-approved and executed")
            else:
                logger.info(f"Swap {swap_id} requires manual approval: {reason}")
                # Set response deadline based on urgency
                urgency = getattr(swap, 'urgency', 'normal')
                deadline_hours = shift_swap_config.get_deadline_hours(urgency)
                
                swap.response_deadline = datetime.now(timezone.utc) + timedelta(hours=deadline_hours)
                logger.debug(f"Set response deadline for swap {swap_id} to {deadline_hours} hours ({urgency} urgency)")
                
                # Send notifications to managers
                self._send_approval_request_notification(swap)
            
            self.db.commit()
            logger.info(f"Swap request {swap_id} processing completed")
            return swap
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error processing swap request {swap_id}: {str(e)}")
            raise
    
    def _execute_swap(self, swap: ShiftSwap):
        """Execute an approved swap"""
        from_shift = swap.from_shift
        
        if swap.to_shift_id:
            # Swapping with another shift
            to_shift = swap.to_shift
            
            # Swap staff IDs
            from_shift.staff_id, to_shift.staff_id = to_shift.staff_id, from_shift.staff_id
        else:
            # Assigning to specific staff
            from_shift.staff_id = swap.to_staff_id
    
    def approve_swap(
        self,
        swap_id: int,
        approver_id: int,
        notes: Optional[str] = None
    ) -> ShiftSwap:
        """Approve a shift swap request"""
        
        swap = self.db.query(ShiftSwap).filter(ShiftSwap.id == swap_id).first()
        if not swap:
            raise ValueError("Swap request not found")
        
        if swap.status != SwapStatus.PENDING:
            raise ValueError("Can only approve pending swap requests")
        
        # Update swap status
        swap.status = SwapStatus.APPROVED
        swap.approved_by_id = approver_id
        swap.approved_at = datetime.now(timezone.utc)
        swap.approval_level = "manager"
        
        if notes:
            swap.manager_notes = notes
        
        # Execute the swap
        self._execute_swap(swap)
        
        # Send notifications
        self._send_approval_notification(swap)
        
        self.db.commit()
        return swap
    
    def reject_swap(
        self,
        swap_id: int,
        approver_id: int,
        reason: str
    ) -> ShiftSwap:
        """Reject a shift swap request"""
        
        swap = self.db.query(ShiftSwap).filter(ShiftSwap.id == swap_id).first()
        if not swap:
            raise ValueError("Swap request not found")
        
        if swap.status != SwapStatus.PENDING:
            raise ValueError("Can only reject pending swap requests")
        
        # Update swap status
        swap.status = SwapStatus.REJECTED
        swap.approved_by_id = approver_id
        swap.approved_at = datetime.now(timezone.utc)
        swap.rejection_reason = reason
        
        # Send notifications
        self._send_rejection_notification(swap)
        
        self.db.commit()
        return swap
    
    def cancel_swap(
        self,
        swap_id: int,
        user_id: int
    ) -> ShiftSwap:
        """Cancel a pending swap request"""
        
        swap = self.db.query(ShiftSwap).filter(ShiftSwap.id == swap_id).first()
        if not swap:
            raise ValueError("Swap request not found")
        
        if swap.status != SwapStatus.PENDING:
            raise ValueError("Can only cancel pending swap requests")
        
        if swap.requester_id != user_id:
            raise ValueError("Only the requester can cancel a swap request")
        
        # Update swap status
        swap.status = SwapStatus.CANCELLED
        swap.updated_at = datetime.utcnow()
        
        # Send notifications
        self._send_cancellation_notification(swap)
        
        self.db.commit()
        return swap
    
    def get_pending_swaps_for_approval(
        self,
        manager_id: int,
        restaurant_id: int
    ) -> List[ShiftSwap]:
        """Get pending swap requests that need manager approval"""
        
        # Get swaps for shifts managed by this manager
        swaps = self.db.query(ShiftSwap).join(
            EnhancedShift, ShiftSwap.from_shift_id == EnhancedShift.id
        ).filter(
            and_(
                ShiftSwap.status == SwapStatus.PENDING,
                EnhancedShift.location_id == restaurant_id,
                ShiftSwap.auto_approval_eligible == False
            )
        ).order_by(ShiftSwap.created_at.desc()).all()
        
        return swaps
    
    def get_swap_history(
        self,
        restaurant_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """Get swap statistics and history"""
        
        query = self.db.query(ShiftSwap).join(
            EnhancedShift, ShiftSwap.from_shift_id == EnhancedShift.id
        ).filter(EnhancedShift.location_id == restaurant_id)
        
        if start_date:
            query = query.filter(ShiftSwap.created_at >= start_date)
        if end_date:
            query = query.filter(ShiftSwap.created_at <= end_date)
        
        swaps = query.all()
        
        # Calculate statistics
        total_swaps = len(swaps)
        approved_swaps = len([s for s in swaps if s.status == SwapStatus.APPROVED])
        rejected_swaps = len([s for s in swaps if s.status == SwapStatus.REJECTED])
        pending_swaps = len([s for s in swaps if s.status == SwapStatus.PENDING])
        cancelled_swaps = len([s for s in swaps if s.status == SwapStatus.CANCELLED])
        
        # Calculate average approval time
        approval_times = []
        for swap in swaps:
            if swap.status == SwapStatus.APPROVED and swap.approved_at:
                # Ensure both datetimes are timezone-aware for comparison
                approved_at = swap.approved_at
                created_at = swap.created_at
                if approved_at.tzinfo is None:
                    approved_at = approved_at.replace(tzinfo=timezone.utc)
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                time_diff = (approved_at - created_at).total_seconds() / 3600
                approval_times.append(time_diff)
        
        avg_approval_time = sum(approval_times) / len(approval_times) if approval_times else None
        
        # Get most common reasons
        reasons = {}
        for swap in swaps:
            if swap.reason:
                reasons[swap.reason] = reasons.get(swap.reason, 0) + 1
        
        most_common_reasons = [
            {"reason": reason, "count": count}
            for reason, count in sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:5]
        ]
        
        return {
            "total_swaps": total_swaps,
            "approved_swaps": approved_swaps,
            "rejected_swaps": rejected_swaps,
            "pending_swaps": pending_swaps,
            "cancelled_swaps": cancelled_swaps,
            "average_approval_time_hours": avg_approval_time,
            "most_common_reasons": most_common_reasons,
            "swap_trends": self._calculate_swap_trends(swaps)
        }
    
    def _calculate_swap_trends(self, swaps: List[ShiftSwap]) -> List[Dict]:
        """Calculate swap trends over time"""
        trends = {}
        
        for swap in swaps:
            month_key = swap.created_at.strftime("%Y-%m")
            if month_key not in trends:
                trends[month_key] = {
                    "month": month_key,
                    "total": 0,
                    "approved": 0,
                    "rejected": 0,
                    "auto_approved": 0
                }
            
            trends[month_key]["total"] += 1
            
            if swap.status == SwapStatus.APPROVED:
                trends[month_key]["approved"] += 1
                if swap.approval_level == "auto":
                    trends[month_key]["auto_approved"] += 1
            elif swap.status == SwapStatus.REJECTED:
                trends[month_key]["rejected"] += 1
        
        return list(trends.values())
    
    def _send_approval_notification(self, swap: ShiftSwap):
        """Send notification for approved swap"""
        # TODO: Implement actual notification sending
        swap.requester_notified = True
        if swap.to_staff_id:
            swap.to_staff_notified = True
        swap.notification_sent_at = datetime.now(timezone.utc)
        logger.info(f"Approval notification sent for swap {swap.id}")
    
    def _send_rejection_notification(self, swap: ShiftSwap):
        """Send notification for rejected swap"""
        # TODO: Implement actual notification sending
        swap.requester_notified = True
        swap.notification_sent_at = datetime.now(timezone.utc)
        logger.info(f"Rejection notification sent for swap {swap.id}")
    
    def _send_approval_request_notification(self, swap: ShiftSwap):
        """Send notification to managers for approval"""
        # TODO: Implement actual notification sending
        swap.manager_notified = True
        swap.notification_sent_at = datetime.now(timezone.utc)
        logger.info(f"Approval request notification sent for swap {swap.id}")
    
    def _send_cancellation_notification(self, swap: ShiftSwap):
        """Send notification for cancelled swap"""
        # TODO: Implement actual notification sending
        if swap.to_staff_id:
            swap.to_staff_notified = True
        swap.manager_notified = True
        swap.notification_sent_at = datetime.now(timezone.utc)
        logger.info(f"Cancellation notification sent for swap {swap.id}")