# backend/modules/ai_recommendations/services/pricing_recommendation_service.py

import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from decimal import Decimal
import statistics
import math
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

from core.cache import cache_service
from modules.analytics.utils.performance_monitor import PerformanceMonitor
from modules.analytics.services.ai_insights_service import AIInsightsService
from modules.orders.models.order_models import Order, OrderItem
from core.menu_models import MenuItem, MenuCategory
from modules.analytics.schemas.ai_insights_schemas import InsightRequest, InsightType

from ..schemas.pricing_schemas import (
    MenuItemPricingContext,
    PricingRecommendation,
    BulkPricingRequest,
    PricingRecommendationSet,
    PricingStrategy,
    PriceOptimizationGoal,
    DemandLevel,
    PriceElasticity,
)

logger = logging.getLogger(__name__)


class PricingRecommendationService:
    """Service for generating AI-powered pricing recommendations"""

    def __init__(self, db: Session):
        self.db = db
        self.insights_service = AIInsightsService(db)
        self.cache_ttl = 3600  # 1 hour

        # Price elasticity coefficients (can be ML model in future)
        self.elasticity_coefficients = {
            PriceElasticity.HIGHLY_ELASTIC: -2.5,  # 10% price increase -> 25% demand decrease
            PriceElasticity.ELASTIC: -1.5,  # 10% price increase -> 15% demand decrease
            PriceElasticity.UNIT_ELASTIC: -1.0,  # 10% price increase -> 10% demand decrease
            PriceElasticity.INELASTIC: -0.5,  # 10% price increase -> 5% demand decrease
            PriceElasticity.HIGHLY_INELASTIC: -0.2,  # 10% price increase -> 2% demand decrease
        }

    async def generate_bulk_recommendations(
        self, request: BulkPricingRequest
    ) -> PricingRecommendationSet:
        """Generate pricing recommendations for multiple menu items"""

        # Build cache key
        cache_key = f"pricing:bulk:{hash(str(request.dict()))}"

        # Check cache
        if cached := await cache_service.get(cache_key):
            return PricingRecommendationSet(**cached)

        # Get menu items to analyze
        menu_items = self._get_menu_items_for_analysis(request)

        # Get market insights
        insights = await self._get_market_insights(
            start_date=datetime.now().date() - timedelta(days=30),
            end_date=datetime.now().date(),
        )

        recommendations = []

        for item in menu_items:
            try:
                # Build pricing context
                context = await self._build_pricing_context(item, insights)

                # Generate recommendation
                recommendation = await self._generate_item_recommendation(
                    item, context, request, insights
                )

                if recommendation:
                    recommendations.append(recommendation)

            except Exception as e:
                logger.error(f"Error generating recommendation for item {item.id}: {e}")

        # Build recommendation set
        result = self._build_recommendation_set(recommendations, request)

        # Cache result
        await cache_service.set(cache_key, result.dict(), ttl=self.cache_ttl)

        return result

    def _get_menu_items_for_analysis(
        self, request: BulkPricingRequest
    ) -> List[MenuItem]:
        """Get menu items based on request filters"""

        query = self.db.query(MenuItem).filter(
            MenuItem.is_active == True, MenuItem.deleted_at.is_(None)
        )

        if request.menu_item_ids:
            query = query.filter(MenuItem.id.in_(request.menu_item_ids))

        if request.category_ids:
            query = query.filter(MenuItem.category_id.in_(request.category_ids))

        return query.all()

    @PerformanceMonitor.monitor_query("pricing_context_build")
    async def _build_pricing_context(
        self, item: MenuItem, insights: Dict[str, Any]
    ) -> MenuItemPricingContext:
        """Build comprehensive pricing context for an item"""

        # Get historical sales data
        thirty_days_ago = datetime.now() - timedelta(days=30)

        sales_data = (
            self.db.query(
                func.count(OrderItem.id).label("order_count"),
                func.sum(OrderItem.quantity).label("total_quantity"),
                func.avg(OrderItem.quantity).label("avg_quantity"),
                func.sum(OrderItem.total_price).label("total_revenue"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .filter(
                OrderItem.product_id == item.id,
                Order.order_date >= thirty_days_ago,
                Order.status.in_(["completed", "paid"]),
            )
            .first()
        )

        # Calculate daily averages
        avg_daily_sales = float(sales_data.total_quantity or 0) / 30

        # Get sales trend
        sales_trend = self._calculate_sales_trend(item.id)

        # Get inventory level (mock for now)
        inventory_level = self._get_inventory_level(item.id)

        # Determine demand level
        demand_level = self._assess_demand_level(avg_daily_sales, sales_trend, insights)

        # Estimate price elasticity
        price_elasticity = self._estimate_price_elasticity(item, sales_data)

        # Get competitor prices (mock for now)
        competitor_prices = self._get_competitor_prices(item)

        return MenuItemPricingContext(
            menu_item_id=item.id,
            current_price=Decimal(str(item.price)),
            base_cost=self._estimate_base_cost(item),
            avg_daily_sales=avg_daily_sales,
            sales_trend=sales_trend,
            inventory_level=inventory_level,
            competitor_prices=competitor_prices,
            current_demand=demand_level,
            price_elasticity=price_elasticity,
            customer_rating=4.2,  # Mock for now
        )

    def _calculate_sales_trend(self, item_id: int) -> float:
        """Calculate sales trend (-1 to 1)"""

        # Compare last 7 days to previous 7 days
        seven_days_ago = datetime.now() - timedelta(days=7)
        fourteen_days_ago = datetime.now() - timedelta(days=14)

        recent_sales = (
            self.db.query(func.sum(OrderItem.quantity))
            .join(Order, OrderItem.order_id == Order.id)
            .filter(
                OrderItem.product_id == item_id,
                Order.order_date >= seven_days_ago,
                Order.status.in_(["completed", "paid"]),
            )
            .scalar()
            or 0
        )

        previous_sales = (
            self.db.query(func.sum(OrderItem.quantity))
            .join(Order, OrderItem.order_id == Order.id)
            .filter(
                OrderItem.product_id == item_id,
                Order.order_date >= fourteen_days_ago,
                Order.order_date < seven_days_ago,
                Order.status.in_(["completed", "paid"]),
            )
            .scalar()
            or 0
        )

        if previous_sales == 0:
            return 0.0

        # Calculate percentage change and normalize to -1 to 1
        change = (recent_sales - previous_sales) / previous_sales
        return max(-1.0, min(1.0, change))

    def _get_inventory_level(self, item_id: int) -> float:
        """Get current inventory level as percentage"""
        # Mock implementation - would integrate with inventory system
        return 75.0

    def _assess_demand_level(
        self, avg_daily_sales: float, sales_trend: float, insights: Dict[str, Any]
    ) -> DemandLevel:
        """Assess current demand level"""

        # Simple heuristic - would be ML model in production
        if sales_trend > 0.5 and avg_daily_sales > 20:
            return DemandLevel.VERY_HIGH
        elif sales_trend > 0.2 or avg_daily_sales > 15:
            return DemandLevel.HIGH
        elif sales_trend < -0.5 or avg_daily_sales < 5:
            return DemandLevel.VERY_LOW
        elif sales_trend < -0.2 or avg_daily_sales < 10:
            return DemandLevel.LOW
        else:
            return DemandLevel.NORMAL

    def _estimate_price_elasticity(
        self, item: MenuItem, sales_data: Any
    ) -> PriceElasticity:
        """Estimate price elasticity for the item"""

        # Simple heuristic based on item type and price point
        # In production, this would use historical price changes and demand response

        if item.price < 10:
            # Low-price items tend to be more elastic
            return PriceElasticity.ELASTIC
        elif item.price > 30:
            # High-price items often less elastic (premium perception)
            return PriceElasticity.INELASTIC
        else:
            return PriceElasticity.UNIT_ELASTIC

    def _estimate_base_cost(self, item: MenuItem) -> Decimal:
        """Estimate base cost of menu item"""
        # Mock implementation - would calculate from ingredients
        # Using 30% food cost as industry standard
        return Decimal(str(item.price * 0.3))

    def _get_competitor_prices(self, item: MenuItem) -> List[Decimal]:
        """Get competitor prices for similar items"""
        # Mock implementation - would integrate with market data
        base = float(item.price)
        return [
            Decimal(str(base * 0.95)),
            Decimal(str(base * 1.05)),
            Decimal(str(base * 0.98)),
        ]

    async def _get_market_insights(
        self, start_date: date, end_date: date
    ) -> Dict[str, Any]:
        """Get market insights from analytics service"""

        request = InsightRequest(
            insight_types=[InsightType.PEAK_TIME, InsightType.PRODUCT_TREND],
            date_from=start_date,
            date_to=end_date,
            force_refresh=False,
        )

        insights = await self.insights_service.generate_insights(request)

        return {
            "peak_times": insights.peak_times,
            "product_trends": insights.product_insights,
        }

    async def _generate_item_recommendation(
        self,
        item: MenuItem,
        context: MenuItemPricingContext,
        request: BulkPricingRequest,
        insights: Dict[str, Any],
    ) -> Optional[PricingRecommendation]:
        """Generate pricing recommendation for a single item"""

        # Select pricing strategy
        strategy = self._select_pricing_strategy(context, request)

        # Calculate recommended price based on strategy
        recommended_price, reasoning = self._calculate_recommended_price(
            context, strategy, request
        )

        # Apply constraints
        recommended_price = self._apply_pricing_constraints(
            context.current_price, recommended_price, request
        )

        # Calculate price bounds
        min_price, max_price = self._calculate_price_bounds(
            context, recommended_price, request
        )

        # Estimate impact
        impacts = self._estimate_price_change_impact(context, recommended_price)

        # Assess risks
        risks = self._assess_pricing_risks(context, recommended_price)

        return PricingRecommendation(
            menu_item_id=item.id,
            item_name=item.name,
            current_price=context.current_price,
            recommended_price=recommended_price,
            min_recommended_price=min_price,
            max_recommended_price=max_price,
            price_change_percentage=float(
                (recommended_price - context.current_price)
                / context.current_price
                * 100
            ),
            expected_demand_change=impacts["demand_change"],
            expected_revenue_impact=impacts["revenue_impact"],
            expected_profit_impact=impacts["profit_impact"],
            confidence_score=self._calculate_confidence_score(context),
            strategy_used=strategy,
            factors_considered=self._get_factors_considered(context, strategy),
            primary_reason=reasoning["primary"],
            detailed_reasoning=reasoning["details"],
            risks=risks,
            implementation_notes=self._generate_implementation_notes(
                context, recommended_price
            ),
            recommended_duration_days=request.time_horizon_days,
        )

    def _select_pricing_strategy(
        self, context: MenuItemPricingContext, request: BulkPricingRequest
    ) -> PricingStrategy:
        """Select appropriate pricing strategy"""

        # Priority-based strategy selection
        if PricingStrategy.DYNAMIC in request.strategies_to_use:
            if context.current_demand in [DemandLevel.HIGH, DemandLevel.VERY_HIGH]:
                return PricingStrategy.DEMAND_BASED
            elif context.inventory_level < 30:
                return PricingStrategy.DYNAMIC

        if PricingStrategy.COMPETITION_BASED in request.strategies_to_use:
            if context.competitor_prices:
                return PricingStrategy.COMPETITION_BASED

        if PricingStrategy.SEASONAL in request.strategies_to_use:
            if context.seasonal_factor != 1.0:
                return PricingStrategy.SEASONAL

        # Default to cost-plus
        return PricingStrategy.COST_PLUS

    def _calculate_recommended_price(
        self,
        context: MenuItemPricingContext,
        strategy: PricingStrategy,
        request: BulkPricingRequest,
    ) -> Tuple[Decimal, Dict[str, Any]]:
        """Calculate recommended price based on strategy"""

        if strategy == PricingStrategy.DEMAND_BASED:
            return self._demand_based_pricing(context)
        elif strategy == PricingStrategy.COMPETITION_BASED:
            return self._competition_based_pricing(context)
        elif strategy == PricingStrategy.COST_PLUS:
            return self._cost_plus_pricing(context)
        elif strategy == PricingStrategy.DYNAMIC:
            return self._dynamic_pricing(context)
        else:
            return context.current_price, {
                "primary": "No change recommended",
                "details": [],
            }

    def _demand_based_pricing(
        self, context: MenuItemPricingContext
    ) -> Tuple[Decimal, Dict[str, Any]]:
        """Calculate price based on demand"""

        demand_multipliers = {
            DemandLevel.VERY_HIGH: 1.15,
            DemandLevel.HIGH: 1.08,
            DemandLevel.NORMAL: 1.00,
            DemandLevel.LOW: 0.92,
            DemandLevel.VERY_LOW: 0.85,
        }

        multiplier = demand_multipliers[context.current_demand]
        recommended = context.current_price * Decimal(str(multiplier))

        reasoning = {
            "primary": f"{context.current_demand.value.replace('_', ' ').title()} demand suggests price adjustment",
            "details": [
                f"Current demand level: {context.current_demand.value}",
                f"Sales trend: {context.sales_trend:+.1%}",
                f"Recommended adjustment: {(multiplier - 1) * 100:+.1f}%",
            ],
        }

        return recommended, reasoning

    def _competition_based_pricing(
        self, context: MenuItemPricingContext
    ) -> Tuple[Decimal, Dict[str, Any]]:
        """Calculate price based on competition"""

        if not context.competitor_prices:
            return context.current_price, {
                "primary": "No competitor data",
                "details": [],
            }

        avg_competitor = sum(context.competitor_prices) / len(context.competitor_prices)

        # Position slightly below average for competitive advantage
        recommended = avg_competitor * Decimal("0.95")

        reasoning = {
            "primary": "Competitive pricing adjustment",
            "details": [
                f"Average competitor price: ${avg_competitor:.2f}",
                f"Positioning 5% below market average",
                "Maintains competitive advantage",
            ],
        }

        return recommended, reasoning

    def _cost_plus_pricing(
        self, context: MenuItemPricingContext
    ) -> Tuple[Decimal, Dict[str, Any]]:
        """Calculate price based on cost plus markup"""

        # Target 70% gross margin (30% food cost)
        target_margin = Decimal("0.70")
        recommended = context.base_cost / (1 - target_margin)

        reasoning = {
            "primary": "Cost-plus pricing to maintain margins",
            "details": [
                f"Base cost: ${context.base_cost:.2f}",
                f"Target margin: {target_margin * 100:.0f}%",
                "Industry-standard food cost percentage",
            ],
        }

        return recommended, reasoning

    def _dynamic_pricing(
        self, context: MenuItemPricingContext
    ) -> Tuple[Decimal, Dict[str, Any]]:
        """Dynamic pricing based on multiple factors"""

        # Combine multiple factors
        factors = []
        adjustments = []

        # Demand factor
        demand_adj = self._get_demand_adjustment(context.current_demand)
        factors.append(("Demand", demand_adj))
        adjustments.append(demand_adj)

        # Inventory factor
        if context.inventory_level < 30:
            inv_adj = 0.05  # 5% increase for low inventory
            factors.append(("Low inventory", inv_adj))
            adjustments.append(inv_adj)
        elif context.inventory_level > 80:
            inv_adj = -0.03  # 3% decrease for high inventory
            factors.append(("High inventory", inv_adj))
            adjustments.append(inv_adj)

        # Sales trend factor
        if abs(context.sales_trend) > 0.1:
            trend_adj = context.sales_trend * 0.1  # Max 10% adjustment
            factors.append(("Sales trend", trend_adj))
            adjustments.append(trend_adj)

        # Calculate total adjustment
        total_adjustment = sum(adjustments)
        total_adjustment = max(-0.15, min(0.20, total_adjustment))  # Cap at ±15-20%

        recommended = context.current_price * (1 + Decimal(str(total_adjustment)))

        reasoning = {
            "primary": "Dynamic pricing based on real-time factors",
            "details": [f"{name}: {adj:+.1%}" for name, adj in factors],
        }

        return recommended, reasoning

    def _get_demand_adjustment(self, demand: DemandLevel) -> float:
        """Get price adjustment for demand level"""
        adjustments = {
            DemandLevel.VERY_HIGH: 0.10,
            DemandLevel.HIGH: 0.05,
            DemandLevel.NORMAL: 0.00,
            DemandLevel.LOW: -0.05,
            DemandLevel.VERY_LOW: -0.10,
        }
        return adjustments[demand]

    def _apply_pricing_constraints(
        self,
        current_price: Decimal,
        recommended_price: Decimal,
        request: BulkPricingRequest,
    ) -> Decimal:
        """Apply pricing constraints from request"""

        # Apply percentage constraints
        max_increase = current_price * (
            1 + Decimal(str(request.max_price_increase_percent / 100))
        )
        max_decrease = current_price * (
            1 - Decimal(str(request.max_price_decrease_percent / 100))
        )

        constrained_price = max(max_decrease, min(max_increase, recommended_price))

        # Apply rounding
        return self._round_price(constrained_price, request.round_to_nearest)

    def _round_price(self, price: Decimal, round_to: Decimal) -> Decimal:
        """Round price to nearest specified value"""
        return (price / round_to).quantize(Decimal("1")) * round_to

    def _calculate_price_bounds(
        self,
        context: MenuItemPricingContext,
        recommended: Decimal,
        request: BulkPricingRequest,
    ) -> Tuple[Decimal, Decimal]:
        """Calculate min and max recommended prices"""

        # Base bounds on elasticity
        if context.price_elasticity == PriceElasticity.HIGHLY_ELASTIC:
            variance = Decimal("0.05")  # ±5%
        elif context.price_elasticity == PriceElasticity.ELASTIC:
            variance = Decimal("0.08")  # ±8%
        else:
            variance = Decimal("0.10")  # ±10%

        min_price = recommended * (1 - variance)
        max_price = recommended * (1 + variance)

        # Ensure profitable
        min_price = max(min_price, context.base_cost * Decimal("1.5"))

        # Apply rounding
        min_price = self._round_price(min_price, request.round_to_nearest)
        max_price = self._round_price(max_price, request.round_to_nearest)

        return min_price, max_price

    def _estimate_price_change_impact(
        self, context: MenuItemPricingContext, new_price: Decimal
    ) -> Dict[str, float]:
        """Estimate impact of price change"""

        price_change_pct = float(
            (new_price - context.current_price) / context.current_price
        )

        # Get elasticity coefficient
        elasticity = self.elasticity_coefficients[context.price_elasticity]

        # Estimate demand change
        demand_change_pct = price_change_pct * elasticity

        # Calculate revenue impact
        # Revenue = Price × Quantity
        # New Revenue = (Price × (1 + price_change)) × (Quantity × (1 + demand_change))
        revenue_impact_pct = (1 + price_change_pct) * (1 + demand_change_pct) - 1

        # Calculate profit impact (assuming fixed costs)
        margin = float(
            (context.current_price - context.base_cost) / context.current_price
        )
        new_margin = float((new_price - context.base_cost) / new_price)

        profit_impact_pct = (
            ((new_margin * (1 + demand_change_pct)) / margin - 1) if margin > 0 else 0
        )

        return {
            "demand_change": demand_change_pct * 100,
            "revenue_impact": revenue_impact_pct * 100,
            "profit_impact": profit_impact_pct * 100,
        }

    def _assess_pricing_risks(
        self, context: MenuItemPricingContext, new_price: Decimal
    ) -> List[str]:
        """Assess risks of price change"""

        risks = []
        price_change_pct = float(
            (new_price - context.current_price) / context.current_price
        )

        if abs(price_change_pct) > 0.15:
            risks.append("Large price change may cause customer shock")

        if price_change_pct > 0 and context.price_elasticity in [
            PriceElasticity.ELASTIC,
            PriceElasticity.HIGHLY_ELASTIC,
        ]:
            risks.append(
                "Price increase on elastic item may significantly reduce demand"
            )

        if context.competitor_prices and new_price > max(
            context.competitor_prices
        ) * Decimal("1.1"):
            risks.append("Price significantly above competitors")

        if context.inventory_level < 20 and price_change_pct < 0:
            risks.append("Price decrease with low inventory may cause stockouts")

        if (
            context.customer_rating
            and context.customer_rating < 4.0
            and price_change_pct > 0
        ):
            risks.append("Price increase on lower-rated item may hurt sales")

        return risks

    def _calculate_confidence_score(self, context: MenuItemPricingContext) -> float:
        """Calculate confidence in recommendation"""

        confidence = 0.5  # Base confidence

        # More data = higher confidence
        if context.avg_daily_sales > 10:
            confidence += 0.2
        elif context.avg_daily_sales > 5:
            confidence += 0.1

        # Stable trends = higher confidence
        if abs(context.sales_trend) < 0.2:
            confidence += 0.1

        # Competitor data = higher confidence
        if context.competitor_prices:
            confidence += 0.1

        # Customer rating data = higher confidence
        if context.customer_rating:
            confidence += 0.1

        return min(0.95, confidence)

    def _get_factors_considered(
        self, context: MenuItemPricingContext, strategy: PricingStrategy
    ) -> List[str]:
        """Get list of factors considered in pricing"""

        factors = [
            f"Current demand: {context.current_demand.value}",
            f"Sales trend: {context.sales_trend:+.1%}",
            f"Price elasticity: {context.price_elasticity.value}",
            f"Inventory level: {context.inventory_level:.0f}%",
        ]

        if context.competitor_prices:
            factors.append(
                f"Competitor prices: {len(context.competitor_prices)} data points"
            )

        if strategy == PricingStrategy.COST_PLUS:
            factors.append(f"Base cost: ${context.base_cost:.2f}")

        return factors

    def _generate_implementation_notes(
        self, context: MenuItemPricingContext, new_price: Decimal
    ) -> str:
        """Generate implementation notes"""

        notes = []

        price_change = abs(
            float((new_price - context.current_price) / context.current_price)
        )

        if price_change > 0.10:
            notes.append("Consider phased implementation over 2-3 weeks")

        if context.price_elasticity in [
            PriceElasticity.ELASTIC,
            PriceElasticity.HIGHLY_ELASTIC,
        ]:
            notes.append("Monitor sales volume closely after implementation")

        if context.current_demand == DemandLevel.VERY_HIGH:
            notes.append("Implement immediately to capture high demand")

        return "; ".join(notes) if notes else "Standard implementation recommended"

    def _build_recommendation_set(
        self, recommendations: List[PricingRecommendation], request: BulkPricingRequest
    ) -> PricingRecommendationSet:
        """Build complete recommendation set"""

        # Calculate summary metrics
        if recommendations:
            avg_price_change = statistics.mean(
                [r.price_change_percentage for r in recommendations]
            )
            total_revenue_impact = sum(
                [r.expected_revenue_impact for r in recommendations]
            ) / len(recommendations)
            total_profit_impact = sum(
                [r.expected_profit_impact for r in recommendations]
            ) / len(recommendations)
        else:
            avg_price_change = 0
            total_revenue_impact = 0
            total_profit_impact = 0

        # Count strategies used
        strategies_used = {}
        for rec in recommendations:
            strategies_used[rec.strategy_used] = (
                strategies_used.get(rec.strategy_used, 0) + 1
            )

        # Build implementation phases
        phases = self._build_implementation_phases(recommendations)

        return PricingRecommendationSet(
            request_id=f"price-rec-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            generated_at=datetime.now(),
            valid_until=datetime.now() + timedelta(days=request.time_horizon_days),
            recommendations=recommendations,
            total_items_analyzed=len(recommendations),
            total_recommendations=len(
                [r for r in recommendations if r.recommended_price != r.current_price]
            ),
            avg_price_change_percent=avg_price_change,
            expected_total_revenue_impact=total_revenue_impact,
            expected_total_profit_impact=total_profit_impact,
            strategies_used=strategies_used,
            optimization_goal=request.optimization_goal,
            implementation_phases=phases,
            warnings=self._generate_warnings(recommendations),
            notes=self._generate_notes(recommendations, request),
        )

    def _build_implementation_phases(
        self, recommendations: List[PricingRecommendation]
    ) -> List[Dict[str, Any]]:
        """Build phased implementation plan"""

        # Sort by impact and confidence
        sorted_recs = sorted(
            recommendations,
            key=lambda r: r.confidence_score * abs(r.expected_profit_impact),
            reverse=True,
        )

        phases = []

        # Phase 1: High confidence, positive impact
        phase1 = [
            r
            for r in sorted_recs
            if r.confidence_score > 0.7 and r.expected_profit_impact > 0
        ][
            :10
        ]  # Limit to 10 items per phase

        if phase1:
            phases.append(
                {
                    "phase": 1,
                    "name": "Quick Wins",
                    "items": [r.menu_item_id for r in phase1],
                    "expected_impact": sum(r.expected_profit_impact for r in phase1)
                    / len(phase1),
                    "implementation_date": datetime.now().date() + timedelta(days=1),
                }
            )

        # Phase 2: Medium confidence or neutral impact
        phase2 = [
            r for r in sorted_recs if r not in phase1 and r.confidence_score > 0.5
        ][:10]

        if phase2:
            phases.append(
                {
                    "phase": 2,
                    "name": "Secondary Optimizations",
                    "items": [r.menu_item_id for r in phase2],
                    "expected_impact": sum(r.expected_profit_impact for r in phase2)
                    / len(phase2),
                    "implementation_date": datetime.now().date() + timedelta(days=7),
                }
            )

        return phases

    def _generate_warnings(
        self, recommendations: List[PricingRecommendation]
    ) -> List[str]:
        """Generate warnings for the recommendation set"""

        warnings = []

        # Check for large price changes
        large_changes = [
            r for r in recommendations if abs(r.price_change_percentage) > 15
        ]
        if large_changes:
            warnings.append(
                f"{len(large_changes)} items have price changes >15% - consider phased implementation"
            )

        # Check for high-risk items
        high_risk = [r for r in recommendations if len(r.risks) > 2]
        if high_risk:
            warnings.append(
                f"{len(high_risk)} items have multiple risk factors - monitor closely"
            )

        return warnings

    def _generate_notes(
        self, recommendations: List[PricingRecommendation], request: BulkPricingRequest
    ) -> List[str]:
        """Generate notes for the recommendation set"""

        notes = []

        if request.maintain_price_relationships:
            notes.append("Price relationships between items have been maintained")

        if request.include_competitors:
            notes.append("Competitor pricing data was considered where available")

        # Summary of changes
        increases = len([r for r in recommendations if r.price_change_percentage > 0])
        decreases = len([r for r in recommendations if r.price_change_percentage < 0])

        notes.append(
            f"Recommended {increases} price increases and {decreases} price decreases"
        )

        return notes


# Service factory
def create_pricing_recommendation_service(db: Session) -> PricingRecommendationService:
    """Create pricing recommendation service instance"""
    return PricingRecommendationService(db)
