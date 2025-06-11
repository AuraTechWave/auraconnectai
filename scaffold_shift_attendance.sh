#!/bin/bash

BASE_DIR="./backend/modules/staff"

# Create files for Shift and Attendance
mkdir -p "$BASE_DIR/models"
mkdir -p "$BASE_DIR/schemas"
mkdir -p "$BASE_DIR/routes"
mkdir -p "$BASE_DIR/controllers"
mkdir -p "$BASE_DIR/services"
mkdir -p "$BASE_DIR/tests"

# === SHIFT MODELS ===
cat > "$BASE_DIR/models/shift_models.py" <<EOF
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from backend.core.database import Base

class Shift(Base):
    __tablename__ = "shifts"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    date = Column(DateTime, nullable=False)
    location_id = Column(Integer)
EOF

# === ATTENDANCE MODELS ===
cat > "$BASE_DIR/models/attendance_models.py" <<EOF
from sqlalchemy import Column, Integer, DateTime, ForeignKey, String
from backend.core.database import Base

class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True)
    staff_id = Column(Integer, ForeignKey("staff_members.id"))
    check_in = Column(DateTime)
    check_out = Column(DateTime)
    method = Column(String)  # manual, QR, faceID
    status = Column(String)
EOF

# === SCHEMAS ===
cat > "$BASE_DIR/schemas/shift_schemas.py" <<EOF
from pydantic import BaseModel
from datetime import datetime

class ShiftBase(BaseModel):
    staff_id: int
    start_time: datetime
    end_time: datetime
    date: datetime
    location_id: int

class ShiftOut(ShiftBase):
    id: int

    class Config:
        orm_mode = True
EOF

cat > "$BASE_DIR/schemas/attendance_schemas.py" <<EOF
from pydantic import BaseModel
from datetime import datetime

class AttendanceLogBase(BaseModel):
    staff_id: int
    check_in: datetime
    check_out: datetime
    method: str
    status: str

class AttendanceLogOut(AttendanceLogBase):
    id: int

    class Config:
        orm_mode = True
EOF

# === ROUTES (basic) ===
cat > "$BASE_DIR/routes/shift_routes.py" <<EOF
from fastapi import APIRouter
from backend.modules.staff.controllers.shift_controller import assign_shift

router = APIRouter(prefix="/shifts", tags=["Shifts"])

@router.post("/")
async def create_shift(shift_data: dict):
    return await assign_shift(shift_data)
EOF

cat > "$BASE_DIR/routes/attendance_routes.py" <<EOF
from fastapi import APIRouter
from backend.modules.staff.controllers.attendance_controller import log_attendance

router = APIRouter(prefix="/attendance", tags=["Attendance"])

@router.post("/log")
async def clock_in_out(data: dict):
    return await log_attendance(data)
EOF

# === CONTROLLERS ===
cat > "$BASE_DIR/controllers/shift_controller.py" <<EOF
from backend.modules.staff.services.shift_service import create_shift

async def assign_shift(shift_data):
    return await create_shift(shift_data)
EOF

cat > "$BASE_DIR/controllers/attendance_controller.py" <<EOF
from backend.modules.staff.services.attendance_service import log_clock

async def log_attendance(data):
    return await log_clock(data)
EOF

# === SERVICES ===
cat > "$BASE_DIR/services/shift_service.py" <<EOF
async def create_shift(shift_data):
    return {"message": "Shift assigned", "data": shift_data}
EOF

cat > "$BASE_DIR/services/attendance_service.py" <<EOF
async def log_clock(data):
    return {"message": "Attendance recorded", "data": data}
EOF

# === TESTS ===
cat > "$BASE_DIR/tests/test_shift.py" <<EOF
def test_dummy_shift():
    assert True
EOF

cat > "$BASE_DIR/tests/test_attendance.py" <<EOF
def test_dummy_attendance():
    assert True
EOF

echo "✅ Shift & Attendance scaffolding complete in $BASE_DIR"
