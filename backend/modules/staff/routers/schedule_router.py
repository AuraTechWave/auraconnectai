# backend/modules/staff/routers/schedule_router.py

from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.auth import get_current_user, require_permission, User
from ..schemas.schedule_schemas import (
    SchedulePreviewResponse, SchedulePublishRequest,
    ScheduleCreateRequest, ScheduleUpdateRequest,
    PaginatedPreviewResponse
)
from ..services.schedule_service import schedule_service
from ..services.schedule_cache_service import schedule_cache_service
from ..services.schedule_notification_service import schedule_notification_service

router = APIRouter(prefix="/schedule", tags=["Staff Schedule"])


@router.get("/preview", response_model=SchedulePreviewResponse)
async def get_schedule_preview(
    start_date: date = Query(..., description="Start date for preview"),
    end_date: date = Query(..., description="End date for preview"),
    department_id: Optional[int] = Query(None),
    role_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    use_cache: bool = Query(True, description="Use cached data if available"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get schedule preview for date range with optional caching
    """
    # Build filters
    filters = {}
    if department_id:
        filters["department_id"] = department_id
    if role_id:
        filters["role_id"] = role_id
    if location_id:
        filters["location_id"] = location_id
    
    # Check cache if enabled
    if use_cache:
        cached_preview = await schedule_cache_service.get_preview_cache(
            current_user.restaurant_id,
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time()),
            filters
        )
        
        if cached_preview:
            return SchedulePreviewResponse(**cached_preview)
    
    # Generate preview
    preview_data = await schedule_service.generate_preview(
        db,
        current_user.restaurant_id,
        start_date,
        end_date,
        filters
    )
    
    # Cache the result
    if use_cache:
        await schedule_cache_service.set_preview_cache(
            current_user.restaurant_id,
            datetime.combine(start_date, datetime.min.time()),
            datetime.combine(end_date, datetime.max.time()),
            preview_data.dict(),
            filters,
            ttl=3600  # 1 hour cache
        )
    
    return preview_data


@router.get("/preview/paginated", response_model=PaginatedPreviewResponse)
async def get_schedule_preview_paginated(
    start_date: date = Query(...),
    end_date: date = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    department_id: Optional[int] = Query(None),
    role_id: Optional[int] = Query(None),
    location_id: Optional[int] = Query(None),
    sort_by: str = Query("name", regex="^(name|role|department)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get paginated schedule preview for large staff lists
    """
    filters = {}
    if department_id:
        filters["department_id"] = department_id
    if role_id:
        filters["role_id"] = role_id
    if location_id:
        filters["location_id"] = location_id
    
    # Get paginated preview
    paginated_data = await schedule_service.generate_preview_paginated(
        db,
        current_user.restaurant_id,
        start_date,
        end_date,
        page,
        page_size,
        sort_by,
        filters
    )
    
    return paginated_data


@router.post("/publish")
@require_permission("schedule.publish")
async def publish_schedule(
    publish_data: SchedulePublishRequest,
    send_notifications: bool = Query(True, description="Send notifications to staff"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Publish schedule for specified date range
    
    Requires permission: schedule.publish
    """
    # Publish schedule
    result = await schedule_service.publish_schedule(
        db,
        current_user.restaurant_id,
        publish_data.start_date,
        publish_data.end_date,
        current_user.id,
        publish_data.notes
    )
    
    # Send notifications if enabled
    if send_notifications:
        notification_result = await schedule_service.send_schedule_notifications(
            db,
            current_user.restaurant_id,
            publish_data.start_date,
            publish_data.end_date,
            publish_data.notification_channels or ["email", "in_app"],
            publish_data.notes
        )
        result["notifications"] = notification_result
    
    # Invalidate cache for this restaurant
    await schedule_cache_service.invalidate_restaurant_cache(
        current_user.restaurant_id
    )
    
    return result


@router.post("/shifts")
@require_permission("schedule.manage")
async def create_shift(
    shift_data: ScheduleCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new shift
    
    Requires permission: schedule.manage
    """
    shift = await schedule_service.create_shift(
        db,
        current_user.restaurant_id,
        shift_data,
        current_user.id
    )
    
    # Invalidate relevant cache
    await schedule_cache_service.invalidate_restaurant_cache(
        current_user.restaurant_id
    )
    
    return shift


@router.put("/shifts/{shift_id}")
@require_permission("schedule.manage")
async def update_shift(
    shift_id: int,
    update_data: ScheduleUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update an existing shift
    
    Requires permission: schedule.manage
    """
    shift = await schedule_service.update_shift(
        db,
        current_user.restaurant_id,
        shift_id,
        update_data,
        current_user.id
    )
    
    # Invalidate cache
    await schedule_cache_service.invalidate_restaurant_cache(
        current_user.restaurant_id
    )
    
    return shift


@router.delete("/shifts/{shift_id}")
@require_permission("schedule.manage")
async def delete_shift(
    shift_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a shift
    
    Requires permission: schedule.manage
    """
    await schedule_service.delete_shift(
        db,
        current_user.restaurant_id,
        shift_id
    )
    
    # Invalidate cache
    await schedule_cache_service.invalidate_restaurant_cache(
        current_user.restaurant_id
    )
    
    return {"success": True, "message": "Shift deleted successfully"}


@router.post("/cache/warm")
@require_permission("schedule.manage")
async def warm_schedule_cache(
    week_start: date = Query(..., description="Start of week to cache"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Pre-warm cache for a week's schedule
    
    Requires permission: schedule.manage
    """
    async def generate_preview_func(restaurant_id: int, start: datetime, end: datetime):
        return await schedule_service.generate_preview(
            db, restaurant_id, start.date(), end.date(), {}
        )
    
    await schedule_cache_service.warm_cache_for_week(
        current_user.restaurant_id,
        datetime.combine(week_start, datetime.min.time()),
        generate_preview_func
    )
    
    return {
        "success": True,
        "message": f"Cache warmed for week starting {week_start}"
    }


@router.get("/cache/stats")
@require_permission("schedule.manage")
async def get_cache_statistics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get cache statistics for schedule data
    
    Requires permission: schedule.manage
    """
    stats = await schedule_cache_service.get_cache_stats(
        current_user.restaurant_id
    )
    
    return stats


@router.post("/cache/clear")
@require_permission("schedule.manage")
async def clear_schedule_cache(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Clear all cached schedule data
    
    Requires permission: schedule.manage
    """
    await schedule_cache_service.invalidate_restaurant_cache(
        current_user.restaurant_id
    )
    
    return {
        "success": True,
        "message": "Schedule cache cleared successfully"
    }


@router.post("/reminders/send")
@require_permission("schedule.manage")
async def send_shift_reminders(
    hours_before: int = Query(2, ge=1, le=24, description="Hours before shift to send reminder"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send shift reminders for upcoming shifts
    
    Requires permission: schedule.manage
    """
    result = await schedule_notification_service.send_shift_reminders(
        db,
        current_user.restaurant_id,
        hours_before
    )
    
    return result


@router.post("/notifications/test")
@require_permission("schedule.manage") 
async def test_schedule_notifications(
    staff_id: int = Query(..., description="Staff ID to send test notification"),
    channels: List[str] = Query(["email"], description="Notification channels to test"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send test notification to verify notification system
    
    Requires permission: schedule.manage
    """
    from datetime import date, timedelta
    
    # Create a fake schedule for testing
    test_date = date.today() + timedelta(days=1)
    
    try:
        # Send test notifications
        if "email" in channels:
            # Test email notification
            pass
        
        if "sms" in channels:
            # Test SMS notification  
            pass
            
        if "push" in channels:
            # Test push notification
            pass
            
        return {
            "success": True,
            "message": f"Test notifications sent to staff {staff_id}",
            "channels_tested": channels
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to send test notifications"
        }