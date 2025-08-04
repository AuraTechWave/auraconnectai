# backend/modules/payments/api/split_bill_endpoints.py

from typing import List, Optional, Dict, Any
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field, validator

from core.database import get_db
from core.auth import get_current_user, require_permissions
from core.models import User
from ..services.split_bill_service import split_bill_service
from ..services.tip_service import tip_service
from ..services.payment_service import payment_service
from ..models.split_bill_models import SplitMethod, SplitStatus, ParticipantStatus, TipMethod
from ..models.payment_models import PaymentGateway

router = APIRouter(prefix="/splits", tags=["Split Bills"])


# Additional request models
class PaginationParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


# Request/Response Models

class ParticipantRequest(BaseModel):
    customer_id: Optional[int] = None
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    notify_via_email: bool = True
    notify_via_sms: bool = False


class CreateSplitRequest(BaseModel):
    order_id: int
    split_method: SplitMethod
    participants: List[ParticipantRequest]
    
    # Tip configuration
    tip_method: Optional[TipMethod] = None
    tip_value: Optional[Decimal] = None
    
    # Split configuration based on method
    split_config: Optional[Dict[str, Any]] = None
    
    # Settings
    allow_partial_payments: bool = True
    require_all_acceptance: bool = False
    auto_close_on_completion: bool = True
    send_reminders: bool = True
    expires_in_hours: Optional[int] = 48
    
    @validator('participants')
    def validate_participants(cls, v):
        if len(v) < 2:
            raise ValueError("At least 2 participants required for split")
        return v
    
    @validator('split_config')
    def validate_split_config(cls, v, values):
        if 'split_method' in values:
            method = values['split_method']
            
            if method == SplitMethod.PERCENTAGE:
                if not v or 'percentages' not in v:
                    raise ValueError("Percentage split requires 'percentages' in split_config")
                    
            elif method == SplitMethod.AMOUNT:
                if not v or 'amounts' not in v:
                    raise ValueError("Amount split requires 'amounts' in split_config")
                    
            elif method == SplitMethod.ITEM:
                if not v or 'items' not in v:
                    raise ValueError("Item split requires 'items' in split_config")
        
        return v


class UpdateParticipantStatusRequest(BaseModel):
    status: ParticipantStatus
    decline_reason: Optional[str] = None


class ParticipantPaymentRequest(BaseModel):
    gateway: PaymentGateway
    amount: Decimal
    payment_method_id: Optional[str] = None
    save_payment_method: bool = False
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class TipSuggestionRequest(BaseModel):
    subtotal: Decimal
    percentages: Optional[List[int]] = None


class ProcessTipDistributionRequest(BaseModel):
    distribution_method: str = "pool"
    distribution_config: Optional[Dict[str, Any]] = None


class SplitResponse(BaseModel):
    id: int
    split_id: str
    order_id: int
    split_method: SplitMethod
    status: SplitStatus
    subtotal: float
    tax_amount: float
    service_charge: float
    tip_amount: float
    total_amount: float
    organizer_name: Optional[str]
    participants_count: int
    paid_count: int
    expires_at: Optional[str]
    created_at: str
    
    class Config:
        orm_mode = True


class ParticipantResponse(BaseModel):
    id: int
    name: str
    email: Optional[str]
    share_amount: float
    tip_amount: float
    total_amount: float
    paid_amount: float
    remaining_amount: float
    status: ParticipantStatus
    access_token: Optional[str] = None
    
    class Config:
        orm_mode = True


class SplitDetailResponse(SplitResponse):
    participants: List[ParticipantResponse]
    split_config: Optional[Dict[str, Any]]
    
    class Config:
        orm_mode = True


class PaginatedSplitsResponse(BaseModel):
    items: List[SplitResponse]
    total: int
    page: int
    page_size: int
    pages: int


# Endpoints

@router.post("/", response_model=SplitDetailResponse)
async def create_split(
    request: CreateSplitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new bill split"""
    
    try:
        # Set organizer info
        organizer_info = {
            'customer_id': current_user.customer_id if hasattr(current_user, 'customer_id') else None,
            'name': current_user.full_name,
            'email': current_user.email,
            'phone': current_user.phone if hasattr(current_user, 'phone') else None
        }
        
        # Create split
        split = await split_bill_service.create_split(
            db=db,
            order_id=request.order_id,
            split_method=request.split_method,
            participants=[p.dict() for p in request.participants],
            organizer_info=organizer_info,
            tip_method=request.tip_method,
            tip_value=request.tip_value,
            split_config=request.split_config,
            settings={
                'allow_partial_payments': request.allow_partial_payments,
                'require_all_acceptance': request.require_all_acceptance,
                'auto_close_on_completion': request.auto_close_on_completion,
                'send_reminders': request.send_reminders,
                'expires_in_hours': request.expires_in_hours
            }
        )
        
        # Prepare response
        response = SplitDetailResponse(
            id=split.id,
            split_id=split.split_id,
            order_id=split.order_id,
            split_method=split.split_method,
            status=split.status,
            subtotal=float(split.subtotal),
            tax_amount=float(split.tax_amount),
            service_charge=float(split.service_charge),
            tip_amount=float(split.tip_amount),
            total_amount=float(split.total_amount),
            organizer_name=split.organizer_name,
            participants_count=len(split.participants),
            paid_count=sum(1 for p in split.participants if p.status == ParticipantStatus.PAID),
            expires_at=split.expires_at.isoformat() if split.expires_at else None,
            created_at=split.created_at.isoformat(),
            participants=[
                ParticipantResponse(
                    id=p.id,
                    name=p.name,
                    email=p.email,
                    share_amount=float(p.share_amount),
                    tip_amount=float(p.tip_amount),
                    total_amount=float(p.total_amount),
                    paid_amount=float(p.paid_amount),
                    remaining_amount=float(p.remaining_amount),
                    status=p.status,
                    access_token=p.access_token
                )
                for p in split.participants
            ],
            split_config=split.split_config
        )
        
        return response
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create split: {str(e)}")


@router.get("/{split_id}", response_model=SplitDetailResponse)
async def get_split(
    split_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get split details"""
    
    split = await split_bill_service.get_split(db, split_id, include_participants=True)
    if not split:
        raise HTTPException(status_code=404, detail="Split not found")
    
    # Check permissions
    is_organizer = (
        split.organizer_id == current_user.customer_id if hasattr(current_user, 'customer_id') else False
    )
    is_participant = any(
        p.customer_id == current_user.customer_id if hasattr(current_user, 'customer_id') else False
        for p in split.participants
    )
    
    if not (is_organizer or is_participant or current_user.is_staff):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Prepare response
    response = SplitDetailResponse(
        id=split.id,
        split_id=split.split_id,
        order_id=split.order_id,
        split_method=split.split_method,
        status=split.status,
        subtotal=float(split.subtotal),
        tax_amount=float(split.tax_amount),
        service_charge=float(split.service_charge),
        tip_amount=float(split.tip_amount),
        total_amount=float(split.total_amount),
        organizer_name=split.organizer_name,
        participants_count=len(split.participants),
        paid_count=sum(1 for p in split.participants if p.status == ParticipantStatus.PAID),
        expires_at=split.expires_at.isoformat() if split.expires_at else None,
        created_at=split.created_at.isoformat(),
        participants=[
            ParticipantResponse(
                id=p.id,
                name=p.name,
                email=p.email,
                share_amount=float(p.share_amount),
                tip_amount=float(p.tip_amount),
                total_amount=float(p.total_amount),
                paid_amount=float(p.paid_amount),
                remaining_amount=float(p.remaining_amount),
                status=p.status,
                # Only include access token for organizer
                access_token=p.access_token if is_organizer else None
            )
            for p in split.participants
        ],
        split_config=split.split_config if is_organizer else None
    )
    
    return response


@router.get("/participant/{access_token}", response_model=ParticipantResponse)
async def get_participant_by_token(
    access_token: str,
    db: AsyncSession = Depends(get_db)
):
    """Get participant details by access token (for guest access)"""
    
    split, participant = await split_bill_service.get_split_by_token(db, access_token)
    
    if not split or not participant:
        raise HTTPException(status_code=404, detail="Invalid access token")
    
    return ParticipantResponse(
        id=participant.id,
        name=participant.name,
        email=participant.email,
        share_amount=float(participant.share_amount),
        tip_amount=float(participant.tip_amount),
        total_amount=float(participant.total_amount),
        paid_amount=float(participant.paid_amount),
        remaining_amount=float(participant.remaining_amount),
        status=participant.status
    )


@router.put("/participant/{participant_id}/status")
async def update_participant_status(
    participant_id: int,
    request: UpdateParticipantStatusRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update participant status (accept/decline)"""
    
    try:
        participant = await split_bill_service.update_participant_status(
            db=db,
            participant_id=participant_id,
            status=request.status,
            decline_reason=request.decline_reason
        )
        
        return {
            "success": True,
            "participant_id": participant.id,
            "status": participant.status
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@router.post("/participant/{participant_id}/pay")
async def pay_participant_share(
    participant_id: int,
    request: ParticipantPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Process payment for a participant's share"""
    
    try:
        # Get participant
        from sqlalchemy import select
        from ..models.split_bill_models import SplitParticipant
        
        result = await db.execute(
            select(SplitParticipant).where(SplitParticipant.id == participant_id)
        )
        participant = result.scalar_one_or_none()
        
        if not participant:
            raise HTTPException(status_code=404, detail="Participant not found")
        
        # Create payment
        payment = await payment_service.create_payment(
            db=db,
            order_id=participant.bill_split.order_id,
            gateway=request.gateway,
            amount=request.amount,
            payment_method_id=request.payment_method_id,
            save_payment_method=request.save_payment_method,
            metadata={
                'split_id': participant.split_id,
                'participant_id': participant.id,
                'participant_name': participant.name
            }
        )
        
        # Record payment allocation
        if payment.status in ['completed', 'processing']:
            allocation = await split_bill_service.record_participant_payment(
                db=db,
                participant_id=participant_id,
                payment=payment,
                amount=request.amount
            )
        
        return {
            "success": True,
            "payment_id": payment.payment_id,
            "payment_status": payment.status,
            "remaining_amount": float(participant.remaining_amount)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Payment failed: {str(e)}")


@router.post("/{split_id}/cancel")
async def cancel_split(
    split_id: int,
    reason: Optional[str] = Body(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Cancel a bill split"""
    
    # Get split
    split = await split_bill_service.get_split(db, split_id)
    if not split:
        raise HTTPException(status_code=404, detail="Split not found")
    
    # Check permissions
    is_organizer = (
        split.organizer_id == current_user.customer_id if hasattr(current_user, 'customer_id') else False
    )
    
    if not (is_organizer or current_user.is_staff):
        raise HTTPException(status_code=403, detail="Only organizer can cancel split")
    
    try:
        split = await split_bill_service.cancel_split(db, split_id, reason)
        
        return {
            "success": True,
            "split_id": split.id,
            "status": split.status
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel split: {str(e)}")


@router.post("/{split_id}/remind")
async def send_payment_reminders(
    split_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send payment reminders to pending participants"""
    
    # Get split
    split = await split_bill_service.get_split(db, split_id)
    if not split:
        raise HTTPException(status_code=404, detail="Split not found")
    
    # Check permissions
    is_organizer = (
        split.organizer_id == current_user.customer_id if hasattr(current_user, 'customer_id') else False
    )
    
    if not (is_organizer or current_user.is_staff):
        raise HTTPException(status_code=403, detail="Only organizer can send reminders")
    
    try:
        await split_bill_service.send_reminders(db, split_id)
        
        return {
            "success": True,
            "message": "Reminders sent successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send reminders: {str(e)}")


# Tip calculation endpoints

@router.post("/tips/calculate")
async def calculate_tip(
    subtotal: Decimal = Body(...),
    tip_method: TipMethod = Body(...),
    tip_value: Decimal = Body(...),
    current_total: Optional[Decimal] = Body(None)
):
    """Calculate tip amount"""
    
    tip_amount = tip_service.calculate_tip(
        subtotal=subtotal,
        tip_method=tip_method,
        tip_value=tip_value,
        current_total=current_total
    )
    
    return {
        "subtotal": float(subtotal),
        "tip_amount": float(tip_amount),
        "total": float(subtotal + tip_amount)
    }


@router.post("/tips/suggestions")
async def get_tip_suggestions(
    request: TipSuggestionRequest
):
    """Get suggested tip amounts"""
    
    suggestions = tip_service.suggest_tip_amounts(
        subtotal=request.subtotal,
        default_percentages=request.percentages
    )
    
    return {
        "subtotal": float(request.subtotal),
        "suggestions": suggestions
    }


@router.post("/{split_id}/tips/distribute")
@require_permissions("manage_tips")
async def process_tip_distribution(
    split_id: int,
    request: ProcessTipDistributionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Process tip distribution for a completed split"""
    
    # Get split
    split = await split_bill_service.get_split(db, split_id)
    if not split:
        raise HTTPException(status_code=404, detail="Split not found")
    
    if split.status != SplitStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Split must be completed to distribute tips")
    
    try:
        # Create tip distribution
        distribution = await tip_service.create_tip_distribution(
            db=db,
            split_id=split_id,
            tip_amount=split.tip_amount,
            distribution_method=request.distribution_method,
            distribution_config=request.distribution_config
        )
        
        # Process distribution
        distribution = await tip_service.process_tip_distribution(
            db=db,
            distribution_id=distribution.id,
            processed_by=current_user.id
        )
        
        return {
            "success": True,
            "distribution_id": distribution.id,
            "tip_amount": float(distribution.tip_amount),
            "distributions": distribution.distributions
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process tip distribution: {str(e)}")


# Additional endpoints for pagination and resending

@router.get("/", response_model=PaginatedSplitsResponse)
async def list_splits(
    status: Optional[SplitStatus] = Query(None),
    organizer: bool = Query(False, description="Only show splits I organized"),
    participant: bool = Query(False, description="Only show splits I'm participating in"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated list of splits for current user"""
    
    from sqlalchemy import or_, func
    
    # Build base query
    query = select(BillSplit)
    count_query = select(func.count(BillSplit.id))
    
    # Apply filters
    conditions = []
    
    if organizer:
        if hasattr(current_user, 'customer_id') and current_user.customer_id:
            conditions.append(BillSplit.organizer_id == current_user.customer_id)
    
    if participant:
        if hasattr(current_user, 'customer_id') and current_user.customer_id:
            # Subquery to find splits where user is a participant
            participant_splits = select(SplitParticipant.split_id).where(
                SplitParticipant.customer_id == current_user.customer_id
            ).scalar_subquery()
            conditions.append(BillSplit.id.in_(participant_splits))
    
    if not organizer and not participant:
        # Default: show all splits user is involved in
        if hasattr(current_user, 'customer_id') and current_user.customer_id:
            participant_splits = select(SplitParticipant.split_id).where(
                SplitParticipant.customer_id == current_user.customer_id
            ).scalar_subquery()
            conditions.append(
                or_(
                    BillSplit.organizer_id == current_user.customer_id,
                    BillSplit.id.in_(participant_splits)
                )
            )
    
    if status:
        conditions.append(BillSplit.status == status)
    
    # Apply conditions
    if conditions:
        query = query.where(and_(*conditions))
        count_query = count_query.where(and_(*conditions))
    
    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # Apply pagination
    query = query.order_by(BillSplit.created_at.desc())
    query = query.offset(pagination.offset).limit(pagination.page_size)
    
    # Execute query
    result = await db.execute(query)
    splits = result.scalars().all()
    
    # Prepare response
    items = []
    for split in splits:
        # Get participant count
        participant_result = await db.execute(
            select(func.count(SplitParticipant.id))
            .where(SplitParticipant.split_id == split.id)
        )
        participants_count = participant_result.scalar() or 0
        
        # Get paid count
        paid_result = await db.execute(
            select(func.count(SplitParticipant.id))
            .where(
                and_(
                    SplitParticipant.split_id == split.id,
                    SplitParticipant.status == ParticipantStatus.PAID
                )
            )
        )
        paid_count = paid_result.scalar() or 0
        
        items.append(SplitResponse(
            id=split.id,
            split_id=split.split_id,
            order_id=split.order_id,
            split_method=split.split_method,
            status=split.status,
            subtotal=float(split.subtotal),
            tax_amount=float(split.tax_amount),
            service_charge=float(split.service_charge),
            tip_amount=float(split.tip_amount),
            total_amount=float(split.total_amount),
            organizer_name=split.organizer_name,
            participants_count=participants_count,
            paid_count=paid_count,
            expires_at=split.expires_at.isoformat() if split.expires_at else None,
            created_at=split.created_at.isoformat()
        ))
    
    return PaginatedSplitsResponse(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
        pages=(total + pagination.page_size - 1) // pagination.page_size
    )


@router.post("/{split_id}/resend-invitation/{participant_id}")
async def resend_participant_invitation(
    split_id: int,
    participant_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resend invitation to a specific participant"""
    
    # Get split
    split = await split_bill_service.get_split(db, split_id, include_participants=True)
    if not split:
        raise HTTPException(status_code=404, detail="Split not found")
    
    # Check permissions - only organizer can resend
    is_organizer = (
        split.organizer_id == current_user.customer_id if hasattr(current_user, 'customer_id') else False
    )
    
    if not (is_organizer or current_user.is_staff):
        raise HTTPException(status_code=403, detail="Only organizer can resend invitations")
    
    # Find participant
    participant = next((p for p in split.participants if p.id == participant_id), None)
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    if not participant.email:
        raise HTTPException(status_code=400, detail="Participant has no email address")
    
    try:
        # Queue invitation
        from ..services.split_bill_notification_queue import split_bill_notification_queue
        
        job_id = await split_bill_notification_queue.queue_participant_invitation(
            participant_data={
                'id': participant.id,
                'name': participant.name,
                'email': participant.email,
                'total_amount': float(participant.total_amount),
                'share_amount': float(participant.share_amount),
                'tip_amount': float(participant.tip_amount),
                'access_token': participant.access_token
            },
            split_data={
                'id': split.id,
                'organizer_name': split.organizer_name,
                'total_amount': float(split.total_amount)
            }
        )
        
        # Update invite sent time
        participant.invite_sent_at = datetime.utcnow()
        await db.commit()
        
        return {
            "success": True,
            "message": "Invitation resent successfully",
            "job_id": job_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resend invitation: {str(e)}")


@router.post("/{split_id}/resend-all-invitations")
async def resend_all_invitations(
    split_id: int,
    pending_only: bool = Query(True, description="Only resend to pending participants"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Resend invitations to all (or pending) participants"""
    
    # Get split
    split = await split_bill_service.get_split(db, split_id, include_participants=True)
    if not split:
        raise HTTPException(status_code=404, detail="Split not found")
    
    # Check permissions
    is_organizer = (
        split.organizer_id == current_user.customer_id if hasattr(current_user, 'customer_id') else False
    )
    
    if not (is_organizer or current_user.is_staff):
        raise HTTPException(status_code=403, detail="Only organizer can resend invitations")
    
    try:
        from ..services.split_bill_notification_queue import split_bill_notification_queue
        
        # Filter participants
        participants_to_notify = []
        for participant in split.participants:
            if participant.email and participant.notify_via_email:
                if not pending_only or participant.status == ParticipantStatus.PENDING:
                    participants_to_notify.append({
                        'id': participant.id,
                        'name': participant.name,
                        'email': participant.email,
                        'total_amount': float(participant.total_amount),
                        'share_amount': float(participant.share_amount),
                        'tip_amount': float(participant.tip_amount),
                        'access_token': participant.access_token,
                        'notify_via_email': participant.notify_via_email
                    })
                    participant.invite_sent_at = datetime.utcnow()
        
        if not participants_to_notify:
            return {
                "success": True,
                "message": "No participants to notify",
                "count": 0
            }
        
        # Queue bulk invitations
        job_ids = await split_bill_notification_queue.queue_bulk_invitations(
            participants_to_notify,
            {
                'id': split.id,
                'organizer_name': split.organizer_name,
                'total_amount': float(split.total_amount)
            }
        )
        
        await db.commit()
        
        return {
            "success": True,
            "message": f"Resent invitations to {len(participants_to_notify)} participants",
            "count": len(participants_to_notify),
            "job_ids": job_ids
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resend invitations: {str(e)}")