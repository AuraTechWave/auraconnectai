# backend/modules/promotions/services/ab_testing_service.py

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import logging
import random
import hashlib

from ..models.promotion_models import (
    Promotion,
    PromotionStatus,
    PromotionUsage,
    PromotionAnalytics,
)
from ..schemas.promotion_schemas import PromotionCreate
from ..services.promotion_service import PromotionService
from modules.customers.models.customer_models import Customer

logger = logging.getLogger(__name__)


class ABTestingService:
    """Service for A/B testing promotions"""

    def __init__(self, db: Session):
        self.db = db
        self.promotion_service = PromotionService(db)

    def create_ab_test(
        self,
        test_name: str,
        control_promotion: PromotionCreate,
        variant_promotions: List[PromotionCreate],
        test_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Create an A/B test with control and variant promotions

        Args:
            test_name: Name of the A/B test
            control_promotion: Control promotion configuration
            variant_promotions: List of variant promotion configurations
            test_config: Test configuration including traffic split, duration, etc.

        Returns:
            Dictionary with test information and created promotions
        """
        try:
            # Validate test configuration
            self._validate_ab_test_config(test_config, len(variant_promotions))

            # Generate unique test ID
            test_id = f"ab_{datetime.utcnow().timestamp()}_{hash(test_name) % 10000}"

            # Create control promotion
            control = self.promotion_service.create_promotion(control_promotion)
            control.status = PromotionStatus.DRAFT

            # Add A/B test metadata to control
            if not control.metadata:
                control.metadata = {}

            control.metadata["ab_test"] = {
                "test_id": test_id,
                "test_name": test_name,
                "variant_type": "control",
                "variant_id": "control",
                "traffic_percentage": test_config.get("control_traffic_percentage", 50),
                "test_config": test_config,
                "created_at": datetime.utcnow().isoformat(),
                "test_status": "draft",
            }

            # Create variant promotions
            variants = []
            for idx, variant_data in enumerate(variant_promotions):
                variant = self.promotion_service.create_promotion(variant_data)
                variant.status = PromotionStatus.DRAFT

                if not variant.metadata:
                    variant.metadata = {}

                variant_id = f"variant_{idx + 1}"
                traffic_percentage = (
                    test_config.get("variant_traffic_percentages", [])[idx]
                    if idx < len(test_config.get("variant_traffic_percentages", []))
                    else (50 / len(variant_promotions))
                )

                variant.metadata["ab_test"] = {
                    "test_id": test_id,
                    "test_name": test_name,
                    "variant_type": "variant",
                    "variant_id": variant_id,
                    "traffic_percentage": traffic_percentage,
                    "test_config": test_config,
                    "created_at": datetime.utcnow().isoformat(),
                    "test_status": "draft",
                }

                variants.append(variant)

            self.db.commit()

            logger.info(f"Created A/B test '{test_name}' with {len(variants)} variants")

            return {
                "test_id": test_id,
                "test_name": test_name,
                "control_promotion": control,
                "variant_promotions": variants,
                "test_config": test_config,
                "total_promotions": len(variants) + 1,
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error creating A/B test: {str(e)}")
            raise

    def _validate_ab_test_config(self, test_config: Dict[str, Any], variant_count: int):
        """Validate A/B test configuration"""

        # Check traffic split
        control_traffic = test_config.get("control_traffic_percentage", 50)
        variant_traffic_percentages = test_config.get("variant_traffic_percentages", [])

        if variant_traffic_percentages:
            if len(variant_traffic_percentages) != variant_count:
                raise ValueError(
                    "Number of variant traffic percentages must match number of variants"
                )

            total_traffic = control_traffic + sum(variant_traffic_percentages)
            if abs(total_traffic - 100) > 0.01:  # Allow small floating point errors
                raise ValueError(
                    f"Traffic percentages must sum to 100, got {total_traffic}"
                )

        # Check test duration
        if "duration_days" in test_config and test_config["duration_days"] < 1:
            raise ValueError("Test duration must be at least 1 day")

        # Check minimum sample size
        if (
            "minimum_sample_size" in test_config
            and test_config["minimum_sample_size"] < 10
        ):
            raise ValueError("Minimum sample size must be at least 10")

    def assign_user_to_variant(
        self,
        test_id: str,
        customer_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Assign a user to a variant in an A/B test

        Args:
            test_id: A/B test identifier
            customer_id: Customer ID (if authenticated)
            session_id: Session ID (for anonymous users)

        Returns:
            Dictionary with variant assignment information
        """
        try:
            # Get test promotions
            test_promotions = (
                self.db.query(Promotion)
                .filter(Promotion.metadata["ab_test"]["test_id"].astext == test_id)
                .all()
            )

            if not test_promotions:
                raise ValueError(f"A/B test {test_id} not found")

            # Check if test is active
            control_promotion = next(
                (
                    p
                    for p in test_promotions
                    if p.metadata["ab_test"]["variant_type"] == "control"
                ),
                None,
            )
            if (
                not control_promotion
                or control_promotion.metadata["ab_test"]["test_status"] != "active"
            ):
                raise ValueError(f"A/B test {test_id} is not active")

            # Generate deterministic assignment based on user identifier
            user_identifier = str(customer_id) if customer_id else session_id
            if not user_identifier:
                raise ValueError("Either customer_id or session_id must be provided")

            # Create hash for consistent assignment
            hash_input = f"{test_id}:{user_identifier}"
            user_hash = int(hashlib.md5(hash_input.encode()).hexdigest(), 16)
            assignment_value = (user_hash % 100) + 1  # 1-100

            # Determine variant based on traffic split
            cumulative_percentage = 0
            assigned_promotion = None

            # Sort promotions to ensure consistent ordering (control first, then variants)
            sorted_promotions = sorted(
                test_promotions,
                key=lambda p: (
                    p.metadata["ab_test"]["variant_type"] != "control",
                    p.metadata["ab_test"]["variant_id"],
                ),
            )

            for promotion in sorted_promotions:
                ab_test_data = promotion.metadata["ab_test"]
                traffic_percentage = ab_test_data["traffic_percentage"]
                cumulative_percentage += traffic_percentage

                if assignment_value <= cumulative_percentage:
                    assigned_promotion = promotion
                    break

            if not assigned_promotion:
                # Fallback to control if something went wrong
                assigned_promotion = control_promotion

            # Record assignment (you might want to store this in a separate table)
            assignment_data = {
                "test_id": test_id,
                "customer_id": customer_id,
                "session_id": session_id,
                "assigned_variant": assigned_promotion.metadata["ab_test"][
                    "variant_id"
                ],
                "promotion_id": assigned_promotion.id,
                "assigned_at": datetime.utcnow().isoformat(),
                "assignment_hash": user_hash % 100,
            }

            return assignment_data

        except Exception as e:
            logger.error(f"Error assigning user to variant: {str(e)}")
            raise

    def start_ab_test(self, test_id: str) -> Dict[str, Any]:
        """Start an A/B test by activating all its promotions"""

        try:
            test_promotions = (
                self.db.query(Promotion)
                .filter(Promotion.metadata["ab_test"]["test_id"].astext == test_id)
                .all()
            )

            if not test_promotions:
                raise ValueError(f"A/B test {test_id} not found")

            # Activate all test promotions
            for promotion in test_promotions:
                promotion.status = PromotionStatus.ACTIVE
                promotion.metadata["ab_test"]["test_status"] = "active"
                promotion.metadata["ab_test"][
                    "started_at"
                ] = datetime.utcnow().isoformat()

            self.db.commit()

            logger.info(
                f"Started A/B test {test_id} with {len(test_promotions)} promotions"
            )

            return {
                "test_id": test_id,
                "status": "active",
                "promotions_activated": len(test_promotions),
                "started_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error starting A/B test: {str(e)}")
            raise

    def stop_ab_test(
        self, test_id: str, winning_variant: Optional[str] = None
    ) -> Dict[str, Any]:
        """Stop an A/B test and optionally declare a winner"""

        try:
            test_promotions = (
                self.db.query(Promotion)
                .filter(Promotion.metadata["ab_test"]["test_id"].astext == test_id)
                .all()
            )

            if not test_promotions:
                raise ValueError(f"A/B test {test_id} not found")

            stopped_at = datetime.utcnow().isoformat()

            # Stop all test promotions
            for promotion in test_promotions:
                variant_id = promotion.metadata["ab_test"]["variant_id"]

                if winning_variant and variant_id == winning_variant:
                    # Keep winner active
                    promotion.metadata["ab_test"]["test_status"] = "winner"
                    promotion.metadata["ab_test"]["stopped_at"] = stopped_at
                else:
                    # Pause non-winners
                    promotion.status = PromotionStatus.PAUSED
                    promotion.metadata["ab_test"]["test_status"] = "stopped"
                    promotion.metadata["ab_test"]["stopped_at"] = stopped_at

                    if winning_variant and variant_id != winning_variant:
                        promotion.metadata["ab_test"]["test_status"] = "loser"

            self.db.commit()

            logger.info(
                f"Stopped A/B test {test_id}, winner: {winning_variant or 'none'}"
            )

            return {
                "test_id": test_id,
                "status": "stopped",
                "winning_variant": winning_variant,
                "stopped_at": stopped_at,
                "promotions_affected": len(test_promotions),
            }

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error stopping A/B test: {str(e)}")
            raise

    def get_ab_test_results(self, test_id: str) -> Dict[str, Any]:
        """Get comprehensive results for an A/B test"""

        try:
            test_promotions = (
                self.db.query(Promotion)
                .filter(Promotion.metadata["ab_test"]["test_id"].astext == test_id)
                .all()
            )

            if not test_promotions:
                raise ValueError(f"A/B test {test_id} not found")

            # Get test metadata
            control_promotion = next(
                (
                    p
                    for p in test_promotions
                    if p.metadata["ab_test"]["variant_type"] == "control"
                ),
                None,
            )
            test_config = control_promotion.metadata["ab_test"]["test_config"]
            test_name = control_promotion.metadata["ab_test"]["test_name"]

            # Calculate results for each variant
            variant_results = []

            for promotion in test_promotions:
                ab_test_data = promotion.metadata["ab_test"]

                # Get usage statistics
                usage_stats = (
                    self.db.query(
                        func.count(PromotionUsage.id).label("total_usage"),
                        func.count(func.distinct(PromotionUsage.customer_id)).label(
                            "unique_customers"
                        ),
                        func.sum(PromotionUsage.discount_amount).label(
                            "total_discount"
                        ),
                        func.sum(PromotionUsage.final_order_amount).label(
                            "total_revenue"
                        ),
                        func.avg(PromotionUsage.final_order_amount).label(
                            "avg_order_value"
                        ),
                    )
                    .filter(PromotionUsage.promotion_id == promotion.id)
                    .first()
                )

                # Calculate conversion rate (assuming impressions are tracked)
                impressions = promotion.impressions or 0
                conversions = usage_stats.total_usage or 0
                conversion_rate = (
                    (conversions / impressions * 100) if impressions > 0 else 0
                )

                # Calculate ROI
                total_discount = float(usage_stats.total_discount or 0)
                total_revenue = float(usage_stats.total_revenue or 0)
                roi = (
                    ((total_revenue - total_discount) / total_discount * 100)
                    if total_discount > 0
                    else 0
                )

                variant_result = {
                    "variant_id": ab_test_data["variant_id"],
                    "variant_type": ab_test_data["variant_type"],
                    "promotion_id": promotion.id,
                    "promotion_name": promotion.name,
                    "traffic_percentage": ab_test_data["traffic_percentage"],
                    "metrics": {
                        "impressions": impressions,
                        "conversions": conversions,
                        "conversion_rate": round(conversion_rate, 2),
                        "unique_customers": usage_stats.unique_customers or 0,
                        "total_discount": total_discount,
                        "total_revenue": total_revenue,
                        "avg_order_value": float(usage_stats.avg_order_value or 0),
                        "roi_percentage": round(roi, 2),
                    },
                    "status": ab_test_data.get("test_status", "unknown"),
                }

                variant_results.append(variant_result)

            # Sort results (control first, then variants)
            variant_results.sort(
                key=lambda x: (x["variant_type"] != "control", x["variant_id"])
            )

            # Determine statistical significance and winner
            significance_result = self._calculate_statistical_significance(
                variant_results
            )

            return {
                "test_id": test_id,
                "test_name": test_name,
                "test_config": test_config,
                "test_status": control_promotion.metadata["ab_test"].get(
                    "test_status", "unknown"
                ),
                "started_at": control_promotion.metadata["ab_test"].get("started_at"),
                "stopped_at": control_promotion.metadata["ab_test"].get("stopped_at"),
                "variant_results": variant_results,
                "statistical_analysis": significance_result,
                "winner": self._determine_winner(variant_results, significance_result),
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting A/B test results: {str(e)}")
            raise

    def _calculate_statistical_significance(
        self, variant_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate statistical significance between variants"""

        try:
            # This is a simplified statistical significance calculation
            # In production, you'd want to use proper statistical libraries like scipy

            control = next(
                (v for v in variant_results if v["variant_type"] == "control"), None
            )
            if not control:
                return {"significance": "insufficient_data", "confidence_level": 0}

            control_metrics = control["metrics"]
            control_conversion_rate = control_metrics["conversion_rate"]
            control_conversions = control_metrics["conversions"]
            control_impressions = control_metrics["impressions"]

            if control_impressions < 100 or control_conversions < 10:
                return {"significance": "insufficient_data", "confidence_level": 0}

            # Calculate significance for each variant vs control
            significance_results = []

            for variant in variant_results:
                if variant["variant_type"] == "control":
                    continue

                variant_metrics = variant["metrics"]
                variant_conversion_rate = variant_metrics["conversion_rate"]
                variant_conversions = variant_metrics["conversions"]
                variant_impressions = variant_metrics["impressions"]

                if variant_impressions < 100 or variant_conversions < 10:
                    significance_results.append(
                        {
                            "variant_id": variant["variant_id"],
                            "significance": "insufficient_data",
                            "confidence_level": 0,
                            "improvement": 0,
                        }
                    )
                    continue

                # Simplified z-test calculation
                improvement = (
                    (
                        (variant_conversion_rate - control_conversion_rate)
                        / control_conversion_rate
                        * 100
                    )
                    if control_conversion_rate > 0
                    else 0
                )

                # Simple confidence level estimation (this is very simplified)
                sample_size_factor = (
                    min(control_impressions, variant_impressions) / 1000
                )
                conversion_diff = abs(variant_conversion_rate - control_conversion_rate)

                if conversion_diff < 0.5:
                    confidence_level = 0
                    significance = "not_significant"
                elif conversion_diff < 1.0:
                    confidence_level = min(85, 60 + sample_size_factor * 25)
                    significance = "weak" if confidence_level < 90 else "significant"
                else:
                    confidence_level = min(99, 80 + sample_size_factor * 19)
                    significance = "significant" if confidence_level >= 95 else "weak"

                significance_results.append(
                    {
                        "variant_id": variant["variant_id"],
                        "significance": significance,
                        "confidence_level": round(confidence_level, 1),
                        "improvement": round(improvement, 2),
                    }
                )

            return {
                "control_variant": control["variant_id"],
                "variant_comparisons": significance_results,
                "overall_significance": (
                    "significant"
                    if any(
                        r["significance"] == "significant" for r in significance_results
                    )
                    else "weak"
                ),
            }

        except Exception as e:
            logger.error(f"Error calculating statistical significance: {str(e)}")
            return {"significance": "error", "confidence_level": 0}

    def _determine_winner(
        self, variant_results: List[Dict[str, Any]], significance_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Determine the winning variant based on results and significance"""

        try:
            # Find the variant with the highest conversion rate that is statistically significant
            best_variant = None
            best_conversion_rate = 0

            for variant in variant_results:
                conversion_rate = variant["metrics"]["conversion_rate"]
                variant_id = variant["variant_id"]

                # Check if this variant is statistically significant
                is_significant = False
                if variant["variant_type"] == "control":
                    is_significant = True  # Control is always "significant"
                else:
                    for comparison in significance_result.get(
                        "variant_comparisons", []
                    ):
                        if (
                            comparison["variant_id"] == variant_id
                            and comparison["significance"] == "significant"
                        ):
                            is_significant = True
                            break

                if is_significant and conversion_rate > best_conversion_rate:
                    best_conversion_rate = conversion_rate
                    best_variant = variant

            if best_variant:
                return {
                    "variant_id": best_variant["variant_id"],
                    "variant_type": best_variant["variant_type"],
                    "conversion_rate": best_conversion_rate,
                    "improvement_over_control": (
                        0
                        if best_variant["variant_type"] == "control"
                        else (
                            round(
                                (
                                    (
                                        best_conversion_rate
                                        - next(
                                            v["metrics"]["conversion_rate"]
                                            for v in variant_results
                                            if v["variant_type"] == "control"
                                        )
                                    )
                                    / next(
                                        v["metrics"]["conversion_rate"]
                                        for v in variant_results
                                        if v["variant_type"] == "control"
                                    )
                                    * 100
                                ),
                                2,
                            )
                            if next(
                                v["metrics"]["conversion_rate"]
                                for v in variant_results
                                if v["variant_type"] == "control"
                            )
                            > 0
                            else 0
                        )
                    ),
                }

            return None

        except Exception as e:
            logger.error(f"Error determining winner: {str(e)}")
            return None

    def get_active_ab_tests(self) -> List[Dict[str, Any]]:
        """Get all currently active A/B tests"""

        try:
            active_tests = (
                self.db.query(Promotion)
                .filter(Promotion.metadata["ab_test"]["test_status"].astext == "active")
                .all()
            )

            # Group by test_id
            tests_by_id = {}
            for promotion in active_tests:
                test_id = promotion.metadata["ab_test"]["test_id"]
                if test_id not in tests_by_id:
                    tests_by_id[test_id] = {
                        "test_id": test_id,
                        "test_name": promotion.metadata["ab_test"]["test_name"],
                        "started_at": promotion.metadata["ab_test"].get("started_at"),
                        "promotions": [],
                    }

                tests_by_id[test_id]["promotions"].append(
                    {
                        "promotion_id": promotion.id,
                        "variant_id": promotion.metadata["ab_test"]["variant_id"],
                        "variant_type": promotion.metadata["ab_test"]["variant_type"],
                        "traffic_percentage": promotion.metadata["ab_test"][
                            "traffic_percentage"
                        ],
                    }
                )

            return list(tests_by_id.values())

        except Exception as e:
            logger.error(f"Error getting active A/B tests: {str(e)}")
            raise
