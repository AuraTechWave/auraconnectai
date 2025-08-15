# backend/modules/staff/services/schedule_service.py

from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta, time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from sqlalchemy.orm import selectinload
import math
import logging

from ..models import Staff, Schedule, StaffRole
from ..schemas.schedule_schemas import (
    SchedulePreviewResponse,
    ScheduleCreateRequest,
    ScheduleUpdateRequest,
    PaginatedPreviewResponse,
    ScheduleResponse,
)
from .schedule_notification_service import schedule_notification_service

logger = logging.getLogger(__name__)


class ScheduleService:
    """Core service for schedule operations"""

    async def generate_preview(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date,
        filters: Optional[Dict[str, Any]] = None,
    ) -> SchedulePreviewResponse:
        """Generate schedule preview with summary statistics"""

        filters = filters or {}

        # Build query with filters
        query = (
            select(Schedule)
            .where(
                and_(
                    Schedule.restaurant_id == restaurant_id,
                    Schedule.date >= start_date,
                    Schedule.date <= end_date,
                )
            )
            .options(selectinload(Schedule.staff).selectinload(Staff.role))
        )

        # Apply filters
        if filters.get("role_id"):
            query = query.join(Staff).where(Staff.role_id == filters["role_id"])

        if filters.get("department_id"):
            query = (
                query.join(Staff)
                .join(StaffRole)
                .where(StaffRole.department_id == filters["department_id"])
            )

        result = await db.execute(query)
        schedules = result.scalars().all()

        # Group data for response
        by_date = {}
        by_staff = {}
        total_hours = 0
        coverage_gaps = []

        for schedule in schedules:
            # Group by date
            date_key = schedule.date.isoformat()
            if date_key not in by_date:
                by_date[date_key] = []

            by_date[date_key].append(
                {
                    "schedule_id": schedule.id,
                    "staff_id": schedule.staff_id,
                    "staff_name": schedule.staff.name,
                    "role": schedule.staff.role.name if schedule.staff.role else None,
                    "start_time": schedule.start_time.strftime("%H:%M"),
                    "end_time": schedule.end_time.strftime("%H:%M"),
                    "hours": schedule.total_hours,
                    "is_published": schedule.is_published,
                }
            )

            # Group by staff
            staff_key = schedule.staff_id
            if staff_key not in by_staff:
                by_staff[staff_key] = {
                    "staff_id": schedule.staff_id,
                    "staff_name": schedule.staff.name,
                    "role": schedule.staff.role.name if schedule.staff.role else None,
                    "total_hours": 0,
                    "shifts": [],
                }

            by_staff[staff_key]["shifts"].append(
                {
                    "schedule_id": schedule.id,
                    "date": schedule.date.isoformat(),
                    "start_time": schedule.start_time.strftime("%H:%M"),
                    "end_time": schedule.end_time.strftime("%H:%M"),
                    "hours": schedule.total_hours,
                    "is_published": schedule.is_published,
                }
            )

            by_staff[staff_key]["total_hours"] += schedule.total_hours
            total_hours += schedule.total_hours

        # Check for coverage gaps (basic implementation)
        coverage_gaps = await self._check_coverage_gaps(
            db, restaurant_id, start_date, end_date, schedules
        )

        return SchedulePreviewResponse(
            date_range={"start": start_date.isoformat(), "end": end_date.isoformat()},
            total_shifts=len(schedules),
            by_date=by_date,
            by_staff=list(by_staff.values()),
            summary={
                "total_hours": total_hours,
                "average_hours_per_staff": total_hours / max(len(by_staff), 1),
                "coverage_gaps": coverage_gaps,
            },
        )

    async def generate_preview_paginated(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date,
        page: int,
        page_size: int,
        sort_by: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> PaginatedPreviewResponse:
        """Generate paginated schedule preview"""

        filters = filters or {}

        # Get staff with schedules in date range
        staff_query = (
            select(Staff)
            .where(and_(Staff.restaurant_id == restaurant_id, Staff.is_active == True))
            .options(selectinload(Staff.role))
        )

        # Apply filters
        if filters.get("role_id"):
            staff_query = staff_query.where(Staff.role_id == filters["role_id"])

        if filters.get("department_id"):
            staff_query = staff_query.join(StaffRole).where(
                StaffRole.department_id == filters["department_id"]
            )

        # Apply sorting
        if sort_by == "name":
            staff_query = staff_query.order_by(Staff.name)
        elif sort_by == "role":
            staff_query = staff_query.join(StaffRole).order_by(StaffRole.name)

        # Get total count
        count_result = await db.execute(
            select(func.count(Staff.id)).select_from(staff_query.subquery())
        )
        total_items = count_result.scalar()

        # Apply pagination
        offset = (page - 1) * page_size
        staff_query = staff_query.offset(offset).limit(page_size)

        staff_result = await db.execute(staff_query)
        staff_members = staff_result.scalars().all()

        # Get schedules for these staff members
        staff_ids = [s.id for s in staff_members]
        schedule_query = select(Schedule).where(
            and_(
                Schedule.restaurant_id == restaurant_id,
                Schedule.staff_id.in_(staff_ids),
                Schedule.date >= start_date,
                Schedule.date <= end_date,
            )
        )

        schedule_result = await db.execute(schedule_query)
        schedules = schedule_result.scalars().all()

        # Group schedules by staff
        schedules_by_staff = {}
        for schedule in schedules:
            if schedule.staff_id not in schedules_by_staff:
                schedules_by_staff[schedule.staff_id] = []
            schedules_by_staff[schedule.staff_id].append(schedule)

        # Build response items
        items = []
        for staff in staff_members:
            staff_schedules = schedules_by_staff.get(staff.id, [])

            items.append(
                {
                    "staff_id": staff.id,
                    "staff_name": staff.name,
                    "role": staff.role.name if staff.role else None,
                    "total_hours": sum(s.total_hours for s in staff_schedules),
                    "shift_count": len(staff_schedules),
                    "schedules": [
                        {
                            "schedule_id": s.id,
                            "date": s.date.isoformat(),
                            "start_time": s.start_time.strftime("%H:%M"),
                            "end_time": s.end_time.strftime("%H:%M"),
                            "hours": s.total_hours,
                            "is_published": s.is_published,
                        }
                        for s in staff_schedules
                    ],
                }
            )

        total_pages = math.ceil(total_items / page_size)

        return PaginatedPreviewResponse(
            items=items,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_previous=page > 1,
        )

    async def publish_schedule(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date,
        published_by: int,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Publish schedule for date range"""

        # Get unpublished schedules in range
        query = select(Schedule).where(
            and_(
                Schedule.restaurant_id == restaurant_id,
                Schedule.date >= start_date,
                Schedule.date <= end_date,
                Schedule.is_published == False,
            )
        )

        result = await db.execute(query)
        schedules = result.scalars().all()

        if not schedules:
            return {
                "success": True,
                "message": "No unpublished schedules found in date range",
                "schedules_published": 0,
            }

        # Mark schedules as published
        now = datetime.utcnow()
        for schedule in schedules:
            schedule.is_published = True
            schedule.published_at = now
            schedule.published_by = published_by
            schedule.updated_at = now

        await db.commit()

        return {
            "success": True,
            "message": f"Published {len(schedules)} schedules",
            "schedules_published": len(schedules),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "published_at": now.isoformat(),
            "notes": notes,
        }

    async def send_schedule_notifications(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date,
        channels: List[str] = ["email", "in_app"],
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send notifications for published schedule"""

        return (
            await schedule_notification_service.send_schedule_published_notifications(
                db, restaurant_id, start_date, end_date, channels, notes
            )
        )

    async def create_shift(
        self,
        db: AsyncSession,
        restaurant_id: int,
        shift_data: ScheduleCreateRequest,
        created_by: int,
    ) -> ScheduleResponse:
        """Create a new shift"""

        # Calculate total hours
        start_datetime = datetime.combine(shift_data.date, shift_data.start_time)
        end_datetime = datetime.combine(shift_data.date, shift_data.end_time)

        # Handle overnight shifts
        if end_datetime <= start_datetime:
            end_datetime += timedelta(days=1)

        total_hours = (end_datetime - start_datetime).total_seconds() / 3600

        # Create schedule
        schedule = Schedule(
            restaurant_id=restaurant_id,
            staff_id=shift_data.staff_id,
            date=shift_data.date,
            start_time=shift_data.start_time,
            end_time=shift_data.end_time,
            total_hours=total_hours,
            break_duration=shift_data.break_duration or 0,
            notes=shift_data.notes,
            created_by=created_by,
            is_published=False,
        )

        db.add(schedule)
        await db.flush()

        # Get staff details for response
        staff_result = await db.execute(
            select(Staff)
            .where(Staff.id == shift_data.staff_id)
            .options(selectinload(Staff.role))
        )
        staff = staff_result.scalar_one()

        await db.commit()

        return ScheduleResponse(
            id=schedule.id,
            staff_id=schedule.staff_id,
            staff_name=staff.name,
            role=staff.role.name if staff.role else None,
            date=schedule.date,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            total_hours=schedule.total_hours,
            break_duration=schedule.break_duration,
            notes=schedule.notes,
            is_published=schedule.is_published,
            published_at=schedule.published_at,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )

    async def update_shift(
        self,
        db: AsyncSession,
        restaurant_id: int,
        shift_id: int,
        update_data: ScheduleUpdateRequest,
        updated_by: int,
    ) -> ScheduleResponse:
        """Update an existing shift"""

        # Get existing schedule
        query = (
            select(Schedule)
            .where(
                and_(Schedule.id == shift_id, Schedule.restaurant_id == restaurant_id)
            )
            .options(selectinload(Schedule.staff).selectinload(Staff.role))
        )

        result = await db.execute(query)
        schedule = result.scalar_one_or_none()

        if not schedule:
            raise ValueError(f"Schedule {shift_id} not found")

        # Track if published schedule is being modified
        was_published = schedule.is_published

        # Update fields
        if update_data.start_time is not None:
            schedule.start_time = update_data.start_time
        if update_data.end_time is not None:
            schedule.end_time = update_data.end_time
        if update_data.break_duration is not None:
            schedule.break_duration = update_data.break_duration
        if update_data.notes is not None:
            schedule.notes = update_data.notes

        # Recalculate total hours
        start_datetime = datetime.combine(schedule.date, schedule.start_time)
        end_datetime = datetime.combine(schedule.date, schedule.end_time)

        if end_datetime <= start_datetime:
            end_datetime += timedelta(days=1)

        schedule.total_hours = (end_datetime - start_datetime).total_seconds() / 3600
        schedule.updated_at = datetime.utcnow()

        await db.commit()

        # Send update notifications if schedule was published
        if was_published:
            await schedule_notification_service.send_schedule_updated_notifications(
                db, restaurant_id, [schedule], ["email", "push"]
            )

        return ScheduleResponse(
            id=schedule.id,
            staff_id=schedule.staff_id,
            staff_name=schedule.staff.name,
            role=schedule.staff.role.name if schedule.staff.role else None,
            date=schedule.date,
            start_time=schedule.start_time,
            end_time=schedule.end_time,
            total_hours=schedule.total_hours,
            break_duration=schedule.break_duration,
            notes=schedule.notes,
            is_published=schedule.is_published,
            published_at=schedule.published_at,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )

    async def delete_shift(self, db: AsyncSession, restaurant_id: int, shift_id: int):
        """Delete a shift"""

        query = select(Schedule).where(
            and_(Schedule.id == shift_id, Schedule.restaurant_id == restaurant_id)
        )

        result = await db.execute(query)
        schedule = result.scalar_one_or_none()

        if not schedule:
            raise ValueError(f"Schedule {shift_id} not found")

        await db.delete(schedule)
        await db.commit()

    async def _check_coverage_gaps(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date,
        schedules: List[Schedule],
    ) -> List[Dict[str, Any]]:
        """Check for potential coverage gaps"""

        # Simple implementation - check for days with less than minimum coverage
        MIN_STAFF_PER_DAY = 3  # Configurable business rule

        coverage_by_date = {}
        for schedule in schedules:
            date_key = schedule.date
            if date_key not in coverage_by_date:
                coverage_by_date[date_key] = 0
            coverage_by_date[date_key] += 1

        gaps = []
        current_date = start_date
        while current_date <= end_date:
            staff_count = coverage_by_date.get(current_date, 0)
            if staff_count < MIN_STAFF_PER_DAY:
                gaps.append(
                    {
                        "date": current_date.isoformat(),
                        "staff_scheduled": staff_count,
                        "minimum_required": MIN_STAFF_PER_DAY,
                        "severity": "high" if staff_count == 0 else "medium",
                    }
                )
            current_date += timedelta(days=1)

        return gaps


# Create singleton service
schedule_service = ScheduleService()
