from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

from core.auth import User, get_current_user, MOCK_USERS

router = APIRouter(prefix="/api/v1/gdpr", tags=["GDPR Compliance"])

# In-memory consent store. In production, persist to DB.
CONSENT_STORE: Dict[int, Dict[str, bool]] = {}

class ConsentPreferences(BaseModel):
    """User consent preferences."""
    marketing: bool = Field(..., description="Consent to receive marketing communications")
    analytics: bool = Field(..., description="Consent to analytics tracking")
    third_party_sharing: bool = Field(..., description="Consent to share data with third parties")


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
async def export_user_data(current_user: User = Depends(get_current_user)):
    """Export personal data for the authenticated user as required by GDPR Article 20."""
    # Gather data we have in memory. In production, fetch from persistent storage.
    user_record = MOCK_USERS.get(current_user.username)
    if not user_record:
        raise HTTPException(status_code=404, detail="User not found")

    data_package = {
        "user": {k: v for k, v in user_record.items() if k != "hashed_password"},
        "consents": CONSENT_STORE.get(current_user.id, {}),
    }
    return data_package


@router.delete("/delete", status_code=status.HTTP_202_ACCEPTED)
async def request_account_deletion(current_user: User = Depends(get_current_user)):
    """Request deletion of personal data. For demo, we immediately wipe in-memory data."""
    # Remove from mock DB
    if current_user.username in MOCK_USERS:
        del MOCK_USERS[current_user.username]
    # Remove consents
    if current_user.id in CONSENT_STORE:
        del CONSENT_STORE[current_user.id]
    # Mark user inactive (in case downstream still references)
    current_user.is_active = False
    return {"detail": "Account deletion processed"}