import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.database import Base
from modules.staff.models.staff_models import StaffMember, Role
from modules.staff.models.biometric_models import StaffBiometric
from modules.staff.models.attendance_models import AttendanceLog
from modules.staff.services.biometric_service import BiometricService
from modules.staff.enums.staff_enums import StaffStatus
from modules.staff.enums.attendance_enums import CheckInMethod, AttendanceStatus


@pytest.fixture
def test_db():
    """Create a test database session"""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestSessionLocal()

    yield db

    db.close()


@pytest.fixture
def test_staff(test_db):
    """Create test staff members"""
    # Create a role
    role = Role(id=1, name="Server", permissions="basic")
    test_db.add(role)

    # Create staff members
    staff1 = StaffMember(
        id=1,
        name="John Doe",
        email="john@example.com",
        role_id=1,
        status=StaffStatus.ACTIVE,
    )
    staff2 = StaffMember(
        id=2,
        name="Jane Smith",
        email="jane@example.com",
        role_id=1,
        status=StaffStatus.ACTIVE,
    )

    test_db.add(staff1)
    test_db.add(staff2)
    test_db.commit()

    return [staff1, staff2]


class TestBiometricService:
    """Test cases for biometric service"""

    def test_fingerprint_enrollment(self, test_db, test_staff):
        """Test fingerprint enrollment with salted hashing"""
        service = BiometricService(test_db)

        # Test successful enrollment
        fingerprint_data = "base64_encoded_fingerprint_template"
        success, message = service.enroll_fingerprint(
            staff_id=1, fingerprint_data=fingerprint_data, device_id="TEST-001"
        )

        assert success is True
        assert "successfully" in message

        # Check that biometric record was created
        biometric = (
            test_db.query(StaffBiometric).filter(StaffBiometric.staff_id == 1).first()
        )

        assert biometric is not None
        assert biometric.is_fingerprint_enabled is True
        assert biometric.fingerprint_hash is not None
        assert biometric.fingerprint_template is not None
        assert biometric.fingerprint_enrolled_at is not None

        # Verify salt is embedded in template
        assert b"|" in biometric.fingerprint_template

    def test_fingerprint_enrollment_nonexistent_staff(self, test_db):
        """Test fingerprint enrollment for non-existent staff"""
        service = BiometricService(test_db)

        success, message = service.enroll_fingerprint(
            staff_id=999, fingerprint_data="test_data", device_id="TEST-001"
        )

        assert success is False
        assert "not found" in message

    def test_face_enrollment(self, test_db, test_staff):
        """Test face ID enrollment with salted hashing"""
        service = BiometricService(test_db)

        # Test successful enrollment
        face_data = "base64_encoded_face_embeddings"
        success, message = service.enroll_face(
            staff_id=2, face_data=face_data, device_id="TEST-002"
        )

        assert success is True
        assert "successfully" in message

        # Check that biometric record was created
        biometric = (
            test_db.query(StaffBiometric).filter(StaffBiometric.staff_id == 2).first()
        )

        assert biometric is not None
        assert biometric.is_face_enabled is True
        assert biometric.face_hash is not None
        assert biometric.face_template is not None
        assert biometric.face_enrolled_at is not None

    def test_pin_setup(self, test_db, test_staff):
        """Test PIN setup with salted hashing"""
        service = BiometricService(test_db)

        # Test successful PIN setup
        success, message = service.setup_pin(staff_id=1, pin="1234")

        assert success is True
        assert "successfully" in message

        # Check that PIN was stored with salt
        biometric = (
            test_db.query(StaffBiometric).filter(StaffBiometric.staff_id == 1).first()
        )

        assert biometric is not None
        assert biometric.is_pin_enabled is True
        assert biometric.pin_hash is not None
        assert ":" in biometric.pin_hash  # Salt separator
        assert biometric.pin_updated_at is not None

    def test_biometric_verification_and_checkin(self, test_db, test_staff):
        """Test biometric verification and attendance check-in"""
        service = BiometricService(test_db)

        # First enroll fingerprint
        fingerprint_data = "test_fingerprint_data"
        service.enroll_fingerprint(1, fingerprint_data, "TEST-001")

        # Test verification and check-in
        success, staff_id, message = service.verify_biometric(
            biometric_data=fingerprint_data,
            method=CheckInMethod.FINGERPRINT,
            device_id="TEST-001",
            location_lat=40.7128,
            location_lng=-74.0060,
        )

        assert success is True
        assert staff_id == 1
        assert "checked in" in message

        # Verify attendance log was created
        attendance = (
            test_db.query(AttendanceLog).filter(AttendanceLog.staff_id == 1).first()
        )

        assert attendance is not None
        assert attendance.method == CheckInMethod.FINGERPRINT
        assert attendance.status == AttendanceStatus.CHECKED_IN
        assert attendance.check_in is not None
        assert attendance.check_out is None
        assert attendance.location_lat == 40.7128
        assert attendance.location_lng == -74.0060

    def test_biometric_checkout(self, test_db, test_staff):
        """Test biometric check-out"""
        service = BiometricService(test_db)

        # Enroll and check in first
        fingerprint_data = "test_fingerprint_data"
        service.enroll_fingerprint(1, fingerprint_data, "TEST-001")
        service.verify_biometric(
            fingerprint_data, CheckInMethod.FINGERPRINT, "TEST-001"
        )

        # Now test check-out
        success, staff_id, message = service.verify_biometric(
            biometric_data=fingerprint_data,
            method=CheckInMethod.FINGERPRINT,
            device_id="TEST-001",
        )

        assert success is True
        assert staff_id == 1
        assert "checked out" in message

        # Verify attendance log was updated
        attendance = (
            test_db.query(AttendanceLog).filter(AttendanceLog.staff_id == 1).first()
        )

        assert attendance is not None
        assert attendance.status == AttendanceStatus.CHECKED_OUT
        assert attendance.check_out is not None

    def test_pin_verification(self, test_db, test_staff):
        """Test PIN verification and check-in"""
        service = BiometricService(test_db)

        # Setup PIN
        service.setup_pin(1, "1234")

        # Test correct PIN
        success, message = service.verify_pin(
            staff_id=1, pin="1234", device_id="TEST-001"
        )

        assert success is True
        assert "checked in" in message

        # Test incorrect PIN
        success, message = service.verify_pin(
            staff_id=1, pin="0000", device_id="TEST-001"
        )

        assert success is False
        assert "Invalid PIN" in message

    def test_salt_uniqueness(self, test_db, test_staff):
        """Test that each enrollment generates unique salts"""
        service = BiometricService(test_db)

        # Enroll same fingerprint data for two different staff
        fingerprint_data = "same_fingerprint_data"
        service.enroll_fingerprint(1, fingerprint_data, "TEST-001")
        service.enroll_fingerprint(2, fingerprint_data, "TEST-002")

        # Get both biometric records
        bio1 = (
            test_db.query(StaffBiometric).filter(StaffBiometric.staff_id == 1).first()
        )
        bio2 = (
            test_db.query(StaffBiometric).filter(StaffBiometric.staff_id == 2).first()
        )

        # Extract salts
        salt1 = bio1.fingerprint_template.split(b"|")[0].decode()
        salt2 = bio2.fingerprint_template.split(b"|")[0].decode()

        # Salts should be different
        assert salt1 != salt2

        # Hashes should also be different due to different salts
        assert bio1.fingerprint_hash != bio2.fingerprint_hash

    def test_biometric_not_recognized(self, test_db, test_staff):
        """Test handling of unrecognized biometric data"""
        service = BiometricService(test_db)

        # Enroll one fingerprint
        service.enroll_fingerprint(1, "enrolled_data", "TEST-001")

        # Try to verify with different data
        success, staff_id, message = service.verify_biometric(
            biometric_data="different_data",
            method=CheckInMethod.FINGERPRINT,
            device_id="TEST-001",
        )

        assert success is False
        assert staff_id is None
        assert "not recognized" in message


@pytest.mark.asyncio
class TestBiometricAPI:
    """Test cases for biometric API endpoints"""

    async def test_fingerprint_enrollment_endpoint(self, client, test_token):
        """Test fingerprint enrollment API endpoint"""
        # This would require setting up a test client with FastAPI TestClient
        # Example structure:
        # response = client.post(
        #     "/api/v1/staff/fingerprint/enroll",
        #     json={
        #         "staff_id": 1,
        #         "fingerprint_data": "base64_data",
        #         "device_id": "TEST-001"
        #     },
        #     headers={"Authorization": f"Bearer {test_token}"}
        # )
        # assert response.status_code == 200
        # assert response.json()["success"] is True
        pass
