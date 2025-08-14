"""Factory patterns for creating test fixtures"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass, field
from modules.staff.models.scheduling_models import (
    ShiftSwap, EnhancedShift, SwapApprovalRule
)
from modules.staff.models.staff_models import StaffMember, Role
from modules.staff.enums.scheduling_enums import (
    ShiftStatus, SwapStatus, ShiftType
)
from modules.core.models import Restaurant, Location


@dataclass
class RestaurantFactory:
    """Factory for creating test restaurants"""
    id: int = 1
    name: str = "Test Restaurant"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def create(self) -> Restaurant:
        return Restaurant(
            id=self.id,
            name=self.name,
            created_at=self.created_at
        )


@dataclass
class LocationFactory:
    """Factory for creating test locations"""
    id: int = 1
    name: str = "Main Location"
    restaurant_id: int = 1
    restaurant: Optional[Restaurant] = None
    
    def create(self) -> Location:
        return Location(
            id=self.id,
            name=self.name,
            restaurant_id=self.restaurant_id,
            restaurant=self.restaurant
        )


@dataclass
class RoleFactory:
    """Factory for creating test roles"""
    id: int = 1
    name: str = "Server"
    restaurant_id: int = 1
    
    def create(self) -> Role:
        return Role(
            id=self.id,
            name=self.name,
            restaurant_id=self.restaurant_id
        )


@dataclass
class StaffMemberFactory:
    """Factory for creating test staff members"""
    id: int = 1
    name: str = "John Doe"
    role_id: int = 1
    role: Optional[Role] = None
    restaurant_id: int = 1
    tenure_days: int = 120
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc) - timedelta(days=self.tenure_days)
    
    def create(self) -> StaffMember:
        return StaffMember(
            id=self.id,
            name=self.name,
            role_id=self.role_id,
            role=self.role,
            restaurant_id=self.restaurant_id,
            created_at=self.created_at
        )
    
    @classmethod
    def create_batch(cls, count: int, base_id: int = 1, **kwargs) -> list:
        """Create multiple staff members"""
        staff_members = []
        for i in range(count):
            factory = cls(
                id=base_id + i,
                name=f"Staff {base_id + i}",
                **kwargs
            )
            staff_members.append(factory.create())
        return staff_members


@dataclass
class ShiftFactory:
    """Factory for creating test shifts"""
    id: int = 1
    staff_id: int = 1
    staff_member: Optional[StaffMember] = None
    role_id: int = 1
    role: Optional[Role] = None
    location_id: int = 1
    location: Optional[Location] = None
    days_from_now: int = 1
    start_hour: int = 9
    end_hour: int = 17
    shift_type: ShiftType = ShiftType.REGULAR
    status: ShiftStatus = ShiftStatus.SCHEDULED
    
    def create(self) -> EnhancedShift:
        shift_date = datetime.now(timezone.utc) + timedelta(days=self.days_from_now)
        return EnhancedShift(
            id=self.id,
            staff_id=self.staff_id,
            staff_member=self.staff_member,
            role_id=self.role_id,
            role=self.role,
            location_id=self.location_id,
            location=self.location,
            date=shift_date.date(),
            start_time=shift_date.replace(hour=self.start_hour, minute=0),
            end_time=shift_date.replace(hour=self.end_hour, minute=0),
            shift_type=self.shift_type,
            status=self.status
        )
    
    @classmethod
    def create_pair(cls, staff1: StaffMember, staff2: StaffMember, 
                   location: Location, role: Role) -> tuple:
        """Create a pair of shifts for swapping"""
        shift1 = cls(
            id=1,
            staff_id=staff1.id,
            staff_member=staff1,
            role_id=role.id,
            role=role,
            location_id=location.id,
            location=location
        ).create()
        
        shift2 = cls(
            id=2,
            staff_id=staff2.id,
            staff_member=staff2,
            role_id=role.id,
            role=role,
            location_id=location.id,
            location=location
        ).create()
        
        return shift1, shift2


@dataclass
class SwapApprovalRuleFactory:
    """Factory for creating swap approval rules"""
    id: int = 1
    restaurant_id: int = 1
    rule_name: str = "Default Rule"
    is_active: bool = True
    priority: int = 1
    max_hours_difference: Optional[float] = 2.0
    same_role_required: bool = True
    same_location_required: bool = True
    min_advance_notice_hours: int = 24
    max_advance_notice_hours: Optional[int] = None
    min_tenure_days: int = 90
    max_swaps_per_month: int = 3
    no_recent_violations: bool = True
    performance_rating_min: Optional[float] = None
    blackout_dates: list = field(default_factory=list)
    restricted_shifts: list = field(default_factory=list)
    peak_hours_restricted: bool = False
    peak_hour_ranges: list = field(default_factory=lambda: [(11, 14), (17, 20)])
    requires_manager_approval: bool = True
    requires_both_staff_consent: bool = True
    approval_timeout_hours: int = 48
    
    def create(self) -> SwapApprovalRule:
        rule = SwapApprovalRule(
            id=self.id,
            restaurant_id=self.restaurant_id,
            rule_name=self.rule_name,
            is_active=self.is_active,
            priority=self.priority,
            max_hours_difference=self.max_hours_difference,
            same_role_required=self.same_role_required,
            same_location_required=self.same_location_required,
            min_advance_notice_hours=self.min_advance_notice_hours,
            max_advance_notice_hours=self.max_advance_notice_hours,
            min_tenure_days=self.min_tenure_days,
            max_swaps_per_month=self.max_swaps_per_month,
            no_recent_violations=self.no_recent_violations,
            performance_rating_min=self.performance_rating_min,
            blackout_dates=self.blackout_dates,
            restricted_shifts=self.restricted_shifts,
            peak_hours_restricted=self.peak_hours_restricted,
            requires_manager_approval=self.requires_manager_approval,
            requires_both_staff_consent=self.requires_both_staff_consent,
            approval_timeout_hours=self.approval_timeout_hours
        )
        # Add peak_hour_ranges as a custom attribute
        rule.peak_hour_ranges = self.peak_hour_ranges
        return rule


@dataclass
class ShiftSwapFactory:
    """Factory for creating shift swap requests"""
    id: int = 1
    requester_id: int = 1
    requester: Optional[StaffMember] = None
    from_shift_id: int = 1
    from_shift: Optional[EnhancedShift] = None
    to_shift_id: Optional[int] = None
    to_shift: Optional[EnhancedShift] = None
    to_staff_id: Optional[int] = None
    to_staff: Optional[StaffMember] = None
    status: SwapStatus = SwapStatus.PENDING
    reason: Optional[str] = "Personal commitment"
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
    
    def create(self) -> ShiftSwap:
        return ShiftSwap(
            id=self.id,
            requester_id=self.requester_id,
            requester=self.requester,
            from_shift_id=self.from_shift_id,
            from_shift=self.from_shift,
            to_shift_id=self.to_shift_id,
            to_shift=self.to_shift,
            to_staff_id=self.to_staff_id,
            to_staff=self.to_staff,
            status=self.status,
            reason=self.reason,
            created_at=self.created_at
        )