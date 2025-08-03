# backend/modules/orders/utils/inventory_logging.py

import logging
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
from functools import wraps
import traceback


class InventoryLogger:
    """Specialized logger for inventory operations with structured logging"""
    
    def __init__(self, name: str = "inventory_deduction"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Create formatter for structured logs
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(extra_data)s'
        )
        
        # Add handler if not already present
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def _format_extra_data(self, **kwargs) -> Dict:
        """Format extra data for structured logging"""
        extra = {
            'timestamp': datetime.utcnow().isoformat(),
            'extra_data': json.dumps(kwargs, default=str)
        }
        return extra
    
    def log_deduction_start(self, order_id: int, user_id: int, 
                           order_items: List[Any], deduction_type: str):
        """Log the start of an inventory deduction operation"""
        self.logger.info(
            f"Starting inventory deduction for order {order_id}",
            extra=self._format_extra_data(
                event="deduction_start",
                order_id=order_id,
                user_id=user_id,
                deduction_type=deduction_type,
                item_count=len(order_items),
                menu_item_ids=[item.menu_item_id for item in order_items]
            )
        )
    
    def log_deduction_success(self, order_id: int, deducted_items: List[Dict],
                             low_stock_alerts: List[Dict], processing_time_ms: float):
        """Log successful inventory deduction"""
        self.logger.info(
            f"Successfully deducted inventory for order {order_id}",
            extra=self._format_extra_data(
                event="deduction_success",
                order_id=order_id,
                deducted_count=len(deducted_items),
                low_stock_count=len(low_stock_alerts),
                processing_time_ms=processing_time_ms,
                deducted_items=deducted_items,
                low_stock_alerts=low_stock_alerts
            )
        )
    
    def log_insufficient_inventory(self, order_id: int, insufficient_items: List[Dict]):
        """Log insufficient inventory error"""
        self.logger.warning(
            f"Insufficient inventory for order {order_id}",
            extra=self._format_extra_data(
                event="insufficient_inventory",
                order_id=order_id,
                insufficient_count=len(insufficient_items),
                insufficient_items=insufficient_items
            )
        )
    
    def log_missing_recipe(self, order_id: int, menu_items: List[Dict]):
        """Log missing recipe configuration"""
        self.logger.error(
            f"Missing recipe configuration for order {order_id}",
            extra=self._format_extra_data(
                event="missing_recipe",
                order_id=order_id,
                missing_count=len(menu_items),
                menu_items=menu_items,
                requires_manual_review=True
            )
        )
    
    def log_inventory_not_found(self, order_id: int, inventory_ids: List[int]):
        """Log inventory items not found"""
        self.logger.error(
            f"Inventory items not found for order {order_id}",
            extra=self._format_extra_data(
                event="inventory_not_found",
                order_id=order_id,
                missing_inventory_ids=inventory_ids,
                requires_manual_review=True
            )
        )
    
    def log_deduction_error(self, order_id: int, error: Exception, 
                           error_type: str = "unknown"):
        """Log general deduction error"""
        self.logger.error(
            f"Error deducting inventory for order {order_id}: {str(error)}",
            extra=self._format_extra_data(
                event="deduction_error",
                order_id=order_id,
                error_type=error_type,
                error_message=str(error),
                error_class=error.__class__.__name__,
                traceback=traceback.format_exc()
            )
        )
    
    def log_reversal_start(self, order_id: int, user_id: int, reason: str):
        """Log start of inventory reversal"""
        self.logger.info(
            f"Starting inventory reversal for order {order_id}",
            extra=self._format_extra_data(
                event="reversal_start",
                order_id=order_id,
                user_id=user_id,
                reason=reason
            )
        )
    
    def log_reversal_success(self, order_id: int, reversed_items: List[Dict]):
        """Log successful inventory reversal"""
        self.logger.info(
            f"Successfully reversed inventory for order {order_id}",
            extra=self._format_extra_data(
                event="reversal_success",
                order_id=order_id,
                reversed_count=len(reversed_items),
                reversed_items=reversed_items
            )
        )
    
    def log_concurrent_deduction(self, order_id: int, existing_adjustments: List[int]):
        """Log concurrent deduction attempt"""
        self.logger.warning(
            f"Concurrent deduction attempt detected for order {order_id}",
            extra=self._format_extra_data(
                event="concurrent_deduction",
                order_id=order_id,
                existing_adjustments=existing_adjustments
            )
        )
    
    def log_manual_review_required(self, order_id: int, reason: str, 
                                  details: Dict[str, Any]):
        """Log when manual review is required"""
        self.logger.warning(
            f"Manual review required for order {order_id}: {reason}",
            extra=self._format_extra_data(
                event="manual_review_required",
                order_id=order_id,
                reason=reason,
                details=details,
                requires_manual_review=True
            )
        )
    
    def log_low_stock_notification(self, inventory_id: int, item_name: str,
                                  current_quantity: float, threshold: float):
        """Log low stock notification"""
        self.logger.warning(
            f"Low stock alert: {item_name} (ID: {inventory_id})",
            extra=self._format_extra_data(
                event="low_stock_alert",
                inventory_id=inventory_id,
                item_name=item_name,
                current_quantity=current_quantity,
                threshold=threshold,
                percentage_remaining=(current_quantity / threshold * 100) if threshold > 0 else 0
            )
        )


def log_inventory_operation(operation_type: str):
    """Decorator for logging inventory operations"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger = InventoryLogger()
            start_time = datetime.utcnow()
            
            # Extract common parameters
            self = args[0] if args else None
            order_id = kwargs.get('order_id', 'unknown')
            user_id = kwargs.get('user_id', 'unknown')
            
            try:
                # Log operation start
                logger.logger.info(
                    f"Starting {operation_type} operation",
                    extra=logger._format_extra_data(
                        event=f"{operation_type}_start",
                        order_id=order_id,
                        user_id=user_id,
                        function=func.__name__
                    )
                )
                
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Calculate processing time
                processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # Log success
                logger.logger.info(
                    f"Completed {operation_type} operation",
                    extra=logger._format_extra_data(
                        event=f"{operation_type}_complete",
                        order_id=order_id,
                        user_id=user_id,
                        processing_time_ms=processing_time_ms,
                        function=func.__name__
                    )
                )
                
                return result
                
            except Exception as e:
                # Calculate processing time
                processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # Log error
                logger.logger.error(
                    f"Error in {operation_type} operation: {str(e)}",
                    extra=logger._format_extra_data(
                        event=f"{operation_type}_error",
                        order_id=order_id,
                        user_id=user_id,
                        processing_time_ms=processing_time_ms,
                        function=func.__name__,
                        error=str(e),
                        error_type=e.__class__.__name__,
                        traceback=traceback.format_exc()
                    )
                )
                raise
        
        return wrapper
    return decorator