from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from core.auth import User, get_current_user, MOCK_USERS
from core.database import get_db
from core.rbac_service import RBACService

router = APIRouter(prefix="/api/v1/gdpr", tags=["GDPR Compliance"])

# In-memory consent store. In production, persist to DB.
CONSENT_STORE: Dict[int, Dict[str, bool]] = {}


class ConsentPreferences(BaseModel):
    """User consent preferences."""

    marketing: bool = Field(
        ..., description="Consent to receive marketing communications"
    )
    analytics: bool = Field(..., description="Consent to analytics tracking")
    third_party_sharing: bool = Field(
        ..., description="Consent to share data with third parties"
    )


def _serialize_rbac_user(user: Any, rbac_service: RBACService) -> Dict[str, Any]:
    """Serialize RBAC user data for GDPR exports without sensitive fields."""

    if user is None:
        return {}

    roles = [role.name for role in rbac_service.get_user_roles(user.id)]

    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "default_tenant_id": user.default_tenant_id,
        "accessible_tenant_ids": user.accessible_tenant_ids or [],
        "roles": roles,
        "last_login": user.last_login.isoformat() if getattr(user, "last_login", None) else None,
        "created_at": user.created_at.isoformat() if getattr(user, "created_at", None) else None,
        "updated_at": user.updated_at.isoformat() if getattr(user, "updated_at", None) else None,
    }


def _load_user_export(
    current_user: User, db: Session
) -> Optional[Dict[str, Any]]:
    """Load exportable user data from RBAC or fallback legacy store."""

    rbac_service = RBACService(db)
    rbac_user = rbac_service.get_user_by_id(current_user.id)

    if rbac_user:
        return _serialize_rbac_user(rbac_user, rbac_service)

    legacy = MOCK_USERS.get(current_user.username)
    if legacy:
        return {k: v for k, v in legacy.items() if k != "hashed_password"}

    return None


@router.get("/consents", response_model=ConsentPreferences)
async def get_consents(current_user: User = Depends(get_current_user)):
    """Retrieve current consent preferences for the authenticated user."""
    prefs = CONSENT_STORE.get(current_user.id)
    if prefs is None:
        # Default: no consent granted until explicitly provided
        prefs = {"marketing": False, "analytics": False, "third_party_sharing": False}
        CONSENT_STORE[current_user.id] = prefs
    return ConsentPreferences(**prefs)


@router.post("/consents", response_model=ConsentPreferences)
async def update_consents(
    preferences: ConsentPreferences,
    current_user: User = Depends(get_current_user),
):
    """Update consent preferences for the authenticated user."""
    CONSENT_STORE[current_user.id] = preferences.dict()
    return preferences


@router.get("/export", response_model=Dict[str, Any])
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export personal data for the authenticated user as required by GDPR Article 20."""
    user_record = _load_user_export(current_user, db)
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": user_record,
        "consents": CONSENT_STORE.get(current_user.id, {}),
    }


@router.delete("/delete", status_code=status.HTTP_204_NO_CONTENT)
async def request_account_deletion(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete user account and all associated personal data.

    This performs immediate synchronous deletion. In production, consider
    implementing async processing with status tracking.
    """
    rbac_service = RBACService(db)
    rbac_user = rbac_service.get_user_by_id(current_user.id)

    if rbac_user:
        rbac_user.is_active = False
        rbac_user.first_name = None
        rbac_user.last_name = None
        rbac_user.phone = None
        rbac_user.accessible_tenant_ids = []
        rbac_user.email = f"deleted-{rbac_user.id}@auraconnect.invalid"
        db.add(rbac_user)
        db.commit()
    elif current_user.username in MOCK_USERS:
        MOCK_USERS[current_user.username]["is_active"] = False
        del MOCK_USERS[current_user.username]

    # Remove consent records
    if current_user.id in CONSENT_STORE:
        del CONSENT_STORE[current_user.id]

    # Return 204 No Content for successful deletion
    # Note: FastAPI will automatically return empty response with 204
    return None
