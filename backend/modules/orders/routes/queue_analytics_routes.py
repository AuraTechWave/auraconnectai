"""
API routes for queue analytics and dashboards.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case
from datetime import datetime, timedelta

from core.database import get_db
from core.decorators import handle_api_errors
from ...auth.services.auth_service import get_current_user
from ...auth.models import User
from ..models.queue_models import (
    OrderQueue,
    QueueItem,
    QueueMetrics,
    QueueType,
    QueueStatus,
    QueueItemStatus,
)
from ..models.order_models import Order

router = APIRouter(prefix="/api/v1/orders/queues/analytics", tags=["queue-analytics"])


@router.get("/dashboard")
@handle_api_errors
async def get_queue_dashboard(
    time_range: str = Query("today", regex="^(today|week|month|custom)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    queue_ids: Optional[List[int]] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get comprehensive queue dashboard data.

    Includes:
    - Current queue status for all queues
    - Performance metrics
    - Volume trends
    - Staff utilization
    """
    # Determine date range
    if time_range == "today":
        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end = datetime.utcnow()
    elif time_range == "week":
        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()
    elif time_range == "month":
        start = datetime.utcnow() - timedelta(days=30)
        end = datetime.utcnow()
    else:  # custom
        if not start_date or not end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date and end_date required for custom range",
            )
        start = start_date
        end = end_date

    # Get queues
    queue_query = db.query(OrderQueue)
    if queue_ids:
        queue_query = queue_query.filter(OrderQueue.id.in_(queue_ids))
    queues = queue_query.all()

    # Build dashboard data
    dashboard = {
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "range": time_range,
        },
        "queues": [],
        "summary": {
            "total_items_processed": 0,
            "avg_wait_time": 0,
            "on_time_percentage": 0,
            "busiest_hour": None,
            "staff_utilization": 0,
        },
        "trends": {"hourly_volume": [], "wait_time_trend": [], "completion_rate": []},
    }

    # Process each queue
    for queue in queues:
        queue_data = await _get_queue_analytics(db, queue, start, end)
        dashboard["queues"].append(queue_data)

        # Update summary
        dashboard["summary"]["total_items_processed"] += queue_data["metrics"][
            "items_completed"
        ]

    # Calculate overall metrics
    if dashboard["queues"]:
        total_wait_time = sum(
            q["metrics"]["avg_wait_time"] * q["metrics"]["items_completed"]
            for q in dashboard["queues"]
        )
        total_items = dashboard["summary"]["total_items_processed"]

        if total_items > 0:
            dashboard["summary"]["avg_wait_time"] = round(
                total_wait_time / total_items, 1
            )

        # On-time percentage
        total_on_time = sum(
            q["metrics"]["on_time_percentage"] * q["metrics"]["items_completed"]
            for q in dashboard["queues"]
        )
        if total_items > 0:
            dashboard["summary"]["on_time_percentage"] = round(
                total_on_time / total_items, 1
            )

    # Get trends
    dashboard["trends"] = await _get_queue_trends(db, queue_ids, start, end)

    return dashboard


@router.get("/performance/{queue_id}")
@handle_api_errors
async def get_queue_performance(
    queue_id: int,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed performance metrics for a specific queue.

    Includes:
    - Wait time distribution
    - Completion rates by hour
    - Staff performance
    - Bottleneck analysis
    """
    queue = db.query(OrderQueue).filter(OrderQueue.id == queue_id).first()
    if not queue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Queue {queue_id} not found"
        )

    start_date = datetime.utcnow() - timedelta(days=days)

    # Get metrics
    metrics = (
        db.query(QueueMetrics)
        .filter(
            QueueMetrics.queue_id == queue_id, QueueMetrics.metric_date >= start_date
        )
        .all()
    )

    # Calculate performance indicators
    performance = {
        "queue_id": queue_id,
        "queue_name": queue.name,
        "period_days": days,
        "wait_time_distribution": _calculate_wait_time_distribution(metrics),
        "hourly_performance": _calculate_hourly_performance(metrics),
        "daily_trends": _calculate_daily_trends(metrics),
        "bottlenecks": _identify_bottlenecks(db, queue_id, start_date),
        "recommendations": _generate_recommendations(metrics),
    }

    return performance


@router.get("/staff-utilization")
@handle_api_errors
async def get_staff_utilization(
    start_date: datetime = Query(...),
    end_date: datetime = Query(...),
    queue_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get staff utilization metrics across queues.

    Shows:
    - Items processed per staff member
    - Average handling time
    - Efficiency scores
    """
    query = db.query(
        QueueItem.assigned_to_id,
        func.count(QueueItem.id).label("items_processed"),
        func.avg(QueueItem.prep_time_actual).label("avg_prep_time"),
        func.avg(
            case(
                (QueueItem.prep_time_actual <= 15, 100),
                (QueueItem.prep_time_actual <= 20, 80),
                (QueueItem.prep_time_actual <= 30, 60),
                else_=40,
            )
        ).label("efficiency_score"),
    ).filter(
        QueueItem.completed_at >= start_date,
        QueueItem.completed_at <= end_date,
        QueueItem.assigned_to_id.isnot(None),
    )

    if queue_id:
        query = query.filter(QueueItem.queue_id == queue_id)

    staff_stats = query.group_by(QueueItem.assigned_to_id).all()

    # Format results
    utilization = []
    for stat in staff_stats:
        # Get staff info
        from ...staff.models import StaffMember

        staff = (
            db.query(StaffMember).filter(StaffMember.id == stat.assigned_to_id).first()
        )

        if staff:
            utilization.append(
                {
                    "staff_id": stat.assigned_to_id,
                    "staff_name": f"{staff.first_name} {staff.last_name}",
                    "items_processed": stat.items_processed,
                    "avg_prep_time": (
                        round(stat.avg_prep_time, 1) if stat.avg_prep_time else 0
                    ),
                    "efficiency_score": (
                        round(stat.efficiency_score, 1) if stat.efficiency_score else 0
                    ),
                }
            )

    # Sort by items processed
    utilization.sort(key=lambda x: x["items_processed"], reverse=True)

    return {
        "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
        "staff_utilization": utilization,
        "summary": {
            "total_staff": len(utilization),
            "total_items": sum(u["items_processed"] for u in utilization),
            "avg_efficiency": (
                round(
                    sum(u["efficiency_score"] for u in utilization) / len(utilization),
                    1,
                )
                if utilization
                else 0
            ),
        },
    }


@router.get("/peak-analysis")
@handle_api_errors
async def get_peak_analysis(
    days: int = Query(7, ge=1, le=30),
    queue_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze peak hours and busy periods.

    Helps with:
    - Staff scheduling
    - Capacity planning
    - Preparation optimization
    """
    start_date = datetime.utcnow() - timedelta(days=days)

    # Get hourly volume data
    query = db.query(
        func.extract("hour", QueueItem.queued_at).label("hour"),
        func.extract("dow", QueueItem.queued_at).label("day_of_week"),
        func.count(QueueItem.id).label("item_count"),
        func.avg(QueueItem.wait_time_actual).label("avg_wait"),
    ).filter(QueueItem.queued_at >= start_date)

    if queue_id:
        query = query.filter(QueueItem.queue_id == queue_id)

    hourly_data = query.group_by("hour", "day_of_week").all()

    # Process data into heat map
    heat_map = {}
    for data in hourly_data:
        hour = int(data.hour)
        dow = int(data.day_of_week)

        if hour not in heat_map:
            heat_map[hour] = {}

        heat_map[hour][dow] = {
            "volume": data.item_count,
            "avg_wait": round(data.avg_wait, 1) if data.avg_wait else 0,
        }

    # Identify peak hours
    peak_hours = []
    for hour, days in heat_map.items():
        total_volume = sum(d["volume"] for d in days.values())
        avg_volume = total_volume / len(days) if days else 0

        peak_hours.append(
            {
                "hour": hour,
                "avg_volume": round(avg_volume, 1),
                "peak_days": [
                    dow
                    for dow, data in days.items()
                    if data["volume"] > avg_volume * 1.2
                ],
            }
        )

    # Sort by volume
    peak_hours.sort(key=lambda x: x["avg_volume"], reverse=True)

    return {
        "period_days": days,
        "heat_map": heat_map,
        "peak_hours": peak_hours[:5],  # Top 5 peak hours
        "recommendations": _generate_peak_recommendations(peak_hours),
    }


# Helper functions
async def _get_queue_analytics(
    db: Session, queue: OrderQueue, start: datetime, end: datetime
) -> Dict[str, Any]:
    """Get analytics for a single queue"""
    # Current status
    current_items = (
        db.query(QueueItem.status, func.count(QueueItem.id))
        .filter(
            QueueItem.queue_id == queue.id,
            QueueItem.status.notin_(
                [QueueItemStatus.COMPLETED, QueueItemStatus.CANCELLED]
            ),
        )
        .group_by(QueueItem.status)
        .all()
    )

    status_counts = {status.value: count for status, count in current_items}

    # Period metrics
    period_items = (
        db.query(QueueItem)
        .filter(
            QueueItem.queue_id == queue.id,
            QueueItem.queued_at >= start,
            QueueItem.queued_at <= end,
        )
        .all()
    )

    completed_items = [i for i in period_items if i.status == QueueItemStatus.COMPLETED]

    # Calculate metrics
    metrics = {
        "items_queued": len(period_items),
        "items_completed": len(completed_items),
        "items_cancelled": len(
            [i for i in period_items if i.status == QueueItemStatus.CANCELLED]
        ),
        "avg_wait_time": 0,
        "max_wait_time": 0,
        "on_time_percentage": 0,
    }

    if completed_items:
        wait_times = [i.wait_time_actual for i in completed_items if i.wait_time_actual]
        if wait_times:
            metrics["avg_wait_time"] = round(sum(wait_times) / len(wait_times), 1)
            metrics["max_wait_time"] = max(wait_times)

        # On-time calculation
        on_time = len(
            [
                i
                for i in completed_items
                if i.completed_at
                and i.estimated_ready_time
                and i.completed_at <= i.estimated_ready_time
            ]
        )
        metrics["on_time_percentage"] = round(on_time / len(completed_items) * 100, 1)

    return {
        "queue_id": queue.id,
        "queue_name": queue.name,
        "queue_type": queue.queue_type.value,
        "status": queue.status.value,
        "current_status": status_counts,
        "metrics": metrics,
    }


async def _get_queue_trends(
    db: Session, queue_ids: Optional[List[int]], start: datetime, end: datetime
) -> Dict[str, Any]:
    """Get trend data for queues"""
    # Hourly volume
    query = db.query(
        func.date_trunc("hour", QueueItem.queued_at).label("hour"),
        func.count(QueueItem.id).label("count"),
    ).filter(QueueItem.queued_at >= start, QueueItem.queued_at <= end)

    if queue_ids:
        query = query.filter(QueueItem.queue_id.in_(queue_ids))

    hourly_volume = query.group_by("hour").order_by("hour").all()

    # Wait time trend
    wait_query = db.query(
        func.date_trunc("hour", QueueItem.completed_at).label("hour"),
        func.avg(QueueItem.wait_time_actual).label("avg_wait"),
    ).filter(
        QueueItem.completed_at >= start,
        QueueItem.completed_at <= end,
        QueueItem.wait_time_actual.isnot(None),
    )

    if queue_ids:
        wait_query = wait_query.filter(QueueItem.queue_id.in_(queue_ids))

    wait_trend = wait_query.group_by("hour").order_by("hour").all()

    return {
        "hourly_volume": [
            {"hour": h.hour.isoformat(), "count": h.count} for h in hourly_volume
        ],
        "wait_time_trend": [
            {"hour": w.hour.isoformat(), "avg_wait": round(w.avg_wait, 1)}
            for w in wait_trend
        ],
    }


def _calculate_wait_time_distribution(
    metrics: List[QueueMetrics],
) -> List[Dict[str, Any]]:
    """Calculate wait time distribution"""
    distribution = {"0-5": 0, "5-10": 0, "10-15": 0, "15-20": 0, "20+": 0}

    for metric in metrics:
        if metric.avg_wait_time <= 5:
            distribution["0-5"] += metric.items_completed
        elif metric.avg_wait_time <= 10:
            distribution["5-10"] += metric.items_completed
        elif metric.avg_wait_time <= 15:
            distribution["10-15"] += metric.items_completed
        elif metric.avg_wait_time <= 20:
            distribution["15-20"] += metric.items_completed
        else:
            distribution["20+"] += metric.items_completed

    return [{"range": k, "count": v, "percentage": 0} for k, v in distribution.items()]


def _calculate_hourly_performance(metrics: List[QueueMetrics]) -> List[Dict[str, Any]]:
    """Calculate performance by hour of day"""
    hourly = {}

    for metric in metrics:
        hour = metric.hour_of_day
        if hour not in hourly:
            hourly[hour] = {"volume": 0, "completed": 0, "wait_time": 0, "count": 0}

        hourly[hour]["volume"] += metric.items_queued
        hourly[hour]["completed"] += metric.items_completed
        hourly[hour]["wait_time"] += metric.avg_wait_time
        hourly[hour]["count"] += 1

    # Calculate averages
    performance = []
    for hour, data in hourly.items():
        performance.append(
            {
                "hour": hour,
                "avg_volume": round(data["volume"] / data["count"], 1),
                "completion_rate": (
                    round(data["completed"] / data["volume"] * 100, 1)
                    if data["volume"] > 0
                    else 0
                ),
                "avg_wait_time": round(data["wait_time"] / data["count"], 1),
            }
        )

    return sorted(performance, key=lambda x: x["hour"])


def _calculate_daily_trends(metrics: List[QueueMetrics]) -> List[Dict[str, Any]]:
    """Calculate daily trend data"""
    daily = {}

    for metric in metrics:
        date = metric.metric_date.date()
        if date not in daily:
            daily[date] = {"volume": 0, "completed": 0, "wait_time": 0, "on_time": 0}

        daily[date]["volume"] += metric.items_queued
        daily[date]["completed"] += metric.items_completed
        daily[date]["wait_time"] += metric.avg_wait_time * metric.items_completed
        daily[date]["on_time"] += metric.on_time_percentage * metric.items_completed

    # Format results
    trends = []
    for date, data in daily.items():
        trends.append(
            {
                "date": date.isoformat(),
                "volume": data["volume"],
                "completed": data["completed"],
                "avg_wait_time": (
                    round(data["wait_time"] / data["completed"], 1)
                    if data["completed"] > 0
                    else 0
                ),
                "on_time_percentage": (
                    round(data["on_time"] / data["completed"], 1)
                    if data["completed"] > 0
                    else 0
                ),
            }
        )

    return sorted(trends, key=lambda x: x["date"])


def _identify_bottlenecks(
    db: Session, queue_id: int, start_date: datetime
) -> List[Dict[str, Any]]:
    """Identify bottlenecks in queue processing"""
    bottlenecks = []

    # Long wait times
    long_waits = (
        db.query(
            func.date_trunc("hour", QueueItem.queued_at).label("hour"),
            func.count(QueueItem.id).label("count"),
        )
        .filter(
            QueueItem.queue_id == queue_id,
            QueueItem.queued_at >= start_date,
            QueueItem.wait_time_actual > 20,  # More than 20 minutes
        )
        .group_by("hour")
        .having(func.count(QueueItem.id) > 5)
        .all()
    )

    for wait in long_waits:
        bottlenecks.append(
            {
                "type": "long_wait",
                "time": wait.hour.isoformat(),
                "severity": "high" if wait.count > 10 else "medium",
                "details": f"{wait.count} items waited >20 minutes",
            }
        )

    return bottlenecks


def _generate_recommendations(metrics: List[QueueMetrics]) -> List[Dict[str, Any]]:
    """Generate recommendations based on metrics"""
    recommendations = []

    if metrics:
        avg_wait = sum(m.avg_wait_time for m in metrics) / len(metrics)
        if avg_wait > 15:
            recommendations.append(
                {
                    "priority": "high",
                    "type": "staffing",
                    "message": "Average wait time exceeds 15 minutes. Consider adding staff during peak hours.",
                }
            )

        low_completion = [m for m in metrics if m.on_time_percentage < 80]
        if len(low_completion) > len(metrics) * 0.3:
            recommendations.append(
                {
                    "priority": "medium",
                    "type": "process",
                    "message": "On-time completion below 80% for 30% of periods. Review preparation processes.",
                }
            )

    return recommendations


def _generate_peak_recommendations(peak_hours: List[Dict[str, Any]]) -> List[str]:
    """Generate recommendations for peak hour management"""
    recommendations = []

    if peak_hours and peak_hours[0]["avg_volume"] > 50:
        recommendations.append(
            f"Peak hour at {peak_hours[0]['hour']}:00 with {peak_hours[0]['avg_volume']} average items. "
            "Ensure adequate staffing during this period."
        )

    # Check for consecutive peak hours
    consecutive_peaks = []
    for i in range(len(peak_hours) - 1):
        if abs(peak_hours[i]["hour"] - peak_hours[i + 1]["hour"]) == 1:
            consecutive_peaks.append(peak_hours[i]["hour"])

    if len(consecutive_peaks) >= 3:
        recommendations.append(
            f"Extended peak period from {min(consecutive_peaks)}:00 to {max(consecutive_peaks)+1}:00. "
            "Consider staggered staff shifts for coverage."
        )

    return recommendations
