# backend/modules/ai_recommendations/services/staffing_recommendation_service.py

import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date, time, timedelta
from decimal import Decimal
import statistics
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc, case

from core.cache import cache_service
from modules.analytics.utils.performance_monitor import PerformanceMonitor
from modules.analytics.services.ai_insights_service import AIInsightsService
from modules.orders.models.order_models import Order
from modules.staff.models.staff_models import StaffMember, Role
from modules.staff.models.shift_models import Shift
from modules.analytics.schemas.ai_insights_schemas import InsightRequest, InsightType

from ..schemas.staffing_schemas import (
    StaffRole, ShiftType, DayOfWeek, StaffingLevel, DemandForecast,
    StaffRequirement, ShiftRecommendation, StaffingPattern,
    StaffingOptimizationRequest, StaffingRecommendationSet,
    StaffPerformanceMetrics, LaborCostAnalysis
)

logger = logging.getLogger(__name__)


class StaffingRecommendationService:
    """Service for generating AI-powered staffing recommendations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.insights_service = AIInsightsService(db)
        self.cache_ttl = 3600  # 1 hour
        
        # Default staff-to-order ratios by role (orders per hour per staff)
        self.productivity_standards = {
            StaffRole.CHEF: 15,
            StaffRole.LINE_COOK: 20,
            StaffRole.PREP_COOK: 30,
            StaffRole.SERVER: 12,
            StaffRole.HOST: 40,
            StaffRole.BARTENDER: 15,
            StaffRole.BUSSER: 25,
            StaffRole.DISHWASHER: 35,
            StaffRole.CASHIER: 30,
            StaffRole.MANAGER: 100  # Managers handle overall operations
        }
        
        # Minimum staff requirements regardless of demand
        self.minimum_staff = {
            StaffRole.MANAGER: 1,
            StaffRole.CHEF: 1,
            StaffRole.SERVER: 2,
            StaffRole.DISHWASHER: 1
        }
    
    async def generate_staffing_recommendations(
        self,
        request: StaffingOptimizationRequest
    ) -> StaffingRecommendationSet:
        """Generate comprehensive staffing recommendations"""
        
        # Build cache key
        cache_key = f"staffing:recommendations:{hash(str(request.dict()))}"
        
        # Check cache
        if cached := await cache_service.get(cache_key):
            return StaffingRecommendationSet(**cached)
        
        # Get demand forecasts
        demand_forecasts = await self._generate_demand_forecasts(
            request.start_date,
            request.end_date
        )
        
        # Get historical patterns
        patterns = await self._identify_staffing_patterns(
            request.start_date - timedelta(days=90),
            request.start_date
        )
        
        # Generate daily recommendations
        daily_recommendations = []
        
        current_date = request.start_date
        while current_date <= request.end_date:
            try:
                daily_rec = await self._generate_daily_recommendation(
                    current_date,
                    demand_forecasts.get(current_date, []),
                    patterns,
                    request
                )
                daily_recommendations.append(daily_rec)
            except Exception as e:
                logger.error(f"Error generating recommendation for {current_date}: {e}")
            
            current_date += timedelta(days=1)
        
        # Build recommendation set
        result = self._build_recommendation_set(
            daily_recommendations,
            patterns,
            request
        )
        
        # Cache result
        await cache_service.set(cache_key, result.dict(), ttl=self.cache_ttl)
        
        return result
    
    @PerformanceMonitor.monitor_query("demand_forecast_generation")
    async def _generate_demand_forecasts(
        self,
        start_date: date,
        end_date: date
    ) -> Dict[date, List[DemandForecast]]:
        """Generate hourly demand forecasts for date range"""
        
        forecasts = defaultdict(list)
        
        # Get historical data for pattern analysis
        historical_data = self._get_historical_demand_data(
            start_date - timedelta(days=90),
            start_date
        )
        
        current_date = start_date
        while current_date <= end_date:
            # Get day of week
            dow = current_date.weekday()
            
            # Generate hourly forecasts for the day
            for hour in range(24):
                # Get historical average for this day/hour
                hist_avg = self._get_historical_average(
                    historical_data,
                    dow,
                    hour
                )
                
                # Apply trend and seasonality
                forecast = self._apply_forecast_adjustments(
                    hist_avg,
                    current_date,
                    hour
                )
                
                forecasts[current_date].append(forecast)
            
            current_date += timedelta(days=1)
        
        return dict(forecasts)
    
    def _get_historical_demand_data(
        self,
        start_date: date,
        end_date: date
    ) -> List[Dict[str, Any]]:
        """Get historical order data for analysis"""
        
        data = self.db.query(
            func.date(Order.order_date).label('date'),
            func.extract('hour', Order.order_date).label('hour'),
            func.extract('dow', Order.order_date).label('day_of_week'),
            func.count(Order.id).label('order_count'),
            func.sum(Order.total_amount).label('revenue'),
            func.count(func.distinct(Order.customer_id)).label('customer_count')
        ).filter(
            and_(
                func.date(Order.order_date) >= start_date,
                func.date(Order.order_date) <= end_date,
                Order.status.in_(['completed', 'paid'])
            )
        ).group_by(
            'date', 'hour', 'day_of_week'
        ).all()
        
        return [
            {
                'date': row.date,
                'hour': row.hour,
                'day_of_week': row.day_of_week,
                'order_count': row.order_count,
                'revenue': row.revenue,
                'customer_count': row.customer_count
            }
            for row in data
        ]
    
    def _get_historical_average(
        self,
        historical_data: List[Dict[str, Any]],
        day_of_week: int,
        hour: int
    ) -> Dict[str, float]:
        """Calculate historical averages for specific day/hour"""
        
        matching_data = [
            d for d in historical_data
            if d['day_of_week'] == day_of_week and d['hour'] == hour
        ]
        
        if not matching_data:
            return {
                'avg_orders': 0,
                'avg_revenue': 0,
                'avg_customers': 0
            }
        
        return {
            'avg_orders': statistics.mean([d['order_count'] for d in matching_data]),
            'avg_revenue': statistics.mean([float(d['revenue']) for d in matching_data]),
            'avg_customers': statistics.mean([d['customer_count'] for d in matching_data])
        }
    
    def _apply_forecast_adjustments(
        self,
        base_forecast: Dict[str, float],
        forecast_date: date,
        hour: int
    ) -> DemandForecast:
        """Apply adjustments to base forecast"""
        
        # Simple growth trend (would use time series model in production)
        growth_factor = 1.02  # 2% growth
        
        predicted_orders = int(base_forecast['avg_orders'] * growth_factor)
        predicted_revenue = Decimal(str(base_forecast['avg_revenue'] * growth_factor))
        predicted_customers = int(base_forecast['avg_customers'] * growth_factor)
        
        # Calculate confidence intervals (±20% for now)
        orders_lower = int(predicted_orders * 0.8)
        orders_upper = int(predicted_orders * 1.2)
        
        # Check for holidays/events
        is_holiday = self._is_holiday(forecast_date)
        is_special_event = self._has_special_event(forecast_date)
        
        # Adjust for special conditions
        if is_holiday:
            predicted_orders = int(predicted_orders * 1.3)
            predicted_revenue = predicted_revenue * Decimal("1.3")
            predicted_customers = int(predicted_customers * 1.3)
        
        return DemandForecast(
            date=forecast_date,
            hour=hour,
            predicted_orders=predicted_orders,
            predicted_revenue=predicted_revenue,
            predicted_customers=predicted_customers,
            orders_lower_bound=orders_lower,
            orders_upper_bound=orders_upper,
            confidence_level=0.85,
            is_holiday=is_holiday,
            is_special_event=is_special_event,
            weather_impact=1.0
        )
    
    def _is_holiday(self, check_date: date) -> bool:
        """Check if date is a holiday"""
        # Simple implementation - would use holiday calendar in production
        # Check for major US holidays
        if check_date.month == 1 and check_date.day == 1:  # New Year's
            return True
        if check_date.month == 7 and check_date.day == 4:  # July 4th
            return True
        if check_date.month == 12 and check_date.day == 25:  # Christmas
            return True
        # Add more holidays as needed
        return False
    
    def _has_special_event(self, check_date: date) -> bool:
        """Check if date has special events"""
        # Would integrate with event calendar
        return False
    
    async def _identify_staffing_patterns(
        self,
        start_date: date,
        end_date: date
    ) -> List[StaffingPattern]:
        """Identify optimal staffing patterns from historical data"""
        
        patterns = []
        
        # Analyze weekday pattern
        weekday_pattern = await self._analyze_pattern(
            start_date,
            end_date,
            [0, 1, 2, 3, 4],  # Monday-Friday
            "Weekday Standard"
        )
        if weekday_pattern:
            patterns.append(weekday_pattern)
        
        # Analyze weekend pattern
        weekend_pattern = await self._analyze_pattern(
            start_date,
            end_date,
            [5, 6],  # Saturday-Sunday
            "Weekend Standard"
        )
        if weekend_pattern:
            patterns.append(weekend_pattern)
        
        return patterns
    
    async def _analyze_pattern(
        self,
        start_date: date,
        end_date: date,
        days_of_week: List[int],
        pattern_name: str
    ) -> Optional[StaffingPattern]:
        """Analyze staffing pattern for specific days"""
        
        # Get peak times for these days
        insights_request = InsightRequest(
            insight_types=[InsightType.PEAK_TIME],
            date_from=start_date,
            date_to=end_date
        )
        
        insights = await self.insights_service.generate_insights(insights_request)
        
        if not insights.peak_times:
            return None
        
        # Build hourly requirements based on insights
        hourly_requirements = {}
        
        for hour in range(24):
            # Determine if this is a peak hour
            is_peak = (
                insights.peak_times.primary_peak and 
                insights.peak_times.primary_peak.hour == hour
            ) or (
                insights.peak_times.secondary_peak and
                insights.peak_times.secondary_peak.hour == hour
            )
            
            # Calculate staff requirements
            if is_peak:
                requirements = self._calculate_peak_requirements()
            elif hour < 10 or hour > 22:
                requirements = self._calculate_minimal_requirements()
            else:
                requirements = self._calculate_normal_requirements()
            
            hourly_requirements[hour] = requirements
        
        # Calculate totals
        total_hours = sum(
            sum(counts.values())
            for counts in hourly_requirements.values()
        )
        
        return StaffingPattern(
            pattern_name=pattern_name,
            applicable_days=[DayOfWeek(d) for d in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] if ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].index(d) in days_of_week],
            hourly_requirements=hourly_requirements,
            recommended_shifts=self._generate_shift_templates(hourly_requirements),
            total_labor_hours=total_hours,
            average_hourly_cost=Decimal("18.50"),  # Would calculate from actual rates
            expected_service_level=0.92,
            min_staff_threshold=self.minimum_staff,
            surge_capacity={role: 2 for role in StaffRole}
        )
    
    def _calculate_peak_requirements(self) -> Dict[StaffRole, int]:
        """Calculate staff requirements for peak hours"""
        return {
            StaffRole.MANAGER: 2,
            StaffRole.CHEF: 2,
            StaffRole.LINE_COOK: 3,
            StaffRole.PREP_COOK: 2,
            StaffRole.SERVER: 6,
            StaffRole.HOST: 2,
            StaffRole.BARTENDER: 2,
            StaffRole.BUSSER: 3,
            StaffRole.DISHWASHER: 2,
            StaffRole.CASHIER: 2
        }
    
    def _calculate_normal_requirements(self) -> Dict[StaffRole, int]:
        """Calculate staff requirements for normal hours"""
        return {
            StaffRole.MANAGER: 1,
            StaffRole.CHEF: 1,
            StaffRole.LINE_COOK: 2,
            StaffRole.PREP_COOK: 1,
            StaffRole.SERVER: 4,
            StaffRole.HOST: 1,
            StaffRole.BARTENDER: 1,
            StaffRole.BUSSER: 2,
            StaffRole.DISHWASHER: 1,
            StaffRole.CASHIER: 1
        }
    
    def _calculate_minimal_requirements(self) -> Dict[StaffRole, int]:
        """Calculate minimal staff requirements"""
        return {
            StaffRole.MANAGER: 1,
            StaffRole.CHEF: 1,
            StaffRole.LINE_COOK: 1,
            StaffRole.SERVER: 2,
            StaffRole.DISHWASHER: 1
        }
    
    def _generate_shift_templates(
        self,
        hourly_requirements: Dict[int, Dict[StaffRole, int]]
    ) -> List[Dict[str, Any]]:
        """Generate recommended shift templates"""
        
        shifts = []
        
        # Morning shift (6 AM - 2 PM)
        morning_staff = self._aggregate_requirements(hourly_requirements, 6, 14)
        if any(morning_staff.values()):
            shifts.append({
                "shift_type": ShiftType.MORNING,
                "start_time": "06:00",
                "end_time": "14:00",
                "staff_requirements": morning_staff
            })
        
        # Lunch shift (10 AM - 6 PM)
        lunch_staff = self._aggregate_requirements(hourly_requirements, 10, 18)
        if any(lunch_staff.values()):
            shifts.append({
                "shift_type": ShiftType.LUNCH,
                "start_time": "10:00",
                "end_time": "18:00",
                "staff_requirements": lunch_staff
            })
        
        # Dinner shift (4 PM - 12 AM)
        dinner_staff = self._aggregate_requirements(hourly_requirements, 16, 24)
        if any(dinner_staff.values()):
            shifts.append({
                "shift_type": ShiftType.DINNER,
                "start_time": "16:00",
                "end_time": "00:00",
                "staff_requirements": dinner_staff
            })
        
        return shifts
    
    def _aggregate_requirements(
        self,
        hourly_requirements: Dict[int, Dict[StaffRole, int]],
        start_hour: int,
        end_hour: int
    ) -> Dict[StaffRole, int]:
        """Aggregate staff requirements for a time range"""
        
        aggregated = defaultdict(int)
        
        for hour in range(start_hour, end_hour):
            if hour in hourly_requirements:
                for role, count in hourly_requirements[hour].items():
                    aggregated[role] = max(aggregated[role], count)
        
        return dict(aggregated)
    
    async def _generate_daily_recommendation(
        self,
        recommendation_date: date,
        demand_forecasts: List[DemandForecast],
        patterns: List[StaffingPattern],
        request: StaffingOptimizationRequest
    ) -> ShiftRecommendation:
        """Generate staffing recommendation for a specific day"""
        
        # Select appropriate pattern
        dow = recommendation_date.weekday()
        pattern = next(
            (p for p in patterns if dow in [d.value for d in p.applicable_days]),
            patterns[0] if patterns else None
        )
        
        # Calculate staff requirements based on demand
        staff_requirements = self._calculate_staff_requirements(
            demand_forecasts,
            request
        )
        
        # Get current scheduled staff
        current_scheduled = self._get_current_schedule(recommendation_date)
        
        # Calculate gaps
        staffing_gap = self._calculate_staffing_gap(
            staff_requirements,
            current_scheduled
        )
        
        # Determine staffing level
        staffing_level = self._assess_staffing_level(staffing_gap)
        
        # Calculate costs
        labor_cost = self._calculate_labor_cost(staff_requirements)
        total_predicted_orders = sum(f.predicted_orders for f in demand_forecasts)
        cost_per_order = labor_cost / total_predicted_orders if total_predicted_orders > 0 else Decimal("0")
        
        total_predicted_revenue = sum(f.predicted_revenue for f in demand_forecasts)
        labor_percentage = float(labor_cost / total_predicted_revenue * 100) if total_predicted_revenue > 0 else 0
        
        # Identify peak hours
        peak_hours = [
            f.hour for f in sorted(
                demand_forecasts,
                key=lambda x: x.predicted_orders,
                reverse=True
            )[:3]
        ]
        
        # Generate flexibility notes
        flexibility_notes = self._generate_flexibility_notes(
            staff_requirements,
            demand_forecasts
        )
        
        return ShiftRecommendation(
            date=recommendation_date,
            start_time=time(6, 0),  # Default restaurant hours
            end_time=time(23, 0),
            shift_type=ShiftType.FULL_DAY,
            staff_requirements=staff_requirements,
            predicted_workload={
                "total_orders": total_predicted_orders,
                "total_revenue": str(total_predicted_revenue),
                "peak_hour_orders": max(f.predicted_orders for f in demand_forecasts)
            },
            peak_hours=peak_hours,
            estimated_labor_cost=labor_cost,
            cost_per_order=cost_per_order,
            labor_percentage=labor_percentage,
            current_scheduled=current_scheduled,
            staffing_gap=staffing_gap,
            staffing_level=staffing_level,
            priority_roles_to_fill=self._identify_priority_roles(staffing_gap),
            flexibility_notes=flexibility_notes
        )
    
    def _calculate_staff_requirements(
        self,
        demand_forecasts: List[DemandForecast],
        request: StaffingOptimizationRequest
    ) -> List[StaffRequirement]:
        """Calculate staff requirements based on demand"""
        
        requirements = []
        
        # Get peak hour demand
        peak_demand = max(f.predicted_orders for f in demand_forecasts) if demand_forecasts else 0
        
        for role in StaffRole:
            # Calculate based on productivity standards
            productivity = self.productivity_standards.get(role, 20)
            
            # Base requirement
            base_required = max(
                self.minimum_staff.get(role, 0),
                int(peak_demand / productivity)
            )
            
            # Apply buffer
            buffer_multiplier = 1 + (request.buffer_percentage / 100)
            optimal = int(base_required * buffer_multiplier)
            
            # Max useful is optimal + 50%
            max_useful = int(optimal * 1.5)
            
            requirements.append(StaffRequirement(
                role=role,
                min_required=base_required,
                optimal=optimal,
                max_useful=max_useful,
                required_skills=self._get_required_skills(role),
                preferred_skills=self._get_preferred_skills(role)
            ))
        
        return requirements
    
    def _get_required_skills(self, role: StaffRole) -> List[str]:
        """Get required skills for role"""
        skills_map = {
            StaffRole.CHEF: ["Food Safety Certification", "5+ years experience"],
            StaffRole.BARTENDER: ["Alcohol Service License"],
            StaffRole.MANAGER: ["Management Experience", "Food Safety Certification"]
        }
        return skills_map.get(role, [])
    
    def _get_preferred_skills(self, role: StaffRole) -> List[str]:
        """Get preferred skills for role"""
        skills_map = {
            StaffRole.SERVER: ["Wine Knowledge", "Upselling"],
            StaffRole.LINE_COOK: ["Grill Experience", "Sauté Experience"],
            StaffRole.HOST: ["Reservation Systems", "Customer Service"]
        }
        return skills_map.get(role, [])
    
    def _get_current_schedule(self, schedule_date: date) -> Dict[StaffRole, int]:
        """Get currently scheduled staff for date"""
        
        # Query existing shifts
        shifts = self.db.query(
            Role.name,
            func.count(Shift.id).label('count')
        ).join(
            StaffMember, Shift.staff_id == StaffMember.id
        ).join(
            Role, StaffMember.role_id == Role.id
        ).filter(
            func.date(Shift.date) == schedule_date
        ).group_by(Role.name).all()
        
        # Map to StaffRole enum
        scheduled = {}
        role_mapping = {
            "Manager": StaffRole.MANAGER,
            "Chef": StaffRole.CHEF,
            "Server": StaffRole.SERVER,
            # Add more mappings as needed
        }
        
        for role_name, count in shifts:
            if role_name in role_mapping:
                scheduled[role_mapping[role_name]] = count
        
        # Fill in zeros for unscheduled roles
        for role in StaffRole:
            if role not in scheduled:
                scheduled[role] = 0
        
        return scheduled
    
    def _calculate_staffing_gap(
        self,
        requirements: List[StaffRequirement],
        current: Dict[StaffRole, int]
    ) -> Dict[StaffRole, int]:
        """Calculate staffing gap"""
        
        gap = {}
        
        for req in requirements:
            current_count = current.get(req.role, 0)
            gap[req.role] = req.optimal - current_count
        
        return gap
    
    def _assess_staffing_level(
        self,
        gap: Dict[StaffRole, int]
    ) -> StaffingLevel:
        """Assess overall staffing level"""
        
        total_gap = sum(gap.values())
        critical_gaps = sum(1 for role, g in gap.items() if g > 0 and role in self.minimum_staff)
        
        if total_gap <= -5:
            return StaffingLevel.SEVERELY_OVERSTAFFED
        elif total_gap < -2:
            return StaffingLevel.OVERSTAFFED
        elif critical_gaps > 0 or total_gap > 5:
            return StaffingLevel.SEVERELY_UNDERSTAFFED
        elif total_gap > 2:
            return StaffingLevel.UNDERSTAFFED
        else:
            return StaffingLevel.OPTIMAL
    
    def _calculate_labor_cost(
        self,
        requirements: List[StaffRequirement]
    ) -> Decimal:
        """Calculate estimated labor cost"""
        
        # Average hourly rates by role (would get from database)
        hourly_rates = {
            StaffRole.MANAGER: Decimal("25.00"),
            StaffRole.CHEF: Decimal("22.00"),
            StaffRole.LINE_COOK: Decimal("16.00"),
            StaffRole.PREP_COOK: Decimal("14.00"),
            StaffRole.SERVER: Decimal("10.00"),  # Plus tips
            StaffRole.HOST: Decimal("13.00"),
            StaffRole.BARTENDER: Decimal("12.00"),  # Plus tips
            StaffRole.BUSSER: Decimal("12.00"),
            StaffRole.DISHWASHER: Decimal("13.00"),
            StaffRole.CASHIER: Decimal("14.00")
        }
        
        total_cost = Decimal("0")
        
        for req in requirements:
            rate = hourly_rates.get(req.role, Decimal("15.00"))
            # Assume 8-hour shifts
            total_cost += rate * req.optimal * 8
        
        return total_cost
    
    def _identify_priority_roles(
        self,
        gap: Dict[StaffRole, int]
    ) -> List[StaffRole]:
        """Identify priority roles to fill"""
        
        # Sort by gap size and criticality
        priority_order = [
            StaffRole.MANAGER,
            StaffRole.CHEF,
            StaffRole.SERVER,
            StaffRole.LINE_COOK,
            StaffRole.DISHWASHER
        ]
        
        priorities = []
        
        # First add critical roles with gaps
        for role in priority_order:
            if gap.get(role, 0) > 0:
                priorities.append(role)
        
        # Then add other roles with gaps
        for role, gap_count in sorted(gap.items(), key=lambda x: x[1], reverse=True):
            if role not in priorities and gap_count > 0:
                priorities.append(role)
        
        return priorities[:5]  # Top 5 priorities
    
    def _generate_flexibility_notes(
        self,
        requirements: List[StaffRequirement],
        forecasts: List[DemandForecast]
    ) -> List[str]:
        """Generate flexibility notes for staffing"""
        
        notes = []
        
        # Check confidence levels
        low_confidence = [f for f in forecasts if f.confidence_level < 0.8]
        if len(low_confidence) > len(forecasts) * 0.3:
            notes.append("Forecast confidence is lower than usual - maintain scheduling flexibility")
        
        # Check for demand spikes
        if forecasts:
            avg_orders = statistics.mean([f.predicted_orders for f in forecasts])
            spikes = [f for f in forecasts if f.predicted_orders > avg_orders * 1.5]
            if spikes:
                spike_hours = [f.hour for f in spikes]
                notes.append(f"Demand spikes expected at hours: {spike_hours}")
        
        # Cross-training opportunities
        notes.append("Consider cross-training staff for flexibility during peak hours")
        
        return notes
    
    def _build_recommendation_set(
        self,
        daily_recommendations: List[ShiftRecommendation],
        patterns: List[StaffingPattern],
        request: StaffingOptimizationRequest
    ) -> StaffingRecommendationSet:
        """Build complete recommendation set"""
        
        # Calculate totals
        total_hours = sum(
            sum(req.optimal * 8 for req in rec.staff_requirements)
            for rec in daily_recommendations
        )
        
        total_cost = sum(
            rec.estimated_labor_cost
            for rec in daily_recommendations
        )
        
        avg_labor_percentage = statistics.mean([
            rec.labor_percentage
            for rec in daily_recommendations
            if rec.labor_percentage > 0
        ]) if daily_recommendations else 0
        
        # Identify risks
        understaffing_risks = self._identify_understaffing_risks(daily_recommendations)
        overstaffing_risks = self._identify_overstaffing_risks(daily_recommendations)
        
        # Build implementation priorities
        implementation_priority = self._build_implementation_priorities(daily_recommendations)
        
        return StaffingRecommendationSet(
            request_id=f"staff-opt-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            generated_at=datetime.now(),
            period_start=request.start_date,
            period_end=request.end_date,
            daily_recommendations=daily_recommendations,
            patterns_identified=patterns,
            total_recommended_hours=total_hours,
            total_estimated_cost=total_cost,
            average_labor_percentage=avg_labor_percentage,
            expected_service_level=0.92,  # Would calculate from requirements
            understaffing_risks=understaffing_risks,
            overstaffing_risks=overstaffing_risks,
            implementation_priority=implementation_priority,
            scheduling_conflicts=[],  # Would identify from staff availability
            training_requirements=self._identify_training_needs(daily_recommendations),
            alerts=self._generate_alerts(daily_recommendations),
            warnings=self._generate_warnings(daily_recommendations)
        )
    
    def _identify_understaffing_risks(
        self,
        recommendations: List[ShiftRecommendation]
    ) -> List[Dict[str, Any]]:
        """Identify understaffing risks"""
        
        risks = []
        
        severely_understaffed = [
            rec for rec in recommendations
            if rec.staffing_level == StaffingLevel.SEVERELY_UNDERSTAFFED
        ]
        
        if severely_understaffed:
            risks.append({
                "risk_type": "severe_understaffing",
                "dates": [rec.date for rec in severely_understaffed],
                "impact": "High risk of poor service and staff burnout",
                "mitigation": "Urgent hiring or overtime authorization needed"
            })
        
        return risks
    
    def _identify_overstaffing_risks(
        self,
        recommendations: List[ShiftRecommendation]
    ) -> List[Dict[str, Any]]:
        """Identify overstaffing risks"""
        
        risks = []
        
        overstaffed = [
            rec for rec in recommendations
            if rec.staffing_level in [StaffingLevel.OVERSTAFFED, StaffingLevel.SEVERELY_OVERSTAFFED]
        ]
        
        if overstaffed:
            total_excess_cost = sum(
                rec.estimated_labor_cost * Decimal("0.2")  # Assume 20% overstaffed
                for rec in overstaffed
            )
            
            risks.append({
                "risk_type": "overstaffing",
                "dates": [rec.date for rec in overstaffed],
                "impact": f"Excess labor cost of ${total_excess_cost:.2f}",
                "mitigation": "Reduce shifts or offer voluntary time off"
            })
        
        return risks
    
    def _build_implementation_priorities(
        self,
        recommendations: List[ShiftRecommendation]
    ) -> List[Dict[str, Any]]:
        """Build implementation priorities"""
        
        priorities = []
        
        # Priority 1: Fix severe understaffing
        severe_dates = [
            rec.date for rec in recommendations
            if rec.staffing_level == StaffingLevel.SEVERELY_UNDERSTAFFED
        ]
        
        if severe_dates:
            priorities.append({
                "priority": 1,
                "action": "Address severe understaffing",
                "dates": severe_dates,
                "urgency": "immediate"
            })
        
        # Priority 2: Fill critical roles
        critical_gaps = defaultdict(list)
        for rec in recommendations:
            for role in rec.priority_roles_to_fill[:2]:  # Top 2 priority roles
                critical_gaps[role].append(rec.date)
        
        for role, dates in critical_gaps.items():
            if len(dates) > 3:  # Persistent gap
                priorities.append({
                    "priority": 2,
                    "action": f"Hire additional {role.value}",
                    "dates": dates[:7],  # Show first week
                    "urgency": "high"
                })
        
        return priorities[:5]  # Top 5 priorities
    
    def _identify_training_needs(
        self,
        recommendations: List[ShiftRecommendation]
    ) -> List[Dict[str, Any]]:
        """Identify training requirements"""
        
        training_needs = []
        
        # Check for roles consistently understaffed
        role_gaps = defaultdict(int)
        for rec in recommendations:
            for role, gap in rec.staffing_gap.items():
                if gap > 0:
                    role_gaps[role] += 1
        
        # Roles understaffed >50% of the time need cross-training
        for role, gap_days in role_gaps.items():
            if gap_days > len(recommendations) * 0.5:
                training_needs.append({
                    "role": role.value,
                    "training_type": "cross_training",
                    "urgency": "high",
                    "candidates": f"Train {role.value} from similar roles"
                })
        
        return training_needs
    
    def _generate_alerts(
        self,
        recommendations: List[ShiftRecommendation]
    ) -> List[str]:
        """Generate alerts for critical issues"""
        
        alerts = []
        
        # Check labor percentage
        high_labor = [
            rec for rec in recommendations
            if rec.labor_percentage > 35
        ]
        
        if high_labor:
            alerts.append(
                f"Labor cost exceeds 35% on {len(high_labor)} days - review pricing or efficiency"
            )
        
        # Check severe understaffing
        severe = [
            rec for rec in recommendations
            if rec.staffing_level == StaffingLevel.SEVERELY_UNDERSTAFFED
        ]
        
        if severe:
            alerts.append(
                f"CRITICAL: Severe understaffing on {len(severe)} days - immediate action required"
            )
        
        return alerts
    
    def _generate_warnings(
        self,
        recommendations: List[ShiftRecommendation]
    ) -> List[str]:
        """Generate warnings for potential issues"""
        
        warnings = []
        
        # Check for consistent patterns
        if recommendations:
            avg_gap = statistics.mean([
                sum(rec.staffing_gap.values())
                for rec in recommendations
            ])
            
            if avg_gap > 3:
                warnings.append(
                    "Consistent understaffing detected - consider permanent staff increase"
                )
            elif avg_gap < -3:
                warnings.append(
                    "Consistent overstaffing detected - review base staffing levels"
                )
        
        return warnings


# Service factory
def create_staffing_recommendation_service(db: Session) -> StaffingRecommendationService:
    """Create staffing recommendation service instance"""
    return StaffingRecommendationService(db)