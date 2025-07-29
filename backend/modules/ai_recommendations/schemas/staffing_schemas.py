# backend/modules/ai_recommendations/schemas/staffing_schemas.py

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from enum import Enum


class StaffRole(str, Enum):
    """Staff role categories"""
    MANAGER = "manager"
    CHEF = "chef"
    LINE_COOK = "line_cook"
    PREP_COOK = "prep_cook"
    SERVER = "server"
    HOST = "host"
    BARTENDER = "bartender"
    BUSSER = "busser"
    DISHWASHER = "dishwasher"
    CASHIER = "cashier"
    DELIVERY = "delivery"


class ShiftType(str, Enum):
    """Types of shifts"""
    MORNING = "morning"
    LUNCH = "lunch"
    AFTERNOON = "afternoon"
    DINNER = "dinner"
    LATE_NIGHT = "late_night"
    FULL_DAY = "full_day"
    SPLIT = "split"


class DayOfWeek(str, Enum):
    """Days of the week"""
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


class StaffingLevel(str, Enum):
    """Staffing level categories"""
    SEVERELY_UNDERSTAFFED = "severely_understaffed"
    UNDERSTAFFED = "understaffed"
    OPTIMAL = "optimal"
    OVERSTAFFED = "overstaffed"
    SEVERELY_OVERSTAFFED = "severely_overstaffed"


class DemandForecast(BaseModel):
    """Demand forecast for a specific time period"""
    date: date
    hour: int = Field(..., ge=0, le=23)
    
    # Predicted metrics
    predicted_orders: int = Field(..., ge=0)
    predicted_revenue: Decimal = Field(..., ge=0)
    predicted_customers: int = Field(..., ge=0)
    
    # Confidence intervals
    orders_lower_bound: int
    orders_upper_bound: int
    confidence_level: float = Field(default=0.95, ge=0, le=1)
    
    # Factors
    is_holiday: bool = False
    is_special_event: bool = False
    weather_impact: float = Field(default=1.0, description="Weather impact multiplier")
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-02-01",
                "hour": 12,
                "predicted_orders": 45,
                "predicted_revenue": "675.50",
                "predicted_customers": 38,
                "orders_lower_bound": 35,
                "orders_upper_bound": 55,
                "confidence_level": 0.90
            }
        }


class StaffRequirement(BaseModel):
    """Staff requirements for a specific role and time"""
    role: StaffRole
    min_required: int = Field(..., ge=0)
    optimal: int = Field(..., ge=0)
    max_useful: int = Field(..., ge=0)
    
    # Skills/certifications required
    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)
    
    @validator('optimal')
    def validate_optimal(cls, v, values):
        if 'min_required' in values and v < values['min_required']:
            raise ValueError('optimal must be >= min_required')
        return v
    
    @validator('max_useful')
    def validate_max_useful(cls, v, values):
        if 'optimal' in values and v < values['optimal']:
            raise ValueError('max_useful must be >= optimal')
        return v


class ShiftRecommendation(BaseModel):
    """Recommended shift for staffing"""
    date: date
    start_time: time
    end_time: time
    shift_type: ShiftType
    
    # Staffing requirements by role
    staff_requirements: List[StaffRequirement]
    
    # Predicted workload
    predicted_workload: Dict[str, Any]
    peak_hours: List[int]
    
    # Cost analysis
    estimated_labor_cost: Decimal
    cost_per_order: Decimal
    labor_percentage: float = Field(..., ge=0, le=100)
    
    # Current vs recommended
    current_scheduled: Dict[StaffRole, int]
    staffing_gap: Dict[StaffRole, int]
    staffing_level: StaffingLevel
    
    # Recommendations
    priority_roles_to_fill: List[StaffRole]
    flexibility_notes: List[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "date": "2025-02-01",
                "start_time": "10:00:00",
                "end_time": "22:00:00",
                "shift_type": "full_day",
                "estimated_labor_cost": "1250.00",
                "cost_per_order": "8.50",
                "labor_percentage": 28.5,
                "staffing_level": "understaffed",
                "priority_roles_to_fill": ["server", "line_cook"]
            }
        }


class StaffingPattern(BaseModel):
    """Optimal staffing pattern for a typical period"""
    pattern_name: str
    applicable_days: List[DayOfWeek]
    applicable_dates: Optional[List[date]] = None
    
    # Hourly staff requirements
    hourly_requirements: Dict[int, Dict[StaffRole, int]]  # hour -> role -> count
    
    # Shift templates
    recommended_shifts: List[Dict[str, Any]]
    
    # Metrics
    total_labor_hours: float
    average_hourly_cost: Decimal
    expected_service_level: float = Field(..., ge=0, le=1)
    
    # Flexibility
    min_staff_threshold: Dict[StaffRole, int]
    surge_capacity: Dict[StaffRole, int]
    
    class Config:
        json_schema_extra = {
            "example": {
                "pattern_name": "Weekday Standard",
                "applicable_days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                "total_labor_hours": 120.0,
                "average_hourly_cost": "18.50",
                "expected_service_level": 0.95
            }
        }


class StaffingOptimizationRequest(BaseModel):
    """Request for staffing optimization"""
    start_date: date
    end_date: date
    
    # Optimization goals
    primary_goal: str = Field(default="minimize_cost", description="Primary optimization goal")
    service_level_target: float = Field(default=0.90, ge=0, le=1)
    
    # Constraints
    max_weekly_hours_per_staff: int = Field(default=40, ge=1, le=60)
    min_shift_length_hours: float = Field(default=4.0, ge=2.0)
    max_shift_length_hours: float = Field(default=10.0, le=12.0)
    
    # Cost constraints
    target_labor_percentage: Optional[float] = Field(None, ge=10, le=40)
    max_daily_labor_cost: Optional[Decimal] = None
    
    # Staff availability
    available_staff: Optional[Dict[int, Dict[str, Any]]] = None
    staff_preferences: Optional[Dict[int, List[str]]] = None
    
    # Special considerations
    include_breaks: bool = Field(default=True)
    account_for_training: bool = Field(default=True)
    buffer_percentage: float = Field(default=10.0, ge=0, le=30)
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        
        # Limit to 3 months
        if 'start_date' in values and (v - values['start_date']).days > 90:
            raise ValueError('Date range cannot exceed 90 days')
        
        return v


class StaffingRecommendationSet(BaseModel):
    """Complete set of staffing recommendations"""
    request_id: str
    generated_at: datetime
    period_start: date
    period_end: date
    
    # Daily recommendations
    daily_recommendations: List[ShiftRecommendation]
    
    # Patterns identified
    patterns_identified: List[StaffingPattern]
    
    # Summary metrics
    total_recommended_hours: float
    total_estimated_cost: Decimal
    average_labor_percentage: float
    expected_service_level: float
    
    # Optimization results
    cost_savings_vs_current: Optional[Decimal] = None
    efficiency_improvement: Optional[float] = None
    
    # Risk analysis
    understaffing_risks: List[Dict[str, Any]]
    overstaffing_risks: List[Dict[str, Any]]
    
    # Implementation
    implementation_priority: List[Dict[str, Any]]
    scheduling_conflicts: List[Dict[str, Any]]
    training_requirements: List[Dict[str, Any]]
    
    # Alerts and warnings
    alerts: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "request_id": "staff-opt-2025-01-29-001",
                "generated_at": "2025-01-29T10:00:00Z",
                "period_start": "2025-02-01",
                "period_end": "2025-02-07",
                "total_recommended_hours": 840.0,
                "total_estimated_cost": "15750.00",
                "average_labor_percentage": 26.5,
                "expected_service_level": 0.93
            }
        }


class StaffPerformanceMetrics(BaseModel):
    """Performance metrics for staff optimization"""
    staff_id: int
    role: StaffRole
    
    # Productivity metrics
    orders_per_hour: float
    revenue_per_hour: Decimal
    tables_per_hour: Optional[float] = None
    
    # Quality metrics
    customer_satisfaction: Optional[float] = Field(None, ge=1, le=5)
    error_rate: float = Field(..., ge=0, le=1)
    
    # Availability
    availability_score: float = Field(..., ge=0, le=1)
    reliability_score: float = Field(..., ge=0, le=1)
    
    # Cost
    hourly_rate: Decimal
    overtime_rate: Decimal
    
    # Skills and experience
    skill_level: int = Field(..., ge=1, le=5)
    certifications: List[str] = Field(default_factory=list)
    cross_trained_roles: List[StaffRole] = Field(default_factory=list)


class ScheduleOptimizationResult(BaseModel):
    """Result of schedule optimization"""
    schedule_id: str
    optimization_status: str
    
    # Proposed schedule
    proposed_shifts: List[Dict[str, Any]]
    
    # Metrics comparison
    current_metrics: Dict[str, Any]
    proposed_metrics: Dict[str, Any]
    improvements: Dict[str, float]
    
    # Staff assignments
    staff_assignments: Dict[int, List[Dict[str, Any]]]
    
    # Compliance
    labor_law_compliant: bool
    break_requirements_met: bool
    overtime_minimized: bool
    
    # Implementation readiness
    can_auto_apply: bool
    manual_adjustments_needed: List[str]
    approval_required_from: List[str]


class LaborCostAnalysis(BaseModel):
    """Detailed labor cost analysis"""
    period: str
    total_hours: float
    total_cost: Decimal
    
    # Breakdown by role
    cost_by_role: Dict[StaffRole, Decimal]
    hours_by_role: Dict[StaffRole, float]
    
    # Efficiency metrics
    revenue_per_labor_hour: Decimal
    orders_per_labor_hour: float
    labor_cost_percentage: float
    
    # Overtime analysis
    regular_hours: float
    overtime_hours: float
    overtime_cost: Decimal
    
    # Comparisons
    vs_budget: Optional[float] = None
    vs_last_period: Optional[float] = None
    vs_industry_benchmark: Optional[float] = None
    
    # Recommendations
    optimization_opportunities: List[Dict[str, Any]]
    estimated_savings: Optional[Decimal] = None