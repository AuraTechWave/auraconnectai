#!/bin/bash

BASE_DIR="./backend/modules/staff"

# Define folders
FOLDERS=("models" "schemas" "routes" "controllers" "services" "permissions" "utils" "enums" "tests")

# Create base folder and subfolders
mkdir -p "$BASE_DIR"
for folder in "${FOLDERS[@]}"; do
    mkdir -p "$BASE_DIR/$folder"
done

# Create __init__.py
echo "# staff module init" > "$BASE_DIR/__init__.py"

# Starter files with basic stubs
cat > "$BASE_DIR/models/staff_models.py" <<EOF
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.core.database import Base

class StaffMember(Base):
    __tablename__ = "staff_members"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    phone = Column(String)
    role_id = Column(Integer, ForeignKey("roles.id"))
    status = Column(String)
    start_date = Column(DateTime)
    photo_url = Column(String)

    role = relationship("Role", back_populates="staff_members")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    permissions = Column(String)

    staff_members = relationship("StaffMember", back_populates="role")
EOF

cat > "$BASE_DIR/schemas/staff_schemas.py" <<EOF
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class StaffBase(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    role_id: int

class StaffCreate(StaffBase):
    start_date: Optional[datetime]

class StaffOut(StaffBase):
    id: int
    status: str
    photo_url: Optional[str] = None

    class Config:
        orm_mode = True

class RoleBase(BaseModel):
    name: str
    permissions: List[str]

class RoleOut(RoleBase):
    id: int

    class Config:
        orm_mode = True
EOF

cat > "$BASE_DIR/routes/staff_routes.py" <<EOF
from fastapi import APIRouter
from backend.modules.staff.controllers.staff_controller import get_all_staff, create_staff

router = APIRouter(prefix="/staff", tags=["Staff"])

@router.get("/members")
async def list_staff():
    return await get_all_staff()

@router.post("/members")
async def add_staff(staff_data: dict):
    return await create_staff(staff_data)
EOF

cat > "$BASE_DIR/controllers/staff_controller.py" <<EOF
from backend.modules.staff.services.staff_service import fetch_all_staff, register_staff

async def get_all_staff():
    return await fetch_all_staff()

async def create_staff(staff_data):
    return await register_staff(staff_data)
EOF

cat > "$BASE_DIR/services/staff_service.py" <<EOF
async def fetch_all_staff():
    return {"message": "List of staff members"}

async def register_staff(staff_data):
    return {"message": "Staff created", "data": staff_data}
EOF

cat > "$BASE_DIR/permissions/staff_permissions.py" <<EOF
def check_permission(user, permission_key):
    permissions = user.get("permissions", [])
    return permission_key in permissions
EOF

cat > "$BASE_DIR/utils/staff_utils.py" <<EOF
def format_phone_number(phone: str) -> str:
    return phone.replace(" ", "").replace("-", "")
EOF

cat > "$BASE_DIR/enums/staff_enums.py" <<EOF
from enum import Enum

class StaffStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ON_LEAVE = "on_leave"
EOF

cat > "$BASE_DIR/tests/test_staff.py" <<EOF
def test_dummy_staff_module():
    assert True
EOF

cat > "$BASE_DIR/constants.py" <<EOF
DEFAULT_SHIFT_HOURS = 8
ALLOWED_STATUSES = ["active", "inactive", "on_leave"]
EOF

echo "✅ Staff module scaffolded at $BASE_DIR"
