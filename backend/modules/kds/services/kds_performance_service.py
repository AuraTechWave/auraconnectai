# backend/modules/kds/services/kds_performance_service.py

"""
KDS Performance Tracking and Metrics Service
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging
from dataclasses import dataclass
from enum import Enum

from ..models.kds_models import (
    KDSOrderItem,
    KitchenStation,
    DisplayStatus,
    StationType,
)
from modules.orders.models.order_models import Order, OrderItem
from modules.staff.models.staff_models import StaffMember

logger = logging.getLogger(__name__)


@dataclass
class StationMetrics:
    """Performance metrics for a kitchen station"""

    station_id: int
    station_name: str
    total_items: int
    completed_items: int
    average_prep_time: float  # minutes
    average_wait_time: float  # minutes
    items_per_hour: float
    completion_rate: float  # percentage
    late_order_percentage: float
    recall_rate: float
    busiest_hour: Optional[int]
    current_load: int
    staff_performance: Dict[int, Dict[str, Any]]


@dataclass
class KitchenAnalytics:
    """Overall kitchen performance analytics"""

    total_orders: int
    total_items: int
    average_order_time: float  # minutes
    peak_hours: List[int]
    bottleneck_stations: List[str]
    staff_rankings: List[Dict[str, Any]]
    hourly_throughput: Dict[int, int]
    daily_trends: Dict[str, Any]
    efficiency_score: float  # 0-100


class TimeRange(Enum):
    """Time range options for analytics"""

    LAST_HOUR = "last_hour"
    TODAY = "today"
    LAST_24_HOURS = "last_24_hours"
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"
    CUSTOM = "custom"


class KDSPerformanceService:
    """Service for tracking and analyzing KDS performance"""

    def __init__(self, db: Session):
        self.db = db

    def get_station_metrics(
        self,
        station_id: int,
        time_range: TimeRange = TimeRange.TODAY,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> StationMetrics:
        """Get performance metrics for a specific station"""
        
        # Determine date range
        date_filter = self._get_date_filter(time_range, start_date, end_date)
        
        # Get station info
        station = self.db.query(KitchenStation).filter_by(id=station_id).first()
        if not station:
            raise ValueError(f"Station {station_id} not found")
        
        # Query KDS items for the station
        items_query = self.db.query(KDSOrderItem).filter(
            and_(
                KDSOrderItem.station_id == station_id,
                KDSOrderItem.received_at >= date_filter["start"],
                KDSOrderItem.received_at <= date_filter["end"],
            )
        )
        
        all_items = items_query.all()
        completed_items = [
            item for item in all_items if item.status == DisplayStatus.COMPLETED
        ]
        
        # Calculate metrics
        total_items = len(all_items)
        completed_count = len(completed_items)
        
        # Average prep time (for completed items)
        avg_prep_time = 0
        if completed_items:
            prep_times = [
                (item.completed_at - item.started_at).total_seconds() / 60
                for item in completed_items
                if item.started_at and item.completed_at
            ]
            avg_prep_time = sum(prep_times) / len(prep_times) if prep_times else 0
        
        # Average wait time (from received to completed)
        avg_wait_time = 0
        if completed_items:
            wait_times = [
                (item.completed_at - item.received_at).total_seconds() / 60
                for item in completed_items
                if item.completed_at
            ]
            avg_wait_time = sum(wait_times) / len(wait_times) if wait_times else 0
        
        # Items per hour
        hours_elapsed = (date_filter["end"] - date_filter["start"]).total_seconds() / 3600
        items_per_hour = completed_count / hours_elapsed if hours_elapsed > 0 else 0
        
        # Completion rate
        completion_rate = (completed_count / total_items * 100) if total_items > 0 else 0
        
        # Late orders (items that exceeded target time)
        late_items = [item for item in all_items if item.is_late]
        late_percentage = (len(late_items) / total_items * 100) if total_items > 0 else 0
        
        # Recall rate
        recalled_items = [item for item in all_items if item.recall_count > 0]
        recall_rate = (len(recalled_items) / total_items * 100) if total_items > 0 else 0
        
        # Busiest hour
        busiest_hour = self._get_busiest_hour(station_id, date_filter)
        
        # Current load
        current_load = self.db.query(KDSOrderItem).filter(
            and_(
                KDSOrderItem.station_id == station_id,
                KDSOrderItem.status.in_([DisplayStatus.PENDING, DisplayStatus.IN_PROGRESS]),
            )
        ).count()
        
        # Staff performance
        staff_performance = self._get_staff_performance(station_id, date_filter)
        
        return StationMetrics(
            station_id=station_id,
            station_name=station.name,
            total_items=total_items,
            completed_items=completed_count,
            average_prep_time=round(avg_prep_time, 2),
            average_wait_time=round(avg_wait_time, 2),
            items_per_hour=round(items_per_hour, 2),
            completion_rate=round(completion_rate, 2),
            late_order_percentage=round(late_percentage, 2),
            recall_rate=round(recall_rate, 2),
            busiest_hour=busiest_hour,
            current_load=current_load,
            staff_performance=staff_performance,
        )

    def get_kitchen_analytics(
        self,
        restaurant_id: int,
        time_range: TimeRange = TimeRange.TODAY,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> KitchenAnalytics:
        """Get overall kitchen performance analytics"""
        
        date_filter = self._get_date_filter(time_range, start_date, end_date)
        
        # Get all stations for the restaurant
        stations = self.db.query(KitchenStation).all()
        
        # Total orders and items
        total_items_query = self.db.query(KDSOrderItem).filter(
            and_(
                KDSOrderItem.received_at >= date_filter["start"],
                KDSOrderItem.received_at <= date_filter["end"],
            )
        )
        
        total_items = total_items_query.count()
        
        # Get unique orders (need to join with OrderItem to get actual order_id)
        from modules.orders.models.order_models import OrderItem
        
        unique_orders = (
            self.db.query(OrderItem.order_id)
            .join(KDSOrderItem, KDSOrderItem.order_item_id == OrderItem.id)
            .filter(
                and_(
                    KDSOrderItem.received_at >= date_filter["start"],
                    KDSOrderItem.received_at <= date_filter["end"],
                )
            )
            .distinct()
            .all()
        )
        
        total_orders = len(unique_orders)
        
        # Average order time
        completed_items = total_items_query.filter(
            KDSOrderItem.status == DisplayStatus.COMPLETED
        ).all()
        
        avg_order_time = 0
        if completed_items:
            order_times = [
                (item.completed_at - item.received_at).total_seconds() / 60
                for item in completed_items
                if item.completed_at
            ]
            avg_order_time = sum(order_times) / len(order_times) if order_times else 0
        
        # Peak hours
        peak_hours = self._get_peak_hours(date_filter)
        
        # Bottleneck stations
        bottleneck_stations = self._identify_bottlenecks(stations, date_filter)
        
        # Staff rankings
        staff_rankings = self._get_staff_rankings(date_filter)
        
        # Hourly throughput
        hourly_throughput = self._get_hourly_throughput(date_filter)
        
        # Daily trends
        daily_trends = self._get_daily_trends(date_filter)
        
        # Efficiency score (0-100)
        efficiency_score = self._calculate_efficiency_score(
            completion_rate=len(completed_items) / total_items * 100 if total_items > 0 else 0,
            avg_order_time=avg_order_time,
            recall_rate=self._get_overall_recall_rate(date_filter),
        )
        
        return KitchenAnalytics(
            total_orders=total_orders,
            total_items=total_items,
            average_order_time=round(avg_order_time, 2),
            peak_hours=peak_hours,
            bottleneck_stations=bottleneck_stations,
            staff_rankings=staff_rankings,
            hourly_throughput=hourly_throughput,
            daily_trends=daily_trends,
            efficiency_score=round(efficiency_score, 2),
        )

    def get_real_time_metrics(self, station_id: Optional[int] = None) -> Dict[str, Any]:
        """Get real-time metrics for monitoring"""
        
        from sqlalchemy.orm import joinedload
        
        base_query = self.db.query(KDSOrderItem).options(
            joinedload(KDSOrderItem.station)
        )
        
        if station_id:
            base_query = base_query.filter(KDSOrderItem.station_id == station_id)
        
        # Current active items with station data loaded
        active_items = base_query.filter(
            KDSOrderItem.status.in_([DisplayStatus.PENDING, DisplayStatus.IN_PROGRESS])
        ).all()
        
        # Items by status
        status_counts = {}
        for status in DisplayStatus:
            count = base_query.filter(KDSOrderItem.status == status).count()
            status_counts[status.value] = count
        
        # Average wait times for active items
        wait_times = []
        critical_items = []
        warning_items = []
        
        now = datetime.utcnow()
        for item in active_items:
            wait_time = (now - item.received_at).total_seconds() / 60
            wait_times.append(wait_time)
            
            if item.station:
                if wait_time > item.station.critical_time_minutes:
                    critical_items.append({
                        "id": item.id,
                        "order_item_id": item.order_item_id,
                        "display_name": item.display_name,
                        "wait_time": round(wait_time, 2),
                    })
                elif wait_time > item.station.warning_time_minutes:
                    warning_items.append({
                        "id": item.id,
                        "order_item_id": item.order_item_id,
                        "display_name": item.display_name,
                        "wait_time": round(wait_time, 2),
                    })
        
        avg_current_wait = sum(wait_times) / len(wait_times) if wait_times else 0
        
        return {
            "active_items_count": len(active_items),
            "status_breakdown": status_counts,
            "average_current_wait_time": round(avg_current_wait, 2),
            "critical_items": critical_items,
            "warning_items": warning_items,
            "oldest_item_wait_time": round(max(wait_times), 2) if wait_times else 0,
        }

    def get_staff_performance(
        self,
        staff_id: int,
        time_range: TimeRange = TimeRange.TODAY,
    ) -> Dict[str, Any]:
        """Get performance metrics for a specific staff member"""
        
        date_filter = self._get_date_filter(time_range)
        
        # Items completed by this staff member
        completed_items = self.db.query(KDSOrderItem).filter(
            and_(
                KDSOrderItem.completed_by_id == staff_id,
                KDSOrderItem.status == DisplayStatus.COMPLETED,
                KDSOrderItem.completed_at >= date_filter["start"],
                KDSOrderItem.completed_at <= date_filter["end"],
            )
        ).all()
        
        # Items started by this staff member
        started_items = self.db.query(KDSOrderItem).filter(
            and_(
                KDSOrderItem.started_by_id == staff_id,
                KDSOrderItem.started_at >= date_filter["start"],
                KDSOrderItem.started_at <= date_filter["end"],
            )
        ).all()
        
        # Calculate metrics
        total_completed = len(completed_items)
        total_started = len(started_items)
        
        # Average completion time
        completion_times = []
        for item in completed_items:
            if item.started_at and item.completed_at:
                time_taken = (item.completed_at - item.started_at).total_seconds() / 60
                completion_times.append(time_taken)
        
        avg_completion_time = (
            sum(completion_times) / len(completion_times) if completion_times else 0
        )
        
        # Recall rate for items handled
        recalled_items = [item for item in completed_items if item.recall_count > 0]
        recall_rate = (
            len(recalled_items) / total_completed * 100 if total_completed > 0 else 0
        )
        
        # Hourly productivity
        hourly_productivity = {}
        for item in completed_items:
            hour = item.completed_at.hour
            hourly_productivity[hour] = hourly_productivity.get(hour, 0) + 1
        
        # Get staff info
        staff = self.db.query(StaffMember).filter_by(id=staff_id).first()
        
        return {
            "staff_id": staff_id,
            "staff_name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
            "items_completed": total_completed,
            "items_started": total_started,
            "average_completion_time": round(avg_completion_time, 2),
            "accuracy_rate": round(100 - recall_rate, 2),
            "recall_rate": round(recall_rate, 2),
            "hourly_productivity": hourly_productivity,
            "peak_productivity_hour": (
                max(hourly_productivity, key=hourly_productivity.get)
                if hourly_productivity
                else None
            ),
        }

    def _get_date_filter(
        self,
        time_range: TimeRange,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, datetime]:
        """Get date filter based on time range"""
        
        now = datetime.utcnow()
        
        if time_range == TimeRange.CUSTOM:
            if not start_date or not end_date:
                raise ValueError("Custom range requires start_date and end_date")
            return {"start": start_date, "end": end_date}
        
        elif time_range == TimeRange.LAST_HOUR:
            return {"start": now - timedelta(hours=1), "end": now}
        
        elif time_range == TimeRange.TODAY:
            return {
                "start": now.replace(hour=0, minute=0, second=0, microsecond=0),
                "end": now,
            }
        
        elif time_range == TimeRange.LAST_24_HOURS:
            return {"start": now - timedelta(hours=24), "end": now}
        
        elif time_range == TimeRange.LAST_WEEK:
            return {"start": now - timedelta(days=7), "end": now}
        
        elif time_range == TimeRange.LAST_MONTH:
            return {"start": now - timedelta(days=30), "end": now}
        
        else:
            return {
                "start": now.replace(hour=0, minute=0, second=0, microsecond=0),
                "end": now,
            }

    def _get_busiest_hour(
        self, station_id: int, date_filter: Dict[str, datetime]
    ) -> Optional[int]:
        """Get the busiest hour for a station"""
        
        hourly_counts = (
            self.db.query(
                func.extract("hour", KDSOrderItem.received_at).label("hour"),
                func.count(KDSOrderItem.id).label("count"),
            )
            .filter(
                and_(
                    KDSOrderItem.station_id == station_id,
                    KDSOrderItem.received_at >= date_filter["start"],
                    KDSOrderItem.received_at <= date_filter["end"],
                )
            )
            .group_by("hour")
            .order_by(func.count(KDSOrderItem.id).desc())
            .first()
        )
        
        return int(hourly_counts.hour) if hourly_counts else None

    def _get_staff_performance(
        self, station_id: int, date_filter: Dict[str, datetime]
    ) -> Dict[int, Dict[str, Any]]:
        """Get performance metrics for all staff at a station"""
        
        staff_metrics = {}
        
        # Get all staff who worked at this station
        staff_items = (
            self.db.query(
                KDSOrderItem.completed_by_id,
                func.count(KDSOrderItem.id).label("count"),
                func.avg(
                    func.extract(
                        "epoch",
                        KDSOrderItem.completed_at - KDSOrderItem.started_at
                    ) / 60
                ).label("avg_time"),
            )
            .filter(
                and_(
                    KDSOrderItem.station_id == station_id,
                    KDSOrderItem.status == DisplayStatus.COMPLETED,
                    KDSOrderItem.completed_at >= date_filter["start"],
                    KDSOrderItem.completed_at <= date_filter["end"],
                    KDSOrderItem.completed_by_id.isnot(None),
                )
            )
            .group_by(KDSOrderItem.completed_by_id)
            .all()
        )
        
        for staff_id, count, avg_time in staff_items:
            staff = self.db.query(StaffMember).filter_by(id=staff_id).first()
            staff_metrics[staff_id] = {
                "name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
                "items_completed": count,
                "average_time": round(avg_time, 2) if avg_time else 0,
            }
        
        return staff_metrics

    def _get_peak_hours(self, date_filter: Dict[str, datetime]) -> List[int]:
        """Identify peak hours based on order volume"""
        
        hourly_counts = (
            self.db.query(
                func.extract("hour", KDSOrderItem.received_at).label("hour"),
                func.count(KDSOrderItem.id).label("count"),
            )
            .filter(
                and_(
                    KDSOrderItem.received_at >= date_filter["start"],
                    KDSOrderItem.received_at <= date_filter["end"],
                )
            )
            .group_by("hour")
            .order_by(func.count(KDSOrderItem.id).desc())
            .limit(3)
            .all()
        )
        
        return [int(hour) for hour, _ in hourly_counts]

    def _identify_bottlenecks(
        self, stations: List[KitchenStation], date_filter: Dict[str, datetime]
    ) -> List[str]:
        """Identify bottleneck stations based on wait times"""
        
        bottlenecks = []
        
        for station in stations:
            # Get average wait time for this station
            avg_wait = (
                self.db.query(
                    func.avg(
                        func.extract(
                            "epoch",
                            func.coalesce(
                                KDSOrderItem.completed_at,
                                func.current_timestamp()
                            ) - KDSOrderItem.received_at
                        ) / 60
                    )
                )
                .filter(
                    and_(
                        KDSOrderItem.station_id == station.id,
                        KDSOrderItem.received_at >= date_filter["start"],
                        KDSOrderItem.received_at <= date_filter["end"],
                    )
                )
                .scalar()
            )
            
            # If average wait time exceeds critical threshold, it's a bottleneck
            if avg_wait and avg_wait > station.critical_time_minutes:
                bottlenecks.append(station.name)
        
        return bottlenecks

    def _get_staff_rankings(
        self, date_filter: Dict[str, datetime]
    ) -> List[Dict[str, Any]]:
        """Get staff rankings based on performance"""
        
        rankings = (
            self.db.query(
                KDSOrderItem.completed_by_id,
                func.count(KDSOrderItem.id).label("items_completed"),
                func.avg(
                    func.extract(
                        "epoch",
                        KDSOrderItem.completed_at - KDSOrderItem.started_at
                    ) / 60
                ).label("avg_time"),
            )
            .filter(
                and_(
                    KDSOrderItem.status == DisplayStatus.COMPLETED,
                    KDSOrderItem.completed_at >= date_filter["start"],
                    KDSOrderItem.completed_at <= date_filter["end"],
                    KDSOrderItem.completed_by_id.isnot(None),
                )
            )
            .group_by(KDSOrderItem.completed_by_id)
            .order_by(func.count(KDSOrderItem.id).desc())
            .limit(10)
            .all()
        )
        
        staff_rankings = []
        for rank, (staff_id, items, avg_time) in enumerate(rankings, 1):
            staff = self.db.query(StaffMember).filter_by(id=staff_id).first()
            staff_rankings.append({
                "rank": rank,
                "staff_id": staff_id,
                "staff_name": f"{staff.first_name} {staff.last_name}" if staff else "Unknown",
                "items_completed": items,
                "average_time": round(avg_time, 2) if avg_time else 0,
            })
        
        return staff_rankings

    def _get_hourly_throughput(
        self, date_filter: Dict[str, datetime]
    ) -> Dict[int, int]:
        """Get hourly throughput data"""
        
        hourly_data = (
            self.db.query(
                func.extract("hour", KDSOrderItem.completed_at).label("hour"),
                func.count(KDSOrderItem.id).label("count"),
            )
            .filter(
                and_(
                    KDSOrderItem.status == DisplayStatus.COMPLETED,
                    KDSOrderItem.completed_at >= date_filter["start"],
                    KDSOrderItem.completed_at <= date_filter["end"],
                )
            )
            .group_by("hour")
            .all()
        )
        
        return {int(hour): count for hour, count in hourly_data}

    def _get_daily_trends(self, date_filter: Dict[str, datetime]) -> Dict[str, Any]:
        """Get daily trend data"""
        
        # Average completion time by day of week
        dow_data = (
            self.db.query(
                func.extract("dow", KDSOrderItem.completed_at).label("dow"),
                func.avg(
                    func.extract(
                        "epoch",
                        KDSOrderItem.completed_at - KDSOrderItem.received_at
                    ) / 60
                ).label("avg_time"),
                func.count(KDSOrderItem.id).label("count"),
            )
            .filter(
                and_(
                    KDSOrderItem.status == DisplayStatus.COMPLETED,
                    KDSOrderItem.completed_at >= date_filter["start"],
                    KDSOrderItem.completed_at <= date_filter["end"],
                )
            )
            .group_by("dow")
            .all()
        )
        
        days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
        daily_trends = {}
        
        for dow, avg_time, count in dow_data:
            day_name = days[int(dow)]
            daily_trends[day_name] = {
                "average_time": round(avg_time, 2) if avg_time else 0,
                "total_items": count,
            }
        
        return daily_trends

    def _get_overall_recall_rate(self, date_filter: Dict[str, datetime]) -> float:
        """Calculate overall recall rate"""
        
        total_items = self.db.query(KDSOrderItem).filter(
            and_(
                KDSOrderItem.received_at >= date_filter["start"],
                KDSOrderItem.received_at <= date_filter["end"],
            )
        ).count()
        
        recalled_items = self.db.query(KDSOrderItem).filter(
            and_(
                KDSOrderItem.received_at >= date_filter["start"],
                KDSOrderItem.received_at <= date_filter["end"],
                KDSOrderItem.recall_count > 0,
            )
        ).count()
        
        return (recalled_items / total_items * 100) if total_items > 0 else 0

    def _calculate_efficiency_score(
        self, completion_rate: float, avg_order_time: float, recall_rate: float
    ) -> float:
        """Calculate overall efficiency score (0-100)"""
        
        # Weighted scoring
        # - Completion rate: 40%
        # - Speed (inverse of avg time): 30%
        # - Quality (inverse of recall rate): 30%
        
        completion_score = completion_rate * 0.4
        
        # Speed score (assuming 15 minutes is ideal, 30+ is poor)
        if avg_order_time <= 15:
            speed_score = 30
        elif avg_order_time >= 30:
            speed_score = 0
        else:
            speed_score = (30 - avg_order_time) / 15 * 30
        
        # Quality score (inverse of recall rate)
        quality_score = (100 - recall_rate) * 0.3
        
        return completion_score + speed_score + quality_score

    def generate_performance_report(
        self,
        restaurant_id: int,
        time_range: TimeRange = TimeRange.TODAY,
        format: str = "json",
    ) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        
        # Get analytics
        analytics = self.get_kitchen_analytics(restaurant_id, time_range)
        
        # Get metrics for each station
        stations = self.db.query(KitchenStation).all()
        station_metrics = []
        
        for station in stations:
            try:
                metrics = self.get_station_metrics(station.id, time_range)
                station_metrics.append(metrics.__dict__)
            except Exception as e:
                logger.error(f"Error getting metrics for station {station.id}: {e}")
        
        # Get real-time status
        real_time = self.get_real_time_metrics()
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "time_range": time_range.value,
            "restaurant_id": restaurant_id,
            "summary": {
                "total_orders": analytics.total_orders,
                "total_items": analytics.total_items,
                "average_order_time": analytics.average_order_time,
                "efficiency_score": analytics.efficiency_score,
            },
            "analytics": analytics.__dict__,
            "station_metrics": station_metrics,
            "real_time_status": real_time,
            "recommendations": self._generate_recommendations(analytics, station_metrics),
        }
        
        if format == "json":
            return report
        else:
            # Could add other formats like PDF, CSV, etc.
            return report

    def _generate_recommendations(
        self, analytics: KitchenAnalytics, station_metrics: List[Dict]
    ) -> List[str]:
        """Generate recommendations based on performance data"""
        
        recommendations = []
        
        # Check for bottlenecks
        if analytics.bottleneck_stations:
            recommendations.append(
                f"Consider adding staff to these bottleneck stations: {', '.join(analytics.bottleneck_stations)}"
            )
        
        # Check efficiency score
        if analytics.efficiency_score < 70:
            recommendations.append(
                "Overall efficiency is below target. Review workflows and staff training."
            )
        
        # Check for high recall rates
        for metrics in station_metrics:
            if metrics.get("recall_rate", 0) > 10:
                recommendations.append(
                    f"High recall rate at {metrics['station_name']}. Review quality control procedures."
                )
        
        # Check for understaffed periods
        if analytics.peak_hours:
            recommendations.append(
                f"Peak hours are {analytics.peak_hours}. Ensure adequate staffing during these times."
            )
        
        return recommendations