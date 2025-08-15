"""Custom exceptions for shift swap operations"""

from typing import Optional


class ShiftSwapException(Exception):
    """Base exception for shift swap operations"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ShiftNotFoundException(ShiftSwapException):
    """Raised when a requested shift is not found"""

    def __init__(self, shift_id: int):
        super().__init__(message=f"Shift with ID {shift_id} not found", status_code=404)


class UnauthorizedSwapException(ShiftSwapException):
    """Raised when user attempts to swap a shift they don't own"""

    def __init__(self, message: str = "You can only swap your own shifts"):
        super().__init__(message=message, status_code=403)


class InvalidSwapRequestException(ShiftSwapException):
    """Raised when swap request validation fails"""

    def __init__(self, reason: str):
        super().__init__(message=f"Invalid swap request: {reason}", status_code=400)


class SwapLimitExceededException(ShiftSwapException):
    """Raised when user exceeds monthly swap limit"""

    def __init__(self, limit: int, current_count: int):
        super().__init__(
            message=f"Monthly swap limit of {limit} exceeded (current: {current_count})",
            status_code=429,
        )


class InsufficientTenureException(ShiftSwapException):
    """Raised when user doesn't meet tenure requirements"""

    def __init__(self, required_days: int, actual_days: int):
        super().__init__(
            message=f"Insufficient tenure: {required_days} days required, you have {actual_days} days",
            status_code=403,
        )


class BlackoutPeriodException(ShiftSwapException):
    """Raised when swap is attempted during blackout period"""

    def __init__(self, date: str):
        super().__init__(
            message=f"Shift swaps are not allowed on {date} (blackout period)",
            status_code=403,
        )


class InsufficientAdvanceNoticeException(ShiftSwapException):
    """Raised when swap request doesn't meet advance notice requirements"""

    def __init__(self, required_hours: int, actual_hours: float):
        super().__init__(
            message=f"Insufficient advance notice: {required_hours} hours required, only {actual_hours:.1f} hours until shift",
            status_code=400,
        )


class PeakHoursRestrictionException(ShiftSwapException):
    """Raised when swap is attempted for peak hours shift"""

    def __init__(self):
        super().__init__(
            message="Shift swaps during peak hours require manager approval",
            status_code=403,
        )
