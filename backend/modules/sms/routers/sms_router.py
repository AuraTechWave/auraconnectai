# backend/modules/sms/routers/sms_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from core.database import get_db
from core.auth import get_current_user
from modules.sms.services.sms_service import SMSService
from modules.sms.services.cost_tracking_service import CostTrackingService
from modules.sms.services.delivery_tracking_service import DeliveryTrackingService
from modules.sms.schemas.sms_schemas import (
    SMSSendRequest, SMSBulkSendRequest, SMSMessageResponse,
    SMSStatusUpdate, SMSCostSummary
)
from modules.sms.models.sms_models import SMSStatus

router = APIRouter(prefix="/api/v1/sms", tags=["SMS"])


@router.post("/send", response_model=SMSMessageResponse)
async def send_sms(
    request: SMSSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Send a single SMS message"""
    try:
        sms_service = SMSService(db)
        message = await sms_service.send_sms(request, current_user.id)
        return message
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")


@router.post("/send-bulk", response_model=List[SMSMessageResponse])
async def send_bulk_sms(
    request: SMSBulkSendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Send bulk SMS messages"""
    try:
        sms_service = SMSService(db)
        messages = await sms_service.send_bulk_sms(request, current_user.id)
        return messages
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send bulk SMS: {str(e)}")


@router.get("/messages", response_model=List[SMSMessageResponse])
async def get_messages(
    customer_id: Optional[int] = Query(None),
    phone_number: Optional[str] = Query(None),
    status: Optional[SMSStatus] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get SMS message history with filters"""
    sms_service = SMSService(db)
    messages = sms_service.get_message_history(
        customer_id=customer_id,
        phone_number=phone_number,
        start_date=start_date,
        end_date=end_date,
        status=status,
        limit=limit,
        offset=offset
    )
    return messages


@router.get("/messages/{message_id}", response_model=SMSMessageResponse)
async def get_message(
    message_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get a specific SMS message"""
    from modules.sms.models.sms_models import SMSMessage
    
    message = db.query(SMSMessage).filter(SMSMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return message


@router.put("/messages/{message_id}/status")
async def update_message_status(
    message_id: int,
    status_update: SMSStatusUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Manually update message status"""
    sms_service = SMSService(db)
    message = sms_service.update_message_status(
        provider_message_id=str(message_id),
        status=status_update.status,
        delivered_at=status_update.delivered_at,
        failed_at=status_update.failed_at,
        error_message=status_update.error_message
    )
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    return {"success": True, "message": "Status updated"}


@router.get("/statistics")
async def get_statistics(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get SMS statistics for a period"""
    sms_service = SMSService(db)
    stats = sms_service.get_message_statistics(start_date, end_date)
    return stats


@router.get("/costs/summary", response_model=SMSCostSummary)
async def get_cost_summary(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get SMS cost summary for a period"""
    cost_service = CostTrackingService(db)
    summary = cost_service.get_cost_summary(start_date, end_date)
    return summary


@router.get("/costs/report")
async def get_billing_report(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Generate detailed billing report"""
    cost_service = CostTrackingService(db)
    report = cost_service.generate_billing_report(start_date, end_date)
    return report


@router.get("/delivery/metrics")
async def get_delivery_metrics(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get delivery metrics for a period"""
    delivery_service = DeliveryTrackingService(db)
    metrics = delivery_service.get_delivery_metrics(start_date, end_date)
    return metrics


@router.get("/delivery/real-time")
async def get_real_time_status(
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Get real-time status of recent messages"""
    delivery_service = DeliveryTrackingService(db)
    status = delivery_service.get_real_time_status(limit)
    return status


@router.post("/retry-failed")
async def retry_failed_messages(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Retry failed messages"""
    async def retry_messages():
        sms_service = SMSService(db)
        count = await sms_service.retry_failed_messages()
        return count
    
    background_tasks.add_task(retry_messages)
    return {"message": "Retry process started in background"}


@router.post("/process-scheduled")
async def process_scheduled_messages(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Process scheduled messages"""
    async def process_messages():
        sms_service = SMSService(db)
        count = await sms_service.process_scheduled_messages()
        return count
    
    background_tasks.add_task(process_messages)
    return {"message": "Processing scheduled messages in background"}


@router.post("/check-pending-deliveries")
async def check_pending_deliveries(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """Check and update pending delivery statuses"""
    async def check_deliveries():
        delivery_service = DeliveryTrackingService(db)
        count = await delivery_service.check_pending_deliveries()
        return count
    
    background_tasks.add_task(check_deliveries)
    return {"message": "Checking pending deliveries in background"}