from modules.staff.services.staff_service import fetch_all_staff, register_staff


async def get_all_staff():
    return await fetch_all_staff()


async def create_staff(staff_data):
    return await register_staff(staff_data)
