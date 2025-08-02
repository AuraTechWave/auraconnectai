from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FingerprintEnrollmentRequest(BaseModel):
    staff_id: int
    fingerprint_data: str  # Base64 encoded fingerprint template
    device_id: str
    
    
class FingerprintEnrollmentResponse(BaseModel):
    success: bool
    message: str
    enrolled_at: Optional[datetime]
    

class FaceEnrollmentRequest(BaseModel):
    staff_id: int
    face_data: str  # Base64 encoded face template/embeddings
    device_id: str
    

class FaceEnrollmentResponse(BaseModel):
    success: bool
    message: str
    enrolled_at: Optional[datetime]
    

class BiometricCheckInRequest(BaseModel):
    fingerprint_data: Optional[str] = None  # Base64 encoded fingerprint template
    face_data: Optional[str] = None  # Base64 encoded face template
    device_id: str
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    

class BiometricCheckInResponse(BaseModel):
    success: bool
    message: str
    staff_id: Optional[int]
    staff_name: Optional[str]
    check_in_time: Optional[datetime]
    method: str
    

class PinSetupRequest(BaseModel):
    staff_id: int
    pin: str = Field(..., min_length=4, max_length=6, regex="^[0-9]+$")
    

class PinCheckInRequest(BaseModel):
    staff_id: int
    pin: str
    device_id: str
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None