from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime, date, timedelta

from core.database import get_db
from core.auth import get_current_user
from ..models.scheduling_models import (
    ShiftSwap, EnhancedShift, SwapApprovalRule
)
from ..models.staff_models import StaffMember
from ..schemas.scheduling_schemas import (
    ShiftSwapRequest, ShiftSwapApproval, ShiftSwapResponse,
    ShiftSwapListFilter, SwapApprovalRuleCreate, SwapApprovalRuleUpdate,
    SwapApprovalRuleResponse, ShiftSwapHistory
)
from ..services.shift_swap_service import ShiftSwapService
from ..services.scheduling_service import SchedulingService
from ..enums.scheduling_enums import SwapStatus
from ..utils.permissions import SchedulingPermissions

router = APIRouter()


# Shift Swap Management
@router.post("/swaps", response_model=ShiftSwapResponse)
async def request_shift_swap(
    swap_request: ShiftSwapRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Request a shift swap with enhanced workflow support.
    
    Features:
    - Auto-approval for eligible swaps
    - Notification scheduling
    - Response deadline tracking
    """
    # Verify requester owns the from_shift
    from_shift = db.query(EnhancedShift).options(
        joinedload(EnhancedShift.staff_member).joinedload(StaffMember.role),
        joinedload(EnhancedShift.location)
    ).filter(
        EnhancedShift.id == swap_request.from_shift_id
    ).first()
    
    if not from_shift:
        raise HTTPException(status_code=404, detail="Shift not found")
    
    if from_shift.staff_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Can only swap your own shifts")
    
    # Validate the swap request
    service = SchedulingService(db)
    valid, reason = service.validate_swap_request(
        swap_request.from_shift_id,
        swap_request.to_shift_id,
        swap_request.to_staff_id
    )
    
    if not valid:
        raise HTTPException(status_code=400, detail=reason)
    
    # Create swap request
    db_swap = ShiftSwap(
        requester_id=current_user["user_id"],
        **swap_request.dict(exclude={'urgency', 'preferred_response_by'})
    )
    
    # Set response deadline based on urgency
    if swap_request.preferred_response_by:
        db_swap.response_deadline = swap_request.preferred_response_by
    elif swap_request.urgency == "urgent":
        db_swap.response_deadline = datetime.utcnow() + timedelta(hours=24)
    elif swap_request.urgency == "flexible":
        db_swap.response_deadline = datetime.utcnow() + timedelta(hours=72)
    else:
        db_swap.response_deadline = datetime.utcnow() + timedelta(hours=48)
    
    db.add(db_swap)
    db.commit()
    db.refresh(db_swap)
    
    # Process the swap request (check for auto-approval)
    swap_service = ShiftSwapService(db)
    db_swap = swap_service.process_swap_request(
        db_swap.id,
        from_shift.location.restaurant_id
    )
    
    # Build response
    return _build_swap_response(db_swap, db)


@router.get("/swaps", response_model=List[ShiftSwapResponse])
async def list_shift_swaps(
    status: Optional[SwapStatus] = None,
    requester_id: Optional[int] = None,
    staff_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    pending_approval: Optional[bool] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    List shift swap requests with filtering options.
    
    - staff_id: Shows swaps where user is requester or target
    - pending_approval: Shows only swaps waiting for approval
    """
    query = db.query(ShiftSwap).options(
        joinedload(ShiftSwap.requester),
        joinedload(ShiftSwap.to_staff),
        joinedload(ShiftSwap.approved_by),
        joinedload(ShiftSwap.from_shift).joinedload(EnhancedShift.staff_member),
        joinedload(ShiftSwap.to_shift)
    )
    
    # Apply filters
    if status:
        query = query.filter(ShiftSwap.status == status)
    
    if requester_id:
        query = query.filter(ShiftSwap.requester_id == requester_id)
    
    if staff_id:
        query = query.filter(
            or_(
                ShiftSwap.requester_id == staff_id,
                ShiftSwap.to_staff_id == staff_id
            )
        )
    
    if date_from or date_to:
        query = query.join(
            EnhancedShift, ShiftSwap.from_shift_id == EnhancedShift.id
        )
        if date_from:
            query = query.filter(EnhancedShift.date >= date_from)
        if date_to:
            query = query.filter(EnhancedShift.date <= date_to)
    
    if pending_approval is True:
        query = query.filter(
            and_(
                ShiftSwap.status == SwapStatus.PENDING,
                ShiftSwap.auto_approval_eligible == False
            )
        )
    
    # Pagination
    total = query.count()
    swaps = query.order_by(ShiftSwap.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    
    # Build responses
    return [_build_swap_response(swap, db) for swap in swaps]


@router.get("/swaps/{swap_id}", response_model=ShiftSwapResponse)
async def get_shift_swap(
    swap_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get details of a specific shift swap request"""
    swap = db.query(ShiftSwap).options(
        joinedload(ShiftSwap.requester),
        joinedload(ShiftSwap.to_staff),
        joinedload(ShiftSwap.approved_by),
        joinedload(ShiftSwap.from_shift).joinedload(EnhancedShift.staff_member),
        joinedload(ShiftSwap.to_shift)
    ).filter(ShiftSwap.id == swap_id).first()
    
    if not swap:
        raise HTTPException(status_code=404, detail="Swap request not found")
    
    # Check permissions
    if not (
        swap.requester_id == current_user["user_id"] or
        swap.to_staff_id == current_user["user_id"] or
        SchedulingPermissions.has_permission(current_user["sub"], "view_all_swaps", db)
    ):
        raise HTTPException(status_code=403, detail="Not authorized to view this swap")
    
    return _build_swap_response(swap, db)


@router.put("/swaps/{swap_id}/approve")
async def approve_shift_swap(
    swap_id: int,
    approval: ShiftSwapApproval,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Approve or reject a shift swap request.
    
    Requires manager or supervisor permissions.
    """
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "approve_swap",
        db
    )
    
    service = ShiftSwapService(db)
    
    if approval.status == SwapStatus.APPROVED:
        swap = service.approve_swap(
            swap_id,
            current_user["user_id"],
            approval.manager_notes
        )
        return {"message": "Shift swap approved", "swap_id": swap.id}
    
    elif approval.status == SwapStatus.REJECTED:
        if not approval.rejection_reason:
            raise HTTPException(
                status_code=400,
                detail="Rejection reason is required"
            )
        
        swap = service.reject_swap(
            swap_id,
            current_user["user_id"],
            approval.rejection_reason
        )
        return {"message": "Shift swap rejected", "swap_id": swap.id}
    
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid status. Must be APPROVED or REJECTED"
        )


@router.delete("/swaps/{swap_id}")
async def cancel_shift_swap(
    swap_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Cancel a pending shift swap request"""
    service = ShiftSwapService(db)
    
    try:
        swap = service.cancel_swap(swap_id, current_user["user_id"])
        return {"message": "Shift swap cancelled", "swap_id": swap.id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/swaps/pending/approvals", response_model=List[ShiftSwapResponse])
async def get_pending_approvals(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get pending swap requests that need manager approval"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "approve_swap",
        db
    )
    
    # Get user's restaurant
    staff = db.query(StaffMember).filter(
        StaffMember.id == current_user["user_id"]
    ).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    service = ShiftSwapService(db)
    swaps = service.get_pending_swaps_for_approval(
        current_user["user_id"],
        staff.restaurant_id
    )
    
    return [_build_swap_response(swap, db) for swap in swaps]


# Swap Approval Rules
@router.post("/swap-rules", response_model=SwapApprovalRuleResponse)
async def create_swap_approval_rule(
    rule: SwapApprovalRuleCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Create a new swap approval rule (Admin only)"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "manage_swap_rules",
        db
    )
    
    # Get user's restaurant
    staff = db.query(StaffMember).filter(
        StaffMember.id == current_user["user_id"]
    ).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    db_rule = SwapApprovalRule(
        restaurant_id=staff.restaurant_id,
        **rule.dict()
    )
    
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    
    return db_rule


@router.get("/swap-rules", response_model=List[SwapApprovalRuleResponse])
async def list_swap_approval_rules(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """List swap approval rules for the restaurant"""
    # Get user's restaurant
    staff = db.query(StaffMember).filter(
        StaffMember.id == current_user["user_id"]
    ).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    query = db.query(SwapApprovalRule).filter(
        SwapApprovalRule.restaurant_id == staff.restaurant_id
    )
    
    if is_active is not None:
        query = query.filter(SwapApprovalRule.is_active == is_active)
    
    return query.order_by(SwapApprovalRule.priority.desc()).all()


@router.put("/swap-rules/{rule_id}", response_model=SwapApprovalRuleResponse)
async def update_swap_approval_rule(
    rule_id: int,
    rule_update: SwapApprovalRuleUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Update a swap approval rule (Admin only)"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "manage_swap_rules",
        db
    )
    
    db_rule = db.query(SwapApprovalRule).filter(
        SwapApprovalRule.id == rule_id
    ).first()
    
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    for key, value in rule_update.dict(exclude_unset=True).items():
        setattr(db_rule, key, value)
    
    db.commit()
    db.refresh(db_rule)
    
    return db_rule


@router.delete("/swap-rules/{rule_id}")
async def delete_swap_approval_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Delete a swap approval rule (Admin only)"""
    # Check permission
    SchedulingPermissions.require_permission(
        current_user["sub"],
        "manage_swap_rules",
        db
    )
    
    db_rule = db.query(SwapApprovalRule).filter(
        SwapApprovalRule.id == rule_id
    ).first()
    
    if not db_rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    
    db.delete(db_rule)
    db.commit()
    
    return {"message": "Rule deleted successfully"}


# Swap History and Analytics
@router.get("/swaps/history/stats", response_model=ShiftSwapHistory)
async def get_swap_history_stats(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """Get swap history statistics and trends"""
    # Get user's restaurant
    staff = db.query(StaffMember).filter(
        StaffMember.id == current_user["user_id"]
    ).first()
    
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    service = ShiftSwapService(db)
    
    start_datetime = datetime.combine(start_date, datetime.min.time()) if start_date else None
    end_datetime = datetime.combine(end_date, datetime.max.time()) if end_date else None
    
    history = service.get_swap_history(
        staff.restaurant_id,
        start_datetime,
        end_datetime
    )
    
    return ShiftSwapHistory(**history)


# Helper function
def _build_swap_response(swap: ShiftSwap, db: Session) -> ShiftSwapResponse:
    """Build a comprehensive swap response"""
    from_shift = swap.from_shift
    
    response_dict = {
        "id": swap.id,
        "requester_id": swap.requester_id,
        "requester_name": swap.requester.name if swap.requester else "Unknown",
        "from_shift_id": swap.from_shift_id,
        "from_shift_details": {
            "date": from_shift.date,
            "start_time": from_shift.start_time,
            "end_time": from_shift.end_time,
            "role": from_shift.role.name if from_shift.role else None,
            "location": from_shift.location.name if from_shift.location else None
        },
        "to_shift_id": swap.to_shift_id,
        "to_staff_id": swap.to_staff_id,
        "status": swap.status,
        "reason": swap.reason,
        "manager_notes": swap.manager_notes,
        "rejection_reason": swap.rejection_reason,
        "approved_by_id": swap.approved_by_id,
        "approved_by_name": swap.approved_by.name if swap.approved_by else None,
        "approved_at": swap.approved_at,
        "approval_level": swap.approval_level,
        "auto_approval_eligible": swap.auto_approval_eligible,
        "auto_approval_reason": swap.auto_approval_reason,
        "response_deadline": swap.response_deadline,
        "requester_notified": swap.requester_notified,
        "to_staff_notified": swap.to_staff_notified,
        "manager_notified": swap.manager_notified,
        "created_at": swap.created_at,
        "updated_at": swap.updated_at
    }
    
    if swap.to_shift_id and swap.to_shift:
        to_shift = swap.to_shift
        response_dict["to_shift_details"] = {
            "date": to_shift.date,
            "start_time": to_shift.start_time,
            "end_time": to_shift.end_time,
            "role": to_shift.role.name if to_shift.role else None,
            "location": to_shift.location.name if to_shift.location else None,
            "staff_name": to_shift.staff_member.name if to_shift.staff_member else None
        }
    
    if swap.to_staff_id and swap.to_staff:
        response_dict["to_staff_name"] = swap.to_staff.name
    
    return ShiftSwapResponse(**response_dict)