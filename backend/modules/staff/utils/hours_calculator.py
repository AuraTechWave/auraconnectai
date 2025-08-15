"""
Hours calculation utilities for payroll processing.

Extracted from enhanced_payroll_engine.py to improve maintainability
and separate concerns.
"""

from decimal import Decimal
from datetime import datetime, date
from dataclasses import dataclass
from typing import List, Dict
from sqlalchemy.orm import Session

from ..models.attendance_models import AttendanceLog
from ..services.attendance_optimizer import AttendanceOptimizer, DailyHoursSummary
from ..services.config_manager import ConfigManager


@dataclass
class HoursBreakdown:
    """Detailed breakdown of hours worked."""

    regular_hours: Decimal
    overtime_hours: Decimal
    double_time_hours: Decimal = Decimal("0.00")
    holiday_hours: Decimal = Decimal("0.00")
    sick_hours: Decimal = Decimal("0.00")
    vacation_hours: Decimal = Decimal("0.00")

    @property
    def total_hours(self) -> Decimal:
        """Calculate total hours worked."""
        return (
            self.regular_hours
            + self.overtime_hours
            + self.double_time_hours
            + self.holiday_hours
            + self.sick_hours
            + self.vacation_hours
        )


class HoursCalculator:
    """Utility class for calculating various types of hours."""

    def __init__(self, db: Session):
        self.db = db
        self.optimizer = AttendanceOptimizer(db)
        self.config_manager = ConfigManager(db)

    def calculate_hours_for_period(
        self,
        staff_id: int,
        start_date: date,
        end_date: date,
        use_optimized: bool = True,
    ) -> HoursBreakdown:
        """
        Calculate detailed hours breakdown for a pay period.

        Args:
            staff_id: Staff member ID
            start_date: Pay period start date
            end_date: Pay period end date
            use_optimized: Whether to use SQL aggregation optimization

        Returns:
            HoursBreakdown with regular and overtime hours
        """
        if use_optimized:
            return self._calculate_hours_optimized(staff_id, start_date, end_date)
        else:
            return self._calculate_hours_legacy(staff_id, start_date, end_date)

    def _calculate_hours_optimized(
        self, staff_id: int, start_date: date, end_date: date
    ) -> HoursBreakdown:
        """Optimized hours calculation using SQL aggregation."""
        # Get daily summaries using SQL aggregation
        daily_summaries = self.optimizer.get_daily_hours_aggregated(
            staff_id, start_date, end_date
        )

        # Calculate overtime efficiently
        # Fetch dynamic overtime rules from configuration manager
        overtime_rules = self.config_manager.get_overtime_rules()
        overtime_breakdown = self.optimizer.calculate_overtime_efficiently(
            daily_summaries,
            daily_overtime_threshold=overtime_rules["daily_threshold"],
            weekly_overtime_threshold=overtime_rules["weekly_threshold"],
        )

        return HoursBreakdown(
            regular_hours=overtime_breakdown["regular_hours"],
            overtime_hours=overtime_breakdown["overtime_hours"],
            double_time_hours=overtime_breakdown["double_time_hours"],
        )

    def _calculate_hours_legacy(
        self, staff_id: int, start_date: date, end_date: date
    ) -> HoursBreakdown:
        """Legacy day-by-day calculation method (kept for compatibility)."""
        # Get attendance logs for the period
        attendance_logs = (
            self.db.query(AttendanceLog)
            .filter(
                AttendanceLog.staff_id == staff_id,
                AttendanceLog.check_in
                >= datetime.combine(start_date, datetime.min.time()),
                AttendanceLog.check_in
                < datetime.combine(end_date, datetime.min.time()),
                AttendanceLog.check_out.isnot(None),
            )
            .all()
        )

        total_hours = Decimal("0.00")
        daily_hours: List[Decimal] = []

        # Calculate hours by day to properly handle daily overtime rules
        current_day = start_date
        while current_day < end_date:
            day_start = datetime.combine(current_day, datetime.min.time())
            day_end = datetime.combine(current_day, datetime.max.time())

            day_logs = [
                log for log in attendance_logs if day_start <= log.check_in <= day_end
            ]

            day_hours = Decimal("0.00")
            for log in day_logs:
                if log.check_out and log.check_in:
                    hours = (log.check_out - log.check_in).total_seconds() / 3600
                    day_hours += Decimal(str(hours))

            daily_hours.append(day_hours)
            total_hours += day_hours
            current_day = date.fromordinal(current_day.toordinal() + 1)

        # Calculate regular vs overtime hours
        # Rule: Over 8 hours per day = daily overtime
        # Rule: Over 40 hours per week = weekly overtime
        # Fetch overtime thresholds
        overtime_rules = self.config_manager.get_overtime_rules()
        daily_threshold = overtime_rules["daily_threshold"]
        weekly_threshold = overtime_rules["weekly_threshold"]

        regular_hours = Decimal("0.00")
        overtime_hours = Decimal("0.00")

        for day_hours in daily_hours:
            if day_hours > daily_threshold:
                regular_hours += daily_threshold
                overtime_hours += day_hours - daily_threshold
            else:
                regular_hours += day_hours

        # Adjust for weekly overtime
        if total_hours > weekly_threshold:
            weekly_overtime = total_hours - weekly_threshold
            if weekly_overtime > overtime_hours:
                # Convert some regular hours to overtime
                additional_overtime = weekly_overtime - overtime_hours
                regular_hours -= additional_overtime
                overtime_hours += additional_overtime

        return HoursBreakdown(
            regular_hours=max(regular_hours, Decimal("0.00")),
            overtime_hours=max(overtime_hours, Decimal("0.00")),
        )

    def calculate_holiday_hours(
        self, staff_id: int, start_date: date, end_date: date, holiday_dates: List[date]
    ) -> Decimal:
        """Calculate holiday hours worked."""
        holiday_hours = Decimal("0.00")

        for holiday_date in holiday_dates:
            if start_date <= holiday_date < end_date:
                day_start = datetime.combine(holiday_date, datetime.min.time())
                day_end = datetime.combine(holiday_date, datetime.max.time())

                holiday_logs = (
                    self.db.query(AttendanceLog)
                    .filter(
                        AttendanceLog.staff_id == staff_id,
                        AttendanceLog.check_in >= day_start,
                        AttendanceLog.check_in <= day_end,
                        AttendanceLog.check_out.isnot(None),
                    )
                    .all()
                )

                for log in holiday_logs:
                    if log.check_out and log.check_in:
                        hours = (log.check_out - log.check_in).total_seconds() / 3600
                        holiday_hours += Decimal(str(hours))

        return holiday_hours

    def batch_calculate_hours(
        self, staff_ids: List[int], start_date: date, end_date: date
    ) -> Dict[int, HoursBreakdown]:
        """
        Calculate hours for multiple staff members efficiently.

        Uses batch processing to optimize database queries.
        """
        # Use the optimizer for batch processing
        batch_results = self.optimizer.batch_calculate_hours_for_staff(
            staff_ids, start_date, end_date
        )

        hours_breakdowns = {}
        for staff_id in staff_ids:
            if staff_id in batch_results:
                total_hours = batch_results[staff_id]["total_hours"]
                # Apply overtime rules for batch processing (weekly only)
                overtime_rules = self.config_manager.get_overtime_rules()
                weekly_threshold = overtime_rules["weekly_threshold"]
                if total_hours > weekly_threshold:
                    regular_hours = weekly_threshold
                    overtime_hours = total_hours - weekly_threshold
                else:
                    regular_hours = total_hours
                    overtime_hours = Decimal("0.00")

                hours_breakdowns[staff_id] = HoursBreakdown(
                    regular_hours=regular_hours, overtime_hours=overtime_hours
                )
            else:
                # No attendance data
                hours_breakdowns[staff_id] = HoursBreakdown(
                    regular_hours=Decimal("0.00"), overtime_hours=Decimal("0.00")
                )

        return hours_breakdowns

    def get_attendance_summary(
        self, staff_id: int, start_date: date, end_date: date
    ) -> Dict[str, any]:
        """Get comprehensive attendance summary for reporting."""
        return self.optimizer.get_attendance_statistics(staff_id, start_date, end_date)
