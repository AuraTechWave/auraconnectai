# backend/modules/analytics/routers/pos/alerts_routes.py

"""
POS Analytics alerts routes.

Handles alert management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional
import logging

from core.database import get_db
from core.auth import get_current_user
from core.auth import User
from core.auth import require_permission

# NotFoundError replaced with standard KeyError

from ...schemas.pos_analytics_schemas import AlertSeverity
from ...services.pos_alerts_service import POSAlertsService

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/alerts/active")
async def get_active_pos_alerts(
    severity: Optional[AlertSeverity] = Query(None, description="Filter by severity"),
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    terminal_id: Optional[str] = Query(None, description="Filter by terminal"),
    limit: int = Query(50, ge=1, le=200, description="Maximum alerts to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
):
    """
    Get active POS analytics alerts with pagination.

    Returns list of active alerts with filtering options.

    Requires: analytics.view permission
    Rate limit: 60 requests per minute
    """

    try:
        service = POSAlertsService(db)

        alerts, total_count = await service.get_active_alerts(
            severity=severity,
            provider_id=provider_id,
            terminal_id=terminal_id,
            limit=limit,
            offset=offset,
        )

        return {
            "alerts": alerts,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total_count,
            "filters": {
                "severity": severity,
                "provider_id": provider_id,
                "terminal_id": terminal_id,
            },
        }

    except Exception as e:
        logger.error(f"Error getting POS alerts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve POS alerts",
        )


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_pos_alert(
    alert_id: str,
    notes: Optional[str] = Query(
        None, description="Acknowledgment notes", max_length=500
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
):
    """
    Acknowledge a POS analytics alert.

    Marks the alert as acknowledged by the current user.

    Requires: analytics.manage permission
    """

    try:
        service = POSAlertsService(db)

        await service.acknowledge_alert(
            alert_id=alert_id, acknowledged_by=current_user.id, notes=notes
        )

        return {
            "success": True,
            "message": "Alert acknowledged successfully",
            "alert_id": alert_id,
        }

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found or already acknowledged",
        )
    except Exception as e:
        logger.error(f"Error acknowledging alert: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to acknowledge alert",
        )


@router.post("/alerts/{alert_id}/resolve")
async def resolve_pos_alert(
    alert_id: str,
    resolution_notes: str = Query(..., description="Resolution notes", max_length=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
):
    """
    Resolve a POS analytics alert.

    Marks the alert as resolved with resolution notes.

    Requires: analytics.manage permission
    """

    try:
        service = POSAlertsService(db)

        await service.resolve_alert(
            alert_id=alert_id,
            resolved_by=current_user.id,
            resolution_notes=resolution_notes,
        )

        return {
            "success": True,
            "message": "Alert resolved successfully",
            "alert_id": alert_id,
        }

    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found"
        )
    except Exception as e:
        logger.error(f"Error resolving alert: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve alert",
        )


@router.get("/alerts/history")
async def get_alert_history(
    provider_id: Optional[int] = Query(None, description="Filter by provider"),
    terminal_id: Optional[str] = Query(None, description="Filter by terminal"),
    days_back: int = Query(7, ge=1, le=90, description="Days of history to retrieve"),
    limit: int = Query(100, ge=1, le=500, description="Maximum alerts to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("analytics:read")),
):
    """
    Get historical alerts.

    Returns resolved and acknowledged alerts from the specified time period.

    Requires: analytics.view permission
    """

    try:
        service = POSAlertsService(db)

        history = await service.get_alert_history(
            provider_id=provider_id,
            terminal_id=terminal_id,
            days_back=days_back,
            limit=limit,
        )

        return {
            "alerts": history,
            "count": len(history),
            "days_back": days_back,
            "filters": {"provider_id": provider_id, "terminal_id": terminal_id},
        }

    except Exception as e:
        logger.error(f"Error getting alert history: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve alert history",
        )
