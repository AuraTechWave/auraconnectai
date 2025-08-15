# backend/modules/tables/services/realtime_table_service.py

"""
Real-time table status service with turn time tracking and heat map data
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case, desc, asc
from sqlalchemy.orm import selectinload
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

from ..models.table_models import (
    Table,
    TableSession,
    TableReservation,
    TableStateLog,
    TableStatus,
    ReservationStatus,
)
from ..websocket.table_websocket import manager as websocket_manager
from core.database_utils import get_db_context

logger = logging.getLogger(__name__)


class TurnTimeAlert(str, Enum):
    """Turn time alert levels"""
    NORMAL = "normal"
    WARNING = "warning"  # Approaching expected turn time
    CRITICAL = "critical"  # Exceeded expected turn time
    EXCESSIVE = "excessive"  # Far exceeded expected turn time


@dataclass
class TableTurnTime:
    """Table turn time tracking data"""
    table_id: int
    table_number: str
    current_duration_minutes: int
    expected_duration_minutes: int
    alert_level: TurnTimeAlert
    guest_count: int
    server_name: Optional[str]
    order_value: Optional[float]
    session_start: datetime
    
    @property
    def overrun_minutes(self) -> int:
        return max(0, self.current_duration_minutes - self.expected_duration_minutes)
    
    @property
    def progress_percentage(self) -> float:
        return min(100.0, (self.current_duration_minutes / self.expected_duration_minutes) * 100)


@dataclass
class TableHeatMapData:
    """Heat map visualization data for a table"""
    table_id: int
    table_number: str
    heat_score: float  # 0-100 scale
    occupancy_rate: float  # 0-100 percentage
    revenue_per_hour: float
    turn_count_today: int
    avg_turn_time_minutes: float
    status: TableStatus
    position_x: int
    position_y: int
    
    @property
    def heat_color(self) -> str:
        """Get heat map color based on score"""
        if self.heat_score >= 80:
            return "#FF4444"  # Hot red
        elif self.heat_score >= 60:
            return "#FF8800"  # Orange
        elif self.heat_score >= 40:
            return "#FFAA00"  # Yellow
        elif self.heat_score >= 20:
            return "#88DD88"  # Light green
        else:
            return "#CCCCCC"  # Cool gray


class RealtimeTableService:
    """Service for real-time table status updates and analytics"""
    
    def __init__(self):
        self.monitoring_task: Optional[asyncio.Task] = None
        self.turn_time_thresholds = {
            "breakfast": 45,  # minutes
            "lunch": 60,
            "dinner": 90,
            "default": 75,
        }
        
    async def start_monitoring(self):
        """Start real-time monitoring task"""
        if self.monitoring_task and not self.monitoring_task.done():
            return
            
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Started table real-time monitoring")
    
    async def stop_monitoring(self):
        """Stop real-time monitoring task"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Stopped table real-time monitoring")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while True:
            try:
                await self._broadcast_realtime_updates()
                await asyncio.sleep(10)  # Update every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(5)
    
    async def _broadcast_realtime_updates(self):
        """Broadcast real-time updates to all connected clients"""
        restaurant_ids = list(websocket_manager.active_connections.keys())
        
        for restaurant_id in restaurant_ids:
            try:
                async with get_db_context() as db:
                    # Get turn time alerts
                    turn_alerts = await self.get_turn_time_alerts(db, restaurant_id)
                    
                    # Get occupancy changes
                    occupancy_data = await self.get_occupancy_summary(db, restaurant_id)
                    
                    # Get heat map data
                    heat_map = await self.get_heat_map_data(db, restaurant_id)
                    
                    # Broadcast updates
                    await websocket_manager.broadcast_to_restaurant(
                        restaurant_id,
                        {
                            "type": "realtime_update",
                            "data": {
                                "turn_alerts": [alert.__dict__ for alert in turn_alerts],
                                "occupancy": occupancy_data,
                                "heat_map": [hm.__dict__ for hm in heat_map],
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        }
                    )
                    
            except Exception as e:
                logger.error(f"Error broadcasting updates for restaurant {restaurant_id}: {e}")
    
    async def get_turn_time_alerts(
        self, 
        db: AsyncSession, 
        restaurant_id: int
    ) -> List[TableTurnTime]:
        """Get tables with turn time alerts"""
        
        # Get all occupied tables with active sessions
        query = (
            select(Table, TableSession)
            .join(TableSession, and_(
                Table.id == TableSession.table_id,
                TableSession.end_time.is_(None)
            ))
            .where(and_(
                Table.restaurant_id == restaurant_id,
                Table.status == TableStatus.OCCUPIED
            ))
            .options(selectinload(TableSession.server))
        )
        
        result = await db.execute(query)
        table_sessions = result.all()
        
        turn_times = []
        current_time = datetime.utcnow()
        
        for table, session in table_sessions:
            # Calculate current duration
            duration = current_time - session.start_time
            current_minutes = int(duration.total_seconds() / 60)
            
            # Determine expected duration based on time of day
            expected_minutes = self._get_expected_turn_time(session.start_time)
            
            # Calculate alert level
            alert_level = self._calculate_alert_level(current_minutes, expected_minutes)
            
            # Get order value if available
            order_value = None
            if session.order_id:
                # TODO: Get order value from orders module
                pass
            
            turn_time = TableTurnTime(
                table_id=table.id,
                table_number=table.table_number,
                current_duration_minutes=current_minutes,
                expected_duration_minutes=expected_minutes,
                alert_level=alert_level,
                guest_count=session.guest_count,
                server_name=session.server.name if session.server else None,
                order_value=order_value,
                session_start=session.start_time,
            )
            
            # Only include tables with warnings or alerts
            if alert_level != TurnTimeAlert.NORMAL:
                turn_times.append(turn_time)
        
        # Sort by alert level priority
        alert_priority = {
            TurnTimeAlert.EXCESSIVE: 4,
            TurnTimeAlert.CRITICAL: 3,
            TurnTimeAlert.WARNING: 2,
            TurnTimeAlert.NORMAL: 1,
        }
        
        turn_times.sort(key=lambda tt: alert_priority[tt.alert_level], reverse=True)
        return turn_times
    
    def _get_expected_turn_time(self, start_time: datetime) -> int:
        """Get expected turn time based on time of day"""
        hour = start_time.hour
        
        if 6 <= hour < 11:  # Breakfast
            return self.turn_time_thresholds["breakfast"]
        elif 11 <= hour < 15:  # Lunch
            return self.turn_time_thresholds["lunch"]
        elif 17 <= hour < 23:  # Dinner
            return self.turn_time_thresholds["dinner"]
        else:
            return self.turn_time_thresholds["default"]
    
    def _calculate_alert_level(self, current_minutes: int, expected_minutes: int) -> TurnTimeAlert:
        """Calculate alert level based on turn time"""
        if current_minutes < expected_minutes * 0.8:
            return TurnTimeAlert.NORMAL
        elif current_minutes < expected_minutes:
            return TurnTimeAlert.WARNING
        elif current_minutes < expected_minutes * 1.5:
            return TurnTimeAlert.CRITICAL
        else:
            return TurnTimeAlert.EXCESSIVE
    
    async def get_occupancy_summary(
        self, 
        db: AsyncSession, 
        restaurant_id: int
    ) -> Dict[str, Any]:
        """Get current occupancy summary"""
        
        # Get table counts by status
        status_query = (
            select(
                Table.status,
                func.count(Table.id).label('count')
            )
            .where(and_(
                Table.restaurant_id == restaurant_id,
                Table.is_active == True
            ))
            .group_by(Table.status)
        )
        
        result = await db.execute(status_query)
        status_counts = {row.status: row.count for row in result.all()}
        
        total_tables = sum(status_counts.values())
        occupied_tables = status_counts.get(TableStatus.OCCUPIED, 0)
        available_tables = status_counts.get(TableStatus.AVAILABLE, 0)
        reserved_tables = status_counts.get(TableStatus.RESERVED, 0)
        
        # Calculate occupancy rate
        occupancy_rate = (occupied_tables / total_tables * 100) if total_tables > 0 else 0
        
        # Get guest count
        guest_query = (
            select(func.sum(TableSession.guest_count))
            .where(and_(
                TableSession.restaurant_id == restaurant_id,
                TableSession.end_time.is_(None)
            ))
        )
        
        result = await db.execute(guest_query)
        current_guests = result.scalar() or 0
        
        # Calculate average turn time for today
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        avg_turn_query = (
            select(func.avg(
                func.extract('epoch', TableSession.end_time - TableSession.start_time) / 60
            ))
            .where(and_(
                TableSession.restaurant_id == restaurant_id,
                TableSession.start_time >= today_start,
                TableSession.end_time.isnot(None)
            ))
        )
        
        result = await db.execute(avg_turn_query)
        avg_turn_time = result.scalar() or 0
        
        return {
            "total_tables": total_tables,
            "occupied_tables": occupied_tables,
            "available_tables": available_tables,
            "reserved_tables": reserved_tables,
            "blocked_tables": total_tables - occupied_tables - available_tables - reserved_tables,
            "occupancy_rate": round(occupancy_rate, 1),
            "current_guests": current_guests,
            "avg_turn_time_today": round(avg_turn_time, 1),
            "status_distribution": status_counts,
        }
    
    async def get_heat_map_data(
        self, 
        db: AsyncSession, 
        restaurant_id: int,
        time_period: str = "today"
    ) -> List[TableHeatMapData]:
        """Get heat map visualization data"""
        
        # Determine time range
        if time_period == "today":
            start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = datetime.now()
        elif time_period == "week":
            start_time = datetime.now() - timedelta(days=7)
            end_time = datetime.now()
        else:
            start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_time = datetime.now()
        
        # Get tables with analytics
        query = (
            select(
                Table.id,
                Table.table_number,
                Table.status,
                Table.position_x,
                Table.position_y,
                func.count(TableSession.id).label('session_count'),
                func.avg(
                    func.extract('epoch', TableSession.end_time - TableSession.start_time) / 60
                ).label('avg_turn_time'),
                func.sum(TableSession.guest_count).label('total_guests'),
            )
            .outerjoin(TableSession, and_(
                Table.id == TableSession.table_id,
                TableSession.start_time >= start_time,
                TableSession.start_time <= end_time,
                TableSession.end_time.isnot(None)
            ))
            .where(and_(
                Table.restaurant_id == restaurant_id,
                Table.is_active == True
            ))
            .group_by(Table.id, Table.table_number, Table.status, Table.position_x, Table.position_y)
        )
        
        result = await db.execute(query)
        table_data = result.all()
        
        heat_map_data = []
        period_hours = (end_time - start_time).total_seconds() / 3600
        
        for row in table_data:
            # Calculate occupancy rate
            session_count = row.session_count or 0
            avg_turn_time = row.avg_turn_time or 0
            total_occupied_hours = (session_count * avg_turn_time / 60) if avg_turn_time > 0 else 0
            occupancy_rate = (total_occupied_hours / period_hours * 100) if period_hours > 0 else 0
            
            # Calculate revenue per hour (placeholder - would need order integration)
            revenue_per_hour = session_count * 50.0  # Estimated $50 per session
            
            # Calculate heat score (0-100) based on multiple factors
            heat_score = self._calculate_heat_score(
                occupancy_rate=occupancy_rate,
                session_count=session_count,
                revenue_per_hour=revenue_per_hour,
                avg_turn_time=avg_turn_time
            )
            
            heat_data = TableHeatMapData(
                table_id=row.id,
                table_number=row.table_number,
                heat_score=heat_score,
                occupancy_rate=min(100.0, occupancy_rate),
                revenue_per_hour=revenue_per_hour,
                turn_count_today=session_count,
                avg_turn_time_minutes=avg_turn_time,
                status=row.status,
                position_x=row.position_x,
                position_y=row.position_y,
            )
            
            heat_map_data.append(heat_data)
        
        return heat_map_data
    
    def _calculate_heat_score(
        self,
        occupancy_rate: float,
        session_count: int,
        revenue_per_hour: float,
        avg_turn_time: float
    ) -> float:
        """Calculate heat score for table (0-100)"""
        
        # Normalize factors to 0-100 scale
        occupancy_score = min(100, occupancy_rate)
        
        # Session count score (assume 8 sessions per day is maximum)
        session_score = min(100, (session_count / 8) * 100)
        
        # Revenue score (assume $400/hour is maximum)
        revenue_score = min(100, (revenue_per_hour / 400) * 100)
        
        # Turn time efficiency score (faster turns = higher score)
        # Assume 60 minutes is optimal, penalize longer times
        if avg_turn_time > 0:
            turn_efficiency = max(0, 100 - ((avg_turn_time - 60) / 60 * 50))
        else:
            turn_efficiency = 50  # Neutral for no data
        
        # Weighted average
        heat_score = (
            occupancy_score * 0.3 +
            session_score * 0.25 +
            revenue_score * 0.25 +
            turn_efficiency * 0.2
        )
        
        return round(heat_score, 1)
    
    async def get_table_turn_analytics(
        self,
        db: AsyncSession,
        restaurant_id: int,
        start_date: datetime,
        end_date: datetime,
        table_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get detailed turn time analytics"""
        
        # Base query for completed sessions
        query = (
            select(
                TableSession.table_id,
                Table.table_number,
                func.count(TableSession.id).label('total_turns'),
                func.avg(
                    func.extract('epoch', TableSession.end_time - TableSession.start_time) / 60
                ).label('avg_turn_time'),
                func.min(
                    func.extract('epoch', TableSession.end_time - TableSession.start_time) / 60
                ).label('min_turn_time'),
                func.max(
                    func.extract('epoch', TableSession.end_time - TableSession.start_time) / 60
                ).label('max_turn_time'),
                func.avg(TableSession.guest_count).label('avg_party_size'),
                func.sum(TableSession.guest_count).label('total_guests'),
            )
            .join(Table, Table.id == TableSession.table_id)
            .where(and_(
                TableSession.restaurant_id == restaurant_id,
                TableSession.start_time >= start_date,
                TableSession.start_time <= end_date,
                TableSession.end_time.isnot(None)
            ))
            .group_by(TableSession.table_id, Table.table_number)
        )
        
        if table_id:
            query = query.where(TableSession.table_id == table_id)
        
        result = await db.execute(query)
        analytics_data = result.all()
        
        # Calculate summary statistics
        total_turns = sum(row.total_turns for row in analytics_data)
        total_guests = sum(row.total_guests for row in analytics_data)
        
        if analytics_data:
            overall_avg_turn_time = sum(
                row.avg_turn_time * row.total_turns for row in analytics_data
            ) / total_turns if total_turns > 0 else 0
            
            overall_avg_party_size = total_guests / total_turns if total_turns > 0 else 0
        else:
            overall_avg_turn_time = 0
            overall_avg_party_size = 0
        
        # Format table analytics
        table_analytics = []
        for row in analytics_data:
            # Calculate turn efficiency score
            expected_turn_time = 75  # Default expected time
            efficiency_score = min(100, (expected_turn_time / row.avg_turn_time) * 100) if row.avg_turn_time > 0 else 0
            
            table_analytics.append({
                "table_id": row.table_id,
                "table_number": row.table_number,
                "total_turns": row.total_turns,
                "avg_turn_time_minutes": round(row.avg_turn_time, 1),
                "min_turn_time_minutes": round(row.min_turn_time, 1),
                "max_turn_time_minutes": round(row.max_turn_time, 1),
                "avg_party_size": round(row.avg_party_size, 1),
                "total_guests": row.total_guests,
                "efficiency_score": round(efficiency_score, 1),
                "revenue_potential": row.total_turns * 50,  # Estimated revenue
            })
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "summary": {
                "total_turns": total_turns,
                "total_guests": total_guests,
                "avg_turn_time_minutes": round(overall_avg_turn_time, 1),
                "avg_party_size": round(overall_avg_party_size, 1),
                "tables_analyzed": len(analytics_data),
            },
            "table_analytics": sorted(
                table_analytics, 
                key=lambda x: x["efficiency_score"], 
                reverse=True
            ),
        }
    
    async def get_peak_hours_analysis(
        self,
        db: AsyncSession,
        restaurant_id: int,
        date: datetime
    ) -> Dict[str, Any]:
        """Analyze peak hours and occupancy patterns"""
        
        start_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        # Get hourly occupancy data
        hourly_query = (
            select(
                func.extract('hour', TableSession.start_time).label('hour'),
                func.count(TableSession.id).label('sessions_started'),
                func.avg(TableSession.guest_count).label('avg_party_size'),
                func.avg(
                    func.extract('epoch', TableSession.end_time - TableSession.start_time) / 60
                ).label('avg_duration')
            )
            .where(and_(
                TableSession.restaurant_id == restaurant_id,
                TableSession.start_time >= start_date,
                TableSession.start_time < end_date,
                TableSession.end_time.isnot(None)
            ))
            .group_by(func.extract('hour', TableSession.start_time))
            .order_by('hour')
        )
        
        result = await db.execute(hourly_query)
        hourly_data = result.all()
        
        # Process hourly data
        hours_analysis = []
        peak_hour = None
        max_sessions = 0
        
        for row in hourly_data:
            hour_data = {
                "hour": int(row.hour),
                "hour_display": f"{int(row.hour):02d}:00",
                "sessions_started": row.sessions_started,
                "avg_party_size": round(row.avg_party_size, 1),
                "avg_duration_minutes": round(row.avg_duration, 1),
                "estimated_capacity_used": row.sessions_started * row.avg_party_size,
            }
            hours_analysis.append(hour_data)
            
            if row.sessions_started > max_sessions:
                max_sessions = row.sessions_started
                peak_hour = hour_data
        
        # Identify service periods
        service_periods = self._identify_service_periods(hours_analysis)
        
        return {
            "date": date.strftime("%Y-%m-%d"),
            "peak_hour": peak_hour,
            "total_sessions": sum(h["sessions_started"] for h in hours_analysis),
            "hourly_breakdown": hours_analysis,
            "service_periods": service_periods,
            "recommendations": self._generate_peak_hour_recommendations(hours_analysis),
        }
    
    def _identify_service_periods(self, hourly_data: List[Dict]) -> List[Dict]:
        """Identify breakfast, lunch, dinner periods from data"""
        periods = []
        
        # Define potential service windows
        service_windows = [
            {"name": "Breakfast", "start": 6, "end": 11},
            {"name": "Lunch", "start": 11, "end": 15},
            {"name": "Dinner", "start": 17, "end": 22},
        ]
        
        for window in service_windows:
            period_data = [
                h for h in hourly_data 
                if window["start"] <= h["hour"] < window["end"]
            ]
            
            if period_data:
                total_sessions = sum(h["sessions_started"] for h in period_data)
                peak_hour = max(period_data, key=lambda x: x["sessions_started"])
                
                periods.append({
                    "name": window["name"],
                    "start_hour": window["start"],
                    "end_hour": window["end"],
                    "total_sessions": total_sessions,
                    "peak_hour": peak_hour["hour"],
                    "peak_sessions": peak_hour["sessions_started"],
                    "avg_duration": round(
                        sum(h["avg_duration_minutes"] for h in period_data) / len(period_data), 1
                    ) if period_data else 0,
                })
        
        return periods
    
    def _generate_peak_hour_recommendations(self, hourly_data: List[Dict]) -> List[str]:
        """Generate recommendations based on peak hour analysis"""
        recommendations = []
        
        if not hourly_data:
            return recommendations
        
        # Find peak hours
        peak_sessions = max(h["sessions_started"] for h in hourly_data)
        peak_hours = [h for h in hourly_data if h["sessions_started"] >= peak_sessions * 0.8]
        
        if len(peak_hours) > 3:
            recommendations.append(
                "Consider staggered reservation times during peak hours to distribute load"
            )
        
        # Check for long average durations
        long_duration_hours = [h for h in hourly_data if h["avg_duration_minutes"] > 90]
        if long_duration_hours:
            recommendations.append(
                "Monitor turn times during high-duration periods to optimize table turnover"
            )
        
        # Check for low utilization periods
        avg_sessions = sum(h["sessions_started"] for h in hourly_data) / len(hourly_data)
        low_util_hours = [h for h in hourly_data if h["sessions_started"] < avg_sessions * 0.3]
        
        if low_util_hours:
            recommendations.append(
                "Consider promotional strategies for low-utilization hours"
            )
        
        return recommendations


# Create singleton service
realtime_table_service = RealtimeTableService()