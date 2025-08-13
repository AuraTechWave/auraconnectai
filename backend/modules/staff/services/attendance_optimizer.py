"""
Optimized attendance processing using SQL aggregation.

This module provides efficient attendance data processing and overtime calculations
using SQL aggregation to minimize database queries and improve performance.
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date, and_, or_

from ..models.attendance_models import AttendanceLog

logger = logging.getLogger(__name__)


@dataclass
class DailyHoursSummary:
    """Summary of hours worked for a single day."""
    work_date: date
    total_hours: Decimal
    shifts_count: int
    first_check_in: Optional[datetime]
    last_check_out: Optional[datetime]


class AttendanceOptimizer:
    """Optimized attendance processing using SQL aggregation."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_daily_hours_aggregated(
        self, 
        staff_id: int, 
        start_date: date, 
        end_date: date
    ) -> List[DailyHoursSummary]:
        """
        Get daily hours summary using SQL aggregation for efficiency.
        
        Args:
            staff_id: Staff member ID
            start_date: Start date for the period
            end_date: End date for the period
            
        Returns:
            List of DailyHoursSummary objects
        """
        try:
            # Validate inputs
            if not isinstance(staff_id, int) or staff_id <= 0:
                raise ValueError(f"Invalid staff_id: {staff_id}")
            
            if not isinstance(start_date, date) or not isinstance(end_date, date):
                raise ValueError("start_date and end_date must be date objects")
            
            if start_date >= end_date:
                raise ValueError("start_date must be before end_date")
            
            # Check for reasonable date range (prevent excessive queries)
            if (end_date - start_date).days > 365:
                logger.warning(f"Large date range requested: {start_date} to {end_date} for staff {staff_id}")
            
            query = self.db.query(
                cast(AttendanceLog.check_in, Date).label('work_date'),
                func.sum(
                    func.extract('epoch', AttendanceLog.check_out - AttendanceLog.check_in) / 3600
                ).label('total_hours'),
                func.count(AttendanceLog.id).label('shifts_count'),
                func.min(AttendanceLog.check_in).label('first_check_in'),
                func.max(AttendanceLog.check_out).label('last_check_out')
            ).filter(
                AttendanceLog.staff_id == staff_id,
                AttendanceLog.check_in >= datetime.combine(start_date, datetime.min.time()),
                AttendanceLog.check_in < datetime.combine(end_date, datetime.min.time()),
                AttendanceLog.check_out.isnot(None)
            ).group_by(
                cast(AttendanceLog.check_in, Date)
            ).order_by(
                cast(AttendanceLog.check_in, Date)
            )
            
            results = query.all()
            
            daily_summaries = [
                DailyHoursSummary(
                    work_date=result.work_date,
                    total_hours=Decimal(str(result.total_hours or 0)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                    shifts_count=result.shifts_count,
                    first_check_in=result.first_check_in,
                    last_check_out=result.last_check_out
                )
                for result in results
            ]
            
            logger.debug(f"Retrieved {len(daily_summaries)} daily summaries for staff {staff_id}")
            return daily_summaries
            
        except Exception as e:
            logger.error(f"Error getting daily hours for staff {staff_id}: {e}")
            # Return empty list on error to prevent downstream failures
            return []
    
    def calculate_overtime_efficiently(
        self, 
        daily_summaries: List[DailyHoursSummary],
        daily_overtime_threshold: Decimal = Decimal('8.0'),
        weekly_overtime_threshold: Decimal = Decimal('40.0'),
        double_time_threshold: Decimal = Decimal('12.0'),
        double_time_weekly_threshold: Decimal = Decimal('60.0')
    ) -> Dict[str, Decimal]:
        """
        Calculate overtime using optimized logic with improved edge case handling.
        
        Args:
            daily_summaries: Pre-aggregated daily hours
            daily_overtime_threshold: Hours per day before daily OT
            weekly_overtime_threshold: Hours per week before weekly OT
            double_time_threshold: Hours per day before double time
            double_time_weekly_threshold: Hours per week before double time
            
        Returns:
            Dictionary with regular_hours, overtime_hours, double_time_hours, total_hours
        """
        if not daily_summaries:
            return {
                'regular_hours': Decimal('0.00'),
                'overtime_hours': Decimal('0.00'),
                'double_time_hours': Decimal('0.00'),
                'total_hours': Decimal('0.00')
            }
        
        # Initialize totals
        total_regular = Decimal('0.00')
        total_daily_overtime = Decimal('0.00')
        total_weekly_overtime = Decimal('0.00')
        total_double_time = Decimal('0.00')
        weekly_total = Decimal('0.00')
        
        # First pass: Calculate daily overtime and accumulate weekly total
        daily_regular_hours = []
        for day_summary in daily_summaries:
            daily_hours = day_summary.total_hours
            weekly_total += daily_hours
            
            # Calculate daily overtime
            if daily_hours > daily_overtime_threshold:
                daily_regular = daily_overtime_threshold
                daily_ot = daily_hours - daily_overtime_threshold
                total_daily_overtime += daily_ot
            else:
                daily_regular = daily_hours
                daily_ot = Decimal('0.00')
            
            daily_regular_hours.append(daily_regular)
        
        # Second pass: Calculate weekly overtime
        if weekly_total > weekly_overtime_threshold:
            weekly_ot_hours = weekly_total - weekly_overtime_threshold
            
            # Distribute weekly overtime across days, prioritizing days with more hours
            remaining_weekly_ot = weekly_ot_hours
            for i, day_summary in enumerate(daily_summaries):
                if remaining_weekly_ot <= 0:
                    break
                
                # Convert regular hours to weekly overtime (up to the daily regular hours)
                conversion_amount = min(remaining_weekly_ot, daily_regular_hours[i])
                daily_regular_hours[i] -= conversion_amount
                total_weekly_overtime += conversion_amount
                remaining_weekly_ot -= conversion_amount
        
        # Calculate total regular hours
        total_regular = sum(daily_regular_hours)
        
        # Third pass: Calculate double time
        # Double time applies to hours over the daily threshold AND weekly threshold
        for day_summary in daily_summaries:
            daily_hours = day_summary.total_hours
            
            # Daily double time (over 12 hours in a day)
            if daily_hours > double_time_threshold:
                daily_double_time = daily_hours - double_time_threshold
                total_double_time += daily_double_time
        
        # Weekly double time (over 60 hours in a week)
        if weekly_total > double_time_weekly_threshold:
            weekly_double_time = weekly_total - double_time_weekly_threshold
            # Only count the additional double time beyond what's already calculated
            additional_double_time = weekly_double_time - total_double_time
            if additional_double_time > 0:
                total_double_time += additional_double_time
        
        # Calculate final overtime (excluding double time)
        total_overtime = total_daily_overtime + total_weekly_overtime - total_double_time
        
        # Ensure no negative values
        total_regular = max(total_regular, Decimal('0.00'))
        total_overtime = max(total_overtime, Decimal('0.00'))
        total_double_time = max(total_double_time, Decimal('0.00'))
        
        # Validate that totals add up correctly
        calculated_total = total_regular + total_overtime + total_double_time
        if abs(calculated_total - weekly_total) > Decimal('0.01'):
            # Adjust regular hours to account for rounding differences
            total_regular = weekly_total - total_overtime - total_double_time
            total_regular = max(total_regular, Decimal('0.00'))
        
        return {
            'regular_hours': total_regular.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'overtime_hours': total_overtime.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'double_time_hours': total_double_time.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'total_hours': weekly_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        }
    
    def get_attendance_statistics(
        self, 
        staff_id: int, 
        start_date: date, 
        end_date: date
    ) -> Dict[str, any]:
        """
        Get comprehensive attendance statistics using SQL aggregation.
        
        Args:
            staff_id: Staff member ID
            start_date: Start date for the period
            end_date: End date for the period
            
        Returns:
            Dictionary with attendance statistics
        """
        # Get daily summaries
        daily_summaries = self.get_daily_hours_aggregated(staff_id, start_date, end_date)
        
        if not daily_summaries:
            return {
                'total_days': 0,
                'total_hours': Decimal('0.00'),
                'average_hours_per_day': Decimal('0.00'),
                'max_hours_in_day': Decimal('0.00'),
                'min_hours_in_day': Decimal('0.00'),
                'total_shifts': 0,
                'average_shifts_per_day': Decimal('0.00'),
                'days_with_overtime': 0,
                'total_overtime_hours': Decimal('0.00')
            }
        
        # Calculate statistics
        total_days = len(daily_summaries)
        total_hours = sum(day.total_hours for day in daily_summaries)
        total_shifts = sum(day.shifts_count for day in daily_summaries)
        
        hours_per_day = [day.total_hours for day in daily_summaries]
        max_hours = max(hours_per_day)
        min_hours = min(hours_per_day)
        
        # Count days with overtime (assuming 8-hour threshold)
        days_with_overtime = sum(1 for hours in hours_per_day if hours > Decimal('8.0'))
        
        # Calculate overtime hours
        overtime_hours = sum(
            max(Decimal('0.00'), hours - Decimal('8.0')) 
            for hours in hours_per_day
        )
        
        return {
            'total_days': total_days,
            'total_hours': total_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'average_hours_per_day': (total_hours / total_days).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if total_days > 0 else Decimal('0.00'),
            'max_hours_in_day': max_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'min_hours_in_day': min_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            'total_shifts': total_shifts,
            'average_shifts_per_day': (Decimal(str(total_shifts)) / total_days).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if total_days > 0 else Decimal('0.00'),
            'days_with_overtime': days_with_overtime,
            'total_overtime_hours': overtime_hours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        }
    
    def batch_calculate_hours_for_staff(
        self, 
        staff_ids: List[int], 
        start_date: date, 
        end_date: date,
        daily_overtime_threshold: Decimal = Decimal('8.0'),
        weekly_overtime_threshold: Decimal = Decimal('40.0'),
        double_time_threshold: Decimal = Decimal('12.0'),
        double_time_weekly_threshold: Decimal = Decimal('60.0')
    ) -> Dict[int, Dict[str, any]]:
        """
        Calculate hours for multiple staff members efficiently.
        
        Args:
            staff_ids: List of staff member IDs
            start_date: Start date for the period
            end_date: End date for the period
            daily_overtime_threshold: Hours per day before daily OT
            weekly_overtime_threshold: Hours per week before weekly OT
            double_time_threshold: Hours per day before double time
            double_time_weekly_threshold: Hours per week before double time
            
        Returns:
            Dictionary mapping staff_id to hours breakdown
        """
        if not staff_ids:
            return {}
        
        # Use a single query to get all staff data
        query = self.db.query(
            AttendanceLog.staff_id,
            cast(AttendanceLog.check_in, Date).label('work_date'),
            func.sum(
                func.extract('epoch', AttendanceLog.check_out - AttendanceLog.check_in) / 3600
            ).label('total_hours')
        ).filter(
            AttendanceLog.staff_id.in_(staff_ids),
            AttendanceLog.check_in >= datetime.combine(start_date, datetime.min.time()),
            AttendanceLog.check_in < datetime.combine(end_date, datetime.min.time()),
            AttendanceLog.check_out.isnot(None)
        ).group_by(
            AttendanceLog.staff_id,
            cast(AttendanceLog.check_in, Date)
        )
        
        results = query.all()
        
        # Group results by staff_id
        staff_data = {}
        for staff_id in staff_ids:
            staff_data[staff_id] = []
        
        for result in results:
            staff_data[result.staff_id].append({
                'work_date': result.work_date,
                'total_hours': Decimal(str(result.total_hours or 0))
            })
        
        # Calculate hours for each staff member
        batch_results = {}
        for staff_id, daily_data in staff_data.items():
            if not daily_data:
                batch_results[staff_id] = {
                    'total_hours': Decimal('0.00'),
                    'regular_hours': Decimal('0.00'),
                    'overtime_hours': Decimal('0.00')
                }
                continue
            
            # Convert to DailyHoursSummary format
            daily_summaries = [
                DailyHoursSummary(
                    work_date=day['work_date'],
                    total_hours=day['total_hours'],
                    shifts_count=1,  # Simplified for batch processing
                    first_check_in=None,
                    last_check_out=None
                )
                for day in daily_data
            ]
            
            # Calculate overtime
            overtime_breakdown = self.calculate_overtime_efficiently(
                daily_summaries,
                daily_overtime_threshold,
                weekly_overtime_threshold,
                double_time_threshold,
                double_time_weekly_threshold
            )
            
            batch_results[staff_id] = {
                'total_hours': overtime_breakdown['total_hours'],
                'regular_hours': overtime_breakdown['regular_hours'],
                'overtime_hours': overtime_breakdown['overtime_hours'],
                'double_time_hours': overtime_breakdown['double_time_hours']
            }
        
        return batch_results