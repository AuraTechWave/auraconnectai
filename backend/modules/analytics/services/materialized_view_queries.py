# backend/modules/analytics/services/materialized_view_queries.py

"""
Query services that leverage materialized views for optimal performance.

These queries use pre-aggregated data from materialized views to provide
fast analytics responses without complex joins and aggregations.
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import text, and_, or_
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)


class MaterializedViewQueries:
    """Provides optimized queries using materialized views"""
    
    @staticmethod
    def get_daily_sales_summary(
        db: Session,
        start_date: date,
        end_date: date,
        restaurant_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get daily sales summary from materialized view"""
        
        query = """
            SELECT 
                sale_date,
                total_orders,
                unique_customers,
                total_revenue,
                avg_order_value,
                total_discounts,
                total_tax,
                completed_orders,
                cancelled_orders,
                lunch_orders,
                dinner_orders,
                active_staff,
                highest_order_value,
                lowest_order_value
            FROM mv_daily_sales_summary
            WHERE sale_date BETWEEN :start_date AND :end_date
        """
        
        params = {"start_date": start_date, "end_date": end_date}
        
        if restaurant_id:
            query += " AND restaurant_id = :restaurant_id"
            params["restaurant_id"] = restaurant_id
        
        query += " ORDER BY sale_date DESC"
        
        result = db.execute(text(query), params)
        
        return [
            {
                "date": row.sale_date,
                "total_orders": row.total_orders,
                "unique_customers": row.unique_customers,
                "total_revenue": float(row.total_revenue),
                "avg_order_value": float(row.avg_order_value),
                "total_discounts": float(row.total_discounts),
                "total_tax": float(row.total_tax),
                "completed_orders": row.completed_orders,
                "cancelled_orders": row.cancelled_orders,
                "lunch_orders": row.lunch_orders,
                "dinner_orders": row.dinner_orders,
                "active_staff": row.active_staff,
                "highest_order": float(row.highest_order_value),
                "lowest_order": float(row.lowest_order_value),
                "cancellation_rate": (
                    row.cancelled_orders / (row.completed_orders + row.cancelled_orders) * 100
                    if (row.completed_orders + row.cancelled_orders) > 0
                    else 0
                ),
            }
            for row in result
        ]
    
    @staticmethod
    def get_top_products_from_view(
        db: Session,
        start_date: date,
        end_date: date,
        limit: int = 10,
        restaurant_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get top performing products from materialized view"""
        
        query = """
            SELECT 
                product_id,
                product_name,
                category_id,
                category_name,
                SUM(quantity_sold) as total_quantity,
                SUM(revenue) as total_revenue,
                SUM(order_count) as total_orders,
                AVG(avg_price) as average_price,
                COUNT(DISTINCT sale_date) as days_sold
            FROM mv_product_performance
            WHERE sale_date BETWEEN :start_date AND :end_date
        """
        
        params = {"start_date": start_date, "end_date": end_date}
        
        if restaurant_id:
            query += " AND restaurant_id = :restaurant_id"
            params["restaurant_id"] = restaurant_id
        
        query += """
            GROUP BY product_id, product_name, category_id, category_name
            ORDER BY total_revenue DESC
            LIMIT :limit
        """
        
        params["limit"] = limit
        
        result = db.execute(text(query), params)
        
        products = []
        rank = 1
        for row in result:
            products.append({
                "rank": rank,
                "product_id": row.product_id,
                "product_name": row.product_name,
                "category_id": row.category_id,
                "category_name": row.category_name,
                "total_quantity": row.total_quantity,
                "total_revenue": float(row.total_revenue),
                "total_orders": row.total_orders,
                "average_price": float(row.average_price),
                "days_sold": row.days_sold,
                "revenue_per_day": float(row.total_revenue) / row.days_sold if row.days_sold > 0 else 0,
            })
            rank += 1
        
        return products
    
    @staticmethod
    def get_hourly_patterns(
        db: Session,
        restaurant_id: Optional[int] = None,
        day_of_week: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get hourly sales patterns from materialized view"""
        
        query = """
            SELECT 
                hour_of_day,
                day_of_week,
                SUM(order_count) as total_orders,
                SUM(total_revenue) as total_revenue,
                AVG(avg_order_value) as avg_order_value,
                SUM(unique_customers) as total_customers,
                AVG(avg_processing_minutes) as avg_processing_time
            FROM mv_hourly_sales_patterns
            WHERE 1=1
        """
        
        params = {}
        
        if restaurant_id:
            query += " AND restaurant_id = :restaurant_id"
            params["restaurant_id"] = restaurant_id
        
        if day_of_week is not None:
            query += " AND day_of_week = :day_of_week"
            params["day_of_week"] = day_of_week
        
        query += """
            GROUP BY hour_of_day, day_of_week
            ORDER BY hour_of_day, day_of_week
        """
        
        result = db.execute(text(query), params)
        
        patterns = []
        for row in result:
            patterns.append({
                "hour": int(row.hour_of_day),
                "day_of_week": int(row.day_of_week) if row.day_of_week is not None else None,
                "order_count": row.total_orders,
                "revenue": float(row.total_revenue),
                "avg_order_value": float(row.avg_order_value),
                "customer_count": row.total_customers,
                "avg_processing_minutes": float(row.avg_processing_time) if row.avg_processing_time else None,
                "is_peak": row.total_orders > 50,  # Simple peak detection
            })
        
        return patterns
    
    @staticmethod
    def get_customer_segments(
        db: Session,
        restaurant_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get customer segmentation from materialized view"""
        
        query = """
            SELECT 
                customer_segment,
                COUNT(*) as customer_count,
                SUM(lifetime_value) as total_value,
                AVG(lifetime_value) as avg_value,
                AVG(total_orders) as avg_orders,
                AVG(avg_order_value) as avg_order_size,
                AVG(days_since_last_order) as avg_days_inactive,
                AVG(orders_per_month) as avg_frequency
            FROM mv_customer_lifetime_value
            WHERE lifetime_value > 0
        """
        
        params = {}
        
        if restaurant_id:
            query += " AND restaurant_id = :restaurant_id"
            params["restaurant_id"] = restaurant_id
        
        query += " GROUP BY customer_segment"
        
        result = db.execute(text(query), params)
        
        segments = {}
        total_customers = 0
        total_value = 0
        
        for row in result:
            segments[row.customer_segment] = {
                "count": row.customer_count,
                "total_value": float(row.total_value),
                "avg_value": float(row.avg_value),
                "avg_orders": float(row.avg_orders),
                "avg_order_size": float(row.avg_order_size),
                "avg_days_inactive": float(row.avg_days_inactive) if row.avg_days_inactive else 0,
                "avg_frequency": float(row.avg_frequency) if row.avg_frequency else 0,
            }
            total_customers += row.customer_count
            total_value += float(row.total_value)
        
        # Calculate percentages
        for segment, data in segments.items():
            data["customer_percentage"] = (data["count"] / total_customers * 100) if total_customers > 0 else 0
            data["value_percentage"] = (data["total_value"] / total_value * 100) if total_value > 0 else 0
        
        return {
            "segments": segments,
            "summary": {
                "total_customers": total_customers,
                "total_lifetime_value": total_value,
                "average_customer_value": total_value / total_customers if total_customers > 0 else 0,
            }
        }
    
    @staticmethod
    def get_pos_provider_trends(
        db: Session,
        start_date: date,
        end_date: date,
        provider_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get POS provider performance trends from materialized view"""
        
        query = """
            SELECT 
                provider_id,
                provider_name,
                provider_code,
                snapshot_date,
                total_transactions,
                successful_transactions,
                failed_transactions,
                total_transaction_value,
                avg_uptime,
                avg_sync_time,
                total_terminals,
                online_terminals
            FROM mv_pos_provider_daily_summary
            WHERE snapshot_date BETWEEN :start_date AND :end_date
        """
        
        params = {"start_date": start_date, "end_date": end_date}
        
        if provider_id:
            query += " AND provider_id = :provider_id"
            params["provider_id"] = provider_id
        
        query += " ORDER BY provider_id, snapshot_date"
        
        result = db.execute(text(query), params)
        
        trends = []
        for row in result:
            success_rate = (
                row.successful_transactions / row.total_transactions * 100
                if row.total_transactions > 0
                else 0
            )
            
            terminal_health = (
                row.online_terminals / row.total_terminals * 100
                if row.total_terminals > 0
                else 100
            )
            
            trends.append({
                "provider_id": row.provider_id,
                "provider_name": row.provider_name,
                "date": row.snapshot_date,
                "transactions": {
                    "total": row.total_transactions,
                    "successful": row.successful_transactions,
                    "failed": row.failed_transactions,
                    "success_rate": success_rate,
                    "total_value": float(row.total_transaction_value),
                },
                "performance": {
                    "uptime": float(row.avg_uptime),
                    "sync_time_ms": float(row.avg_sync_time),
                },
                "terminals": {
                    "total": row.total_terminals,
                    "online": row.online_terminals,
                    "health_percentage": terminal_health,
                },
            })
        
        return trends
    
    @staticmethod
    def refresh_materialized_views(db: Session, view_name: Optional[str] = None):
        """Manually refresh materialized views"""
        
        try:
            if view_name:
                # Refresh specific view
                db.execute(text(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {view_name}"))
                logger.info(f"Refreshed materialized view: {view_name}")
            else:
                # Refresh all analytics views
                db.execute(text("SELECT refresh_analytics_materialized_views()"))
                logger.info("Refreshed all analytics materialized views")
            
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Error refreshing materialized views: {e}")
            db.rollback()
            return False
    
    @staticmethod
    def get_materialized_view_stats(db: Session) -> Dict[str, Any]:
        """Get statistics about materialized views"""
        
        query = """
            SELECT 
                schemaname,
                matviewname,
                pg_size_pretty(pg_total_relation_size(schemaname||'.'||matviewname)) as size,
                (SELECT MAX(last_refresh) FROM pg_stat_user_tables WHERE tablename = matviewname) as last_refresh
            FROM pg_matviews
            WHERE matviewname LIKE 'mv_%'
            ORDER BY matviewname
        """
        
        result = db.execute(text(query))
        
        views = []
        for row in result:
            views.append({
                "name": row.matviewname,
                "schema": row.schemaname,
                "size": row.size,
                "last_refresh": row.last_refresh,
            })
        
        return {
            "materialized_views": views,
            "count": len(views),
        }


# Export the class
__all__ = ["MaterializedViewQueries"]