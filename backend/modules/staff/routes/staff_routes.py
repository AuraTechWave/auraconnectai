from fastapi import APIRouter
from backend.modules.staff.controllers.staff_controller import (
    get_all_staff,
    create_staff,
)

router = APIRouter(prefix="/staff", tags=["Staff"])


@router.get("/members")
async def list_staff():
    return await get_all_staff()


@router.post("/members")
async def add_staff(staff_data: dict):
    return await create_staff(staff_data)
