"""
Table analytics service for turn time tracking and occupancy analysis.

This service provides comprehensive analytics for table management including
turn times, occupancy rates, and performance metrics.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, extract
from sqlalchemy.orm import selectinload
import logging
from decimal import Decimal
from collections import defaultdict

from ..models.table_models import (
    Table, TableSession, TableReservation, 
    TableStatus, ReservationStatus
)
from modules.orders.models.order_models import Order

logger = logging.getLogger(__name__)


class TableAnalyticsService:
    """Service for table analytics and metrics"""
    
    async def get_current_analytics(
        self,
        db: AsyncSession,
        restaurant_id: int,
        floor_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get current real-time analytics for tables"""
        
        # Base query for tables
        table_query = select(Table).where(
            and_(
                Table.restaurant_id == restaurant_id,
                Table.is_active == True
            )
        )
        
        if floor_id:
            table_query = table_query.where(Table.floor_id == floor_id)
            
        # Get all tables
        result = await db.execute(table_query)
        tables = result.scalars().all()
        total_tables = len(tables)
        
        # Count tables by status
        status_counts = defaultdict(int)
        for table in tables:
            status_counts[table.status.value] += 1
            
        # Get active sessions for turn time calculation
        session_query = (
            select(TableSession)
            .join(Table)
            .where(
                and_(
                    Table.restaurant_id == restaurant_id,
                    TableSession.end_time.is_(None)
                )
            )
        )
        
        if floor_id:
            session_query = session_query.where(Table.floor_id == floor_id)
            
        result = await db.execute(session_query)
        active_sessions = result.scalars().all()
        
        # Calculate turn times
        turn_times = []
        total_guests = 0
        
        for session in active_sessions:
            duration = (datetime.utcnow() - session.start_time).total_seconds() / 60
            turn_times.append(duration)
            total_guests += session.guest_count or 0
            
        # Calculate metrics
        occupancy_rate = (
            (status_counts.get(TableStatus.OCCUPIED.value, 0) / total_tables * 100)
            if total_tables > 0 else 0
        )
        
        avg_turn_time = sum(turn_times) / len(turn_times) if turn_times else 0
        
        # Get today's completed sessions for historical turn time
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)
        
        completed_query = (
            select(
                func.avg(
                    extract('epoch', TableSession.end_time - TableSession.start_time) / 60
                ).label('avg_duration'),
                func.count(TableSession.id).label('count')
            )
            .join(Table)
            .where(
                and_(
                    Table.restaurant_id == restaurant_id,
                    TableSession.end_time.isnot(None),
                    TableSession.start_time >= today_start
                )
            )
        )
        
        if floor_id:
            completed_query = completed_query.where(Table.floor_id == floor_id)
            
        result = await db.execute(completed_query)
        completed_stats = result.one()
        
        return {
            "overview": {
                "total_tables": total_tables,
                "occupied_tables": status_counts.get(TableStatus.OCCUPIED.value, 0),
                "available_tables": status_counts.get(TableStatus.AVAILABLE.value, 0),
                "reserved_tables": status_counts.get(TableStatus.RESERVED.value, 0),
                "occupancy_rate": round(occupancy_rate, 1),
                "total_guests_seated": total_guests
            },
            "turn_times": {
                "current_average_minutes": round(avg_turn_time, 1),
                "today_average_minutes": round(completed_stats.avg_duration or 0, 1),
                "active_sessions": len(active_sessions),
                "completed_today": completed_stats.count or 0
            },
            "status_breakdown": dict(status_counts),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    async def get_turn_time_analytics(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date,
        floor_id: Optional[int] = None,
        group_by: str = "day"  # day, hour, day_of_week
    ) -> Dict[str, Any]:
        """Get detailed turn time analytics for a period"""
        
        # Build base query
        query = (
            select(
                TableSession,
                Table,
                extract('epoch', TableSession.end_time - TableSession.start_time) / 60
            )
            .join(Table)
            .where(
                and_(
                    Table.restaurant_id == restaurant_id,
                    TableSession.end_time.isnot(None),
                    TableSession.start_time >= start_date,
                    TableSession.end_time <= end_date + timedelta(days=1)
                )
            )
        )
        
        if floor_id:
            query = query.where(Table.floor_id == floor_id)
            
        result = await db.execute(query)
        sessions_data = [
            {
                "session": session,
                "table": table,
                "duration_minutes": duration
            }
            for session, table, duration in result.all()
        ]
        
        # Group data based on requested grouping
        grouped_data = defaultdict(lambda: {
            "sessions": [],
            "total_duration": 0,
            "guest_counts": []
        })
        
        for data in sessions_data:
            session = data["session"]
            
            # Determine group key
            if group_by == "hour":
                key = session.start_time.strftime("%H:00")
            elif group_by == "day_of_week":
                key = session.start_time.strftime("%A")
            else:  # day
                key = session.start_time.date().isoformat()
                
            grouped_data[key]["sessions"].append(data)
            grouped_data[key]["total_duration"] += data["duration_minutes"]
            grouped_data[key]["guest_counts"].append(session.guest_count or 0)
            
        # Calculate statistics for each group
        analytics = {}
        for key, group in grouped_data.items():
            session_count = len(group["sessions"])
            durations = [s["duration_minutes"] for s in group["sessions"]]
            
            analytics[key] = {
                "session_count": session_count,
                "average_turn_time": round(sum(durations) / session_count, 1),
                "min_turn_time": round(min(durations), 1),
                "max_turn_time": round(max(durations), 1),
                "total_guests": sum(group["guest_counts"]),
                "average_party_size": round(
                    sum(group["guest_counts"]) / session_count, 1
                )
            }
            
        # Calculate overall statistics
        all_durations = [
            data["duration_minutes"] 
            for group in grouped_data.values() 
            for data in group["sessions"]
        ]
        
        overall_stats = {
            "total_sessions": len(all_durations),
            "average_turn_time": round(
                sum(all_durations) / len(all_durations), 1
            ) if all_durations else 0,
            "min_turn_time": round(min(all_durations), 1) if all_durations else 0,
            "max_turn_time": round(max(all_durations), 1) if all_durations else 0,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "group_by": group_by
            }
        }
        
        return {
            "analytics": analytics,
            "overall": overall_stats
        }
        
    async def get_table_performance_metrics(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date,
        table_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get performance metrics for individual tables"""
        
        # Query for table performance
        query = (
            select(
                Table,
                func.count(TableSession.id).label('session_count'),
                func.avg(
                    extract('epoch', TableSession.end_time - TableSession.start_time) / 60
                ).label('avg_turn_time'),
                func.sum(TableSession.guest_count).label('total_guests'),
                func.sum(Order.total_amount).label('total_revenue')
            )
            .outerjoin(
                TableSession,
                and_(
                    Table.id == TableSession.table_id,
                    TableSession.start_time >= start_date,
                    TableSession.end_time <= end_date + timedelta(days=1),
                    TableSession.end_time.isnot(None)
                )
            )
            .outerjoin(Order, TableSession.order_id == Order.id)
            .where(Table.restaurant_id == restaurant_id)
            .group_by(Table.id)
        )
        
        if table_id:
            query = query.where(Table.id == table_id)
            
        result = await db.execute(query)
        
        metrics = []
        for table, session_count, avg_turn_time, total_guests, total_revenue in result.all():
            # Calculate utilization rate (hours used / available hours)
            days = (end_date - start_date).days + 1
            available_hours = days * 12  # Assuming 12 operating hours per day
            
            used_hours = (
                (session_count * (avg_turn_time or 0)) / 60 
                if session_count else 0
            )
            
            utilization_rate = (
                (used_hours / available_hours * 100) 
                if available_hours > 0 else 0
            )
            
            metrics.append({
                "table": {
                    "id": table.id,
                    "number": table.table_number,
                    "floor_id": table.floor_id,
                    "capacity": {
                        "min": table.min_capacity,
                        "max": table.max_capacity
                    }
                },
                "performance": {
                    "session_count": session_count or 0,
                    "average_turn_time_minutes": round(avg_turn_time or 0, 1),
                    "total_guests_served": total_guests or 0,
                    "total_revenue": float(total_revenue or 0),
                    "revenue_per_session": (
                        float(total_revenue or 0) / session_count 
                        if session_count else 0
                    ),
                    "utilization_rate": round(utilization_rate, 1)
                }
            })
            
        # Sort by revenue
        metrics.sort(key=lambda x: x["performance"]["total_revenue"], reverse=True)
        
        return metrics
        
    async def get_average_turn_time(
        self,
        db: AsyncSession,
        restaurant_id: int,
        lookback_days: int = 7
    ) -> Optional[float]:
        """Get average turn time for the restaurant"""
        
        since = datetime.utcnow() - timedelta(days=lookback_days)
        
        query = (
            select(
                func.avg(
                    extract('epoch', TableSession.end_time - TableSession.start_time) / 60
                )
            )
            .join(Table)
            .where(
                and_(
                    Table.restaurant_id == restaurant_id,
                    TableSession.end_time.isnot(None),
                    TableSession.start_time >= since
                )
            )
        )
        
        result = await db.execute(query)
        avg_time = result.scalar()
        
        return float(avg_time) if avg_time else None
        
    async def get_peak_hours_analysis(
        self,
        db: AsyncSession,
        restaurant_id: int,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """Analyze peak hours for table occupancy"""
        
        since = datetime.utcnow() - timedelta(days=lookback_days)
        
        # Query sessions by hour
        query = (
            select(
                extract('hour', TableSession.start_time).label('hour'),
                extract('dow', TableSession.start_time).label('day_of_week'),
                func.count(TableSession.id).label('session_count'),
                func.avg(TableSession.guest_count).label('avg_guests')
            )
            .join(Table)
            .where(
                and_(
                    Table.restaurant_id == restaurant_id,
                    TableSession.start_time >= since
                )
            )
            .group_by('hour', 'day_of_week')
        )
        
        result = await db.execute(query)
        
        # Process data into heat map format
        heat_map = defaultdict(lambda: defaultdict(int))
        hourly_totals = defaultdict(int)
        
        for hour, day_of_week, count, avg_guests in result.all():
            heat_map[int(day_of_week)][int(hour)] = count
            hourly_totals[int(hour)] += count
            
        # Find peak hours
        peak_hours = sorted(
            hourly_totals.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        # Convert to readable format
        days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        heat_map_data = []
        for day_num, hours in heat_map.items():
            for hour, count in hours.items():
                heat_map_data.append({
                    "day": days[day_num],
                    "hour": f"{hour:02d}:00",
                    "sessions": count
                })
                
        return {
            "heat_map": heat_map_data,
            "peak_hours": [
                {"hour": f"{hour:02d}:00", "total_sessions": count}
                for hour, count in peak_hours
            ],
            "analysis_period_days": lookback_days
        }
        
    async def get_reservation_analytics(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get analytics for table reservations"""
        
        query = (
            select(
                TableReservation.status,
                func.count(TableReservation.id).label('count'),
                func.avg(TableReservation.guest_count).label('avg_party_size')
            )
            .join(Table)
            .where(
                and_(
                    Table.restaurant_id == restaurant_id,
                    TableReservation.reservation_date >= start_date,
                    TableReservation.reservation_date <= end_date
                )
            )
            .group_by(TableReservation.status)
        )
        
        result = await db.execute(query)
        
        status_breakdown = {}
        total_reservations = 0
        total_guests = 0
        
        for status, count, avg_party in result.all():
            status_breakdown[status.value] = {
                "count": count,
                "average_party_size": round(avg_party or 0, 1)
            }
            total_reservations += count
            total_guests += count * (avg_party or 0)
            
        # Calculate key metrics
        confirmation_rate = (
            (status_breakdown.get(ReservationStatus.CONFIRMED.value, {}).get('count', 0) / 
             total_reservations * 100)
            if total_reservations > 0 else 0
        )
        
        no_show_rate = (
            (status_breakdown.get(ReservationStatus.NO_SHOW.value, {}).get('count', 0) / 
             total_reservations * 100)
            if total_reservations > 0 else 0
        )
        
        return {
            "summary": {
                "total_reservations": total_reservations,
                "total_expected_guests": round(total_guests),
                "confirmation_rate": round(confirmation_rate, 1),
                "no_show_rate": round(no_show_rate, 1)
            },
            "status_breakdown": status_breakdown,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }