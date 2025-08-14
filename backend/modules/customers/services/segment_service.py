from __future__ import annotations

# backend/modules/customers/services/segment_service.py
"""Service layer for customer segmentation.

Provides CRUD operations and dynamic membership evaluation for
``CustomerSegment`` objects using the SQLAlchemy ORM.  The service is kept
separate from the extremely large ``customer_service`` module to avoid
further bloat and to keep the segmentation concern isolated.

The first implementation purposefully supports only a small subset of the
possible segmentation criteria (orders, spending, tier, status) that cover
the majority of marketing use-cases.  New criteria can be added centrally in
``_apply_criteria`` without touching the public API.
"""

from datetime import datetime
from typing import Any, Dict, List, Sequence

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..models.customer_models import Customer, CustomerSegment
from ..schemas.customer_schemas import (
    CustomerSegmentCreate,
    CustomerSegment as CustomerSegmentSchema,
)


class CustomerSegmentService:
    """Encapsulates Customer segmentation logic."""

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------

    def __init__(self, db: Session):
        self.db: Session = db

    # ------------------------------------------------------------------
    # Public CRUD helpers
    # ------------------------------------------------------------------

    def list_segments(self) -> List[CustomerSegment]:
        return self.db.query(CustomerSegment).all()

    def get_segment(self, segment_id: int) -> CustomerSegment | None:
        return (
            self.db.query(CustomerSegment)
            .filter(CustomerSegment.id == segment_id)
            .first()
        )

    def create_segment(self, data: CustomerSegmentCreate) -> CustomerSegment:
        segment = CustomerSegment(
            name=data.name,
            description=data.description,
            criteria=data.criteria or {},
            is_dynamic=data.is_dynamic,
            is_active=True,
        )
        self.db.add(segment)
        self.db.commit()
        self.db.refresh(segment)

        # Evaluate membership immediately so that *member_count* is accurate.
        self.evaluate_segment(segment.id)
        return segment

    def update_segment(
        self,
        segment_id: int,
        update_values: Dict[str, Any],
    ) -> CustomerSegment:
        segment = self.get_segment(segment_id)
        if not segment:
            raise ValueError("Segment not found")

        for field in (
            "name",
            "description",
            "criteria",
            "is_dynamic",
            "is_active",
        ):
            if field in update_values:
                setattr(segment, field, update_values[field])

        segment.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(segment)

        # For dynamic segments we want to re-evaluate after updating.
        if segment.is_dynamic:
            self.evaluate_segment(segment.id)
        return segment

    def delete_segment(self, segment_id: int) -> None:
        segment = self.get_segment(segment_id)
        if not segment:
            raise ValueError("Segment not found")
        self.db.delete(segment)
        self.db.commit()

    # ------------------------------------------------------------------
    # Membership helpers
    # ------------------------------------------------------------------

    def evaluate_segment(self, segment_id: int) -> CustomerSegment:
        """Re-calculate membership of a *dynamic* segment.

        For *static* segments this method is a no-op apart from refreshing the
        member count.
        """
        segment = self.get_segment(segment_id)
        if not segment:
            raise ValueError("Segment not found")

        # For static segments, only update the member count
        if not segment.is_dynamic:
            segment.member_count = len(segment.customers)  # type: ignore[arg-type]
            segment.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(segment)
            return segment

        # For dynamic segments, re-evaluate membership
        customers = self._filter_customers(segment.criteria or {})

        # Replace membership list.
        segment.customers = customers  # type: ignore[assignment]
        segment.member_count = len(customers)
        segment.updated_at = datetime.utcnow()  # Use updated_at for consistency

        self.db.commit()
        self.db.refresh(segment)
        return segment

    def get_segment_customers(self, segment_id: int) -> Sequence[Customer]:
        segment = self.get_segment(segment_id)
        if not segment:
            raise ValueError("Segment not found")
        return segment.customers  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _filter_customers(self, criteria: Dict[str, Any]) -> List[Customer]:
        """Return *all* customers matching *criteria*.

        The current implementation supports the following optional keys:
        - ``tier``:            List[str]
        - ``status``:          List[str]
        - ``min_orders``:      int
        - ``max_orders``:      int
        - ``min_spent``:       float
        - ``max_spent``:       float
        Future enhancements can extend this method.
        """

        query = self.db.query(Customer).filter(Customer.deleted_at.is_(None))

        if tier := criteria.get("tier"):
            query = query.filter(Customer.tier.in_(tier))
        if status := criteria.get("status"):
            query = query.filter(Customer.status.in_(status))
        if (min_orders := criteria.get("min_orders")) is not None:
            query = query.filter(Customer.total_orders >= min_orders)
        if (max_orders := criteria.get("max_orders")) is not None:
            query = query.filter(Customer.total_orders <= max_orders)
        if (min_spent := criteria.get("min_spent")) is not None:
            query = query.filter(Customer.total_spent >= min_spent)
        if (max_spent := criteria.get("max_spent")) is not None:
            query = query.filter(Customer.total_spent <= max_spent)

        return query.all()