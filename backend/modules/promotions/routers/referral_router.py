# backend/modules/promotions/routers/referral_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime

from backend.core.database import get_db
from backend.modules.auth.dependencies import get_current_user, require_admin
from backend.modules.customers.models.customer_models import Customer

from ..models.promotion_models import ReferralStatus
from ..schemas.promotion_schemas import (
    ReferralProgramCreate, ReferralProgram as ReferralProgramSchema,
    CustomerReferralCreate, CustomerReferral as CustomerReferralSchema
)
from ..services.referral_service import ReferralService

router = APIRouter(prefix="/referrals", tags=["referrals"])


@router.post("/programs", response_model=ReferralProgramSchema)
def create_referral_program(
    program_data: ReferralProgramCreate,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Create a new referral program"""
    try:
        service = ReferralService(db)
        program = service.create_referral_program(
            program_data=program_data,
            created_by=current_user.id if hasattr(current_user, 'id') else None
        )
        return program
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create referral program")


@router.get("/programs", response_model=List[ReferralProgramSchema])
def get_referral_programs(
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get all referral programs"""
    try:
        from ..models.promotion_models import ReferralProgram
        
        query = db.query(ReferralProgram)
        
        if active_only:
            now = datetime.utcnow()
            query = query.filter(
                ReferralProgram.is_active == True,
                ReferralProgram.start_date <= now
            ).filter(
                (ReferralProgram.end_date.is_(None)) |
                (ReferralProgram.end_date > now)
            )
        
        programs = query.order_by(ReferralProgram.created_at.desc()).all()
        return programs
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get referral programs")


@router.get("/programs/{program_id}", response_model=ReferralProgramSchema)
def get_referral_program(
    program_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific referral program"""
    try:
        from ..models.promotion_models import ReferralProgram
        
        program = db.query(ReferralProgram).filter(
            ReferralProgram.id == program_id
        ).first()
        
        if not program:
            raise HTTPException(status_code=404, detail="Referral program not found")
        
        return program
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get referral program")


@router.post("/", response_model=CustomerReferralSchema)
def create_referral(
    referral_data: CustomerReferralCreate,
    program_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Create a new customer referral"""
    try:
        # Verify the referrer is the current user or admin
        if (hasattr(current_user, 'id') and current_user.id != referral_data.referrer_id and 
            not hasattr(current_user, 'is_admin')):
            raise HTTPException(status_code=403, detail="Can only create referrals for yourself")
        
        service = ReferralService(db)
        referral = service.create_referral(
            referral_data=referral_data,
            program_id=program_id
        )
        return referral
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create referral")


@router.get("/customer/{customer_id}/as-referrer", response_model=List[CustomerReferralSchema])
def get_customer_referrals_as_referrer(
    customer_id: int,
    status: Optional[ReferralStatus] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get referrals made by a customer (as referrer)"""
    try:
        # Check if user can access this customer's referrals
        if (hasattr(current_user, 'id') and current_user.id != customer_id and 
            not hasattr(current_user, 'is_admin')):
            raise HTTPException(status_code=403, detail="Access denied")
        
        service = ReferralService(db)
        referrals = service.get_customer_referrals(
            customer_id=customer_id,
            as_referrer=True,
            status=status
        )
        return referrals
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get customer referrals")


@router.get("/customer/{customer_id}/as-referee", response_model=List[CustomerReferralSchema])
def get_customer_referrals_as_referee(
    customer_id: int,
    status: Optional[ReferralStatus] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get referrals received by a customer (as referee)"""
    try:
        # Check if user can access this customer's referrals
        if (hasattr(current_user, 'id') and current_user.id != customer_id and 
            not hasattr(current_user, 'is_admin')):
            raise HTTPException(status_code=403, detail="Access denied")
        
        service = ReferralService(db)
        referrals = service.get_customer_referrals(
            customer_id=customer_id,
            as_referrer=False,
            status=status
        )
        return referrals
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get customer referrals")


@router.get("/my-referrals", response_model=List[CustomerReferralSchema])
def get_my_referrals(
    as_referrer: bool = True,
    status: Optional[ReferralStatus] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get referrals for the current user"""
    try:
        if not hasattr(current_user, 'id'):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        service = ReferralService(db)
        referrals = service.get_customer_referrals(
            customer_id=current_user.id,
            as_referrer=as_referrer,
            status=status
        )
        return referrals
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get your referrals")


@router.get("/code/{referral_code}", response_model=CustomerReferralSchema)
def get_referral_by_code(
    referral_code: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get referral details by code"""
    try:
        service = ReferralService(db)
        referral = service.get_referral_by_code(referral_code)
        
        if not referral:
            raise HTTPException(status_code=404, detail="Referral code not found")
        
        return referral
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get referral")


@router.post("/process-signup")
def process_referral_signup(
    referee_email: str,
    referee_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Process when a referred customer signs up (internal API)"""
    try:
        service = ReferralService(db)
        updated_referrals = service.process_referral_signup(
            referee_email=referee_email,
            referee_id=referee_id
        )
        
        return {
            "message": "Referral signup processed",
            "updated_referrals": len(updated_referrals),
            "referral_ids": [r.id for r in updated_referrals]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to process referral signup")


@router.post("/process-completion")
def process_referral_completion(
    order_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Process referral completion when referee makes qualifying order (internal API)"""
    try:
        service = ReferralService(db)
        processed_referrals = service.process_referral_completion(order_id)
        
        return {
            "message": "Referral completion processed",
            "processed_referrals": len(processed_referrals),
            "referral_data": processed_referrals
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to process referral completion")


@router.post("/{referral_id}/issue-rewards")
def issue_referral_rewards(
    referral_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Issue rewards for a completed referral"""
    try:
        service = ReferralService(db)
        results = service.issue_referral_rewards(referral_id)
        
        return {
            "message": "Referral rewards processed",
            "results": results
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to issue referral rewards")


@router.get("/analytics")
def get_referral_analytics(
    program_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get referral program analytics"""
    try:
        service = ReferralService(db)
        analytics = service.get_referral_analytics(
            program_id=program_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not analytics:
            return {"message": "No referral data found for the specified criteria"}
        
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get referral analytics")


@router.post("/expire-old")
def expire_old_referrals(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Expire referrals that have passed their expiration date (admin/cron task)"""
    try:
        service = ReferralService(db)
        expired_count = service.expire_old_referrals()
        
        return {
            "message": "Old referrals expired",
            "expired_count": expired_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to expire old referrals")


@router.post("/generate-code/{customer_id}")
def generate_referral_code(
    customer_id: int,
    length: int = Query(8, ge=4, le=20),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Generate a referral code for a customer (for preview/testing)"""
    try:
        # Check if user can generate code for this customer
        if (hasattr(current_user, 'id') and current_user.id != customer_id and 
            not hasattr(current_user, 'is_admin')):
            raise HTTPException(status_code=403, detail="Access denied")
        
        service = ReferralService(db)
        code = service.generate_referral_code(
            customer_id=customer_id,
            length=length
        )
        
        return {"code": code}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate referral code")


@router.get("/programs/{program_id}/analytics")
def get_program_analytics(
    program_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get analytics for a specific referral program"""
    try:
        service = ReferralService(db)
        analytics = service.get_referral_analytics(
            program_id=program_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not analytics:
            raise HTTPException(status_code=404, detail="Program not found or no data")
        
        return analytics
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to get program analytics")