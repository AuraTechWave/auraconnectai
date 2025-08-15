from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_limiter.depends import RateLimiter
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user
from ..models.staff_models import StaffMember
from ..models.biometric_models import StaffBiometric
from ..schemas.biometric_schemas import (
    FingerprintEnrollmentRequest,
    FingerprintEnrollmentResponse,
    FaceEnrollmentRequest,
    FaceEnrollmentResponse,
    BiometricCheckInRequest,
    BiometricCheckInResponse,
    PinSetupRequest,
    PinCheckInRequest,
)
from ..services.biometric_service import BiometricService
from ..enums.attendance_enums import CheckInMethod

router = APIRouter()


@router.post("/fingerprint/enroll", response_model=FingerprintEnrollmentResponse)
async def enroll_fingerprint(
    request: FingerprintEnrollmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Enroll a staff member's fingerprint with enhanced security"""
    service = BiometricService(db)
    success, message = service.enroll_fingerprint(
        request.staff_id, request.fingerprint_data, request.device_id
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Get the enrollment timestamp
    biometric = (
        db.query(StaffBiometric)
        .filter(StaffBiometric.staff_id == request.staff_id)
        .first()
    )

    return FingerprintEnrollmentResponse(
        success=True,
        message=message,
        enrolled_at=(
            biometric.fingerprint_enrolled_at if biometric else datetime.utcnow()
        ),
    )


@router.post("/face/enroll", response_model=FaceEnrollmentResponse)
async def enroll_face(
    request: FaceEnrollmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Enroll a staff member's face ID with enhanced security"""
    service = BiometricService(db)
    success, message = service.enroll_face(
        request.staff_id, request.face_data, request.device_id
    )

    if not success:
        raise HTTPException(status_code=400, detail=message)

    # Get the enrollment timestamp
    biometric = (
        db.query(StaffBiometric)
        .filter(StaffBiometric.staff_id == request.staff_id)
        .first()
    )

    return FaceEnrollmentResponse(
        success=True,
        message=message,
        enrolled_at=biometric.face_enrolled_at if biometric else datetime.utcnow(),
    )


@router.post("/biometric/check-in", response_model=BiometricCheckInResponse)
async def biometric_check_in(
    request: BiometricCheckInRequest, db: Session = Depends(get_db)
):
    """Check in using biometric (fingerprint or face) with enhanced security"""
    service = BiometricService(db)

    # Determine which biometric method to use
    if request.fingerprint_data:
        success, staff_id, message = service.verify_biometric(
            request.fingerprint_data,
            CheckInMethod.FINGERPRINT,
            request.device_id,
            request.location_lat,
            request.location_lng,
        )
        method = "fingerprint"
    elif request.face_data:
        success, staff_id, message = service.verify_biometric(
            request.face_data,
            CheckInMethod.FACE_ID,
            request.device_id,
            request.location_lat,
            request.location_lng,
        )
        method = "face"
    else:
        return BiometricCheckInResponse(
            success=False, message="No biometric data provided", method="unknown"
        )

    if success and staff_id:
        staff = db.query(StaffMember).filter(StaffMember.id == staff_id).first()
        return BiometricCheckInResponse(
            success=True,
            message=message,
            staff_id=staff_id,
            staff_name=staff.name if staff else None,
            check_in_time=datetime.utcnow(),
            method=method,
        )
    else:
        return BiometricCheckInResponse(success=False, message=message, method=method)


@router.post("/fingerprint/check-in", response_model=BiometricCheckInResponse)
async def fingerprint_check_in(
    request: BiometricCheckInRequest, db: Session = Depends(get_db)
):
    """Check in using fingerprint (legacy endpoint - redirects to biometric check-in)"""
    return await biometric_check_in(request, db)


@router.post("/face/check-in", response_model=BiometricCheckInResponse)
async def face_check_in(
    request: BiometricCheckInRequest, db: Session = Depends(get_db)
):
    """Check in using face ID (legacy endpoint - redirects to biometric check-in)"""
    return await biometric_check_in(request, db)


@router.post("/pin/setup")
async def setup_pin(
    request: PinSetupRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Set up PIN for a staff member with enhanced security"""
    service = BiometricService(db)
    success, message = service.setup_pin(request.staff_id, request.pin)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


@router.post(
    "/pin/check-in",
    response_model=BiometricCheckInResponse,
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],  # 5 attempts per minute
)
async def pin_check_in(request: PinCheckInRequest, db: Session = Depends(get_db)):
    """Check in using PIN with enhanced security"""
    service = BiometricService(db)
    success, message = service.verify_pin(
        request.staff_id,
        request.pin,
        request.device_id,
        request.location_lat,
        request.location_lng,
    )

    if success:
        staff = db.query(StaffMember).filter(StaffMember.id == request.staff_id).first()
        return BiometricCheckInResponse(
            success=True,
            message=message,
            staff_id=request.staff_id,
            staff_name=staff.name if staff else None,
            check_in_time=datetime.utcnow(),
            method="pin",
        )
    else:
        return BiometricCheckInResponse(success=False, message=message, method="pin")


@router.get("/biometric/status/{staff_id}")
async def get_biometric_status(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get biometric enrollment status for a staff member"""
    biometric = (
        db.query(StaffBiometric).filter(StaffBiometric.staff_id == staff_id).first()
    )

    if not biometric:
        return {"fingerprint_enrolled": False, "face_enrolled": False, "pin_set": False}

    return {
        "fingerprint_enrolled": biometric.is_fingerprint_enabled,
        "fingerprint_enrolled_at": biometric.fingerprint_enrolled_at,
        "face_enrolled": biometric.is_face_enabled,
        "face_enrolled_at": biometric.face_enrolled_at,
        "pin_set": biometric.is_pin_enabled,
        "pin_updated_at": biometric.pin_updated_at,
    }


@router.delete("/biometric/{staff_id}")
async def delete_biometric_data(
    staff_id: int,
    data_type: str = "all",
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete biometric data for GDPR compliance"""
    service = BiometricService(db)
    success, message = service.delete_biometric_data(staff_id, data_type)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"success": True, "message": message}


@router.get("/biometric/{staff_id}/export")
async def export_biometric_data(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Export biometric data for GDPR data portability"""
    service = BiometricService(db)
    success, data = service.export_biometric_data(staff_id)

    if not success:
        raise HTTPException(status_code=404, detail="No biometric data found")

    return data
