from typing import List, Optional
from datetime import timedelta, datetime, date
from decimal import Decimal
import logging

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, text, case

from ..schemas.analytics_schemas import MenuPerformanceResponse, SalesFilterRequest
from modules.orders.models.order_models import Order, OrderItem
from modules.menu.models.recipe_models import Recipe
from core.menu_models import MenuItem, MenuCategory

logger = logging.getLogger(__name__)


class MenuPerformanceService:
    """Service for generating menu item performance analytics including profitability"""

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def generate_menu_performance_report(
        self,
        filters: SalesFilterRequest,
        page: int = 1,
        per_page: int = 50,
    ) -> List[MenuPerformanceResponse]:
        """Return menu performance analytics for the given filter window."""

        try:
            query = self._build_menu_performance_query(filters)

            # Pagination
            offset = (page - 1) * per_page
            results = query.offset(offset).limit(per_page).all()

            # Compute total revenue/quantity for share calculations if needed in future
            menu_performance: List[MenuPerformanceResponse] = []
            for r in results:
                # Python-side profit calculations for clarity / DB compatibility
                profit = (r.revenue_generated or Decimal("0")) - (
                    r.total_cost or Decimal("0")
                )
                profit_margin: Optional[Decimal] = None
                if r.revenue_generated and r.revenue_generated > 0:
                    profit_margin = (profit / r.revenue_generated) * 100

                menu_performance.append(
                    MenuPerformanceResponse(
                        menu_item_id=r.menu_item_id,
                        menu_item_name=r.menu_item_name,
                        category_id=r.category_id,
                        category_name=r.category_name,
                        quantity_sold=r.quantity_sold or 0,
                        revenue_generated=r.revenue_generated or Decimal("0"),
                        average_price=r.average_price or Decimal("0"),
                        order_frequency=r.order_frequency or 0,
                        total_cost=r.total_cost or Decimal("0"),
                        profit=profit,
                        profit_margin=profit_margin,
                        popularity_rank=r.popularity_rank,
                        revenue_rank=r.revenue_rank,
                        profit_rank=r.profit_rank,
                        period_start=filters.date_from
                        or (datetime.now().date() - timedelta(days=30)),
                        period_end=filters.date_to or datetime.now().date(),
                    )
                )

            return menu_performance
        except Exception as e:
            logger.error("Error generating menu performance report: %s", e)
            raise

    # ------------------------------------------------------------------
    # Query builder
    # ------------------------------------------------------------------
    def _build_menu_performance_query(self, filters: SalesFilterRequest):
        """Construct a query that aggregates sales & cost data per menu item."""

        # ------------------------------------------------------------------
        # Aggregate metrics subquery
        # ------------------------------------------------------------------
        metrics_sub = (
            self.db.query(
                OrderItem.menu_item_id.label("menu_item_id"),
                func.sum(OrderItem.quantity).label("quantity_sold"),
                func.sum(OrderItem.price * OrderItem.quantity).label(
                    "revenue_generated"
                ),
                func.avg(OrderItem.price).label("average_price"),
                func.count(func.distinct(OrderItem.order_id)).label("order_frequency"),
                # Cost — multiply quantity sold by recipe cost (fallback 0)
                func.sum(
                    OrderItem.quantity * func.coalesce(Recipe.total_cost, 0)
                ).label("total_cost"),
            )
            .join(Order)
            .outerjoin(Recipe, Recipe.menu_item_id == OrderItem.menu_item_id)
        )

        # Apply date filters via Order table
        if filters.date_from:
            metrics_sub = metrics_sub.filter(Order.created_at >= filters.date_from)
        if filters.date_to:
            metrics_sub = metrics_sub.filter(
                Order.created_at <= filters.date_to + timedelta(days=1)
            )

        if filters.staff_ids:
            metrics_sub = metrics_sub.filter(Order.staff_id.in_(filters.staff_ids))
        if filters.product_ids:
            metrics_sub = metrics_sub.filter(
                OrderItem.menu_item_id.in_(filters.product_ids)
            )
        if filters.category_ids:
            # Need MenuItem join to filter by category before grouping. Use EXISTS.
            metrics_sub = metrics_sub.filter(
                OrderItem.menu_item_id.in_(
                    self.db.query(MenuItem.id).filter(
                        MenuItem.category_id.in_(filters.category_ids)
                    )
                )
            )

        metrics_sub = metrics_sub.group_by(OrderItem.menu_item_id).subquery()

        # ------------------------------------------------------------------
        # Main query with ranking and name/category joins
        # ------------------------------------------------------------------
        query = (
            self.db.query(
                metrics_sub.c.menu_item_id,
                MenuItem.name.label("menu_item_name"),
                MenuCategory.id.label("category_id"),
                MenuCategory.name.label("category_name"),
                metrics_sub.c.quantity_sold,
                metrics_sub.c.revenue_generated,
                metrics_sub.c.average_price,
                metrics_sub.c.order_frequency,
                metrics_sub.c.total_cost,
                func.rank()
                .over(order_by=desc(metrics_sub.c.quantity_sold))
                .label("popularity_rank"),
                func.rank()
                .over(order_by=desc(metrics_sub.c.revenue_generated))
                .label("revenue_rank"),
                func.rank()
                .over(
                    order_by=desc(
                        metrics_sub.c.revenue_generated - metrics_sub.c.total_cost
                    )
                )
                .label("profit_rank"),
            )
            .join(MenuItem, MenuItem.id == metrics_sub.c.menu_item_id)
            .outerjoin(MenuCategory, MenuCategory.id == MenuItem.category_id)
            .order_by(desc(metrics_sub.c.revenue_generated))
        )

        return query
