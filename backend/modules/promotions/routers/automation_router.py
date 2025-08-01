# backend/modules/promotions/routers/automation_router.py

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime

from core.database import get_db
from modules.auth.dependencies import get_current_user, require_admin

from ..services.automation_service import PromotionAutomationService
from ..schemas.promotion_schemas import PromotionCreate

router = APIRouter(prefix="/automation", tags=["Promotion Automation"])


@router.post("/create")
def create_automated_promotion(
    name: str = Body(...),
    trigger_type: str = Body(..., pattern="^(customer_lifecycle|purchase_behavior|cart_abandonment|loyalty_milestone|inventory_level|weather_condition|competitor_price|seasonal_event)$"),
    trigger_conditions: Dict[str, Any] = Body(...),
    promotion_config: Dict[str, Any] = Body(...),
    automation_options: Dict[str, Any] = Body({}),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Create an automated promotion with trigger conditions
    
    Trigger Types:
    - customer_lifecycle: signup, birthday, win_back
    - purchase_behavior: high_value_purchase, category_purchase
    - cart_abandonment: abandoned cart recovery
    - loyalty_milestone: points_threshold, tier_upgrade
    - inventory_level: low_stock, overstock
    - weather_condition: temperature-based triggers
    - competitor_price: price monitoring triggers
    - seasonal_event: holiday and seasonal triggers
    """
    try:
        service = PromotionAutomationService(db)
        promotion = service.create_automated_promotion(
            name=name,
            trigger_type=trigger_type,
            trigger_conditions=trigger_conditions,
            promotion_config=promotion_config,
            automation_options=automation_options
        )
        return {
            "promotion": promotion,
            "automation": promotion.metadata.get("automation", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create automated promotion: {str(e)}")


@router.post("/process-triggers")
async def process_automation_triggers(
    trigger_type: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Process automation triggers and activate relevant promotions
    This is typically run by a background task scheduler
    """
    try:
        service = PromotionAutomationService(db)
        results = await service.process_triggers(trigger_type)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process automation triggers: {str(e)}")


@router.post("/customer-segment")
def create_customer_segment_promotion(
    segment_criteria: Dict[str, Any] = Body(...),
    promotion_config: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """
    Create a promotion targeted at specific customer segments
    
    Segment Criteria Types:
    - purchase_frequency: Based on order frequency
    - total_spent: Based on total spending
    - customer_attributes: Based on customer attributes
    """
    try:
        service = PromotionAutomationService(db)
        promotion = service.create_customer_segment_promotion(
            segment_criteria=segment_criteria,
            promotion_config=promotion_config
        )
        return {
            "promotion": promotion,
            "segment_targeting": promotion.metadata.get("segment_targeting", {})
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create customer segment promotion: {str(e)}")


@router.post("/evaluate-segment/{customer_id}")
def evaluate_customer_segment(
    customer_id: int,
    segment_criteria: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Evaluate if a customer belongs to a specific segment"""
    try:
        service = PromotionAutomationService(db)
        belongs_to_segment = service.evaluate_customer_segment(
            customer_id=customer_id,
            segment_criteria=segment_criteria
        )
        return {
            "customer_id": customer_id,
            "belongs_to_segment": belongs_to_segment,
            "segment_criteria": segment_criteria,
            "evaluated_at": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate customer segment: {str(e)}")


@router.get("/performance")
def get_automation_performance(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get performance metrics for automated promotions"""
    try:
        service = PromotionAutomationService(db)
        metrics = service.get_automation_performance(
            start_date=start_date,
            end_date=end_date
        )
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get automation performance: {str(e)}")


@router.get("/triggers/available")
def get_available_triggers(
    current_user = Depends(require_admin)
):
    """Get list of available automation triggers with their configuration options"""
    return {
        "customer_lifecycle": {
            "description": "Triggers based on customer lifecycle events",
            "event_types": ["signup", "first_purchase", "birthday", "win_back"],
            "example_conditions": {
                "event_type": "signup",
                "days_inactive": 30  # for win_back
            }
        },
        "purchase_behavior": {
            "description": "Triggers based on purchase patterns",
            "behavior_types": ["high_value_purchase", "category_purchase"],
            "example_conditions": {
                "behavior_type": "high_value_purchase",
                "order_threshold": 100,
                "category_ids": [1, 2, 3]
            }
        },
        "cart_abandonment": {
            "description": "Triggers for abandoned cart recovery",
            "example_conditions": {
                "hours_since_abandonment": 2
            }
        },
        "loyalty_milestone": {
            "description": "Triggers based on loyalty program milestones",
            "milestone_types": ["points_threshold", "tier_upgrade"],
            "example_conditions": {
                "milestone_type": "points_threshold",
                "points_threshold": 1000
            }
        },
        "inventory_level": {
            "description": "Triggers based on inventory levels",
            "trigger_types": ["low_stock", "overstock"],
            "example_conditions": {
                "trigger_type": "low_stock",
                "threshold_percentage": 20
            }
        },
        "weather_condition": {
            "description": "Triggers based on weather conditions",
            "example_conditions": {
                "weather_type": "temperature",
                "temperature_threshold": 80,
                "comparison": "above"
            }
        },
        "competitor_price": {
            "description": "Triggers based on competitor price changes",
            "example_conditions": {
                "price_difference_percentage": 10
            }
        },
        "seasonal_event": {
            "description": "Triggers for seasonal events and holidays",
            "event_types": ["black_friday", "cyber_monday", "christmas", "new_year", "valentines", "summer_start", "back_to_school"],
            "example_conditions": {
                "event_type": "black_friday",
                "days_before": 3
            }
        }
    }


@router.get("/automation-rules")
def get_automation_rules(
    trigger_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Get all automation rules with optional filtering"""
    try:
        from ..models.promotion_models import PromotionRule
        
        query = db.query(PromotionRule).filter(
            PromotionRule.rule_type == 'automation_trigger'
        )
        
        if trigger_type:
            query = query.filter(PromotionRule.condition_type == trigger_type)
        
        if is_active is not None:
            query = query.filter(PromotionRule.is_active == is_active)
        
        rules = query.all()
        
        rule_list = []
        for rule in rules:
            rule_data = {
                "id": rule.id,
                "promotion_id": rule.promotion_id,
                "promotion_name": rule.promotion.name if rule.promotion else None,
                "trigger_type": rule.condition_type,
                "trigger_conditions": rule.condition_value,
                "is_active": rule.is_active,
                "created_at": rule.created_at.isoformat() if rule.created_at else None
            }
            
            # Add automation metadata if available
            if rule.promotion and rule.promotion.metadata:
                automation = rule.promotion.metadata.get("automation", {})
                rule_data["last_triggered"] = automation.get("last_triggered")
                rule_data["trigger_count"] = automation.get("trigger_count", 0)
            
            rule_list.append(rule_data)
        
        return {
            "total_rules": len(rule_list),
            "filters": {
                "trigger_type": trigger_type,
                "is_active": is_active
            },
            "rules": rule_list
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get automation rules: {str(e)}")


@router.put("/rules/{rule_id}/toggle")
def toggle_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Toggle an automation rule on/off"""
    try:
        from ..models.promotion_models import PromotionRule
        
        rule = db.query(PromotionRule).filter(
            PromotionRule.id == rule_id,
            PromotionRule.rule_type == 'automation_trigger'
        ).first()
        
        if not rule:
            raise HTTPException(status_code=404, detail="Automation rule not found")
        
        rule.is_active = not rule.is_active
        db.commit()
        
        return {
            "rule_id": rule_id,
            "is_active": rule.is_active,
            "message": f"Automation rule {'activated' if rule.is_active else 'deactivated'}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to toggle automation rule: {str(e)}")


@router.delete("/rules/{rule_id}")
def delete_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Delete an automation rule"""
    try:
        from ..models.promotion_models import PromotionRule
        
        rule = db.query(PromotionRule).filter(
            PromotionRule.id == rule_id,
            PromotionRule.rule_type == 'automation_trigger'
        ).first()
        
        if not rule:
            raise HTTPException(status_code=404, detail="Automation rule not found")
        
        db.delete(rule)
        db.commit()
        
        return {"message": "Automation rule deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete automation rule: {str(e)}")


@router.post("/test-trigger")
def test_automation_trigger(
    trigger_type: str = Body(...),
    trigger_conditions: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user = Depends(require_admin)
):
    """Test an automation trigger without creating a promotion"""
    try:
        service = PromotionAutomationService(db)
        
        # Get the trigger handler
        handler = service.trigger_handlers.get(trigger_type)
        if not handler:
            raise HTTPException(status_code=400, detail=f"Unknown trigger type: {trigger_type}")
        
        # Test the trigger
        should_trigger, trigger_data = handler(trigger_conditions)
        
        return {
            "trigger_type": trigger_type,
            "trigger_conditions": trigger_conditions,
            "should_trigger": should_trigger,
            "trigger_data": trigger_data,
            "tested_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to test automation trigger: {str(e)}")