# backend/modules/promotions/services/promotion_service.py

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, text
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging
import uuid

from ..models.promotion_models import (
    Promotion,
    PromotionUsage,
    PromotionStatus,
    PromotionType,
    PromotionAnalytics,
)
from ..schemas.promotion_schemas import (
    PromotionCreate,
    PromotionUpdate,
    PromotionSearchParams,
    PromotionSearchResponse,
    PromotionSummary,
    ABTestConfig,
)
from modules.customers.models.customer_models import Customer

logger = logging.getLogger(__name__)


class PromotionService:
    """Service for managing promotions and campaigns"""

    def __init__(self, db: Session):
        self.db = db

    def create_promotion(
        self, promotion_data: PromotionCreate, created_by: Optional[int] = None
    ) -> Promotion:
        """Create a new promotion"""
        try:
            # Generate UUID
            promotion_uuid = uuid.uuid4()

            # Create promotion
            promotion = Promotion(
                uuid=promotion_uuid,
                name=promotion_data.name,
                description=promotion_data.description,
                promotion_type=promotion_data.promotion_type,
                start_date=promotion_data.start_date,
                end_date=promotion_data.end_date,
                timezone=promotion_data.timezone,
                discount_type=promotion_data.discount_type,
                discount_value=promotion_data.discount_value,
                max_discount_amount=promotion_data.max_discount_amount,
                min_order_amount=promotion_data.min_order_amount,
                target_type=promotion_data.target_type,
                target_items=promotion_data.target_items,
                target_customer_segments=promotion_data.target_customer_segments,
                target_tiers=promotion_data.target_tiers,
                max_uses_total=promotion_data.max_uses_total,
                max_uses_per_customer=promotion_data.max_uses_per_customer,
                conditions=promotion_data.conditions,
                stackable=promotion_data.stackable,
                requires_coupon=promotion_data.requires_coupon,
                title=promotion_data.title,
                subtitle=promotion_data.subtitle,
                image_url=promotion_data.image_url,
                banner_text=promotion_data.banner_text,
                terms_and_conditions=promotion_data.terms_and_conditions,
                priority=promotion_data.priority,
                auto_apply=promotion_data.auto_apply,
                is_featured=promotion_data.is_featured,
                is_public=promotion_data.is_public,
                ab_test_variant=promotion_data.ab_test_variant,
                ab_test_traffic_split=promotion_data.ab_test_traffic_split,
            )

            # Set initial status based on start date
            now = datetime.utcnow()
            if promotion_data.start_date > now:
                promotion.status = PromotionStatus.SCHEDULED
            else:
                promotion.status = PromotionStatus.ACTIVE

            self.db.add(promotion)
            self.db.commit()
            self.db.refresh(promotion)

            logger.info(f"Created promotion: {promotion.name} (ID: {promotion.id})")
            return promotion

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating promotion: {str(e)}")
            raise

    def update_promotion(
        self,
        promotion_id: int,
        update_data: PromotionUpdate,
        updated_by: Optional[int] = None,
    ) -> Promotion:
        """Update an existing promotion"""
        try:
            promotion = (
                self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
            )

            if not promotion:
                raise ValueError(f"Promotion {promotion_id} not found")

            # Validate that we can update this promotion
            if promotion.status in [PromotionStatus.CANCELLED, PromotionStatus.ENDED]:
                raise ValueError(
                    f"Cannot update promotion with status {promotion.status}"
                )

            # Update fields
            update_dict = update_data.model_dump(exclude_unset=True)
            for field, value in update_dict.items():
                setattr(promotion, field, value)

            promotion.updated_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(promotion)

            logger.info(f"Updated promotion: {promotion_id}")
            return promotion

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating promotion {promotion_id}: {str(e)}")
            raise

    def get_promotion(self, promotion_id: int) -> Optional[Promotion]:
        """Get a promotion by ID"""
        return self.db.query(Promotion).filter(Promotion.id == promotion_id).first()

    def get_promotion_by_uuid(self, promotion_uuid: str) -> Optional[Promotion]:
        """Get a promotion by UUID"""
        return self.db.query(Promotion).filter(Promotion.uuid == promotion_uuid).first()

    def search_promotions(
        self, params: PromotionSearchParams
    ) -> PromotionSearchResponse:
        """Search promotions with filters and pagination"""
        try:
            query = self.db.query(Promotion)

            # Apply filters
            if params.query:
                search_term = f"%{params.query}%"
                query = query.filter(
                    or_(
                        Promotion.name.ilike(search_term),
                        Promotion.title.ilike(search_term),
                        Promotion.description.ilike(search_term),
                    )
                )

            if params.promotion_type:
                query = query.filter(
                    Promotion.promotion_type.in_(params.promotion_type)
                )

            if params.status:
                query = query.filter(Promotion.status.in_(params.status))

            if params.discount_type:
                query = query.filter(Promotion.discount_type.in_(params.discount_type))

            if params.is_featured is not None:
                query = query.filter(Promotion.is_featured == params.is_featured)

            if params.is_public is not None:
                query = query.filter(Promotion.is_public == params.is_public)

            if params.start_date_from:
                query = query.filter(Promotion.start_date >= params.start_date_from)

            if params.start_date_to:
                query = query.filter(Promotion.start_date <= params.start_date_to)

            if params.requires_coupon is not None:
                query = query.filter(
                    Promotion.requires_coupon == params.requires_coupon
                )

            if params.stackable is not None:
                query = query.filter(Promotion.stackable == params.stackable)

            if params.min_discount_value is not None:
                query = query.filter(
                    Promotion.discount_value >= params.min_discount_value
                )

            if params.max_discount_value is not None:
                query = query.filter(
                    Promotion.discount_value <= params.max_discount_value
                )

            if params.target_customer_segment:
                query = query.filter(
                    Promotion.target_customer_segments.contains(
                        [params.target_customer_segment]
                    )
                )

            # Get total count
            total = query.count()

            # Apply sorting
            sort_column = getattr(Promotion, params.sort_by, Promotion.created_at)
            if params.sort_order == "desc":
                query = query.order_by(sort_column.desc())
            else:
                query = query.order_by(sort_column)

            # Apply pagination
            offset = (params.page - 1) * params.page_size
            promotions = query.offset(offset).limit(params.page_size).all()

            # Convert to summaries
            summaries = [
                PromotionSummary(
                    id=p.id,
                    uuid=p.uuid,
                    name=p.name,
                    promotion_type=p.promotion_type,
                    status=p.status,
                    discount_type=p.discount_type,
                    discount_value=p.discount_value,
                    start_date=p.start_date,
                    end_date=p.end_date,
                    current_uses=p.current_uses,
                    max_uses_total=p.max_uses_total,
                    is_featured=p.is_featured,
                    is_active=p.is_active,
                    days_remaining=p.days_remaining,
                )
                for p in promotions
            ]

            total_pages = (total + params.page_size - 1) // params.page_size

            return PromotionSearchResponse(
                promotions=summaries,
                total=total,
                page=params.page,
                page_size=params.page_size,
                total_pages=total_pages,
            )

        except Exception as e:
            logger.error(f"Error searching promotions: {str(e)}")
            return PromotionSearchResponse(
                promotions=[],
                total=0,
                page=params.page,
                page_size=params.page_size,
                total_pages=0,
            )

    def activate_promotion(self, promotion_id: int) -> bool:
        """Activate a promotion"""
        try:
            promotion = (
                self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
            )

            if not promotion:
                return False

            # Validate activation conditions
            now = datetime.utcnow()
            if promotion.end_date <= now:
                raise ValueError("Cannot activate expired promotion")

            if promotion.status == PromotionStatus.CANCELLED:
                raise ValueError("Cannot activate cancelled promotion")

            promotion.status = PromotionStatus.ACTIVE
            promotion.updated_at = now

            self.db.commit()

            logger.info(f"Activated promotion: {promotion_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error activating promotion {promotion_id}: {str(e)}")
            raise

    def pause_promotion(self, promotion_id: int) -> bool:
        """Pause a promotion"""
        try:
            promotion = (
                self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
            )

            if not promotion:
                return False

            if promotion.status != PromotionStatus.ACTIVE:
                raise ValueError(
                    f"Cannot pause promotion with status {promotion.status}"
                )

            promotion.status = PromotionStatus.PAUSED
            promotion.updated_at = datetime.utcnow()

            self.db.commit()

            logger.info(f"Paused promotion: {promotion_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error pausing promotion {promotion_id}: {str(e)}")
            raise

    def cancel_promotion(self, promotion_id: int, reason: Optional[str] = None) -> bool:
        """Cancel a promotion"""
        try:
            promotion = (
                self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
            )

            if not promotion:
                return False

            if promotion.status in [PromotionStatus.CANCELLED, PromotionStatus.ENDED]:
                return True  # Already cancelled/ended

            promotion.status = PromotionStatus.CANCELLED
            promotion.updated_at = datetime.utcnow()

            self.db.commit()

            logger.info(f"Cancelled promotion: {promotion_id}, reason: {reason}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error cancelling promotion {promotion_id}: {str(e)}")
            raise

    def end_promotion(self, promotion_id: int) -> bool:
        """End a promotion (natural completion)"""
        try:
            promotion = (
                self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
            )

            if not promotion:
                return False

            promotion.status = PromotionStatus.ENDED
            promotion.updated_at = datetime.utcnow()

            self.db.commit()

            logger.info(f"Ended promotion: {promotion_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error ending promotion {promotion_id}: {str(e)}")
            raise

    def record_promotion_usage(
        self,
        promotion_id: int,
        customer_id: Optional[int],
        order_id: int,
        discount_amount: float,
        original_order_amount: float,
        final_order_amount: float,
        usage_method: str = "auto_applied",
        coupon_code: Optional[str] = None,
        staff_member_id: Optional[int] = None,
    ) -> PromotionUsage:
        """Record promotion usage"""
        try:
            # Update promotion usage count
            promotion = (
                self.db.query(Promotion).filter(Promotion.id == promotion_id).first()
            )

            if promotion:
                promotion.current_uses += 1
                promotion.revenue_generated += final_order_amount
                promotion.conversions += 1

            # Create usage record
            usage = PromotionUsage(
                promotion_id=promotion_id,
                customer_id=customer_id,
                order_id=order_id,
                discount_amount=discount_amount,
                original_order_amount=original_order_amount,
                final_order_amount=final_order_amount,
                usage_method=usage_method,
                coupon_code=coupon_code,
                staff_member_id=staff_member_id,
            )

            self.db.add(usage)
            self.db.commit()
            self.db.refresh(usage)

            logger.info(
                f"Recorded promotion usage: {promotion_id} for order {order_id}"
            )
            return usage

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error recording promotion usage: {str(e)}")
            raise

    def get_active_promotions(
        self,
        customer_id: Optional[int] = None,
        customer_tier: Optional[str] = None,
        featured_only: bool = False,
        public_only: bool = True,
    ) -> List[Promotion]:
        """Get currently active promotions"""
        now = datetime.utcnow()

        query = self.db.query(Promotion).filter(
            Promotion.status == PromotionStatus.ACTIVE,
            Promotion.start_date <= now,
            Promotion.end_date >= now,
        )

        if public_only:
            query = query.filter(Promotion.is_public == True)

        if featured_only:
            query = query.filter(Promotion.is_featured == True)

        if customer_tier:
            query = query.filter(
                or_(
                    Promotion.target_tiers.is_(None),
                    Promotion.target_tiers.contains([customer_tier]),
                )
            )

        # Filter by usage limits if customer is provided
        if customer_id:
            # Subquery to get customer usage count for each promotion
            customer_usage_subquery = (
                self.db.query(
                    PromotionUsage.promotion_id,
                    func.count(PromotionUsage.id).label("usage_count"),
                )
                .filter(PromotionUsage.customer_id == customer_id)
                .group_by(PromotionUsage.promotion_id)
                .subquery()
            )

            query = query.outerjoin(
                customer_usage_subquery,
                Promotion.id == customer_usage_subquery.c.promotion_id,
            ).filter(
                or_(
                    Promotion.max_uses_per_customer.is_(None),
                    Promotion.max_uses_per_customer
                    > func.coalesce(customer_usage_subquery.c.usage_count, 0),
                )
            )

        return query.order_by(
            Promotion.priority.desc(), Promotion.created_at.desc()
        ).all()

    def get_featured_promotions(self, limit: int = 10) -> List[Promotion]:
        """Get featured promotions for display"""
        now = datetime.utcnow()

        return (
            self.db.query(Promotion)
            .filter(
                Promotion.status == PromotionStatus.ACTIVE,
                Promotion.is_featured == True,
                Promotion.is_public == True,
                Promotion.start_date <= now,
                Promotion.end_date >= now,
            )
            .order_by(Promotion.priority.desc(), Promotion.created_at.desc())
            .limit(limit)
            .all()
        )

    def update_promotion_status_by_schedule(self) -> Dict[str, int]:
        """Update promotion statuses based on their schedule"""
        try:
            now = datetime.utcnow()

            # Activate scheduled promotions
            activated = (
                self.db.query(Promotion)
                .filter(
                    Promotion.status == PromotionStatus.SCHEDULED,
                    Promotion.start_date <= now,
                )
                .update({"status": PromotionStatus.ACTIVE, "updated_at": now})
            )

            # Expire active promotions
            expired = (
                self.db.query(Promotion)
                .filter(
                    Promotion.status == PromotionStatus.ACTIVE, Promotion.end_date < now
                )
                .update({"status": PromotionStatus.EXPIRED, "updated_at": now})
            )

            self.db.commit()

            logger.info(
                f"Updated promotion statuses: {activated} activated, {expired} expired"
            )

            return {"activated": activated, "expired": expired}

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating promotion statuses: {str(e)}")
            return {"activated": 0, "expired": 0}

    def create_ab_test(self, ab_config: ABTestConfig) -> List[Promotion]:
        """Create A/B test promotions"""
        try:
            created_promotions = []

            for variant in ab_config.variants:
                # Create promotion for this variant
                promotion_data = PromotionCreate(**variant.promotion_config)
                promotion_data.ab_test_variant = variant.variant_name
                promotion_data.ab_test_traffic_split = variant.traffic_split

                # Add test name to promotion name
                promotion_data.name = f"{ab_config.test_name} - {variant.variant_name}"

                promotion = self.create_promotion(promotion_data)
                created_promotions.append(promotion)

            logger.info(
                f"Created A/B test: {ab_config.test_name} with {len(created_promotions)} variants"
            )
            return created_promotions

        except Exception as e:
            logger.error(f"Error creating A/B test: {str(e)}")
            raise

    def get_promotion_analytics_summary(
        self,
        promotion_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive analytics for a promotion"""
        try:
            promotion = self.get_promotion(promotion_id)
            if not promotion:
                return {}

            # Usage analytics
            usage_query = self.db.query(PromotionUsage).filter(
                PromotionUsage.promotion_id == promotion_id
            )

            if start_date:
                usage_query = usage_query.filter(
                    PromotionUsage.created_at >= start_date
                )

            if end_date:
                usage_query = usage_query.filter(PromotionUsage.created_at <= end_date)

            usages = usage_query.all()

            # Calculate metrics
            total_usage = len(usages)
            total_discount = sum(usage.discount_amount for usage in usages)
            total_revenue = sum(usage.final_order_amount for usage in usages)
            unique_customers = len(
                set(usage.customer_id for usage in usages if usage.customer_id)
            )

            # Conversion rate
            conversion_rate = (
                (promotion.conversions / promotion.impressions * 100)
                if promotion.impressions > 0
                else 0
            )

            # Average metrics
            avg_discount = total_discount / total_usage if total_usage > 0 else 0
            avg_order_value = total_revenue / total_usage if total_usage > 0 else 0

            # ROI calculation (simplified)
            promotion_cost = (
                total_discount  # Simplified - actual cost might include other factors
            )
            roi = (
                ((total_revenue - promotion_cost) / promotion_cost * 100)
                if promotion_cost > 0
                else 0
            )

            return {
                "promotion_id": promotion_id,
                "promotion_name": promotion.name,
                "status": promotion.status,
                "period": {
                    "start_date": (
                        start_date.isoformat()
                        if start_date
                        else promotion.start_date.isoformat()
                    ),
                    "end_date": (
                        end_date.isoformat()
                        if end_date
                        else promotion.end_date.isoformat()
                    ),
                },
                "usage_metrics": {
                    "total_usage": total_usage,
                    "unique_customers": unique_customers,
                    "usage_percentage": (
                        (total_usage / promotion.max_uses_total * 100)
                        if promotion.max_uses_total
                        else 0
                    ),
                },
                "financial_metrics": {
                    "total_discount": round(total_discount, 2),
                    "total_revenue": round(total_revenue, 2),
                    "average_discount": round(avg_discount, 2),
                    "average_order_value": round(avg_order_value, 2),
                    "roi_percentage": round(roi, 2),
                },
                "engagement_metrics": {
                    "impressions": promotion.impressions,
                    "clicks": promotion.clicks,
                    "conversions": promotion.conversions,
                    "conversion_rate": round(conversion_rate, 2),
                    "click_through_rate": round(
                        (
                            (promotion.clicks / promotion.impressions * 100)
                            if promotion.impressions > 0
                            else 0
                        ),
                        2,
                    ),
                },
            }

        except Exception as e:
            logger.error(f"Error getting promotion analytics: {str(e)}")
            return {}

    def duplicate_promotion(
        self, promotion_id: int, new_name: str, start_date: datetime, end_date: datetime
    ) -> Promotion:
        """Duplicate an existing promotion with new dates"""
        try:
            original = self.get_promotion(promotion_id)
            if not original:
                raise ValueError(f"Promotion {promotion_id} not found")

            # Create new promotion data
            promotion_data = PromotionCreate(
                name=new_name,
                description=original.description,
                promotion_type=original.promotion_type,
                start_date=start_date,
                end_date=end_date,
                timezone=original.timezone,
                discount_type=original.discount_type,
                discount_value=original.discount_value,
                max_discount_amount=original.max_discount_amount,
                min_order_amount=original.min_order_amount,
                target_type=original.target_type,
                target_items=original.target_items,
                target_customer_segments=original.target_customer_segments,
                target_tiers=original.target_tiers,
                max_uses_total=original.max_uses_total,
                max_uses_per_customer=original.max_uses_per_customer,
                conditions=original.conditions,
                stackable=original.stackable,
                requires_coupon=original.requires_coupon,
                title=original.title,
                subtitle=original.subtitle,
                image_url=original.image_url,
                banner_text=original.banner_text,
                terms_and_conditions=original.terms_and_conditions,
                priority=original.priority,
                auto_apply=original.auto_apply,
                is_featured=original.is_featured,
                is_public=original.is_public,
            )

            duplicated = self.create_promotion(promotion_data)

            logger.info(f"Duplicated promotion {promotion_id} as {duplicated.id}")
            return duplicated

        except Exception as e:
            logger.error(f"Error duplicating promotion {promotion_id}: {str(e)}")
            raise
