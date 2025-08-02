from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, LargeBinary, Boolean
from sqlalchemy.orm import relationship
from core.database import Base
from datetime import datetime


class StaffBiometric(Base):
    __tablename__ = "staff_biometrics"
    
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"), unique=True, nullable=False)
    
    # Fingerprint data (encrypted)
    fingerprint_template = Column(LargeBinary)  # Encrypted fingerprint template
    fingerprint_hash = Column(String)  # Hash for quick comparison
    fingerprint_enrolled_at = Column(DateTime)
    
    # Face ID data (if needed)
    face_template = Column(LargeBinary)  # Encrypted face embeddings
    face_hash = Column(String)  # Hash for quick comparison
    face_enrolled_at = Column(DateTime)
    
    # PIN data
    pin_hash = Column(String)  # Hashed PIN
    pin_updated_at = Column(DateTime)
    
    # Security settings
    is_fingerprint_enabled = Column(Boolean, default=False)
    is_face_enabled = Column(Boolean, default=False)
    is_pin_enabled = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    staff_member = relationship("StaffMember", back_populates="biometric_data")