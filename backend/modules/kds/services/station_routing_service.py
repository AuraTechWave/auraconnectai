# backend/modules/kds/services/station_routing_service.py

"""
Station routing service for Kitchen Display System.
"""

from typing import List, Optional, Dict
from sqlalchemy.orm import Session

from ..models.kds_models import KitchenStation, StationRoutingRule, StationType
from ..schemas.kds_schemas import OrderItem


class StationRoutingService:
    """Service for routing order items to appropriate kitchen stations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_active_stations(self, restaurant_id: int) -> List[KitchenStation]:
        """Get all active stations for a restaurant"""
        return self.db.query(KitchenStation).filter(
            KitchenStation.restaurant_id == restaurant_id,
            KitchenStation.is_active == True
        ).all()
    
    def route_order_item(
        self, 
        order_item: OrderItem, 
        restaurant_id: int
    ) -> List[KitchenStation]:
        """Route an order item to appropriate stations"""
        stations = []
        
        # Get routing rules for the menu item
        rules = self.db.query(StationRoutingRule).filter(
            StationRoutingRule.restaurant_id == restaurant_id,
            StationRoutingRule.is_active == True
        ).filter(
            (StationRoutingRule.menu_item_id == order_item.menu_item_id) |
            (StationRoutingRule.category_id == order_item.category_id) |
            (StationRoutingRule.tag_name.in_(order_item.tags) if order_item.tags else False)
        ).all()
        
        # Apply rules to find stations
        station_ids = set()
        for rule in rules:
            if rule.target_station_id:
                station_ids.add(rule.target_station_id)
        
        # Get stations by IDs
        if station_ids:
            stations = self.db.query(KitchenStation).filter(
                KitchenStation.id.in_(station_ids),
                KitchenStation.is_active == True
            ).all()
        
        # If no specific routing, use default stations
        if not stations:
            stations = self.get_default_stations(restaurant_id)
        
        return stations
    
    def get_default_stations(self, restaurant_id: int) -> List[KitchenStation]:
        """Get default stations when no specific routing is found"""
        return self.db.query(KitchenStation).filter(
            KitchenStation.restaurant_id == restaurant_id,
            KitchenStation.station_type == StationType.PREP,
            KitchenStation.is_active == True
        ).all()
    
    def create_routing_rule(
        self,
        restaurant_id: int,
        rule_data: dict
    ) -> StationRoutingRule:
        """Create a new routing rule"""
        rule = StationRoutingRule(
            restaurant_id=restaurant_id,
            **rule_data
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        return rule
    
    def update_routing_rule(
        self,
        rule_id: int,
        updates: dict
    ) -> Optional[StationRoutingRule]:
        """Update an existing routing rule"""
        rule = self.db.query(StationRoutingRule).filter(
            StationRoutingRule.id == rule_id
        ).first()
        
        if rule:
            for key, value in updates.items():
                setattr(rule, key, value)
            self.db.commit()
            self.db.refresh(rule)
        
        return rule
    
    def delete_routing_rule(self, rule_id: int) -> bool:
        """Delete a routing rule"""
        rule = self.db.query(StationRoutingRule).filter(
            StationRoutingRule.id == rule_id
        ).first()
        
        if rule:
            self.db.delete(rule)
            self.db.commit()
            return True
        
        return False