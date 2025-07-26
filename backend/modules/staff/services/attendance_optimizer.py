"""
Optimized attendance processing service for enhanced payroll engine.

Addresses performance concerns by using SQL aggregation instead of 
day-by-day Python iteration for large datasets.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, case, cast, Date
from typing import Dict, List
from decimal import Decimal
from datetime import datetime, date
from dataclasses import dataclass

from ..models.attendance_models import AttendanceLog


@dataclass
class DailyHoursSummary:
    """Summary of hours worked per day."""
    work_date: date
    total_hours: Decimal
    shifts_count: int
    first_check_in: datetime
    last_check_out: datetime


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
        Get daily hours breakdown using SQL aggregation for performance.
        
        This replaces the day-by-day Python iteration with a single SQL query
        that groups attendance logs by date and calculates hours per day.
        """
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
        
        return [
            DailyHoursSummary(
                work_date=result.work_date,
                total_hours=Decimal(str(result.total_hours or 0)),
                shifts_count=result.shifts_count,
                first_check_in=result.first_check_in,
                last_check_out=result.last_check_out
            )
            for result in results
        ]
    
    def calculate_overtime_efficiently(
        self, 
        daily_summaries: List[DailyHoursSummary],
        daily_overtime_threshold: Decimal = Decimal('8.0'),
        weekly_overtime_threshold: Decimal = Decimal('40.0')
    ) -> Dict[str, Decimal]:
        """
        Calculate overtime using optimized logic.
        
        Args:
            daily_summaries: Pre-aggregated daily hours
            daily_overtime_threshold: Hours per day before daily OT
            weekly_overtime_threshold: Hours per week before weekly OT
            
        Returns:
            Dictionary with regular_hours, overtime_hours, double_time_hours
        """
        total_regular = Decimal('0.00')
        total_daily_overtime = Decimal('0.00')
        total_weekly_overtime = Decimal('0.00')
        weekly_total = Decimal('0.00')
        
        # Calculate daily overtime first
        for day_summary in daily_summaries:
            daily_hours = day_summary.total_hours
            weekly_total += daily_hours
            
            if daily_hours > daily_overtime_threshold:
                daily_regular = daily_overtime_threshold
                daily_ot = daily_hours - daily_overtime_threshold
                total_daily_overtime += daily_ot
            else:
                daily_regular = daily_hours
            
            total_regular += daily_regular
        
        # Calculate weekly overtime (beyond 40 hours)
        if weekly_total > weekly_overtime_threshold:
            # Convert some regular hours to weekly overtime
            weekly_ot_hours = weekly_total - weekly_overtime_threshold
            total_weekly_overtime = min(weekly_ot_hours, total_regular)
            total_regular -= total_weekly_overtime
        
        # Double-time calculation (over 60 hours per week or 12+ hours per day)
        double_time_hours = Decimal('0.00')
        for day_summary in daily_summaries:
            if day_summary.total_hours > Decimal('12.0'):
                double_time_hours += day_summary.total_hours - Decimal('12.0')
        
        # If weekly total > 60, some overtime becomes double-time
        if weekly_total > Decimal('60.0'):
            additional_double_time = weekly_total - Decimal('60.0')
            double_time_hours += additional_double_time
        
        # Adjust other categories to account for double-time
        total_overtime = total_daily_overtime + total_weekly_overtime - double_time_hours
        
        return {
            'regular_hours': max(total_regular, Decimal('0.00')),
            'overtime_hours': max(total_overtime, Decimal('0.00')),
            'double_time_hours': max(double_time_hours, Decimal('0.00')),
            'total_hours': weekly_total
        }
    
    def get_attendance_statistics(
        self, 
        staff_id: int, 
        start_date: date, 
        end_date: date
    ) -> Dict[str, any]:
        """
        Get comprehensive attendance statistics using SQL aggregation.
        
        Returns statistics like average daily hours, longest shift,
        total days worked, etc.
        """
        stats_query = self.db.query(
            func.count(func.distinct(cast(AttendanceLog.check_in, Date))).label('days_worked'),
            func.avg(
                func.extract('epoch', AttendanceLog.check_out - AttendanceLog.check_in) / 3600
            ).label('avg_hours_per_shift'),
            func.max(
                func.extract('epoch', AttendanceLog.check_out - AttendanceLog.check_in) / 3600
            ).label('longest_shift_hours'),
            func.min(
                func.extract('epoch', AttendanceLog.check_out - AttendanceLog.check_in) / 3600
            ).label('shortest_shift_hours'),
            func.sum(
                func.extract('epoch', AttendanceLog.check_out - AttendanceLog.check_in) / 3600
            ).label('total_hours')
        ).filter(
            AttendanceLog.staff_id == staff_id,
            AttendanceLog.check_in >= datetime.combine(start_date, datetime.min.time()),
            AttendanceLog.check_in < datetime.combine(end_date, datetime.min.time()),
            AttendanceLog.check_out.isnot(None)
        ).first()
        
        return {
            'days_worked': stats_query.days_worked or 0,
            'avg_hours_per_shift': Decimal(str(stats_query.avg_hours_per_shift or 0)).quantize(Decimal('0.01')),
            'longest_shift_hours': Decimal(str(stats_query.longest_shift_hours or 0)).quantize(Decimal('0.01')),
            'shortest_shift_hours': Decimal(str(stats_query.shortest_shift_hours or 0)).quantize(Decimal('0.01')),
            'total_hours': Decimal(str(stats_query.total_hours or 0)).quantize(Decimal('0.01')),
            'avg_hours_per_day': (
                Decimal(str(stats_query.total_hours or 0)) / Decimal(str(stats_query.days_worked or 1))
            ).quantize(Decimal('0.01')) if stats_query.days_worked else Decimal('0.00')
        }
    
    def batch_calculate_hours_for_staff(
        self, 
        staff_ids: List[int], 
        start_date: date, 
        end_date: date
    ) -> Dict[int, Dict[str, Decimal]]:
        """
        Batch calculate hours for multiple staff members efficiently.
        
        Uses a single query with GROUP BY staff_id to process multiple
        staff members at once instead of individual queries.
        """
        batch_query = self.db.query(
            AttendanceLog.staff_id,
            func.sum(
                func.extract('epoch', AttendanceLog.check_out - AttendanceLog.check_in) / 3600
            ).label('total_hours'),
            func.count(func.distinct(cast(AttendanceLog.check_in, Date))).label('days_worked'),
            func.count(AttendanceLog.id).label('total_shifts')
        ).filter(
            AttendanceLog.staff_id.in_(staff_ids),
            AttendanceLog.check_in >= datetime.combine(start_date, datetime.min.time()),
            AttendanceLog.check_in < datetime.combine(end_date, datetime.min.time()),
            AttendanceLog.check_out.isnot(None)
        ).group_by(
            AttendanceLog.staff_id
        ).all()
        
        # Initialize results for all staff (even those with no attendance)
        results = {staff_id: {
            'total_hours': Decimal('0.00'),
            'days_worked': 0,
            'total_shifts': 0,
            'avg_hours_per_day': Decimal('0.00')
        } for staff_id in staff_ids}
        
        # Update with actual data
        for row in batch_query:
            total_hours = Decimal(str(row.total_hours or 0))
            days_worked = row.days_worked or 0
            
            results[row.staff_id] = {
                'total_hours': total_hours,
                'days_worked': days_worked,
                'total_shifts': row.total_shifts or 0,
                'avg_hours_per_day': (
                    total_hours / Decimal(str(days_worked))
                ).quantize(Decimal('0.01')) if days_worked > 0 else Decimal('0.00')
            }
        
        return results