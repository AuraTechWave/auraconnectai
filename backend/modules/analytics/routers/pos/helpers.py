# backend/modules/analytics/routers/pos/helpers.py

"""
Helper functions for POS analytics routes.
"""

from typing import Optional, Tuple
from datetime import datetime, timedelta
from fastapi import HTTPException, status

from ...schemas.pos_analytics_schemas import TimeRange


def parse_time_range(
    time_range: TimeRange,
    start_date: Optional[datetime],
    end_date: Optional[datetime]
) -> Tuple[datetime, datetime]:
    """
    Parse time range into start and end dates.
    
    Args:
        time_range: Predefined time range enum
        start_date: Custom start date
        end_date: Custom end date
        
    Returns:
        Tuple of (start_date, end_date)
        
    Raises:
        HTTPException: If custom range is invalid
    """
    
    if time_range == TimeRange.CUSTOM:
        if not start_date or not end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date and end_date required for custom time range"
            )
        
        if start_date >= end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before end_date"
            )
            
        # Limit custom range to 90 days
        if (end_date - start_date).days > 90:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Custom time range cannot exceed 90 days"
            )
            
        return start_date, end_date
    
    # Calculate based on predefined range
    now = datetime.utcnow()
    
    if time_range == TimeRange.LAST_HOUR:
        return now - timedelta(hours=1), now
    elif time_range == TimeRange.LAST_24_HOURS:
        return now - timedelta(days=1), now
    elif time_range == TimeRange.LAST_7_DAYS:
        return now - timedelta(days=7), now
    elif time_range == TimeRange.LAST_30_DAYS:
        return now - timedelta(days=30), now
    else:
        # Default to last 24 hours
        return now - timedelta(days=1), now


def get_media_type(format: str) -> str:
    """Get media type for file format"""
    media_types = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf"
    }
    return media_types.get(format, "application/octet-stream")