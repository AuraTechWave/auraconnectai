# backend/modules/analytics/services/predictive_realtime_service.py

"""
Real-time Predictive Analytics Service.

Provides real-time updates for predictions, alerts, and insights
via WebSocket connections.
"""

import logging
import asyncio
import json
from typing import Dict, List, Optional, Set, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import uuid

from backend.modules.analytics.schemas.predictive_analytics_schemas import (
    RealTimePredictionUpdate, PredictionAlert, DemandForecast,
    PredictiveInsight, StockRecommendation, PredictionConfidence
)
from backend.modules.analytics.services.websocket_manager import WebSocketManager
from backend.modules.analytics.services.demand_prediction_service import DemandPredictionService
from backend.modules.analytics.services.stock_optimization_service import StockOptimizationService
from backend.modules.analytics.services.forecast_monitoring_service import ForecastMonitoringService

logger = logging.getLogger(__name__)


class PredictiveRealtimeService:
    """Service for real-time predictive analytics updates"""
    
    def __init__(self):
        self.websocket_manager = WebSocketManager()
        self.active_subscriptions: Dict[str, Set[str]] = {}  # client_id -> set of entity subscriptions
        self.update_intervals = {
            'demand_forecast': 300,  # 5 minutes
            'stock_alert': 60,       # 1 minute
            'insight': 600          # 10 minutes
        }
        self.running_tasks: Dict[str, asyncio.Task] = {}
        
    async def start_monitoring(self, db: Session):
        """Start all monitoring tasks"""
        try:
            # Start demand forecast updates
            self.running_tasks['demand_forecast'] = asyncio.create_task(
                self._monitor_demand_forecasts(db)
            )
            
            # Start stock alert monitoring
            self.running_tasks['stock_alerts'] = asyncio.create_task(
                self._monitor_stock_alerts(db)
            )
            
            # Start insight generation
            self.running_tasks['insights'] = asyncio.create_task(
                self._generate_insights(db)
            )
            
            logger.info("Predictive realtime monitoring started")
            
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            raise
    
    async def stop_monitoring(self):
        """Stop all monitoring tasks"""
        for task_name, task in self.running_tasks.items():
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    logger.info(f"Task {task_name} cancelled")
        
        self.running_tasks.clear()
        logger.info("Predictive realtime monitoring stopped")
    
    async def subscribe_to_predictions(
        self,
        client_id: str,
        entity_type: str,
        entity_ids: List[int]
    ):
        """Subscribe a client to prediction updates for specific entities"""
        if client_id not in self.active_subscriptions:
            self.active_subscriptions[client_id] = set()
        
        # Add subscriptions
        for entity_id in entity_ids:
            subscription_key = f"{entity_type}:{entity_id}"
            self.active_subscriptions[client_id].add(subscription_key)
        
        logger.info(f"Client {client_id} subscribed to {len(entity_ids)} {entity_type} predictions")
    
    async def unsubscribe_from_predictions(
        self,
        client_id: str,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[int]] = None
    ):
        """Unsubscribe a client from prediction updates"""
        if client_id not in self.active_subscriptions:
            return
        
        if entity_type and entity_ids:
            # Remove specific subscriptions
            for entity_id in entity_ids:
                subscription_key = f"{entity_type}:{entity_id}"
                self.active_subscriptions[client_id].discard(subscription_key)
        else:
            # Remove all subscriptions for client
            self.active_subscriptions.pop(client_id, None)
        
        logger.info(f"Client {client_id} unsubscribed from predictions")
    
    async def _monitor_demand_forecasts(self, db: Session):
        """Monitor and send demand forecast updates"""
        demand_service = DemandPredictionService(db)
        
        while True:
            try:
                await asyncio.sleep(self.update_intervals['demand_forecast'])
                
                # Get all active entity subscriptions
                all_subscriptions = set()
                for subscriptions in self.active_subscriptions.values():
                    all_subscriptions.update(subscriptions)
                
                # Process each unique subscription
                for subscription in all_subscriptions:
                    try:
                        entity_type, entity_id = subscription.split(':')
                        entity_id = int(entity_id)
                        
                        # Generate updated forecast
                        from backend.modules.analytics.schemas.predictive_analytics_schemas import DemandForecastRequest
                        
                        request = DemandForecastRequest(
                            entity_id=entity_id,
                            entity_type=entity_type,
                            horizon_days=7,
                            time_granularity="daily"
                        )
                        
                        forecast = await demand_service.forecast_demand(request)
                        
                        # Create update message
                        update = RealTimePredictionUpdate(
                            update_id=str(uuid.uuid4()),
                            update_type="forecast_update",
                            entity_id=entity_id,
                            entity_type=entity_type,
                            data=forecast
                        )
                        
                        # Send to subscribed clients
                        await self._send_to_subscribers(subscription, update)
                        
                    except Exception as e:
                        logger.error(f"Error updating forecast for {subscription}: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Demand forecast monitoring error: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def _monitor_stock_alerts(self, db: Session):
        """Monitor stock levels and send alerts"""
        stock_service = StockOptimizationService(db)
        monitoring_service = ForecastMonitoringService(db)
        
        while True:
            try:
                await asyncio.sleep(self.update_intervals['stock_alert'])
                
                # Check for stock alerts across all products
                from backend.modules.orders.models.inventory_models import Inventory, MenuItemInventory
                from backend.modules.menu.models import MenuItem
                
                # Get low stock items
                low_stock_items = db.query(Inventory).filter(
                    Inventory.quantity <= Inventory.threshold * 1.1
                ).all()
                
                for inventory in low_stock_items:
                    # Get associated menu items
                    menu_mappings = db.query(MenuItemInventory).filter_by(
                        inventory_id=inventory.id
                    ).all()
                    
                    for mapping in menu_mappings:
                        menu_item = db.query(MenuItem).filter_by(
                            id=mapping.menu_item_id
                        ).first()
                        
                        if menu_item:
                            # Create stock alert
                            alert = PredictionAlert(
                                alert_id=str(uuid.uuid4()),
                                alert_type="stockout_risk",
                                severity="high" if inventory.quantity <= inventory.threshold else "medium",
                                entity_id=menu_item.id,
                                entity_name=menu_item.name,
                                message=f"Low stock alert: {inventory.quantity} {inventory.unit} remaining",
                                predicted_impact={
                                    'current_stock': inventory.quantity,
                                    'threshold': inventory.threshold,
                                    'days_until_stockout': self._estimate_stockout_days(
                                        inventory.quantity,
                                        menu_item.id,
                                        db
                                    )
                                },
                                recommended_actions=[
                                    f"Reorder {inventory.item_name} immediately",
                                    "Consider expedited shipping",
                                    "Update menu availability if needed"
                                ],
                                expires_at=datetime.now() + timedelta(hours=24)
                            )
                            
                            # Create update message
                            update = RealTimePredictionUpdate(
                                update_id=str(uuid.uuid4()),
                                update_type="alert",
                                entity_id=menu_item.id,
                                entity_type="product",
                                data=alert
                            )
                            
                            # Send to subscribers
                            subscription_key = f"product:{menu_item.id}"
                            await self._send_to_subscribers(subscription_key, update)
                
                # Check for anomalies in recent forecasts
                anomaly_alerts = await monitoring_service.detect_forecast_anomalies(
                    "product",
                    None,
                    recent_days=1
                )
                
                for alert in anomaly_alerts:
                    update = RealTimePredictionUpdate(
                        update_id=str(uuid.uuid4()),
                        update_type="alert",
                        entity_id=alert.entity_id,
                        entity_type="product",
                        data=alert
                    )
                    
                    if alert.entity_id:
                        subscription_key = f"product:{alert.entity_id}"
                        await self._send_to_subscribers(subscription_key, update)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stock alert monitoring error: {e}")
                await asyncio.sleep(60)
    
    async def _generate_insights(self, db: Session):
        """Generate and send predictive insights"""
        demand_service = DemandPredictionService(db)
        
        while True:
            try:
                await asyncio.sleep(self.update_intervals['insight'])
                
                # Analyze recent trends for insights
                insights = []
                
                # Check for demand spikes
                spike_insight = await self._detect_demand_spikes(db)
                if spike_insight:
                    insights.append(spike_insight)
                
                # Check for seasonal opportunities
                seasonal_insight = await self._detect_seasonal_opportunities(db)
                if seasonal_insight:
                    insights.append(seasonal_insight)
                
                # Check for inventory optimization opportunities
                optimization_insight = await self._detect_optimization_opportunities(db)
                if optimization_insight:
                    insights.append(optimization_insight)
                
                # Send insights to all connected clients
                for insight in insights:
                    update = RealTimePredictionUpdate(
                        update_id=str(uuid.uuid4()),
                        update_type="insight",
                        entity_id=None,
                        entity_type="overall",
                        data=insight
                    )
                    
                    # Broadcast to all clients
                    await self._broadcast_update(update)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Insight generation error: {e}")
                await asyncio.sleep(300)
    
    def _estimate_stockout_days(
        self,
        current_stock: float,
        product_id: int,
        db: Session
    ) -> int:
        """Estimate days until stockout based on recent demand"""
        # Get average daily demand from last 7 days
        from backend.modules.orders.models.order_models import Order, OrderItem
        
        seven_days_ago = datetime.now() - timedelta(days=7)
        
        daily_demand = db.query(func.sum(OrderItem.quantity)).join(Order).filter(
            OrderItem.menu_item_id == product_id,
            Order.created_at >= seven_days_ago,
            Order.status.notin_(['cancelled', 'failed'])
        ).scalar() or 0
        
        avg_daily_demand = daily_demand / 7
        
        if avg_daily_demand > 0:
            return int(current_stock / avg_daily_demand)
        return 999  # No recent demand
    
    async def _detect_demand_spikes(self, db: Session) -> Optional[PredictiveInsight]:
        """Detect upcoming demand spikes"""
        # Analyze recent order patterns and forecasts
        # This is a simplified implementation
        
        from backend.modules.orders.models.order_models import Order
        
        # Check if current demand is higher than usual
        today_orders = db.query(func.count(Order.id)).filter(
            func.date(Order.created_at) == date.today()
        ).scalar() or 0
        
        # Get average for same day of week
        avg_orders = db.query(func.count(Order.id)).filter(
            func.extract('dow', Order.created_at) == datetime.now().weekday(),
            Order.created_at >= datetime.now() - timedelta(days=28)
        ).scalar() or 0
        
        avg_orders = avg_orders / 4  # 4 weeks
        
        if today_orders > avg_orders * 1.3:  # 30% spike
            return PredictiveInsight(
                insight_id=str(uuid.uuid4()),
                insight_type="demand_trend",
                title="Demand Spike Detected",
                description=f"Current demand is {((today_orders/avg_orders - 1) * 100):.0f}% higher than usual",
                impact_score=8.0,
                affected_entities=[],
                recommended_actions=[
                    {
                        "action": "increase_staffing",
                        "description": "Consider adding extra staff for peak hours",
                        "priority": "high"
                    },
                    {
                        "action": "stock_check",
                        "description": "Verify stock levels for high-demand items",
                        "priority": "high"
                    }
                ],
                confidence=PredictionConfidence.HIGH,
                valid_until=datetime.now() + timedelta(hours=6)
            )
        
        return None
    
    async def _detect_seasonal_opportunities(self, db: Session) -> Optional[PredictiveInsight]:
        """Detect seasonal sales opportunities"""
        # Check for seasonal patterns
        # This is a placeholder implementation
        
        current_month = datetime.now().month
        seasonal_events = {
            12: "Holiday season",
            7: "Summer peak",
            2: "Valentine's period"
        }
        
        if current_month in seasonal_events:
            return PredictiveInsight(
                insight_id=str(uuid.uuid4()),
                insight_type="revenue_opportunity",
                title=f"{seasonal_events[current_month]} Opportunity",
                description=f"Historical data shows increased demand during {seasonal_events[current_month]}",
                impact_score=7.0,
                affected_entities=[],
                recommended_actions=[
                    {
                        "action": "seasonal_promotion",
                        "description": "Launch seasonal promotions to maximize revenue",
                        "priority": "medium"
                    }
                ],
                confidence=PredictionConfidence.MEDIUM,
                valid_until=datetime.now() + timedelta(days=7)
            )
        
        return None
    
    async def _detect_optimization_opportunities(self, db: Session) -> Optional[PredictiveInsight]:
        """Detect inventory optimization opportunities"""
        # Check for overstocked items
        from backend.modules.orders.models.inventory_models import Inventory
        
        overstocked = db.query(Inventory).filter(
            Inventory.quantity > Inventory.threshold * 5
        ).count()
        
        if overstocked > 5:
            return PredictiveInsight(
                insight_id=str(uuid.uuid4()),
                insight_type="stock_risk",
                title="Inventory Optimization Opportunity",
                description=f"{overstocked} items are significantly overstocked",
                impact_score=6.0,
                affected_entities=[],
                recommended_actions=[
                    {
                        "action": "run_promotions",
                        "description": "Consider promotions for overstocked items",
                        "priority": "medium"
                    },
                    {
                        "action": "adjust_ordering",
                        "description": "Reduce order quantities for slow-moving items",
                        "priority": "medium"
                    }
                ],
                confidence=PredictionConfidence.HIGH,
                valid_until=datetime.now() + timedelta(days=3)
            )
        
        return None
    
    async def _send_to_subscribers(
        self,
        subscription_key: str,
        update: RealTimePredictionUpdate
    ):
        """Send update to all clients subscribed to this entity"""
        for client_id, subscriptions in self.active_subscriptions.items():
            if subscription_key in subscriptions:
                await self.websocket_manager.send_personal_message(
                    update.dict(),
                    client_id
                )
    
    async def _broadcast_update(self, update: RealTimePredictionUpdate):
        """Broadcast update to all connected clients"""
        await self.websocket_manager.broadcast(update.dict())
    
    def get_subscription_stats(self) -> Dict[str, Any]:
        """Get statistics about active subscriptions"""
        total_clients = len(self.active_subscriptions)
        total_subscriptions = sum(
            len(subs) for subs in self.active_subscriptions.values()
        )
        
        # Count by entity type
        entity_counts = {}
        for subscriptions in self.active_subscriptions.values():
            for sub in subscriptions:
                entity_type = sub.split(':')[0]
                entity_counts[entity_type] = entity_counts.get(entity_type, 0) + 1
        
        return {
            'total_clients': total_clients,
            'total_subscriptions': total_subscriptions,
            'subscriptions_by_type': entity_counts,
            'active_monitoring_tasks': len(self.running_tasks)
        }


# Global instance
predictive_realtime_service = PredictiveRealtimeService()