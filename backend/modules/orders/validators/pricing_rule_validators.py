# backend/modules/orders/validators/pricing_rule_validators.py

import jsonschema
from jsonschema import validate, ValidationError, Draft7Validator
from typing import Dict, Any, List, Tuple
import logging

logger = logging.getLogger(__name__)

# JSON Schema definitions for rule conditions

TIME_CONDITIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "days_of_week": {
            "type": "array",
            "items": {
                "type": "integer",
                "minimum": 0,
                "maximum": 6
            },
            "minItems": 1,
            "maxItems": 7,
            "uniqueItems": True,
            "description": "Days of week (0=Monday, 6=Sunday)"
        },
        "start_time": {
            "type": "string",
            "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
            "description": "Start time in HH:MM format"
        },
        "end_time": {
            "type": "string",
            "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$",
            "description": "End time in HH:MM format"
        },
        "timezone": {
            "type": "string",
            "description": "Timezone for time conditions (e.g., 'America/New_York')"
        },
        "date_ranges": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "format": "date"
                    },
                    "end_date": {
                        "type": "string",
                        "format": "date"
                    }
                },
                "required": ["start_date", "end_date"]
            }
        }
    },
    "dependencies": {
        "start_time": ["end_time"],
        "end_time": ["start_time"]
    },
    "additionalProperties": False
}

ITEM_CONDITIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "menu_item_ids": {
            "type": "array",
            "items": {
                "type": "integer",
                "minimum": 1
            },
            "minItems": 1,
            "uniqueItems": True,
            "description": "Specific menu item IDs that trigger the rule"
        },
        "category_ids": {
            "type": "array",
            "items": {
                "type": "integer",
                "minimum": 1
            },
            "minItems": 1,
            "uniqueItems": True,
            "description": "Category IDs that trigger the rule"
        },
        "exclude_item_ids": {
            "type": "array",
            "items": {
                "type": "integer",
                "minimum": 1
            },
            "uniqueItems": True,
            "description": "Menu items to exclude from the rule"
        },
        "min_quantity": {
            "type": "integer",
            "minimum": 1,
            "description": "Minimum quantity of qualifying items"
        },
        "max_quantity": {
            "type": "integer",
            "minimum": 1,
            "description": "Maximum quantity for the rule to apply"
        },
        "tags": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Item tags that qualify for the rule"
        }
    },
    "additionalProperties": False
}

CUSTOMER_CONDITIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "loyalty_tier": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["bronze", "silver", "gold", "platinum", "vip"]
            },
            "minItems": 1,
            "uniqueItems": True,
            "description": "Required loyalty tiers"
        },
        "min_orders": {
            "type": "integer",
            "minimum": 0,
            "description": "Minimum number of previous orders"
        },
        "min_lifetime_value": {
            "type": "number",
            "minimum": 0,
            "description": "Minimum lifetime spending"
        },
        "tags": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "Customer tags required"
        },
        "customer_ids": {
            "type": "array",
            "items": {
                "type": "integer",
                "minimum": 1
            },
            "uniqueItems": True,
            "description": "Specific customer IDs"
        },
        "new_customer": {
            "type": "boolean",
            "description": "Apply only to new customers"
        },
        "birthday_month": {
            "type": "boolean",
            "description": "Apply during customer's birthday month"
        }
    },
    "additionalProperties": False
}

ORDER_CONDITIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "min_items": {
            "type": "integer",
            "minimum": 1,
            "description": "Minimum number of items in order"
        },
        "max_items": {
            "type": "integer",
            "minimum": 1,
            "description": "Maximum number of items in order"
        },
        "payment_methods": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["credit_card", "debit_card", "cash", "mobile_payment", "gift_card"]
            },
            "minItems": 1,
            "uniqueItems": True,
            "description": "Allowed payment methods"
        },
        "order_types": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["dine_in", "takeout", "delivery", "curbside", "catering"]
            },
            "minItems": 1,
            "uniqueItems": True,
            "description": "Allowed order types"
        },
        "channels": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": ["web", "mobile", "pos", "phone", "third_party"]
            },
            "minItems": 1,
            "uniqueItems": True,
            "description": "Allowed order channels"
        },
        "min_subtotal": {
            "type": "number",
            "minimum": 0,
            "description": "Minimum order subtotal"
        },
        "max_subtotal": {
            "type": "number",
            "minimum": 0,
            "description": "Maximum order subtotal"
        }
    },
    "additionalProperties": False
}

# Master schema for all conditions
PRICING_RULE_CONDITIONS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "time": TIME_CONDITIONS_SCHEMA,
        "items": ITEM_CONDITIONS_SCHEMA,
        "customer": CUSTOMER_CONDITIONS_SCHEMA,
        "order": ORDER_CONDITIONS_SCHEMA,
        "custom": {
            "type": "object",
            "description": "Custom conditions for advanced rules"
        }
    },
    "additionalProperties": False
}

# Rule type specific schemas
RULE_TYPE_SCHEMAS = {
    "bundle_discount": {
        "type": "object",
        "properties": {
            "bundle_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer", "minimum": 1},
                        "quantity": {"type": "integer", "minimum": 1}
                    },
                    "required": ["item_id", "quantity"]
                },
                "minItems": 2,
                "description": "Items that must be purchased together"
            }
        },
        "required": ["bundle_items"]
    },
    "bogo": {
        "type": "object",
        "properties": {
            "buy_quantity": {"type": "integer", "minimum": 1},
            "get_quantity": {"type": "integer", "minimum": 1},
            "get_discount_percent": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "default": 100
            }
        },
        "required": ["buy_quantity", "get_quantity"]
    },
    "quantity_discount": {
        "type": "object",
        "properties": {
            "tiers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "min_quantity": {"type": "integer", "minimum": 1},
                        "discount_percent": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 100
                        }
                    },
                    "required": ["min_quantity", "discount_percent"]
                },
                "minItems": 1
            }
        },
        "required": ["tiers"]
    }
}


class PricingRuleValidator:
    """Validator for pricing rule conditions"""
    
    def __init__(self):
        self.conditions_validator = Draft7Validator(PRICING_RULE_CONDITIONS_SCHEMA)
    
    def validate_conditions(
        self, 
        conditions: Dict[str, Any],
        rule_type: str = None
    ) -> Tuple[bool, List[str], List[str]]:
        """
        Validate pricing rule conditions
        
        Args:
            conditions: The conditions dictionary to validate
            rule_type: Optional rule type for additional validation
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Validate against main schema
        try:
            validate(instance=conditions, schema=PRICING_RULE_CONDITIONS_SCHEMA)
        except ValidationError as e:
            # Format error messages
            for error in self.conditions_validator.iter_errors(conditions):
                error_path = '.'.join(str(p) for p in error.path)
                errors.append(f"{error_path}: {error.message}")
        
        # Additional rule type specific validation
        if rule_type and rule_type in RULE_TYPE_SCHEMAS:
            if 'custom' in conditions:
                try:
                    validate(
                        instance=conditions['custom'],
                        schema=RULE_TYPE_SCHEMAS[rule_type]
                    )
                except ValidationError as e:
                    errors.append(f"Rule type '{rule_type}' validation: {e.message}")
        
        # Business logic validation
        errors.extend(self._validate_business_logic(conditions, warnings))
        
        return len(errors) == 0, errors, warnings
    
    def _validate_business_logic(
        self, 
        conditions: Dict[str, Any],
        warnings: List[str]
    ) -> List[str]:
        """Validate business logic constraints"""
        errors = []
        
        # Time validation
        if 'time' in conditions:
            time_cond = conditions['time']
            
            # Check time range logic
            if 'start_time' in time_cond and 'end_time' in time_cond:
                start = time_cond['start_time']
                end = time_cond['end_time']
                
                if start == end:
                    errors.append("Start time and end time cannot be the same")
                
                # Check for overnight ranges
                if start > end:
                    warnings.append(
                        "Time range spans midnight - ensure this is intended"
                    )
            
            # Check date ranges
            if 'date_ranges' in time_cond:
                for i, range_item in enumerate(time_cond['date_ranges']):
                    if range_item['start_date'] > range_item['end_date']:
                        errors.append(
                            f"Date range {i}: start_date must be before end_date"
                        )
        
        # Item validation
        if 'items' in conditions:
            items_cond = conditions['items']
            
            # Check for conflicts
            if 'menu_item_ids' in items_cond and 'exclude_item_ids' in items_cond:
                overlap = set(items_cond['menu_item_ids']) & set(
                    items_cond['exclude_item_ids']
                )
                if overlap:
                    errors.append(
                        f"Items {overlap} appear in both include and exclude lists"
                    )
            
            # Check quantity logic
            if 'min_quantity' in items_cond and 'max_quantity' in items_cond:
                if items_cond['min_quantity'] > items_cond['max_quantity']:
                    errors.append("min_quantity cannot be greater than max_quantity")
        
        # Order validation
        if 'order' in conditions:
            order_cond = conditions['order']
            
            # Check item count logic
            if 'min_items' in order_cond and 'max_items' in order_cond:
                if order_cond['min_items'] > order_cond['max_items']:
                    errors.append("min_items cannot be greater than max_items")
            
            # Check subtotal logic
            if 'min_subtotal' in order_cond and 'max_subtotal' in order_cond:
                if order_cond['min_subtotal'] > order_cond['max_subtotal']:
                    errors.append("min_subtotal cannot be greater than max_subtotal")
        
        # Customer validation
        if 'customer' in conditions:
            customer_cond = conditions['customer']
            
            # Check conflicting conditions
            if customer_cond.get('new_customer') and customer_cond.get('min_orders', 0) > 0:
                errors.append(
                    "Cannot require both new_customer and min_orders > 0"
                )
        
        return errors
    
    def normalize_conditions(self, conditions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize conditions to ensure consistent format
        
        Args:
            conditions: Raw conditions dictionary
            
        Returns:
            Normalized conditions dictionary
        """
        normalized = {}
        
        # Only include non-empty sections
        for section in ['time', 'items', 'customer', 'order', 'custom']:
            if section in conditions and conditions[section]:
                normalized[section] = conditions[section]
        
        # Convert lists to sorted lists for consistency
        if 'time' in normalized and 'days_of_week' in normalized['time']:
            normalized['time']['days_of_week'] = sorted(
                normalized['time']['days_of_week']
            )
        
        if 'items' in normalized:
            for field in ['menu_item_ids', 'category_ids', 'exclude_item_ids']:
                if field in normalized['items']:
                    normalized['items'][field] = sorted(normalized['items'][field])
        
        return normalized


# Create singleton validator
pricing_rule_validator = PricingRuleValidator()