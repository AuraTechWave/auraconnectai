# backend/modules/promotions/routers/scheduling_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio

from core.database import get_db
from core.auth import get_current_user, require_admin

from ..services.scheduling_service import PromotionSchedulingService
from ..schemas.promotion_schemas import PromotionCreate

router = APIRouter(prefix="/scheduling", tags=["Promotion Scheduling"])


@router.post("/schedule")
def schedule_promotion(
    promotion_data: PromotionCreate,
    schedule_options: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Schedule a promotion with advanced scheduling options
    
    Schedule Options:
    - recurrence_pattern: 'none', 'daily', 'weekly', 'monthly', 'custom'
    - recurrence_interval: Interval for recurrence (e.g., every 2 weeks)
    - recurrence_days: Days of week/month for recurrence
    - max_occurrences: Maximum number of occurrences
    - auto_activate: Automatically activate when start time is reached
    - auto_deactivate: Automatically deactivate at end time
    - cron_expression: Cron expression for custom scheduling
    """
    try:
        service = PromotionSchedulingService(db)
        promotion = service.schedule_promotion(promotion_data, schedule_options)
        return {
            "promotion": promotion,
            "scheduling": promotion.metadata.get("scheduling", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to schedule promotion: {str(e)}")


@router.post("/process")
async def process_scheduled_promotions(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Manually trigger processing of scheduled promotions
    This is typically run by a background task scheduler
    """
    try:
        service = PromotionSchedulingService(db)
        results = await service.process_scheduled_promotions()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process scheduled promotions: {str(e)}")


@router.post("/time-based")
def create_time_based_promotion(
    promotion_data: PromotionCreate,
    time_rules: List[Dict[str, Any]] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Create a promotion with time-based activation rules
    
    Time Rule Types:
    - hour_of_day: Active during specific hours
    - day_of_week: Active on specific days
    - date_range: Active within date range
    - special_event: Active on special event days
    """
    try:
        service = PromotionSchedulingService(db)
        promotion = service.create_time_based_promotion(promotion_data, time_rules)
        return promotion
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create time-based promotion: {str(e)}")


@router.post("/process-time-rules")
async def process_time_based_promotions(
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Process all promotions with time-based rules"""
    try:
        service = PromotionSchedulingService(db)
        results = await service.process_time_based_promotions()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process time-based promotions: {str(e)}")


@router.post("/sequence")
def create_promotion_sequence(
    sequence_name: str = Body(...),
    promotions: List[Dict[str, Any]] = Body(...),
    trigger_conditions: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Create a sequence of automated promotions
    
    Each promotion in the sequence should include:
    - data: PromotionCreate data
    - delay_after_previous: Delay in hours after previous promotion
    - depends_on: List of previous promotion positions this depends on
    """
    try:
        service = PromotionSchedulingService(db)
        created_promotions = service.create_automated_promotion_sequence(
            sequence_name=sequence_name,
            promotions=promotions,
            trigger_conditions=trigger_conditions
        )
        return {
            "sequence_name": sequence_name,
            "promotions_created": len(created_promotions),
            "promotions": created_promotions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create promotion sequence: {str(e)}")


@router.get("/scheduled")
def get_scheduled_promotions(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    include_recurring: bool = Query(True),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get all scheduled promotions within a date range"""
    try:
        service = PromotionSchedulingService(db)
        scheduled_promotions = service.get_scheduled_promotions(
            start_date=start_date,
            end_date=end_date,
            include_recurring=include_recurring
        )
        return {
            "total": len(scheduled_promotions),
            "scheduled_promotions": scheduled_promotions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get scheduled promotions: {str(e)}")


@router.delete("/scheduled/{promotion_id}")
def cancel_scheduled_promotion(
    promotion_id: int,
    cancel_future_occurrences: bool = Query(True),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Cancel a scheduled promotion"""
    try:
        service = PromotionSchedulingService(db)
        success = service.cancel_scheduled_promotion(
            promotion_id=promotion_id,
            cancel_future_occurrences=cancel_future_occurrences
        )
        if success:
            return {"message": "Scheduled promotion cancelled successfully"}
        else:
            raise HTTPException(status_code=404, detail="Scheduled promotion not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel scheduled promotion: {str(e)}")


@router.get("/time-rules/{promotion_id}/evaluate")
def evaluate_time_based_rules(
    promotion_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Evaluate time-based rules for a specific promotion"""
    try:
        service = PromotionSchedulingService(db)
        should_be_active, reason = service.evaluate_time_based_rules(promotion_id)
        return {
            "promotion_id": promotion_id,
            "should_be_active": should_be_active,
            "reason": reason,
            "evaluated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate time-based rules: {str(e)}")


@router.get("/calendar")
def get_promotion_calendar(
    year: int = Query(..., ge=2020, le=2100),
    month: Optional[int] = Query(None, ge=1, le=12),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get promotion calendar view for a specific month or year"""
    try:
        from calendar import monthrange
        from datetime import date
        
        if month:
            start_date = datetime(year, month, 1)
            _, last_day = monthrange(year, month)
            end_date = datetime(year, month, last_day, 23, 59, 59)
        else:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
        
        service = PromotionSchedulingService(db)
        scheduled_promotions = service.get_scheduled_promotions(
            start_date=start_date,
            end_date=end_date,
            include_recurring=True
        )
        
        # Group by date
        calendar_data = {}
        for promo in scheduled_promotions:
            promo_date = datetime.fromisoformat(promo["start_date"]).date().isoformat()
            if promo_date not in calendar_data:
                calendar_data[promo_date] = []
            calendar_data[promo_date].append({
                "id": promo["id"],
                "name": promo["name"],
                "is_recurring": promo["is_recurring"]
            })
        
        return {
            "year": year,
            "month": month,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat()
            },
            "total_scheduled": len(scheduled_promotions),
            "calendar": calendar_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get promotion calendar: {str(e)}")


@router.post("/preview")
def preview_schedule(
    schedule_options: Dict[str, Any] = Body(...),
    start_date: datetime = Body(...),
    preview_count: int = Body(10, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Preview upcoming occurrences for a schedule configuration"""
    try:
        service = PromotionSchedulingService(db)
        occurrences = []
        current_date = start_date
        
        for _ in range(preview_count):
            next_occurrence = service._calculate_next_occurrence(current_date, schedule_options)
            if not next_occurrence:
                break
            occurrences.append(next_occurrence)
            current_date = datetime.fromisoformat(next_occurrence)
        
        return {
            "schedule_options": schedule_options,
            "preview_count": len(occurrences),
            "occurrences": occurrences
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to preview schedule: {str(e)}")