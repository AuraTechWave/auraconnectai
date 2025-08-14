"""Configuration for shift swap workflow"""
from typing import List, Tuple
from dataclasses import dataclass
from enum import Enum


class UrgencyLevel(str, Enum):
    URGENT = "urgent"
    NORMAL = "normal"
    FLEXIBLE = "flexible"


@dataclass
class ShiftSwapConfig:
    """Configuration for shift swap behavior"""
    
    # Response deadline hours based on urgency
    URGENT_DEADLINE_HOURS: int = 24
    NORMAL_DEADLINE_HOURS: int = 48
    FLEXIBLE_DEADLINE_HOURS: int = 72
    
    # Default peak hour ranges (start_hour, end_hour)
    DEFAULT_PEAK_HOURS: List[Tuple[int, int]] = None
    
    # Auto-approval defaults
    DEFAULT_MIN_ADVANCE_NOTICE_HOURS: int = 24
    DEFAULT_MIN_TENURE_DAYS: int = 90
    DEFAULT_MAX_SWAPS_PER_MONTH: int = 3
    
    # Notification settings
    NOTIFICATION_RETRY_ATTEMPTS: int = 3
    NOTIFICATION_RETRY_DELAY_SECONDS: int = 60
    
    def __post_init__(self):
        if self.DEFAULT_PEAK_HOURS is None:
            # Lunch and dinner rush hours
            self.DEFAULT_PEAK_HOURS = [(11, 14), (17, 20)]
    
    def get_deadline_hours(self, urgency: str) -> int:
        """Get response deadline hours based on urgency"""
        urgency_map = {
            UrgencyLevel.URGENT.value: self.URGENT_DEADLINE_HOURS,
            UrgencyLevel.NORMAL.value: self.NORMAL_DEADLINE_HOURS,
            UrgencyLevel.FLEXIBLE.value: self.FLEXIBLE_DEADLINE_HOURS
        }
        return urgency_map.get(urgency, self.NORMAL_DEADLINE_HOURS)


# Default configuration instance
shift_swap_config = ShiftSwapConfig()