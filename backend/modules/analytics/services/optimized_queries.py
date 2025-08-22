# backend/modules/analytics/services/optimized_queries.py

"""
Optimized query patterns for analytics services to eliminate N+1 queries.

This module provides efficient query builders that use proper joins,
subqueries, and batch loading to minimize database round trips.
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import func, and_, or_, case, text
from sqlalchemy.orm import Session, joinedload, selectinload, contains_eager
from sqlalchemy.sql import Select

import logging

logger = logging.getLogger(__name__)


class OptimizedAnalyticsQueries:
    """Provides optimized query patterns for analytics operations"""

    @staticmethod
    def get_provider_summaries_optimized(
        db: Session,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[List[int]] = None,
        include_offline: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Get provider summaries with terminal stats and alert counts in a single query.
        
        Eliminates N+1 queries by:
        1. Using subqueries for terminal stats
        2. Using subqueries for alert counts
        3. Joining all data in a single query
        """
        
        from modules.orders.models.external_pos_models import ExternalPOSProvider
        from modules.analytics.models.pos_analytics_models import (
            POSAnalyticsSnapshot,
            POSTerminalHealth,
            POSAnalyticsAlert,
        )
        
        # Subquery for terminal statistics
        terminal_stats_subquery = (
            db.query(
                POSTerminalHealth.provider_id,
                func.count(POSTerminalHealth.terminal_id).label("total_terminals"),
                func.sum(
                    case(
                        (POSTerminalHealth.is_online == True, 1),
                        else_=0
                    )
                ).label("active_terminals"),
                func.sum(
                    case(
                        (POSTerminalHealth.is_online == False, 1),
                        else_=0
                    )
                ).label("offline_terminals"),
            )
            .group_by(POSTerminalHealth.provider_id)
            .subquery()
        )
        
        # Subquery for active alert counts
        alert_counts_subquery = (
            db.query(
                POSAnalyticsAlert.provider_id,
                func.count(POSAnalyticsAlert.id).label("active_alerts"),
            )
            .filter(POSAnalyticsAlert.is_active == True)
            .group_by(POSAnalyticsAlert.provider_id)
            .subquery()
        )
        
        # Main query with all joins
        query = (
            db.query(
                ExternalPOSProvider.id,
                ExternalPOSProvider.provider_name,
                ExternalPOSProvider.provider_code,
                ExternalPOSProvider.is_active,
                # Analytics metrics
                func.sum(POSAnalyticsSnapshot.total_transactions).label("total_transactions"),
                func.sum(POSAnalyticsSnapshot.successful_transactions).label("successful_transactions"),
                func.sum(POSAnalyticsSnapshot.failed_transactions).label("failed_transactions"),
                func.sum(POSAnalyticsSnapshot.total_transaction_value).label("total_value"),
                func.sum(POSAnalyticsSnapshot.total_syncs).label("total_syncs"),
                func.sum(POSAnalyticsSnapshot.successful_syncs).label("successful_syncs"),
                func.sum(POSAnalyticsSnapshot.total_webhooks).label("total_webhooks"),
                func.sum(POSAnalyticsSnapshot.successful_webhooks).label("successful_webhooks"),
                func.avg(POSAnalyticsSnapshot.uptime_percentage).label("uptime"),
                func.avg(POSAnalyticsSnapshot.average_sync_time_ms).label("avg_sync_time"),
                func.avg(POSAnalyticsSnapshot.average_webhook_processing_time_ms).label("avg_webhook_time"),
                # Terminal stats from subquery
                func.coalesce(terminal_stats_subquery.c.total_terminals, 0).label("total_terminals"),
                func.coalesce(terminal_stats_subquery.c.active_terminals, 0).label("active_terminals"),
                func.coalesce(terminal_stats_subquery.c.offline_terminals, 0).label("offline_terminals"),
                # Alert counts from subquery
                func.coalesce(alert_counts_subquery.c.active_alerts, 0).label("active_alerts"),
            )
            .join(
                POSAnalyticsSnapshot,
                POSAnalyticsSnapshot.provider_id == ExternalPOSProvider.id,
            )
            .outerjoin(
                terminal_stats_subquery,
                terminal_stats_subquery.c.provider_id == ExternalPOSProvider.id,
            )
            .outerjoin(
                alert_counts_subquery,
                alert_counts_subquery.c.provider_id == ExternalPOSProvider.id,
            )
            .filter(
                POSAnalyticsSnapshot.snapshot_date >= start_date.date(),
                POSAnalyticsSnapshot.snapshot_date <= end_date.date(),
            )
        )
        
        if provider_ids:
            query = query.filter(ExternalPOSProvider.id.in_(provider_ids))
        
        if not include_offline:
            query = query.filter(ExternalPOSProvider.is_active == True)
        
        query = query.group_by(
            ExternalPOSProvider.id,
            ExternalPOSProvider.provider_name,
            ExternalPOSProvider.provider_code,
            ExternalPOSProvider.is_active,
            terminal_stats_subquery.c.total_terminals,
            terminal_stats_subquery.c.active_terminals,
            terminal_stats_subquery.c.offline_terminals,
            alert_counts_subquery.c.active_alerts,
        )
        
        return query.all()

    @staticmethod
    def get_product_performance_with_categories(
        db: Session,
        filters: Any,  # SalesFilterRequest
        page: int = 1,
        per_page: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Get product performance with category information in a single query.
        
        Eliminates N+1 by eagerly loading category data.
        """
        
        from modules.orders.models.order_models import Order, OrderItem
        from modules.menu.models import MenuItem, MenuCategory
        
        # Build product performance query with eager loading
        query = (
            db.query(
                OrderItem.menu_item_id.label("product_id"),
                MenuItem.name.label("product_name"),
                MenuItem.category_id,
                MenuCategory.name.label("category_name"),
                func.sum(OrderItem.quantity).label("quantity_sold"),
                func.sum(OrderItem.price * OrderItem.quantity).label("revenue_generated"),
                func.avg(OrderItem.price).label("average_price"),
                func.count(func.distinct(OrderItem.order_id)).label("order_frequency"),
                # Window functions for ranking
                func.rank().over(
                    order_by=func.sum(OrderItem.quantity).desc()
                ).label("popularity_rank"),
                func.rank().over(
                    order_by=func.sum(OrderItem.price * OrderItem.quantity).desc()
                ).label("revenue_rank"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .join(MenuItem, OrderItem.menu_item_id == MenuItem.id)
            .outerjoin(MenuCategory, MenuItem.category_id == MenuCategory.id)
        )
        
        # Apply filters
        if hasattr(filters, 'date_from') and filters.date_from:
            query = query.filter(Order.created_at >= filters.date_from)
        if hasattr(filters, 'date_to') and filters.date_to:
            query = query.filter(Order.created_at <= filters.date_to)
        
        query = query.group_by(
            OrderItem.menu_item_id,
            MenuItem.name,
            MenuItem.category_id,
            MenuCategory.name,
        )
        
        # Apply pagination
        offset = (page - 1) * per_page
        results = query.offset(offset).limit(per_page).all()
        
        return results

    @staticmethod
    def get_staff_performance_with_shifts(
        db: Session,
        start_date: date,
        end_date: date,
        staff_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get staff performance metrics with shift hours in a single query.
        
        Combines order processing metrics with shift hours calculation.
        """
        
        from modules.orders.models.order_models import Order
        from modules.staff.models.staff_models import StaffMember
        from modules.staff.models.shift_models import Shift
        
        # Subquery for shift hours
        shift_hours_subquery = (
            db.query(
                Shift.staff_id,
                func.sum(
                    func.extract('epoch', Shift.end_time - Shift.start_time) / 3600
                ).label("total_hours")
            )
            .filter(
                Shift.date >= start_date,
                Shift.date <= end_date,
                Shift.status == "completed",
            )
            .group_by(Shift.staff_id)
            .subquery()
        )
        
        # Main query combining orders and shifts
        query = (
            db.query(
                StaffMember.id.label("staff_id"),
                StaffMember.name.label("staff_name"),
                func.count(func.distinct(Order.id)).label("orders_handled"),
                func.sum(Order.total_amount).label("total_revenue"),
                func.avg(Order.total_amount).label("average_order_value"),
                func.avg(
                    func.extract('epoch', Order.completed_at - Order.created_at) / 60
                ).label("average_processing_time"),
                func.coalesce(shift_hours_subquery.c.total_hours, 0).label("total_hours"),
                # Rankings
                func.rank().over(
                    order_by=func.sum(Order.total_amount).desc()
                ).label("revenue_rank"),
                func.rank().over(
                    order_by=func.count(Order.id).desc()
                ).label("order_count_rank"),
            )
            .outerjoin(Order, Order.processed_by_id == StaffMember.id)
            .outerjoin(
                shift_hours_subquery,
                shift_hours_subquery.c.staff_id == StaffMember.id
            )
            .filter(
                or_(
                    Order.created_at.between(start_date, end_date),
                    Order.id.is_(None),  # Include staff with no orders
                )
            )
        )
        
        if staff_ids:
            query = query.filter(StaffMember.id.in_(staff_ids))
        
        query = query.group_by(
            StaffMember.id,
            StaffMember.name,
            shift_hours_subquery.c.total_hours,
        )
        
        return query.all()

    @staticmethod
    def get_customer_insights_batch(
        db: Session,
        start_date: date,
        end_date: date,
        batch_size: int = 1000,
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get customer insights using batch processing to avoid memory issues.
        
        Returns customer metrics indexed by customer_id.
        """
        
        from modules.orders.models.order_models import Order
        from modules.customers.models.customer_models import Customer
        
        # Use a CTE for customer order stats
        customer_stats_cte = (
            db.query(
                Order.customer_id,
                func.count(Order.id).label("order_count"),
                func.sum(Order.total_amount).label("total_spent"),
                func.min(Order.order_date).label("first_order"),
                func.max(Order.order_date).label("last_order"),
                func.avg(Order.total_amount).label("avg_order_value"),
            )
            .filter(
                Order.order_date.between(start_date, end_date),
                Order.status.in_(["completed", "paid"]),
            )
            .group_by(Order.customer_id)
            .cte("customer_stats")
        )
        
        # Query with customer details and stats
        query = (
            db.query(
                Customer.id,
                Customer.first_name,
                Customer.last_name,
                Customer.email,
                Customer.created_at,
                customer_stats_cte.c.order_count,
                customer_stats_cte.c.total_spent,
                customer_stats_cte.c.first_order,
                customer_stats_cte.c.last_order,
                customer_stats_cte.c.avg_order_value,
                # Calculate customer lifetime value
                case(
                    (customer_stats_cte.c.order_count > 10, "vip"),
                    (customer_stats_cte.c.order_count > 5, "regular"),
                    (customer_stats_cte.c.order_count > 1, "occasional"),
                    else_="one_time"
                ).label("segment"),
            )
            .join(
                customer_stats_cte,
                Customer.id == customer_stats_cte.c.customer_id,
            )
        )
        
        # Process in batches
        results = {}
        offset = 0
        
        while True:
            batch = query.offset(offset).limit(batch_size).all()
            if not batch:
                break
                
            for row in batch:
                results[row.id] = {
                    "customer_id": row.id,
                    "name": f"{row.first_name} {row.last_name}",
                    "email": row.email,
                    "order_count": row.order_count,
                    "total_spent": row.total_spent,
                    "first_order": row.first_order,
                    "last_order": row.last_order,
                    "avg_order_value": row.avg_order_value,
                    "segment": row.segment,
                    "days_active": (row.last_order - row.first_order).days + 1,
                }
            
            offset += batch_size
            
        return results

    @staticmethod
    def preload_related_data(db: Session, orders: List[Any]) -> List[Any]:
        """
        Efficiently preload related data for a list of orders.
        
        Uses joinedload and selectinload to prevent N+1 queries.
        """
        
        from modules.orders.models.order_models import Order
        
        # Get order IDs
        order_ids = [order.id for order in orders]
        
        # Reload orders with all related data
        return (
            db.query(Order)
            .options(
                joinedload(Order.customer),
                joinedload(Order.processed_by),
                selectinload(Order.items).joinedload("menu_item"),
                selectinload(Order.payments),
            )
            .filter(Order.id.in_(order_ids))
            .all()
        )