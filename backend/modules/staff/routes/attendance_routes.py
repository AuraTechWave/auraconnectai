from fastapi import APIRouter
from backend.modules.staff.controllers.attendance_controller import (
    log_attendance
)

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/log")
async def clock_in_out(data: dict):
    return await log_attendance(data)
