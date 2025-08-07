# backend/modules/menu/exceptions/recipe_exceptions.py

"""
Enhanced exception classes for recipe management with detailed error payloads.
Includes rule IDs and structured error information for frontend mapping.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum
from fastapi import HTTPException, status


class RecipeErrorCode(str, Enum):
    """Recipe-specific error codes for frontend mapping"""
    
    # Validation errors
    INVALID_RECIPE_DATA = "RCP001"
    MISSING_REQUIRED_FIELD = "RCP002"
    INVALID_INGREDIENT = "RCP003"
    DUPLICATE_INGREDIENT = "RCP004"
    CIRCULAR_DEPENDENCY = "RCP005"
    INVALID_YIELD_QUANTITY = "RCP006"
    INVALID_COST_DATA = "RCP007"
    
    # Business rule errors
    RECIPE_ALREADY_EXISTS = "RCP100"
    RECIPE_NOT_FOUND = "RCP101"
    MENU_ITEM_NOT_FOUND = "RCP102"
    INVENTORY_ITEM_NOT_FOUND = "RCP103"
    INSUFFICIENT_PERMISSIONS = "RCP104"
    RECIPE_IN_USE = "RCP105"
    
    # Calculation errors
    COST_CALCULATION_FAILED = "RCP200"
    MISSING_COST_DATA = "RCP201"
    INVALID_UNIT_CONVERSION = "RCP202"
    
    # Compliance errors
    COMPLIANCE_CHECK_FAILED = "RCP300"
    MISSING_RECIPE_REQUIRED = "RCP301"
    INACTIVE_RECIPE = "RCP302"
    DRAFT_RECIPE_NOT_ALLOWED = "RCP303"
    
    # Performance errors
    OPERATION_TIMEOUT = "RCP400"
    RATE_LIMIT_EXCEEDED = "RCP401"
    CACHE_ERROR = "RCP402"
    
    # Export errors
    EXPORT_FAILED = "RCP500"
    INVALID_EXPORT_FORMAT = "RCP501"
    EXPORT_SIZE_EXCEEDED = "RCP502"


class RecipeException(HTTPException):
    """Base exception for recipe-related errors with enhanced payload"""
    
    def __init__(
        self,
        status_code: int,
        error_code: RecipeErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        field: Optional[str] = None,
        rule_id: Optional[str] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.field = field
        self.rule_id = rule_id
        self.timestamp = datetime.utcnow()
        
        # Build error payload
        error_payload = {
            "error": {
                "code": error_code.value,
                "message": message,
                "timestamp": self.timestamp.isoformat(),
                "details": self.details
            }
        }
        
        if field:
            error_payload["error"]["field"] = field
            
        if rule_id:
            error_payload["error"]["rule_id"] = rule_id
        
        super().__init__(
            status_code=status_code,
            detail=error_payload
        )


class RecipeValidationError(RecipeException):
    """Validation error with field-level details"""
    
    def __init__(
        self,
        error_code: RecipeErrorCode,
        message: str,
        field: str,
        value: Any = None,
        rule_id: Optional[str] = None,
        allowed_values: Optional[List[Any]] = None
    ):
        details = {}
        if value is not None:
            details["provided_value"] = value
        if allowed_values:
            details["allowed_values"] = allowed_values
            
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code=error_code,
            message=message,
            details=details,
            field=field,
            rule_id=rule_id
        )


class RecipeBusinessRuleError(RecipeException):
    """Business rule violation error"""
    
    def __init__(
        self,
        error_code: RecipeErrorCode,
        message: str,
        rule_id: str,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message,
            details=context or {},
            rule_id=rule_id
        )


class RecipeCalculationError(RecipeException):
    """Calculation error with detailed context"""
    
    def __init__(
        self,
        error_code: RecipeErrorCode,
        message: str,
        calculation_type: str,
        input_data: Optional[Dict[str, Any]] = None,
        error_details: Optional[str] = None
    ):
        details = {
            "calculation_type": calculation_type
        }
        if input_data:
            details["input_data"] = input_data
        if error_details:
            details["error_details"] = error_details
            
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code=error_code,
            message=message,
            details=details
        )


class RecipeComplianceError(RecipeException):
    """Compliance violation error"""
    
    def __init__(
        self,
        error_code: RecipeErrorCode,
        message: str,
        rule_id: str,
        menu_items: Optional[List[Dict[str, Any]]] = None,
        compliance_level: Optional[str] = None
    ):
        details = {
            "compliance_level": compliance_level or "error"
        }
        if menu_items:
            details["affected_items"] = menu_items
            
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            error_code=error_code,
            message=message,
            details=details,
            rule_id=rule_id
        )


class RecipePerformanceError(RecipeException):
    """Performance-related error"""
    
    def __init__(
        self,
        error_code: RecipeErrorCode,
        message: str,
        operation: str,
        duration_ms: Optional[float] = None,
        threshold_ms: Optional[float] = None
    ):
        details = {
            "operation": operation
        }
        if duration_ms:
            details["duration_ms"] = duration_ms
        if threshold_ms:
            details["threshold_ms"] = threshold_ms
            
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code=error_code,
            message=message,
            details=details
        )


class RecipeExportError(RecipeException):
    """Export operation error"""
    
    def __init__(
        self,
        error_code: RecipeErrorCode,
        message: str,
        format: str,
        size: Optional[int] = None,
        max_size: Optional[int] = None
    ):
        details = {
            "format": format
        }
        if size:
            details["size"] = size
        if max_size:
            details["max_size"] = max_size
            
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if size and max_size and size > max_size else status.HTTP_400_BAD_REQUEST,
            error_code=error_code,
            message=message,
            details=details
        )


# Validation Rules Registry
class ValidationRule:
    """Validation rule definition"""
    
    def __init__(self, rule_id: str, description: str, validator: callable):
        self.rule_id = rule_id
        self.description = description
        self.validator = validator


# Recipe validation rules
RECIPE_VALIDATION_RULES = {
    "RVR001": ValidationRule(
        "RVR001",
        "Recipe must have at least one ingredient",
        lambda recipe: len(recipe.get("ingredients", [])) > 0
    ),
    "RVR002": ValidationRule(
        "RVR002",
        "Recipe yield quantity must be positive",
        lambda recipe: recipe.get("yield_quantity", 0) > 0
    ),
    "RVR003": ValidationRule(
        "RVR003",
        "Recipe name must be unique per menu item",
        lambda recipe, existing: not existing
    ),
    "RVR004": ValidationRule(
        "RVR004",
        "Ingredient quantities must be positive",
        lambda recipe: all(ing.get("quantity", 0) > 0 for ing in recipe.get("ingredients", []))
    ),
    "RVR005": ValidationRule(
        "RVR005",
        "Recipe must not have circular dependencies",
        lambda recipe, validator: validator.validate_no_circular_dependencies(recipe)
    )
}


def validate_recipe_data(recipe_data: Dict[str, Any], context: Dict[str, Any] = None) -> List[RecipeValidationError]:
    """
    Validate recipe data against all rules.
    
    Args:
        recipe_data: Recipe data to validate
        context: Additional context for validation
        
    Returns:
        List of validation errors
    """
    errors = []
    context = context or {}
    
    for rule_id, rule in RECIPE_VALIDATION_RULES.items():
        try:
            # Pass appropriate arguments based on rule
            if rule.validator.__code__.co_argcount == 1:
                result = rule.validator(recipe_data)
            else:
                result = rule.validator(recipe_data, context.get(rule_id))
                
            if not result:
                errors.append(
                    RecipeValidationError(
                        error_code=RecipeErrorCode.INVALID_RECIPE_DATA,
                        message=rule.description,
                        field="recipe",
                        rule_id=rule_id
                    )
                )
        except Exception as e:
            errors.append(
                RecipeValidationError(
                    error_code=RecipeErrorCode.INVALID_RECIPE_DATA,
                    message=f"Validation rule {rule_id} failed: {str(e)}",
                    field="recipe",
                    rule_id=rule_id
                )
            )
    
    return errors