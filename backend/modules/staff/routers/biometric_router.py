from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import hashlib
import base64

from core.database import get_db
from core.auth import verify_access_token
from ..models.staff_models import StaffMember
from ..models.biometric_models import StaffBiometric
from ..models.attendance_models import AttendanceLog
from ..schemas.biometric_schemas import (
    FingerprintEnrollmentRequest, FingerprintEnrollmentResponse,
    FaceEnrollmentRequest, FaceEnrollmentResponse,
    BiometricCheckInRequest, BiometricCheckInResponse,
    PinSetupRequest, PinCheckInRequest
)
from ..enums.attendance_enums import CheckInMethod, AttendanceStatus

router = APIRouter()


def hash_biometric(biometric_data: str) -> str:
    """Create a hash of biometric data for quick comparison"""
    return hashlib.sha256(biometric_data.encode()).hexdigest()


@router.post("/fingerprint/enroll", response_model=FingerprintEnrollmentResponse)
async def enroll_fingerprint(
    request: FingerprintEnrollmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_access_token)
):
    """Enroll a staff member's fingerprint"""
    # Check if staff member exists
    staff = db.query(StaffMember).filter(StaffMember.id == request.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Check for existing biometric record
    biometric = db.query(StaffBiometric).filter(
        StaffBiometric.staff_id == request.staff_id
    ).first()
    
    if not biometric:
        biometric = StaffBiometric(staff_id=request.staff_id)
        db.add(biometric)
    
    # Store encrypted fingerprint data
    biometric.fingerprint_template = base64.b64decode(request.fingerprint_data)
    biometric.fingerprint_hash = hash_biometric(request.fingerprint_data)
    biometric.fingerprint_enrolled_at = datetime.utcnow()
    biometric.is_fingerprint_enabled = True
    
    db.commit()
    
    return FingerprintEnrollmentResponse(
        success=True,
        message=f"Fingerprint enrolled successfully for {staff.name}",
        enrolled_at=biometric.fingerprint_enrolled_at
    )


@router.post("/face/enroll", response_model=FaceEnrollmentResponse)
async def enroll_face(
    request: FaceEnrollmentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_access_token)
):
    """Enroll a staff member's face ID"""
    # Check if staff member exists
    staff = db.query(StaffMember).filter(StaffMember.id == request.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Check for existing biometric record
    biometric = db.query(StaffBiometric).filter(
        StaffBiometric.staff_id == request.staff_id
    ).first()
    
    if not biometric:
        biometric = StaffBiometric(staff_id=request.staff_id)
        db.add(biometric)
    
    # Store encrypted face data
    biometric.face_template = base64.b64decode(request.face_data)
    biometric.face_hash = hash_biometric(request.face_data)
    biometric.face_enrolled_at = datetime.utcnow()
    biometric.is_face_enabled = True
    
    db.commit()
    
    return FaceEnrollmentResponse(
        success=True,
        message=f"Face ID enrolled successfully for {staff.name}",
        enrolled_at=biometric.face_enrolled_at
    )


@router.post("/biometric/check-in", response_model=BiometricCheckInResponse)
async def biometric_check_in(
    request: BiometricCheckInRequest,
    db: Session = Depends(get_db)
):
    """Check in using biometric (fingerprint or face)"""
    biometric = None
    method = None
    
    # Try fingerprint first if provided
    if request.fingerprint_data:
        fingerprint_hash = hash_biometric(request.fingerprint_data)
        biometric = db.query(StaffBiometric).filter(
            StaffBiometric.fingerprint_hash == fingerprint_hash,
            StaffBiometric.is_fingerprint_enabled == True
        ).first()
        method = CheckInMethod.FINGERPRINT
    
    # Try face ID if fingerprint not provided or not found
    if not biometric and request.face_data:
        face_hash = hash_biometric(request.face_data)
        biometric = db.query(StaffBiometric).filter(
            StaffBiometric.face_hash == face_hash,
            StaffBiometric.is_face_enabled == True
        ).first()
        method = CheckInMethod.FACE_ID
    
    if not biometric:
        return BiometricCheckInResponse(
            success=False,
            message="Biometric not recognized",
            method=str(method.value) if method else "unknown"
        )
    
    # Get staff member
    staff = biometric.staff_member
    
    # Check if already checked in
    today_logs = db.query(AttendanceLog).filter(
        AttendanceLog.staff_id == staff.id,
        AttendanceLog.check_in >= datetime.utcnow().replace(hour=0, minute=0, second=0),
        AttendanceLog.check_out.is_(None)
    ).first()
    
    if today_logs:
        # This is a check-out
        today_logs.check_out = datetime.utcnow()
        today_logs.status = AttendanceStatus.CHECKED_OUT
        message = f"{staff.name} checked out successfully"
    else:
        # This is a check-in
        new_log = AttendanceLog(
            staff_id=staff.id,
            check_in=datetime.utcnow(),
            method=method,
            status=AttendanceStatus.CHECKED_IN,
            device_id=request.device_id,
            location_lat=request.location_lat,
            location_lng=request.location_lng
        )
        db.add(new_log)
        message = f"{staff.name} checked in successfully"
    
    db.commit()
    
    return BiometricCheckInResponse(
        success=True,
        message=message,
        staff_id=staff.id,
        staff_name=staff.name,
        check_in_time=datetime.utcnow(),
        method=str(method.value)
    )


@router.post("/fingerprint/check-in", response_model=BiometricCheckInResponse)
async def fingerprint_check_in(
    request: BiometricCheckInRequest,
    db: Session = Depends(get_db)
):
    """Check in using fingerprint (legacy endpoint - redirects to biometric check-in)"""
    return await biometric_check_in(request, db)


@router.post("/face/check-in", response_model=BiometricCheckInResponse)
async def face_check_in(
    request: BiometricCheckInRequest,
    db: Session = Depends(get_db)
):
    """Check in using face ID (legacy endpoint - redirects to biometric check-in)"""
    return await biometric_check_in(request, db)


@router.post("/pin/setup")
async def setup_pin(
    request: PinSetupRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_access_token)
):
    """Set up PIN for a staff member"""
    # Check if staff member exists
    staff = db.query(StaffMember).filter(StaffMember.id == request.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    # Get or create biometric record
    biometric = db.query(StaffBiometric).filter(
        StaffBiometric.staff_id == request.staff_id
    ).first()
    
    if not biometric:
        biometric = StaffBiometric(staff_id=request.staff_id)
        db.add(biometric)
    
    # Hash and store PIN
    biometric.pin_hash = hashlib.sha256(request.pin.encode()).hexdigest()
    biometric.pin_updated_at = datetime.utcnow()
    biometric.is_pin_enabled = True
    
    db.commit()
    
    return {"success": True, "message": "PIN set successfully"}


@router.post("/pin/check-in", response_model=BiometricCheckInResponse)
async def pin_check_in(
    request: PinCheckInRequest,
    db: Session = Depends(get_db)
):
    """Check in using PIN"""
    # Get staff biometric record
    biometric = db.query(StaffBiometric).filter(
        StaffBiometric.staff_id == request.staff_id,
        StaffBiometric.is_pin_enabled == True
    ).first()
    
    if not biometric:
        return BiometricCheckInResponse(
            success=False,
            message="PIN not set up for this staff member",
            method="pin"
        )
    
    # Verify PIN
    pin_hash = hashlib.sha256(request.pin.encode()).hexdigest()
    if biometric.pin_hash != pin_hash:
        return BiometricCheckInResponse(
            success=False,
            message="Invalid PIN",
            method="pin"
        )
    
    # Process check-in/out (similar to fingerprint)
    staff = biometric.staff_member
    
    today_logs = db.query(AttendanceLog).filter(
        AttendanceLog.staff_id == staff.id,
        AttendanceLog.check_in >= datetime.utcnow().replace(hour=0, minute=0, second=0),
        AttendanceLog.check_out.is_(None)
    ).first()
    
    if today_logs:
        today_logs.check_out = datetime.utcnow()
        today_logs.status = AttendanceStatus.CHECKED_OUT
        message = f"{staff.name} checked out successfully"
    else:
        new_log = AttendanceLog(
            staff_id=staff.id,
            check_in=datetime.utcnow(),
            method=CheckInMethod.PIN,
            status=AttendanceStatus.CHECKED_IN,
            device_id=request.device_id,
            location_lat=request.location_lat,
            location_lng=request.location_lng
        )
        db.add(new_log)
        message = f"{staff.name} checked in successfully"
    
    db.commit()
    
    return BiometricCheckInResponse(
        success=True,
        message=message,
        staff_id=staff.id,
        staff_name=staff.name,
        check_in_time=datetime.utcnow(),
        method="pin"
    )


@router.get("/biometric/status/{staff_id}")
async def get_biometric_status(
    staff_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(verify_access_token)
):
    """Get biometric enrollment status for a staff member"""
    biometric = db.query(StaffBiometric).filter(
        StaffBiometric.staff_id == staff_id
    ).first()
    
    if not biometric:
        return {
            "fingerprint_enrolled": False,
            "face_enrolled": False,
            "pin_set": False
        }
    
    return {
        "fingerprint_enrolled": biometric.is_fingerprint_enabled,
        "fingerprint_enrolled_at": biometric.fingerprint_enrolled_at,
        "face_enrolled": biometric.is_face_enabled,
        "face_enrolled_at": biometric.face_enrolled_at,
        "pin_set": biometric.is_pin_enabled,
        "pin_updated_at": biometric.pin_updated_at
    }