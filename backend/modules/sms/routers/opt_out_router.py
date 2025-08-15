# backend/modules/sms/routers/opt_out_router.py

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from modules.sms.services.opt_out_service import OptOutService
from modules.sms.schemas.sms_schemas import (
    SMSOptOutCreate, SMSOptOutUpdate, SMSOptOutResponse
)
from modules.sms.models.sms_models import SMSTemplateCategory

router = APIRouter(prefix="/api/v1/sms/opt-out", tags=["SMS Opt-Out"])


@router.post("/", response_model=SMSOptOutResponse)
async def process_opt_out(
    opt_out_data: SMSOptOutCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Process an opt-out request"""
    try:
        opt_out_service = OptOutService(db)
        opt_out = opt_out_service.process_opt_out(
            phone_number=opt_out_data.phone_number,
            reason=opt_out_data.opt_out_reason,
            method=opt_out_data.opt_out_method or 'web',
            customer_id=opt_out_data.customer_id,
            categories=[SMSTemplateCategory(cat) for cat in opt_out_data.categories_opted_out] if opt_out_data.categories_opted_out else None,
            ip_address=opt_out_data.ip_address,
            user_agent=opt_out_data.user_agent
        )
        return opt_out
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process opt-out: {str(e)}")


@router.post("/opt-in", response_model=SMSOptOutResponse)
async def process_opt_in(
    phone_number: str,
    categories: Optional[List[SMSTemplateCategory]] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Process an opt-in request (re-subscribe)"""
    try:
        opt_out_service = OptOutService(db)
        opt_out = opt_out_service.process_opt_in(
            phone_number=phone_number,
            method='web',
            categories=categories
        )
        
        if not opt_out:
            return {"message": "No opt-out record found for this number"}
        
        return opt_out
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process opt-in: {str(e)}")


@router.get("/check/{phone_number}")
async def check_opt_out_status(
    phone_number: str,
    category: Optional[SMSTemplateCategory] = Query(None),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Check if a phone number is opted out"""
    opt_out_service = OptOutService(db)
    is_opted_out = opt_out_service.is_opted_out(phone_number, category)
    
    return {
        "phone_number": phone_number,
        "is_opted_out": is_opted_out,
        "category": category.value if category else "all"
    }


@router.get("/list", response_model=List[SMSOptOutResponse])
async def get_opt_out_list(
    opted_out_only: bool = Query(True),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get list of opt-out records"""
    opt_out_service = OptOutService(db)
    opt_outs = opt_out_service.get_opt_out_list(
        opted_out_only=opted_out_only,
        limit=limit,
        offset=offset
    )
    return opt_outs


@router.get("/statistics")
async def get_opt_out_statistics(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get opt-out statistics"""
    opt_out_service = OptOutService(db)
    stats = opt_out_service.get_opt_out_statistics()
    return stats


@router.post("/bulk-opt-out")
async def bulk_opt_out(
    phone_numbers: List[str],
    reason: str = "Bulk opt-out",
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Bulk opt-out multiple phone numbers"""
    try:
        opt_out_service = OptOutService(db)
        count = opt_out_service.bulk_opt_out(
            phone_numbers=phone_numbers,
            reason=reason,
            method='admin'
        )
        return {
            "success": True,
            "processed_count": count,
            "message": f"Successfully opted out {count} phone numbers"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process bulk opt-out: {str(e)}")


@router.get("/export")
async def export_opt_out_list(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Export opt-out list for compliance"""
    opt_out_service = OptOutService(db)
    export_data = opt_out_service.export_opt_out_list()
    
    return {
        "total_records": len(export_data),
        "export_date": datetime.utcnow().isoformat(),
        "data": export_data
    }


@router.post("/process-inbound")
async def process_inbound_message(
    phone_number: str,
    message_body: str,
    customer_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Process inbound SMS for opt-out/opt-in keywords"""
    opt_out_service = OptOutService(db)
    result = opt_out_service.process_inbound_message(
        phone_number=phone_number,
        message_body=message_body,
        customer_id=customer_id
    )
    
    return result