from backend.modules.staff.services.shift_service import create_shift

async def assign_shift(shift_data):
    return await create_shift(shift_data)
