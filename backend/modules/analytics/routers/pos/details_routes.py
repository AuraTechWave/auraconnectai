# backend/modules/analytics/routers/pos/details_routes.py

"""
POS Analytics detail routes.

Handles provider and terminal detail endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import logging

from backend.core.database import get_db
from backend.core.auth import get_current_user
from backend.modules.staff.models import StaffMember
from backend.core.rbac import require_permissions, Permission
from backend.core.exceptions import NotFoundError

from ...schemas.pos_analytics_schemas import (
    POSProviderDetailsRequest, POSProviderDetailsResponse,
    POSTerminalDetailsRequest, POSTerminalDetailsResponse,
    POSComparisonRequest, POSComparisonResponse
)
from ...services.pos_details_service import POSDetailsService
from .helpers import parse_time_range

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/provider/{provider_id}/details", response_model=POSProviderDetailsResponse)
async def get_provider_analytics_details(
    provider_id: int,
    request: POSProviderDetailsRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Get detailed analytics for a specific POS provider.
    
    Returns comprehensive metrics including sync performance,
    webhook processing, error analysis, and terminal breakdown.
    
    Requires: analytics.view permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSDetailsService(db)
        
        # Convert time range
        start_date, end_date = parse_time_range(
            request.time_range,
            request.start_date,
            request.end_date
        )
        
        # Get provider details
        provider_details = await service.get_provider_details(
            provider_id=provider_id,
            start_date=start_date,
            end_date=end_date,
            include_terminals=request.include_terminals,
            include_errors=request.include_errors
        )
        
        return provider_details
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"POS provider {provider_id} not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting provider analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve provider analytics"
        )


@router.post("/terminal/{terminal_id}/details", response_model=POSTerminalDetailsResponse)
async def get_terminal_analytics_details(
    terminal_id: str,
    request: POSTerminalDetailsRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Get detailed analytics for a specific POS terminal.
    
    Returns transaction metrics, sync performance, error analysis,
    and historical trends for the terminal.
    
    Requires: analytics.view permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSDetailsService(db)
        
        # Convert time range
        start_date, end_date = parse_time_range(
            request.time_range,
            request.start_date,
            request.end_date
        )
        
        # Get terminal details
        terminal_details = await service.get_terminal_details(
            terminal_id=terminal_id,
            start_date=start_date,
            end_date=end_date
        )
        
        return terminal_details
        
    except NotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"POS terminal {terminal_id} not found"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting terminal analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve terminal analytics"
        )


@router.post("/compare", response_model=POSComparisonResponse)
async def compare_pos_providers(
    request: POSComparisonRequest,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user)
):
    """
    Compare analytics metrics across multiple POS providers.
    
    Returns side-by-side comparison of key metrics, rankings,
    and insights for selected providers.
    
    Requires: analytics.view permission
    """
    await require_permissions(current_user, [Permission.ANALYTICS_VIEW])
    
    try:
        service = POSDetailsService(db)
        
        # Convert time range
        start_date, end_date = parse_time_range(
            request.time_range,
            request.start_date,
            request.end_date
        )
        
        # Get comparison data
        comparison = await service.compare_providers(
            provider_ids=request.provider_ids,
            start_date=start_date,
            end_date=end_date,
            metrics=request.metrics
        )
        
        return comparison
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error comparing POS providers: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to compare POS providers"
        )