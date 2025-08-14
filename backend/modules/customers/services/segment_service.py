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
import logging

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from core.tenant_context import TenantContext, apply_tenant_filter, validate_tenant_access, CrossTenantAccessLogger

from ..models.customer_models import Customer, CustomerSegment
from ..schemas.customer_schemas import (
    CustomerSegmentCreate,
    CustomerSegment as CustomerSegmentSchema,
)

logger = logging.getLogger(__name__)


class CustomerSegmentService:
    """Encapsulates Customer segmentation logic."""

    # ---------------------------------------------------------------------
    # Construction helpers
    # ---------------------------------------------------------------------

    def __init__(self, db: Session):
        self.db: Session = db
        self.access_logger = CrossTenantAccessLogger(db)

    # ------------------------------------------------------------------
    # Public CRUD helpers
    # ------------------------------------------------------------------

    def list_segments(self) -> List[CustomerSegment]:
        """List all segments for the current tenant"""
        query = self.db.query(CustomerSegment)
        # Apply tenant filtering
        query = apply_tenant_filter(query, CustomerSegment)
        return query.all()

    def get_segment(self, segment_id: int) -> CustomerSegment | None:
        """Get a segment by ID with tenant validation"""
        query = self.db.query(CustomerSegment).filter(CustomerSegment.id == segment_id)
        # Apply tenant filtering
        query = apply_tenant_filter(query, CustomerSegment)
        segment = query.first()
        
        if segment:
            # Validate tenant access
            if not validate_tenant_access(segment, raise_on_violation=False):
                context = TenantContext.get()
                if context:
                    self.access_logger.log_access_attempt(
                        requested_tenant_id=context.get('restaurant_id'),
                        actual_tenant_id=getattr(segment, 'restaurant_id', None),
                        resource_type='CustomerSegment',
                        resource_id=segment_id,
                        action='read',
                        success=False
                    )
                return None
        
        return segment

    def create_segment(self, data: CustomerSegmentCreate) -> CustomerSegment:
        """Create a segment with automatic tenant assignment"""
        context = TenantContext.require_context()
        
        segment = CustomerSegment(
            name=data.name,
            description=data.description,
            criteria=data.criteria or {},
            is_dynamic=data.is_dynamic,
            is_active=True,
        )
        
        # Set tenant fields if they exist on the model
        if hasattr(CustomerSegment, 'restaurant_id') and context.get('restaurant_id') is not None:
            segment.restaurant_id = context.get('restaurant_id')
        
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
        """Update segment with tenant validation"""
        segment = self.get_segment(segment_id)
        if not segment:
            raise ValueError("Segment not found")
        
        # Validate tenant access before update
        validate_tenant_access(segment)

        for field in (
            "name",
            "description",
            "criteria",
            "is_dynamic",
            "is_active",
        ):
            if field in update_values:
                setattr(segment, field, update_values[field])

        segment.last_updated = datetime.utcnow()
        # Also update updated_at if it exists from TimestampMixin
        if hasattr(segment, 'updated_at'):
            segment.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(segment)

        # For dynamic segments we want to re-evaluate after updating.
        if segment.is_dynamic:
            self.evaluate_segment(segment.id)
        return segment

    def delete_segment(self, segment_id: int) -> None:
        """Delete segment with tenant validation"""
        segment = self.get_segment(segment_id)
        if not segment:
            raise ValueError("Segment not found")
        
        # Validate tenant access before deletion
        validate_tenant_access(segment)
        
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
        
        # Validate tenant access
        validate_tenant_access(segment)

        # For static segments, only update the member count
        if not segment.is_dynamic:
            segment.member_count = len(segment.customers)  # type: ignore[arg-type]
            segment.last_updated = datetime.utcnow()
            # Also update updated_at if it exists from TimestampMixin
            if hasattr(segment, 'updated_at'):
                segment.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(segment)
            return segment

        # For dynamic segments, re-evaluate membership
        customers = self._filter_customers(segment.criteria or {})

        # Replace membership list.
        segment.customers = customers  # type: ignore[assignment]
        segment.member_count = len(customers)
        segment.last_updated = datetime.utcnow()
        # Also update updated_at if it exists from TimestampMixin
        if hasattr(segment, 'updated_at'):
            segment.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(segment)
        return segment

    def get_segment_customers(self, segment_id: int) -> Sequence[Customer]:
        """Get customers in a segment with tenant validation"""
        segment = self.get_segment(segment_id)
        if not segment:
            raise ValueError("Segment not found")
        
        # Validate tenant access
        validate_tenant_access(segment)
        
        # Additional filtering of customers to ensure they belong to current tenant
        customers = segment.customers  # type: ignore[assignment]
        if customers:
            # Filter customers by tenant
            context = TenantContext.get()
            if context and context.get('restaurant_id') is not None:
                customers = [c for c in customers if 
                           getattr(c, 'restaurant_id', None) == context.get('restaurant_id')]
        
        return customers  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _filter_customers(self, criteria: Dict[str, Any]) -> List[Customer]:
        """Return *all* customers matching *criteria* within current tenant.

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
        
        # Apply tenant filtering to ensure we only get customers for current tenant
        query = apply_tenant_filter(query, Customer)

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