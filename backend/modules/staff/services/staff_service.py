async def fetch_all_staff():
    return {"message": "List of staff members"}


async def register_staff(staff_data):
    return {"message": "Staff created", "data": staff_data}
