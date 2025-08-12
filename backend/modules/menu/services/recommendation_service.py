from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from core.menu_models import MenuItem
from modules.orders.models.order_models import Order, OrderItem


class MenuRecommendationService:
    """Service class to provide menu item recommendations.

    The algorithm is intentionally simple for the initial iteration:
    1.  If a ``customer_id`` is provided, aggregate that customer's last ``last_n_orders``
        (default 50) and recommend the most frequently ordered items.
    2.  If the list is smaller than ``max_results``, fill the remainder with the most
        popular items across all customers for the same time range.
    3.  Duplicate recommendations are removed while preserving order (customer-specific
        frequency first, then global popularity).

    The returned list is ordered by score (frequency count) in descending order.
    """

    def __init__(self, db: Session):
        self.db = db

    # ---------------------------------------------------------------------
    # Public helpers
    # ---------------------------------------------------------------------

    def get_recommendations(
        self,
        customer_id: Optional[int] = None,
        max_results: int = 5,
        last_n_orders: int = 50,
    ) -> List[Tuple[MenuItem, int]]:
        """Return a ranked list of ``MenuItem`` objects with their corresponding score.

        Args:
            customer_id: Only consider orders from this customer if provided.
            max_results: Maximum number of items to return.
            last_n_orders: Number of most recent orders to inspect when calculating
                popularity.
        """
        if max_results <= 0:
            return []

        customer_ranked: List[Tuple[int, int]] = []  # (menu_item_id, count)

        # ------------------------------------------------------------------
        # 1.  Customer-specific aggregation
        # ------------------------------------------------------------------
        if customer_id is not None:
            customer_ranked = self._aggregate_popularity(
                customer_id=customer_id, last_n_orders=last_n_orders, limit=max_results
            )

        # ------------------------------------------------------------------
        # 2.  Global aggregation (if needed)
        # ------------------------------------------------------------------
        global_needed = max_results - len(customer_ranked)
        global_ranked: List[Tuple[int, int]] = []
        if global_needed > 0:
            global_ranked = self._aggregate_popularity(
                customer_id=None, last_n_orders=last_n_orders, limit=max_results * 2  # grab a few extras
            )

        # ------------------------------------------------------------------
        # 3.  Merge results while respecting original order & uniqueness
        # ------------------------------------------------------------------
        combined: List[Tuple[int, int]] = []
        seen = set()
        for menu_id, count in customer_ranked + global_ranked:
            if menu_id not in seen:
                combined.append((menu_id, count))
                seen.add(menu_id)
            if len(combined) >= max_results:
                break

        if not combined:
            return []

        # Fetch MenuItem objects preserving ranking order
        id_to_item: Dict[int, MenuItem] = {
            item.id: item for item in self.db.query(MenuItem).filter(MenuItem.id.in_([mid for mid, _ in combined])).all()
        }
        results: List[Tuple[MenuItem, int]] = []
        for menu_id, score in combined:
            item = id_to_item.get(menu_id)
            if item:  # Item may have been deleted
                results.append((item, score))
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _aggregate_popularity(
        self,
        customer_id: Optional[int],
        last_n_orders: int,
        limit: int,
    ) -> List[Tuple[int, int]]:
        """Return menu item popularity [(menu_id, count), ...]"""
        # Subquery: get most recent order IDs for scope
        order_query = self.db.query(Order.id)
        if customer_id is not None:
            order_query = order_query.filter(Order.customer_id == customer_id)
        order_query = order_query.order_by(desc(Order.created_at if hasattr(Order, "created_at") else Order.id)).limit(last_n_orders)
        recent_order_ids = [oid for (oid,) in order_query.all()]
        if not recent_order_ids:
            return []

        popularity = (
            self.db.query(OrderItem.menu_item_id, func.sum(OrderItem.quantity).label("cnt"))
            .filter(OrderItem.order_id.in_(recent_order_ids))
            .group_by(OrderItem.menu_item_id)
            .order_by(desc("cnt"))
            .limit(limit)
            .all()
        )
        return [(mid, cnt) for (mid, cnt) in popularity]