from modules.staff.services.attendance_service import log_clock


async def log_attendance(data):
    return await log_clock(data)
