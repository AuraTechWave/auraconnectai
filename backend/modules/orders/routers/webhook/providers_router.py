# backend/modules/orders/routers/webhook/providers_router.py

"""
CRUD operations for external POS provider management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from core.database import get_db
from core.auth import get_current_user
from modules.staff.models.staff_models import StaffMember
from modules.orders.models.external_pos_models import (
    ExternalPOSProvider,
    ExternalPOSWebhookEvent,
)
from modules.orders.schemas.external_pos_schemas import (
    ExternalPOSProviderResponse,
    ExternalPOSProviderCreate,
    ExternalPOSProviderUpdate,
)
from modules.orders.utils.security_utils import mask_sensitive_dict

router = APIRouter(
    prefix="/webhooks/external-pos/providers",
    tags=["Webhook Providers"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=List[ExternalPOSProviderResponse])
async def list_providers(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> List[ExternalPOSProviderResponse]:
    """List all configured external POS providers"""

    check_permission(current_user, "webhooks", "read")

    query = db.query(ExternalPOSProvider)

    if is_active is not None:
        query = query.filter(ExternalPOSProvider.is_active == is_active)

    providers = query.order_by(ExternalPOSProvider.provider_name).all()

    # Convert to response models
    return [
        ExternalPOSProviderResponse(
            id=provider.id,
            provider_code=provider.provider_code,
            provider_name=provider.provider_name,
            webhook_endpoint_id=provider.webhook_endpoint_id,
            webhook_url=f"/api/webhooks/external-pos/{provider.provider_code}/events",
            is_active=provider.is_active,
            auth_type=provider.auth_type,
            supported_events=provider.supported_events,
            rate_limit_per_minute=provider.rate_limit_per_minute,
            created_at=provider.created_at,
            updated_at=provider.updated_at,
        )
        for provider in providers
    ]


@router.post("", response_model=ExternalPOSProviderResponse)
async def create_provider(
    provider_data: ExternalPOSProviderCreate,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> ExternalPOSProviderResponse:
    """Create a new external POS provider configuration"""

    check_permission(current_user, "webhooks", "create")

    # Check if provider code already exists
    existing = (
        db.query(ExternalPOSProvider)
        .filter(ExternalPOSProvider.provider_code == provider_data.provider_code)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Provider with code {provider_data.provider_code} already exists",
        )

    # Create provider
    provider = ExternalPOSProvider(
        provider_code=provider_data.provider_code,
        provider_name=provider_data.provider_name,
        webhook_endpoint_id=provider_data.webhook_endpoint_id,
        is_active=provider_data.is_active,
        auth_type=provider_data.auth_type,
        auth_config=provider_data.auth_config,
        settings=provider_data.settings,
        supported_events=provider_data.supported_events,
        rate_limit_per_minute=provider_data.rate_limit_per_minute,
    )

    db.add(provider)
    db.commit()
    db.refresh(provider)

    return ExternalPOSProviderResponse(
        id=provider.id,
        provider_code=provider.provider_code,
        provider_name=provider.provider_name,
        webhook_endpoint_id=provider.webhook_endpoint_id,
        webhook_url=f"/api/webhooks/external-pos/{provider.provider_code}/events",
        is_active=provider.is_active,
        auth_type=provider.auth_type,
        supported_events=provider.supported_events,
        rate_limit_per_minute=provider.rate_limit_per_minute,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.put("/{provider_id}", response_model=ExternalPOSProviderResponse)
async def update_provider(
    provider_id: int,
    update_data: ExternalPOSProviderUpdate,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
) -> ExternalPOSProviderResponse:
    """Update an external POS provider configuration"""

    check_permission(current_user, "webhooks", "update")

    provider = (
        db.query(ExternalPOSProvider)
        .filter(ExternalPOSProvider.id == provider_id)
        .first()
    )

    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Update fields
    if update_data.provider_name is not None:
        provider.provider_name = update_data.provider_name
    if update_data.is_active is not None:
        provider.is_active = update_data.is_active
    if update_data.auth_config is not None:
        provider.auth_config = update_data.auth_config
    if update_data.settings is not None:
        provider.settings = update_data.settings
    if update_data.supported_events is not None:
        provider.supported_events = update_data.supported_events
    if update_data.rate_limit_per_minute is not None:
        provider.rate_limit_per_minute = update_data.rate_limit_per_minute

    db.commit()
    db.refresh(provider)

    return ExternalPOSProviderResponse(
        id=provider.id,
        provider_code=provider.provider_code,
        provider_name=provider.provider_name,
        webhook_endpoint_id=provider.webhook_endpoint_id,
        webhook_url=f"/api/webhooks/external-pos/{provider.provider_code}/events",
        is_active=provider.is_active,
        auth_type=provider.auth_type,
        supported_events=provider.supported_events,
        rate_limit_per_minute=provider.rate_limit_per_minute,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.delete("/{provider_id}")
async def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
    current_user: StaffMember = Depends(get_current_user),
):
    """Delete an external POS provider configuration"""

    check_permission(current_user, "webhooks", "delete")

    provider = (
        db.query(ExternalPOSProvider)
        .filter(ExternalPOSProvider.id == provider_id)
        .first()
    )

    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Check if provider has any webhook events
    event_count = (
        db.query(ExternalPOSWebhookEvent)
        .filter(ExternalPOSWebhookEvent.provider_id == provider_id)
        .count()
    )

    if event_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete provider with {event_count} existing webhook events. Deactivate instead.",
        )

    db.delete(provider)
    db.commit()

    return {"message": f"Provider {provider.provider_code} deleted successfully"}
