from fastapi import APIRouter
from backend.modules.staff.controllers.shift_controller import assign_shift

router = APIRouter(prefix="/shifts", tags=["Shifts"])

@router.post("/")
async def create_shift(shift_data: dict):
    return await assign_shift(shift_data)
