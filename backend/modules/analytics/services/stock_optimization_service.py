# backend/modules/analytics/services/stock_optimization_service.py

"""
Stock Optimization Service for inventory management.

Implements algorithms for optimal stock levels, reorder points,
safety stock calculations, and multi-objective optimization.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
from scipy import stats
from scipy.optimize import minimize, linprog
import uuid

from core.database import get_db
from modules.analytics.schemas.predictive_analytics_schemas import (
    StockOptimizationRequest, StockOptimizationResult, StockRecommendation,
    DemandForecastRequest, TimeGranularity
)
from modules.analytics.services.demand_prediction_service import DemandPredictionService
from core.inventory_models import Inventory
from core.menu_models import MenuItemInventory
from core.menu_models import MenuItem
from modules.orders.models.order_models import Order, OrderItem

logger = logging.getLogger(__name__)


class StockOptimizationService:
    """Service for optimizing inventory stock levels"""
    
    def __init__(self, db: Session):
        self.db = db
        self.demand_service = DemandPredictionService(db)
        self.cost_calculator = InventoryCostCalculator(db)
        
    async def optimize_stock_levels(
        self,
        request: StockOptimizationRequest
    ) -> StockOptimizationResult:
        """
        Optimize stock levels for products based on demand forecasts.
        
        Args:
            request: Stock optimization request parameters
            
        Returns:
            StockOptimizationResult with recommendations
        """
        try:
            # Get products to optimize
            products = self._get_products_to_optimize(request)
            
            if not products:
                raise ValueError("No products found for optimization")
            
            recommendations = []
            total_investment = Decimal(0)
            
            for product in products:
                try:
                    # Get demand forecast
                    demand_forecast = await self._get_product_demand_forecast(
                        product.id,
                        request.lead_time_days
                    )
                    
                    # Calculate optimal stock levels
                    recommendation = self._calculate_optimal_stock(
                        product,
                        demand_forecast,
                        request
                    )
                    
                    recommendations.append(recommendation)
                    total_investment += recommendation.recommended_stock * Decimal(str(product.cost or 0))
                    
                except Exception as e:
                    logger.warning(f"Failed to optimize product {product.id}: {e}")
                    continue
            
            # Apply budget constraint if specified
            if request.budget_constraint and total_investment > request.budget_constraint:
                recommendations = self._apply_budget_constraint(
                    recommendations,
                    request.budget_constraint
                )
                total_investment = request.budget_constraint
            
            # Calculate overall metrics
            overall_metrics = self._calculate_overall_metrics(recommendations)
            
            return StockOptimizationResult(
                optimization_id=str(uuid.uuid4()),
                recommendations=recommendations,
                total_investment_required=total_investment,
                expected_service_level=overall_metrics['service_level'],
                expected_waste_reduction=overall_metrics['waste_reduction'],
                optimization_summary=overall_metrics
            )
            
        except Exception as e:
            logger.error(f"Stock optimization failed: {e}", exc_info=True)
            raise
    
    def _get_products_to_optimize(
        self,
        request: StockOptimizationRequest
    ) -> List[MenuItem]:
        """Get list of products to optimize"""
        query = self.db.query(MenuItem).filter(MenuItem.is_available == True)
        
        if request.product_ids:
            query = query.filter(MenuItem.id.in_(request.product_ids))
        elif request.category_ids:
            query = query.filter(MenuItem.category_id.in_(request.category_ids))
        
        return query.all()
    
    async def _get_product_demand_forecast(
        self,
        product_id: int,
        horizon_days: int
    ) -> Dict[str, Any]:
        """Get demand forecast for a product"""
        # Create forecast request
        forecast_request = DemandForecastRequest(
            entity_id=product_id,
            entity_type="product",
            time_granularity=TimeGranularity.DAILY,
            horizon_days=horizon_days + 7,  # Extra days for safety
            include_confidence_intervals=True
        )
        
        # Get forecast
        forecast = await self.demand_service.forecast_demand(forecast_request)
        
        # Extract key statistics
        predictions = [p.predicted_value for p in forecast.predictions]
        lower_bounds = [p.lower_bound for p in forecast.predictions]
        upper_bounds = [p.upper_bound for p in forecast.predictions]
        
        return {
            'mean_demand': np.mean(predictions),
            'std_demand': np.std(predictions),
            'max_demand': np.max(predictions),
            'predictions': predictions,
            'lower_bounds': lower_bounds,
            'upper_bounds': upper_bounds
        }
    
    def _calculate_optimal_stock(
        self,
        product: MenuItem,
        demand_forecast: Dict[str, Any],
        request: StockOptimizationRequest
    ) -> StockRecommendation:
        """Calculate optimal stock levels for a product"""
        
        # Get current inventory
        current_inventory = self._get_current_inventory(product.id)
        
        # Extract demand parameters
        mean_demand = demand_forecast['mean_demand']
        std_demand = demand_forecast['std_demand']
        lead_time = request.lead_time_days
        
        # Calculate lead time demand
        lead_time_demand_mean = mean_demand * lead_time
        lead_time_demand_std = std_demand * np.sqrt(lead_time)
        
        # Calculate safety stock
        if request.include_safety_stock:
            z_score = stats.norm.ppf(request.service_level)
            safety_stock = z_score * lead_time_demand_std
        else:
            safety_stock = 0
        
        # Calculate reorder point
        reorder_point = lead_time_demand_mean + safety_stock
        
        # Calculate economic order quantity (EOQ)
        eoq = self._calculate_eoq(
            product,
            mean_demand,
            current_inventory.get('holding_cost', 0.2),
            current_inventory.get('ordering_cost', 50)
        )
        
        # Calculate recommended stock level based on optimization objective
        if request.optimization_objective == "minimize_waste":
            recommended_stock = reorder_point + eoq * 0.5
        elif request.optimization_objective == "maximize_availability":
            recommended_stock = reorder_point + eoq
        else:  # balanced
            recommended_stock = reorder_point + eoq * 0.75
        
        # Calculate costs and risks
        stockout_risk = 1 - request.service_level
        holding_cost = self.cost_calculator.calculate_holding_cost(
            product,
            recommended_stock,
            mean_demand
        )
        stockout_cost = self.cost_calculator.calculate_stockout_cost(
            product,
            stockout_risk,
            mean_demand
        )
        
        return StockRecommendation(
            product_id=product.id,
            product_name=product.name,
            current_stock=current_inventory.get('quantity', 0),
            recommended_stock=float(recommended_stock),
            reorder_point=float(reorder_point),
            reorder_quantity=float(eoq),
            safety_stock=float(safety_stock),
            expected_stockout_risk=float(stockout_risk),
            estimated_holding_cost=holding_cost,
            estimated_stockout_cost=stockout_cost
        )
    
    def _get_current_inventory(self, product_id: int) -> Dict[str, Any]:
        """Get current inventory levels and costs"""
        # Get inventory mapping
        menu_inventory = self.db.query(MenuItemInventory).filter_by(
            menu_item_id=product_id
        ).first()
        
        if menu_inventory:
            inventory = self.db.query(Inventory).filter_by(
                id=menu_inventory.inventory_id
            ).first()
            
            if inventory:
                return {
                    'quantity': float(inventory.quantity),
                    'unit': inventory.unit,
                    'threshold': float(inventory.threshold),
                    'holding_cost': 0.2,  # 20% annual holding cost
                    'ordering_cost': 50   # $50 per order
                }
        
        return {
            'quantity': 0,
            'unit': 'unit',
            'threshold': 0,
            'holding_cost': 0.2,
            'ordering_cost': 50
        }
    
    def _calculate_eoq(
        self,
        product: MenuItem,
        annual_demand: float,
        holding_cost_rate: float,
        ordering_cost: float
    ) -> float:
        """Calculate Economic Order Quantity"""
        # Annual demand
        D = annual_demand * 365
        
        # Ordering cost per order
        S = ordering_cost
        
        # Holding cost per unit per year
        H = float(product.cost or 10) * holding_cost_rate
        
        # EOQ formula: sqrt(2DS/H)
        if H > 0:
            eoq = np.sqrt(2 * D * S / H)
        else:
            eoq = 100  # Default
        
        return max(1, eoq)
    
    def _apply_budget_constraint(
        self,
        recommendations: List[StockRecommendation],
        budget: Decimal
    ) -> List[StockRecommendation]:
        """Apply budget constraint using linear programming"""
        n_products = len(recommendations)
        
        if n_products == 0:
            return recommendations
        
        # Get product costs and values
        costs = []
        values = []
        
        for i, rec in enumerate(recommendations):
            product = self.db.query(MenuItem).filter_by(id=rec.product_id).first()
            cost = float(product.cost or 10)
            value = 1 / (rec.expected_stockout_risk + 0.01)  # Higher value for lower risk
            
            costs.append(cost)
            values.append(value)
        
        # Linear programming problem
        # Maximize: sum(values * quantities)
        # Subject to: sum(costs * quantities) <= budget
        #            0 <= quantities <= recommended_stock
        
        c = [-v for v in values]  # Negative for maximization
        A_ub = [costs]
        b_ub = [float(budget)]
        
        bounds = [(0, rec.recommended_stock) for rec in recommendations]
        
        # Solve
        result = linprog(c, A_ub=A_ub, b_ub=b_ub, bounds=bounds, method='highs')
        
        if result.success:
            # Update recommendations with optimized quantities
            for i, rec in enumerate(recommendations):
                rec.recommended_stock = float(result.x[i])
                
                # Adjust other values proportionally
                ratio = result.x[i] / (rec.recommended_stock + 1e-10)
                rec.reorder_quantity *= ratio
                rec.safety_stock *= ratio
        
        return recommendations
    
    def _calculate_overall_metrics(
        self,
        recommendations: List[StockRecommendation]
    ) -> Dict[str, Any]:
        """Calculate overall optimization metrics"""
        if not recommendations:
            return {
                'service_level': 0,
                'waste_reduction': 0,
                'total_products': 0
            }
        
        # Average service level
        avg_service_level = np.mean([
            1 - rec.expected_stockout_risk
            for rec in recommendations
        ])
        
        # Waste reduction calculation
        total_current = sum(rec.current_stock for rec in recommendations)
        total_recommended = sum(rec.recommended_stock for rec in recommendations)
        
        waste_reduction = 0
        if total_current > 0:
            overstock_items = [
                rec for rec in recommendations
                if rec.current_stock > rec.recommended_stock * 1.2
            ]
            
            if overstock_items:
                excess_stock = sum(
                    rec.current_stock - rec.recommended_stock
                    for rec in overstock_items
                )
                waste_reduction = excess_stock / total_current
        
        return {
            'service_level': float(avg_service_level),
            'waste_reduction': float(waste_reduction),
            'total_products': len(recommendations),
            'products_overstocked': len([
                r for r in recommendations
                if r.current_stock > r.recommended_stock * 1.2
            ]),
            'products_understocked': len([
                r for r in recommendations
                if r.current_stock < r.reorder_point
            ]),
            'total_safety_stock': sum(r.safety_stock for r in recommendations),
            'avg_stockout_risk': np.mean([r.expected_stockout_risk for r in recommendations])
        }


class InventoryCostCalculator:
    """Calculator for inventory-related costs"""
    
    def __init__(self, db: Session):
        self.db = db
        self.default_holding_rate = 0.2  # 20% annual
        self.default_stockout_penalty = 3.0  # 3x profit margin
        
    def calculate_holding_cost(
        self,
        product: MenuItem,
        stock_level: float,
        demand_rate: float
    ) -> Decimal:
        """Calculate holding cost for a product"""
        # Average inventory = stock_level / 2
        avg_inventory = stock_level / 2
        
        # Annual holding cost
        unit_cost = float(product.cost or 10)
        annual_holding_cost = avg_inventory * unit_cost * self.default_holding_rate
        
        # Convert to daily
        daily_holding_cost = annual_holding_cost / 365
        
        return Decimal(str(daily_holding_cost))
    
    def calculate_stockout_cost(
        self,
        product: MenuItem,
        stockout_probability: float,
        demand_rate: float
    ) -> Decimal:
        """Calculate expected stockout cost"""
        # Expected lost sales
        expected_stockouts = demand_rate * stockout_probability
        
        # Lost profit per stockout
        unit_price = float(product.price)
        unit_cost = float(product.cost or unit_price * 0.3)
        profit_margin = unit_price - unit_cost
        
        # Stockout penalty (includes lost profit + customer dissatisfaction)
        stockout_penalty = profit_margin * self.default_stockout_penalty
        
        # Expected daily cost
        daily_stockout_cost = expected_stockouts * stockout_penalty
        
        return Decimal(str(daily_stockout_cost))
    
    def calculate_total_cost(
        self,
        product: MenuItem,
        stock_level: float,
        reorder_point: float,
        demand_params: Dict[str, float]
    ) -> Decimal:
        """Calculate total inventory cost"""
        holding_cost = self.calculate_holding_cost(
            product,
            stock_level,
            demand_params['mean']
        )
        
        # Calculate stockout probability
        if stock_level >= reorder_point:
            stockout_prob = 0.05  # Low probability
        else:
            # Use normal distribution
            z_score = (stock_level - demand_params['mean']) / (demand_params['std'] + 1e-10)
            stockout_prob = stats.norm.cdf(z_score)
        
        stockout_cost = self.calculate_stockout_cost(
            product,
            stockout_prob,
            demand_params['mean']
        )
        
        return holding_cost + stockout_cost


class MultiObjectiveOptimizer:
    """Multi-objective optimization for complex inventory scenarios"""
    
    def __init__(self):
        self.objectives = []
        self.constraints = []
        
    def add_objective(self, objective_func, weight: float = 1.0):
        """Add an objective function to optimize"""
        self.objectives.append((objective_func, weight))
    
    def add_constraint(self, constraint_func):
        """Add a constraint function"""
        self.constraints.append(constraint_func)
    
    def optimize(self, initial_guess: np.ndarray) -> Dict[str, Any]:
        """Perform multi-objective optimization"""
        
        def combined_objective(x):
            """Combined weighted objective function"""
            total = 0
            for obj_func, weight in self.objectives:
                total += weight * obj_func(x)
            return total
        
        # Constraint dictionary for scipy
        constraints = [{'type': 'ineq', 'fun': c} for c in self.constraints]
        
        # Optimize
        result = minimize(
            combined_objective,
            initial_guess,
            method='SLSQP',
            constraints=constraints,
            options={'maxiter': 1000}
        )
        
        return {
            'success': result.success,
            'optimal_values': result.x,
            'objective_value': result.fun,
            'message': result.message
        }