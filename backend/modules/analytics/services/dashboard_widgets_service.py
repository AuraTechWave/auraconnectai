# backend/modules/analytics/services/dashboard_widgets_service.py

import asyncio
import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc
import json

from backend.core.database import get_db
from ..models.analytics_models import SalesAnalyticsSnapshot, AggregationPeriod
from ..schemas.realtime_schemas import (
    WidgetConfiguration, DashboardLayout, WidgetDataResponse, 
    RealtimeMetricResponse, HourlyTrendPoint
)
from .realtime_metrics_service import realtime_metrics_service
from .sales_report_service import SalesReportService
from .trend_service import TrendService

logger = logging.getLogger(__name__)


class WidgetType:
    """Widget type constants"""
    METRIC_CARD = "metric_card"
    LINE_CHART = "line_chart"
    BAR_CHART = "bar_chart"
    PIE_CHART = "pie_chart"
    TABLE = "table"
    GAUGE = "gauge"
    PROGRESS_BAR = "progress_bar"
    SPARKLINE = "sparkline"
    HEATMAP = "heatmap"
    KPI_CARD = "kpi_card"


class DashboardWidgetsService:
    """Service for managing dashboard widgets and layouts"""
    
    def __init__(self):
        self.widget_data_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_ttl = 60  # seconds
        self.widget_processors = {
            WidgetType.METRIC_CARD: self._process_metric_card,
            WidgetType.LINE_CHART: self._process_line_chart,
            WidgetType.BAR_CHART: self._process_bar_chart,
            WidgetType.PIE_CHART: self._process_pie_chart,
            WidgetType.TABLE: self._process_table,
            WidgetType.GAUGE: self._process_gauge,
            WidgetType.PROGRESS_BAR: self._process_progress_bar,
            WidgetType.SPARKLINE: self._process_sparkline,
            WidgetType.HEATMAP: self._process_heatmap,
            WidgetType.KPI_CARD: self._process_kpi_card
        }
    
    async def get_widget_data(
        self, 
        widget_config: WidgetConfiguration,
        force_refresh: bool = False
    ) -> WidgetDataResponse:
        """Get data for a specific widget"""
        
        cache_key = f"{widget_config.widget_id}_{hash(str(widget_config.dict()))}"
        
        # Check cache first
        if not force_refresh and cache_key in self.widget_data_cache:
            cached_data = self.widget_data_cache[cache_key]
            if (datetime.now() - cached_data["timestamp"]).total_seconds() < self.cache_ttl:
                return WidgetDataResponse(
                    widget_id=widget_config.widget_id,
                    widget_type=widget_config.widget_type,
                    data=cached_data["data"],
                    timestamp=cached_data["timestamp"],
                    cache_status="cached"
                )
        
        # Process widget data
        try:
            processor = self.widget_processors.get(widget_config.widget_type)
            if not processor:
                raise ValueError(f"Unknown widget type: {widget_config.widget_type}")
            
            widget_data = await processor(widget_config)
            
            # Cache the result
            self.widget_data_cache[cache_key] = {
                "data": widget_data,
                "timestamp": datetime.now()
            }
            
            return WidgetDataResponse(
                widget_id=widget_config.widget_id,
                widget_type=widget_config.widget_type,
                data=widget_data,
                timestamp=datetime.now(),
                cache_status="fresh"
            )
            
        except Exception as e:
            logger.error(f"Error processing widget {widget_config.widget_id}: {e}")
            raise
    
    async def get_dashboard_layout_data(
        self, 
        layout: DashboardLayout,
        force_refresh: bool = False
    ) -> Dict[str, WidgetDataResponse]:
        """Get data for all widgets in a dashboard layout"""
        
        results = {}
        
        # Process widgets concurrently
        tasks = []
        for widget_config in layout.widgets:
            task = asyncio.create_task(
                self.get_widget_data(widget_config, force_refresh)
            )
            tasks.append((widget_config.widget_id, task))
        
        # Wait for all widgets to complete
        for widget_id, task in tasks:
            try:
                widget_response = await task
                results[widget_id] = widget_response
            except Exception as e:
                logger.error(f"Error processing widget {widget_id}: {e}")
                # Create error response
                results[widget_id] = WidgetDataResponse(
                    widget_id=widget_id,
                    widget_type="error",
                    data={"error": str(e)},
                    timestamp=datetime.now(),
                    cache_status="error"
                )
        
        return results
    
    async def create_default_dashboard_layout(self, user_id: int) -> DashboardLayout:
        """Create a default dashboard layout for a user"""
        
        widgets = [
            # Revenue metric card
            WidgetConfiguration(
                widget_id="revenue_today",
                widget_type=WidgetType.METRIC_CARD,
                title="Today's Revenue",
                position={"x": 0, "y": 0, "width": 3, "height": 2},
                data_source="realtime_metric",
                config={
                    "metric_name": "revenue_current",
                    "format": "currency",
                    "show_change": True,
                    "color_scheme": "success"
                }
            ),
            
            # Orders metric card
            WidgetConfiguration(
                widget_id="orders_today",
                widget_type=WidgetType.METRIC_CARD,
                title="Today's Orders",
                position={"x": 3, "y": 0, "width": 3, "height": 2},
                data_source="realtime_metric",
                config={
                    "metric_name": "orders_current",
                    "format": "number",
                    "show_change": True,
                    "color_scheme": "primary"
                }
            ),
            
            # Customers metric card
            WidgetConfiguration(
                widget_id="customers_today",
                widget_type=WidgetType.METRIC_CARD,
                title="Today's Customers",
                position={"x": 6, "y": 0, "width": 3, "height": 2},
                data_source="realtime_metric",
                config={
                    "metric_name": "customers_current",
                    "format": "number",
                    "show_change": True,
                    "color_scheme": "info"
                }
            ),
            
            # Average order value metric card
            WidgetConfiguration(
                widget_id="aov_today",
                widget_type=WidgetType.METRIC_CARD,
                title="Avg. Order Value",
                position={"x": 9, "y": 0, "width": 3, "height": 2},
                data_source="realtime_metric",
                config={
                    "metric_name": "average_order_value",
                    "format": "currency",
                    "show_change": True,
                    "color_scheme": "warning"
                }
            ),
            
            # Hourly revenue trend line chart
            WidgetConfiguration(
                widget_id="hourly_revenue_trend",
                widget_type=WidgetType.LINE_CHART,
                title="Hourly Revenue Trend",
                position={"x": 0, "y": 2, "width": 8, "height": 4},
                data_source="hourly_trends",
                config={
                    "metric": "revenue",
                    "hours_back": 24,
                    "show_points": True,
                    "fill": True,
                    "color": "#3B82F6"
                }
            ),
            
            # Top staff performance table
            WidgetConfiguration(
                widget_id="top_staff",
                widget_type=WidgetType.TABLE,
                title="Top Staff Performance",
                position={"x": 8, "y": 2, "width": 4, "height": 4},
                data_source="top_performers",
                config={
                    "entity_type": "staff",
                    "limit": 5,
                    "columns": ["name", "revenue", "orders"],
                    "sortable": True
                }
            ),
            
            # Orders by hour bar chart
            WidgetConfiguration(
                widget_id="orders_by_hour",
                widget_type=WidgetType.BAR_CHART,
                title="Orders by Hour",
                position={"x": 0, "y": 6, "width": 6, "height": 3},
                data_source="hourly_trends",
                config={
                    "metric": "orders",
                    "hours_back": 12,
                    "color": "#10B981"
                }
            ),
            
            # Customer distribution pie chart
            WidgetConfiguration(
                widget_id="customer_distribution",
                widget_type=WidgetType.PIE_CHART,
                title="Customer Distribution",
                position={"x": 6, "y": 6, "width": 6, "height": 3},
                data_source="customer_analysis",
                config={
                    "segment_by": "customer_type",
                    "show_labels": True,
                    "show_percentages": True
                }
            )
        ]
        
        return DashboardLayout(
            layout_id=f"default_layout_{user_id}",
            name="Default Dashboard",
            description="Default dashboard layout with key metrics",
            widgets=widgets,
            created_by=user_id,
            is_default=True,
            is_public=False
        )
    
    def invalidate_widget_cache(self, widget_id: Optional[str] = None):
        """Invalidate widget cache"""
        if widget_id:
            # Remove specific widget from cache
            keys_to_remove = [key for key in self.widget_data_cache.keys() if key.startswith(widget_id)]
            for key in keys_to_remove:
                del self.widget_data_cache[key]
        else:
            # Clear all cache
            self.widget_data_cache.clear()
        
        logger.info(f"Widget cache invalidated for: {widget_id or 'all widgets'}")
    
    # Widget processors
    
    async def _process_metric_card(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process metric card widget"""
        
        config = widget_config.config
        metric_name = config.get("metric_name")
        
        if not metric_name:
            raise ValueError("metric_name is required for metric card widget")
        
        # Get metric data
        metric = await realtime_metrics_service.get_realtime_metric(metric_name)
        
        if not metric:
            return {
                "value": 0,
                "change_percentage": 0,
                "status": "no_data",
                "format": config.get("format", "number")
            }
        
        return {
            "value": metric.value,
            "change_percentage": metric.change_percentage,
            "previous_value": metric.previous_value,
            "status": "success",
            "format": config.get("format", "number"),
            "color_scheme": config.get("color_scheme", "primary"),
            "timestamp": metric.timestamp.isoformat()
        }
    
    async def _process_line_chart(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process line chart widget"""
        
        config = widget_config.config
        metric = config.get("metric", "revenue")
        hours_back = config.get("hours_back", 24)
        
        # Get hourly trends
        trends = await realtime_metrics_service.get_hourly_trends(hours_back)
        
        # Extract data for the specific metric
        chart_data = []
        for trend in trends:
            chart_data.append({
                "x": trend["hour"],
                "y": trend.get(metric, 0)
            })
        
        return {
            "data": chart_data,
            "metric": metric,
            "config": {
                "show_points": config.get("show_points", False),
                "fill": config.get("fill", False),
                "color": config.get("color", "#3B82F6"),
                "tension": config.get("tension", 0.4)
            }
        }
    
    async def _process_bar_chart(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process bar chart widget"""
        
        config = widget_config.config
        metric = config.get("metric", "orders")
        hours_back = config.get("hours_back", 12)
        
        # Get hourly trends
        trends = await realtime_metrics_service.get_hourly_trends(hours_back)
        
        # Extract data for bar chart
        labels = []
        data = []
        
        for trend in trends:
            # Format hour for display
            hour_dt = datetime.fromisoformat(trend["hour"])
            labels.append(hour_dt.strftime("%H:00"))
            data.append(trend.get(metric, 0))
        
        return {
            "labels": labels,
            "data": data,
            "config": {
                "color": config.get("color", "#10B981"),
                "horizontal": config.get("horizontal", False)
            }
        }
    
    async def _process_pie_chart(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process pie chart widget"""
        
        config = widget_config.config
        segment_by = config.get("segment_by", "customer_type")
        
        # Get segmented data based on configuration
        if segment_by == "customer_type":
            # Example customer type distribution
            data = [
                {"label": "New Customers", "value": 35, "color": "#3B82F6"},
                {"label": "Returning Customers", "value": 65, "color": "#10B981"}
            ]
        elif segment_by == "order_size":
            # Example order size distribution
            data = [
                {"label": "Small ($0-$25)", "value": 40, "color": "#F59E0B"},
                {"label": "Medium ($25-$50)", "value": 35, "color": "#3B82F6"},
                {"label": "Large ($50+)", "value": 25, "color": "#10B981"}
            ]
        else:
            data = []
        
        return {
            "data": data,
            "config": {
                "show_labels": config.get("show_labels", True),
                "show_percentages": config.get("show_percentages", True)
            }
        }
    
    async def _process_table(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process table widget"""
        
        config = widget_config.config
        entity_type = config.get("entity_type", "staff")
        limit = config.get("limit", 10)
        columns = config.get("columns", ["name", "value"])
        
        if entity_type == "staff":
            # Get top staff performers
            performers = await realtime_metrics_service.get_top_performers(limit)
            staff_data = performers.get("staff", [])
            
            # Format data for table
            rows = []
            for staff in staff_data:
                row = {}
                if "name" in columns:
                    row["name"] = staff.get("name", "Unknown")
                if "revenue" in columns:
                    row["revenue"] = f"${staff.get('revenue', 0):,.2f}"
                if "orders" in columns:
                    row["orders"] = staff.get("orders", 0)
                rows.append(row)
            
            return {
                "columns": columns,
                "rows": rows,
                "total_rows": len(rows)
            }
        
        return {"columns": [], "rows": [], "total_rows": 0}
    
    async def _process_gauge(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process gauge widget"""
        
        config = widget_config.config
        metric_name = config.get("metric_name")
        min_value = config.get("min_value", 0)
        max_value = config.get("max_value", 100)
        
        if not metric_name:
            return {"value": 0, "min": min_value, "max": max_value}
        
        # Get metric data
        metric = await realtime_metrics_service.get_realtime_metric(metric_name)
        
        if not metric:
            return {"value": 0, "min": min_value, "max": max_value}
        
        return {
            "value": min(max_value, max(min_value, metric.value)),
            "min": min_value,
            "max": max_value,
            "percentage": ((metric.value - min_value) / (max_value - min_value)) * 100,
            "config": {
                "color": config.get("color", "#3B82F6"),
                "show_value": config.get("show_value", True)
            }
        }
    
    async def _process_progress_bar(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process progress bar widget"""
        
        config = widget_config.config
        current_value = config.get("current_value", 0)
        target_value = config.get("target_value", 100)
        
        if target_value == 0:
            percentage = 0
        else:
            percentage = min(100, max(0, (current_value / target_value) * 100))
        
        return {
            "current_value": current_value,
            "target_value": target_value,
            "percentage": percentage,
            "config": {
                "color": config.get("color", "#10B981"),
                "show_percentage": config.get("show_percentage", True),
                "show_values": config.get("show_values", True)
            }
        }
    
    async def _process_sparkline(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process sparkline widget"""
        
        config = widget_config.config
        metric = config.get("metric", "revenue")
        hours_back = config.get("hours_back", 12)
        
        # Get trend data
        trends = await realtime_metrics_service.get_hourly_trends(hours_back)
        
        # Extract values for sparkline
        values = [trend.get(metric, 0) for trend in trends]
        
        return {
            "values": values,
            "config": {
                "color": config.get("color", "#3B82F6"),
                "fill": config.get("fill", False),
                "show_dots": config.get("show_dots", False)
            }
        }
    
    async def _process_heatmap(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process heatmap widget"""
        
        config = widget_config.config
        
        # Generate sample heatmap data (hours vs days)
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        hours = [f"{i:02d}:00" for i in range(24)]
        
        # Sample data - in real implementation, this would come from database
        data = []
        for day_idx, day in enumerate(days):
            for hour_idx, hour in enumerate(hours):
                # Generate sample intensity (0-100)
                intensity = (day_idx + 1) * (hour_idx + 1) % 100
                data.append({
                    "x": hour,
                    "y": day,
                    "value": intensity
                })
        
        return {
            "data": data,
            "config": {
                "color_scale": config.get("color_scale", ["#EBF8FF", "#3B82F6"]),
                "show_values": config.get("show_values", False)
            }
        }
    
    async def _process_kpi_card(self, widget_config: WidgetConfiguration) -> Dict[str, Any]:
        """Process KPI card widget"""
        
        config = widget_config.config
        kpi_type = config.get("kpi_type", "revenue_target")
        
        # Get current dashboard snapshot
        snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
        
        if kpi_type == "revenue_target":
            current = float(snapshot.revenue_today)
            target = config.get("target", 1000.0)
            
            return {
                "title": "Revenue Target",
                "current": current,
                "target": target,
                "percentage": min(100, (current / target) * 100) if target > 0 else 0,
                "status": "success" if current >= target else "warning",
                "format": "currency"
            }
        
        elif kpi_type == "orders_target":
            current = snapshot.orders_today
            target = config.get("target", 50)
            
            return {
                "title": "Orders Target", 
                "current": current,
                "target": target,
                "percentage": min(100, (current / target) * 100) if target > 0 else 0,
                "status": "success" if current >= target else "warning",
                "format": "number"
            }
        
        return {
            "title": "Unknown KPI",
            "current": 0,
            "target": 0,
            "percentage": 0,
            "status": "error",
            "format": "number"
        }


# Global dashboard widgets service instance
dashboard_widgets_service = DashboardWidgetsService()


# Utility functions
async def get_widget_data(widget_config: WidgetConfiguration, force_refresh: bool = False) -> WidgetDataResponse:
    """Get data for a widget"""
    return await dashboard_widgets_service.get_widget_data(widget_config, force_refresh)


async def get_dashboard_data(layout: DashboardLayout, force_refresh: bool = False) -> Dict[str, WidgetDataResponse]:
    """Get data for all widgets in a dashboard layout"""
    return await dashboard_widgets_service.get_dashboard_layout_data(layout, force_refresh)


async def create_default_layout(user_id: int) -> DashboardLayout:
    """Create a default dashboard layout"""
    return await dashboard_widgets_service.create_default_dashboard_layout(user_id)


def invalidate_widget_cache(widget_id: Optional[str] = None):
    """Invalidate widget cache"""
    dashboard_widgets_service.invalidate_widget_cache(widget_id)