import hashlib
import secrets
import base64
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict
from sqlalchemy.orm import Session
import logging
import json

from ..models.staff_models import StaffMember
from ..models.biometric_models import StaffBiometric
from ..models.attendance_models import AttendanceLog
from ..enums.attendance_enums import CheckInMethod, AttendanceStatus

logger = logging.getLogger(__name__)

# GDPR compliance settings
BIOMETRIC_RETENTION_DAYS = 730  # 2 years default retention
AUDIT_LOG_RETENTION_DAYS = 2555  # 7 years for audit logs


class BiometricService:
    """Service for handling biometric authentication with enhanced security"""
    
    def __init__(self, db: Session):
        self.db = db
        self._salt_length = 32  # 256 bits
    
    def _generate_salt(self) -> str:
        """Generate a cryptographically secure salt"""
        return secrets.token_hex(self._salt_length)
    
    def _hash_biometric_with_salt(self, biometric_data: str, salt: str) -> str:
        """Create a salted hash of biometric data"""
        # Combine biometric data with salt
        salted_data = f"{biometric_data}{salt}".encode()
        
        # Use SHA-256 with multiple rounds for added security
        hash_rounds = 10000  # PBKDF2-like approach
        current_hash = salted_data
        
        for _ in range(hash_rounds):
            current_hash = hashlib.sha256(current_hash).digest()
        
        return current_hash.hex()
    
    def enroll_fingerprint(
        self, 
        staff_id: int, 
        fingerprint_data: str, 
        device_id: str
    ) -> Tuple[bool, str]:
        """Enroll a staff member's fingerprint with enhanced security"""
        try:
            # Verify staff exists
            staff = self.db.query(StaffMember).filter(
                StaffMember.id == staff_id
            ).first()
            
            if not staff:
                return False, "Staff member not found"
            
            # Get or create biometric record
            biometric = self.db.query(StaffBiometric).filter(
                StaffBiometric.staff_id == staff_id
            ).first()
            
            if not biometric:
                biometric = StaffBiometric(
                    staff_id=staff_id,
                    created_at=datetime.utcnow()
                )
                self.db.add(biometric)
            
            # Generate salt for this fingerprint
            fingerprint_salt = self._generate_salt()
            
            # Create salted hash
            fingerprint_hash = self._hash_biometric_with_salt(
                fingerprint_data, 
                fingerprint_salt
            )
            
            # Store encrypted template with salt embedded
            encrypted_template = base64.b64decode(fingerprint_data)
            
            # Combine salt with template for storage
            template_with_salt = fingerprint_salt.encode() + b'|' + encrypted_template
            
            # Update biometric record
            biometric.fingerprint_template = template_with_salt
            biometric.fingerprint_hash = fingerprint_hash
            biometric.fingerprint_hash_prefix = fingerprint_hash[:8]  # Store prefix for faster lookup
            biometric.fingerprint_enrolled_at = datetime.utcnow()
            biometric.is_fingerprint_enabled = True
            biometric.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"Fingerprint enrolled successfully for staff_id: {staff_id}")
            return True, f"Fingerprint enrolled successfully for {staff.name}"
            
        except Exception as e:
            logger.error(f"Error enrolling fingerprint: {str(e)}")
            self.db.rollback()
            return False, "Failed to enroll fingerprint"
    
    def enroll_face(
        self, 
        staff_id: int, 
        face_data: str, 
        device_id: str
    ) -> Tuple[bool, str]:
        """Enroll a staff member's face ID with enhanced security"""
        try:
            # Verify staff exists
            staff = self.db.query(StaffMember).filter(
                StaffMember.id == staff_id
            ).first()
            
            if not staff:
                return False, "Staff member not found"
            
            # Get or create biometric record
            biometric = self.db.query(StaffBiometric).filter(
                StaffBiometric.staff_id == staff_id
            ).first()
            
            if not biometric:
                biometric = StaffBiometric(
                    staff_id=staff_id,
                    created_at=datetime.utcnow()
                )
                self.db.add(biometric)
            
            # Generate salt for face data
            face_salt = self._generate_salt()
            
            # Create salted hash
            face_hash = self._hash_biometric_with_salt(face_data, face_salt)
            
            # Store encrypted template with salt
            encrypted_template = base64.b64decode(face_data)
            template_with_salt = face_salt.encode() + b'|' + encrypted_template
            
            # Update biometric record
            biometric.face_template = template_with_salt
            biometric.face_hash = face_hash
            biometric.face_hash_prefix = face_hash[:8]  # Store prefix for faster lookup
            biometric.face_enrolled_at = datetime.utcnow()
            biometric.is_face_enabled = True
            biometric.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            logger.info(f"Face ID enrolled successfully for staff_id: {staff_id}")
            return True, f"Face ID enrolled successfully for {staff.name}"
            
        except Exception as e:
            logger.error(f"Error enrolling face ID: {str(e)}")
            self.db.rollback()
            return False, "Failed to enroll face ID"
    
    def verify_biometric(
        self,
        biometric_data: str,
        method: CheckInMethod,
        device_id: str,
        location_lat: Optional[float] = None,
        location_lng: Optional[float] = None
    ) -> Tuple[bool, Optional[int], str]:
        """Verify biometric data and process check-in/out"""
        try:
            # Calculate hash prefix for faster lookup
            test_hash = self._hash_biometric_with_salt(biometric_data, "")  # Temporary hash for prefix
            hash_prefix = test_hash[:8]
            
            # Query biometric records with matching hash prefix first
            if method == CheckInMethod.FINGERPRINT:
                biometrics = self.db.query(StaffBiometric).filter(
                    StaffBiometric.is_fingerprint_enabled == True,
                    StaffBiometric.fingerprint_hash_prefix == hash_prefix
                ).all()
                # Fallback to all records if no prefix match (for legacy data)
                if not biometrics:
                    biometrics = self.db.query(StaffBiometric).filter(
                        StaffBiometric.is_fingerprint_enabled == True,
                        StaffBiometric.fingerprint_hash_prefix.is_(None)
                    ).all()
            elif method == CheckInMethod.FACE_ID:
                biometrics = self.db.query(StaffBiometric).filter(
                    StaffBiometric.is_face_enabled == True,
                    StaffBiometric.face_hash_prefix == hash_prefix
                ).all()
                # Fallback to all records if no prefix match (for legacy data)
                if not biometrics:
                    biometrics = self.db.query(StaffBiometric).filter(
                        StaffBiometric.is_face_enabled == True,
                        StaffBiometric.face_hash_prefix.is_(None)
                    ).all()
            else:
                return False, None, "Invalid biometric method"
            
            # Check each biometric record
            for biometric in biometrics:
                if method == CheckInMethod.FINGERPRINT:
                    stored_template = biometric.fingerprint_template
                    stored_hash = biometric.fingerprint_hash
                else:
                    stored_template = biometric.face_template
                    stored_hash = biometric.face_hash
                
                if not stored_template:
                    continue
                
                # Extract salt from stored template
                try:
                    salt_bytes, template_bytes = stored_template.split(b'|', 1)
                    salt = salt_bytes.decode()
                except:
                    # Handle legacy data without salt
                    logger.warning(f"Legacy biometric data found for staff_id: {biometric.staff_id}")
                    continue
                
                # Hash the provided data with the same salt
                test_hash = self._hash_biometric_with_salt(biometric_data, salt)
                
                # Compare hashes
                if test_hash == stored_hash:
                    # Match found - process check-in/out
                    staff_id = biometric.staff_id
                    success, message = self._process_attendance(
                        staff_id, method, device_id, location_lat, location_lng
                    )
                    return success, staff_id, message
            
            return False, None, "Biometric not recognized"
            
        except Exception as e:
            logger.error(f"Error verifying biometric: {str(e)}")
            return False, None, "Verification failed"
    
    def _process_attendance(
        self,
        staff_id: int,
        method: CheckInMethod,
        device_id: str,
        location_lat: Optional[float],
        location_lng: Optional[float]
    ) -> Tuple[bool, str]:
        """Process attendance check-in/out"""
        try:
            # Get staff member
            staff = self.db.query(StaffMember).filter(
                StaffMember.id == staff_id
            ).first()
            
            if not staff:
                return False, "Staff member not found"
            
            # Check for existing open attendance
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            open_attendance = self.db.query(AttendanceLog).filter(
                AttendanceLog.staff_id == staff_id,
                AttendanceLog.check_in >= today_start,
                AttendanceLog.check_out.is_(None)
            ).first()
            
            if open_attendance:
                # This is a check-out
                open_attendance.check_out = datetime.utcnow()
                open_attendance.status = AttendanceStatus.CHECKED_OUT
                message = f"{staff.name} checked out successfully"
            else:
                # This is a check-in
                new_log = AttendanceLog(
                    staff_id=staff_id,
                    check_in=datetime.utcnow(),
                    method=method,
                    status=AttendanceStatus.CHECKED_IN,
                    device_id=device_id,
                    location_lat=location_lat,
                    location_lng=location_lng
                )
                self.db.add(new_log)
                message = f"{staff.name} checked in successfully"
            
            self.db.commit()
            return True, message
            
        except Exception as e:
            logger.error(f"Error processing attendance: {str(e)}")
            self.db.rollback()
            return False, "Failed to process attendance"
    
    def setup_pin(self, staff_id: int, pin: str) -> Tuple[bool, str]:
        """Set up PIN for a staff member"""
        try:
            # Verify staff exists
            staff = self.db.query(StaffMember).filter(
                StaffMember.id == staff_id
            ).first()
            
            if not staff:
                return False, "Staff member not found"
            
            # Get or create biometric record
            biometric = self.db.query(StaffBiometric).filter(
                StaffBiometric.staff_id == staff_id
            ).first()
            
            if not biometric:
                biometric = StaffBiometric(
                    staff_id=staff_id,
                    created_at=datetime.utcnow()
                )
                self.db.add(biometric)
            
            # Generate salt for PIN
            pin_salt = self._generate_salt()
            
            # Hash PIN with salt
            pin_hash = self._hash_biometric_with_salt(pin, pin_salt)
            
            # Store hash with embedded salt
            biometric.pin_hash = f"{pin_salt}:{pin_hash}"
            biometric.pin_updated_at = datetime.utcnow()
            biometric.is_pin_enabled = True
            biometric.updated_at = datetime.utcnow()
            
            self.db.commit()
            
            return True, "PIN set successfully"
            
        except Exception as e:
            logger.error(f"Error setting up PIN: {str(e)}")
            self.db.rollback()
            return False, "Failed to set up PIN"
    
    def verify_pin(
        self,
        staff_id: int,
        pin: str,
        device_id: str,
        location_lat: Optional[float] = None,
        location_lng: Optional[float] = None
    ) -> Tuple[bool, str]:
        """Verify PIN and process check-in/out"""
        try:
            # Get biometric record
            biometric = self.db.query(StaffBiometric).filter(
                StaffBiometric.staff_id == staff_id,
                StaffBiometric.is_pin_enabled == True
            ).first()
            
            if not biometric or not biometric.pin_hash:
                return False, "PIN not set up for this staff member"
            
            # Extract salt and hash
            try:
                salt, stored_hash = biometric.pin_hash.split(':', 1)
            except:
                # Handle legacy format
                return False, "Invalid PIN format"
            
            # Hash provided PIN with same salt
            test_hash = self._hash_biometric_with_salt(pin, salt)
            
            if test_hash != stored_hash:
                return False, "Invalid PIN"
            
            # Process attendance
            success, message = self._process_attendance(
                staff_id, CheckInMethod.PIN, device_id, location_lat, location_lng
            )
            
            return success, message
            
        except Exception as e:
            logger.error(f"Error verifying PIN: {str(e)}")
            return False, "PIN verification failed"
    
    def delete_biometric_data(self, staff_id: int, data_type: str = "all") -> Tuple[bool, str]:
        """Delete biometric data for GDPR compliance"""
        try:
            biometric = self.db.query(StaffBiometric).filter(
                StaffBiometric.staff_id == staff_id
            ).first()
            
            if not biometric:
                return False, "No biometric data found"
            
            # Log the deletion for audit trail
            self._audit_log("biometric_deletion", {
                "staff_id": staff_id,
                "data_type": data_type,
                "deleted_at": datetime.utcnow().isoformat()
            })
            
            if data_type == "all":
                self.db.delete(biometric)
            elif data_type == "fingerprint":
                biometric.fingerprint_template = None
                biometric.fingerprint_hash = None
                biometric.fingerprint_enrolled_at = None
                biometric.is_fingerprint_enabled = False
            elif data_type == "face":
                biometric.face_template = None
                biometric.face_hash = None
                biometric.face_enrolled_at = None
                biometric.is_face_enabled = False
            elif data_type == "pin":
                biometric.pin_hash = None
                biometric.pin_updated_at = None
                biometric.is_pin_enabled = False
            
            self.db.commit()
            return True, f"Biometric data ({data_type}) deleted successfully"
            
        except Exception as e:
            logger.error(f"Error deleting biometric data: {str(e)}")
            self.db.rollback()
            return False, "Failed to delete biometric data"
    
    def export_biometric_data(self, staff_id: int) -> Tuple[bool, Optional[Dict]]:
        """Export biometric data for GDPR data portability"""
        try:
            biometric = self.db.query(StaffBiometric).filter(
                StaffBiometric.staff_id == staff_id
            ).first()
            
            if not biometric:
                return False, None
            
            # Export only metadata, not actual biometric templates
            export_data = {
                "staff_id": staff_id,
                "biometric_data": {
                    "fingerprint_enrolled": biometric.is_fingerprint_enabled,
                    "fingerprint_enrolled_at": biometric.fingerprint_enrolled_at.isoformat() if biometric.fingerprint_enrolled_at else None,
                    "face_enrolled": biometric.is_face_enabled,
                    "face_enrolled_at": biometric.face_enrolled_at.isoformat() if biometric.face_enrolled_at else None,
                    "pin_enabled": biometric.is_pin_enabled,
                    "pin_updated_at": biometric.pin_updated_at.isoformat() if biometric.pin_updated_at else None,
                },
                "created_at": biometric.created_at.isoformat(),
                "updated_at": biometric.updated_at.isoformat(),
                "export_date": datetime.utcnow().isoformat()
            }
            
            # Log the export
            self._audit_log("biometric_export", {
                "staff_id": staff_id,
                "exported_at": datetime.utcnow().isoformat()
            })
            
            return True, export_data
            
        except Exception as e:
            logger.error(f"Error exporting biometric data: {str(e)}")
            return False, None
    
    def cleanup_expired_data(self) -> Tuple[int, int]:
        """Clean up expired biometric data based on retention policy"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=BIOMETRIC_RETENTION_DAYS)
            
            # Find expired biometric records
            expired_biometrics = self.db.query(StaffBiometric).filter(
                StaffBiometric.updated_at < cutoff_date
            ).all()
            
            biometric_count = len(expired_biometrics)
            
            # Delete expired biometrics
            for biometric in expired_biometrics:
                self._audit_log("biometric_auto_deletion", {
                    "staff_id": biometric.staff_id,
                    "reason": "retention_policy",
                    "last_updated": biometric.updated_at.isoformat()
                })
                self.db.delete(biometric)
            
            # Clean up old audit logs
            audit_cutoff = datetime.utcnow() - timedelta(days=AUDIT_LOG_RETENTION_DAYS)
            # This would need a separate audit log table implementation
            audit_count = 0
            
            self.db.commit()
            return biometric_count, audit_count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired data: {str(e)}")
            self.db.rollback()
            return 0, 0
    
    def _audit_log(self, action: str, details: Dict):
        """Create audit log entry for GDPR compliance"""
        # This would write to a separate audit log table
        # For now, just log to application logs
        logger.info(f"BIOMETRIC_AUDIT: {action} - {json.dumps(details)}")