# backend/modules/pos_migration/services/data_transformation_service.py

"""
Service for transforming and importing POS data according to field mappings.
Handles data type conversions, custom transformations, and batch imports.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..schemas.migration_schemas import (
    MigrationPlan,
    FieldMapping,
    FieldTransformationType,
)
from modules.menu.models import MenuItem, Category, ModifierGroup, Modifier
from modules.customers.models import Customer
from modules.orders.models import Order, OrderItem
from core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class DataTransformationService:
    """Handles data transformation and import operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.transformation_cache = {}
        
    async def transform_and_import_batch(
        self,
        data: List[Dict[str, Any]],
        data_type: str,
        mapping_plan: MigrationPlan,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Transform and import a batch of data"""
        
        result = {
            "success_count": 0,
            "error_count": 0,
            "errors": [],
            "imported_ids": []
        }
        
        # Get relevant field mappings for this data type
        mappings = self._get_mappings_for_type(
            mapping_plan.field_mappings, data_type
        )
        
        for item in data:
            try:
                # Transform data according to mappings
                transformed = await self._transform_item(
                    item, mappings, data_type
                )
                
                # Add tenant_id
                transformed["tenant_id"] = tenant_id
                
                # Import to database
                imported_id = await self._import_item(
                    transformed, data_type, tenant_id
                )
                
                result["success_count"] += 1
                result["imported_ids"].append(imported_id)
                
            except Exception as e:
                logger.error(f"Error importing {data_type}: {e}")
                result["error_count"] += 1
                result["errors"].append({
                    "item": item.get("id", "unknown"),
                    "error": str(e),
                    "data_type": data_type
                })
        
        return result
    
    async def _transform_item(
        self,
        item: Dict[str, Any],
        mappings: List[FieldMapping],
        data_type: str
    ) -> Dict[str, Any]:
        """Transform a single item according to field mappings"""
        
        transformed = {}
        
        for mapping in mappings:
            source_value = self._get_nested_value(item, mapping.source_field)
            
            if source_value is not None:
                # Apply transformation
                transformed_value = await self._apply_transformation(
                    source_value,
                    mapping.transformation,
                    mapping.custom_logic
                )
                
                # Set in target structure
                self._set_nested_value(
                    transformed,
                    mapping.target_field,
                    transformed_value
                )
        
        # Apply data type specific validations
        transformed = self._validate_transformed_data(transformed, data_type)
        
        return transformed
    
    async def _apply_transformation(
        self,
        value: Any,
        transformation_type: FieldTransformationType,
        custom_logic: Optional[str] = None
    ) -> Any:
        """Apply transformation to a value"""
        
        if transformation_type == FieldTransformationType.NONE:
            return value
            
        elif transformation_type == FieldTransformationType.LOWERCASE:
            return str(value).lower() if value else value
            
        elif transformation_type == FieldTransformationType.UPPERCASE:
            return str(value).upper() if value else value
            
        elif transformation_type == FieldTransformationType.PARSE_JSON:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse JSON: {value}")
                    return value
            return value
            
        elif transformation_type == FieldTransformationType.PARSE_DECIMAL:
            return self._parse_decimal(value)
            
        elif transformation_type == FieldTransformationType.CUSTOM:
            if custom_logic:
                return await self._apply_custom_transformation(
                    value, custom_logic
                )
            return value
        
        return value
    
    def _parse_decimal(self, value: Any) -> Decimal:
        """Parse value to Decimal, handling various formats"""
        
        if isinstance(value, Decimal):
            return value
            
        if isinstance(value, (int, float)):
            return Decimal(str(value))
            
        if isinstance(value, str):
            # Remove currency symbols and whitespace
            cleaned = re.sub(r'[^\d.-]', '', value)
            
            # Handle cents (e.g., "1999" -> "19.99")
            if '.' not in cleaned and len(cleaned) > 2:
                # Check if this looks like cents
                try:
                    as_int = int(cleaned)
                    if as_int > 10000:  # Likely cents
                        return Decimal(cleaned[:-2] + '.' + cleaned[-2:])
                except ValueError:
                    pass
            
            try:
                return Decimal(cleaned)
            except InvalidOperation:
                raise ValidationError(f"Cannot parse decimal: {value}")
        
        raise ValidationError(f"Cannot convert to decimal: {type(value)}")
    
    async def _apply_custom_transformation(
        self,
        value: Any,
        custom_logic: str
    ) -> Any:
        """Apply custom transformation logic"""
        
        # This is a simplified version - in production you'd want
        # sandboxed execution or predefined transformation functions
        
        if custom_logic == "split_name":
            # Split full name into first/last
            if isinstance(value, str):
                parts = value.split(' ', 1)
                return {
                    "first_name": parts[0],
                    "last_name": parts[1] if len(parts) > 1 else ""
                }
                
        elif custom_logic == "parse_modifiers":
            # Parse modifier string into structured data
            if isinstance(value, str):
                modifiers = []
                for mod in value.split(','):
                    mod = mod.strip()
                    if ':' in mod:
                        name, price = mod.split(':', 1)
                        modifiers.append({
                            "name": name.strip(),
                            "price": self._parse_decimal(price.strip())
                        })
                    else:
                        modifiers.append({"name": mod, "price": 0})
                return modifiers
                
        elif custom_logic == "map_pos_status":
            # Map POS-specific status to our status
            status_map = {
                "active": "active",
                "enabled": "active",
                "disabled": "inactive",
                "archived": "archived",
                "deleted": "archived"
            }
            return status_map.get(str(value).lower(), "active")
        
        return value
    
    async def _import_item(
        self,
        data: Dict[str, Any],
        data_type: str,
        tenant_id: str
    ) -> str:
        """Import transformed item to database"""
        
        if data_type == "category":
            return await self._import_category(data, tenant_id)
            
        elif data_type == "menu_item":
            return await self._import_menu_item(data, tenant_id)
            
        elif data_type == "modifier":
            return await self._import_modifier(data, tenant_id)
            
        elif data_type == "customer":
            return await self._import_customer(data, tenant_id)
            
        elif data_type == "order":
            return await self._import_order(data, tenant_id)
            
        else:
            raise ValueError(f"Unknown data type: {data_type}")
    
    async def _import_category(
        self,
        data: Dict[str, Any],
        tenant_id: str
    ) -> str:
        """Import category"""
        
        # Check if exists (by name to handle duplicates)
        existing = self.db.query(Category).filter(
            and_(
                Category.tenant_id == tenant_id,
                Category.name == data.get("name")
            )
        ).first()
        
        if existing:
            # Update existing
            for key, value in data.items():
                if hasattr(existing, key) and key != "id":
                    setattr(existing, key, value)
            self.db.commit()
            return str(existing.id)
        else:
            # Create new
            category = Category(**data)
            self.db.add(category)
            self.db.commit()
            return str(category.id)
    
    async def _import_menu_item(
        self,
        data: Dict[str, Any],
        tenant_id: str
    ) -> str:
        """Import menu item"""
        
        # Map category name to ID if needed
        if "category_name" in data and "category_id" not in data:
            category = self.db.query(Category).filter(
                and_(
                    Category.tenant_id == tenant_id,
                    Category.name == data["category_name"]
                )
            ).first()
            
            if category:
                data["category_id"] = category.id
            else:
                # Create category on the fly
                category = Category(
                    tenant_id=tenant_id,
                    name=data["category_name"],
                    is_active=True
                )
                self.db.add(category)
                self.db.commit()
                data["category_id"] = category.id
            
            del data["category_name"]
        
        # Check if exists
        existing = self.db.query(MenuItem).filter(
            and_(
                MenuItem.tenant_id == tenant_id,
                MenuItem.name == data.get("name")
            )
        ).first()
        
        if existing:
            # Update
            for key, value in data.items():
                if hasattr(existing, key) and key != "id":
                    setattr(existing, key, value)
            self.db.commit()
            return str(existing.id)
        else:
            # Create
            item = MenuItem(**data)
            self.db.add(item)
            self.db.commit()
            return str(item.id)
    
    async def _import_modifier(
        self,
        data: Dict[str, Any],
        tenant_id: str
    ) -> str:
        """Import modifier with group"""
        
        # Extract group data if present
        group_name = data.get("group_name", "Default Group")
        
        # Find or create modifier group
        group = self.db.query(ModifierGroup).filter(
            and_(
                ModifierGroup.tenant_id == tenant_id,
                ModifierGroup.name == group_name
            )
        ).first()
        
        if not group:
            group = ModifierGroup(
                tenant_id=tenant_id,
                name=group_name,
                is_required=False,
                min_selections=0,
                max_selections=10
            )
            self.db.add(group)
            self.db.commit()
        
        # Create modifier
        modifier_data = {
            "modifier_group_id": group.id,
            "name": data.get("name"),
            "price": data.get("price", 0),
            "is_available": data.get("is_available", True)
        }
        
        modifier = Modifier(**modifier_data)
        self.db.add(modifier)
        self.db.commit()
        
        return str(modifier.id)
    
    async def _import_customer(
        self,
        data: Dict[str, Any],
        tenant_id: str
    ) -> str:
        """Import customer"""
        
        # Check by email
        email = data.get("email")
        if email:
            existing = self.db.query(Customer).filter(
                and_(
                    Customer.tenant_id == tenant_id,
                    Customer.email == email
                )
            ).first()
            
            if existing:
                # Update
                for key, value in data.items():
                    if hasattr(existing, key) and key != "id":
                        setattr(existing, key, value)
                self.db.commit()
                return str(existing.id)
        
        # Create new
        customer = Customer(**data)
        self.db.add(customer)
        self.db.commit()
        return str(customer.id)
    
    async def _import_order(
        self,
        data: Dict[str, Any],
        tenant_id: str
    ) -> str:
        """Import historical order"""
        
        # This is simplified - real implementation would handle
        # order items, payments, etc.
        
        order_data = {
            "tenant_id": tenant_id,
            "customer_id": data.get("customer_id"),
            "status": data.get("status", "completed"),
            "total_amount": data.get("total_amount", 0),
            "created_at": data.get("created_at", datetime.utcnow())
        }
        
        order = Order(**order_data)
        self.db.add(order)
        
        # Add order items if present
        if "items" in data:
            for item_data in data["items"]:
                order_item = OrderItem(
                    order_id=order.id,
                    menu_item_id=item_data.get("menu_item_id"),
                    quantity=item_data.get("quantity", 1),
                    unit_price=item_data.get("unit_price", 0),
                    subtotal=item_data.get("subtotal", 0)
                )
                self.db.add(order_item)
        
        self.db.commit()
        return str(order.id)
    
    def _get_mappings_for_type(
        self,
        all_mappings: List[FieldMapping],
        data_type: str
    ) -> List[FieldMapping]:
        """Filter mappings relevant to data type"""
        
        # This would use metadata or naming conventions
        # to determine which mappings apply
        
        type_prefixes = {
            "category": ["category.", "cat."],
            "menu_item": ["item.", "product.", "menu."],
            "modifier": ["modifier.", "mod."],
            "customer": ["customer.", "cust."],
            "order": ["order.", "transaction."]
        }
        
        relevant = []
        prefixes = type_prefixes.get(data_type, [])
        
        for mapping in all_mappings:
            # Check if source field matches data type
            for prefix in prefixes:
                if mapping.source_field.startswith(prefix):
                    relevant.append(mapping)
                    break
            
            # Also check common fields
            if mapping.source_field in ["name", "description", "price", "active"]:
                relevant.append(mapping)
        
        return relevant
    
    def _get_nested_value(
        self,
        obj: Dict[str, Any],
        path: str
    ) -> Any:
        """Get value from nested dictionary using dot notation"""
        
        keys = path.split('.')
        value = obj
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    def _set_nested_value(
        self,
        obj: Dict[str, Any],
        path: str,
        value: Any
    ):
        """Set value in nested dictionary using dot notation"""
        
        keys = path.split('.')
        current = obj
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def _validate_transformed_data(
        self,
        data: Dict[str, Any],
        data_type: str
    ) -> Dict[str, Any]:
        """Validate and clean transformed data"""
        
        if data_type == "menu_item":
            # Ensure required fields
            if not data.get("name"):
                raise ValidationError("Menu item name is required")
            
            # Set defaults
            data.setdefault("is_active", True)
            data.setdefault("price", Decimal("0"))
            data.setdefault("preparation_time", 15)
            
        elif data_type == "category":
            if not data.get("name"):
                raise ValidationError("Category name is required")
            
            data.setdefault("is_active", True)
            data.setdefault("display_order", 0)
            
        elif data_type == "customer":
            # Validate email if present
            if data.get("email"):
                email = data["email"].lower().strip()
                if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                    raise ValidationError(f"Invalid email: {email}")
                data["email"] = email
        
        return data
    
    async def validate_field_mappings(
        self,
        mappings: List[FieldMapping],
        sample_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Validate that field mappings work with sample data"""
        
        validation_results = []
        
        for mapping in mappings:
            result = {
                "mapping": mapping.dict(),
                "valid": True,
                "issues": []
            }
            
            # Check if source field exists in sample data
            source_value = self._get_nested_value(
                sample_data, mapping.source_field
            )
            
            if source_value is None:
                result["valid"] = False
                result["issues"].append(
                    f"Source field '{mapping.source_field}' not found in sample data"
                )
            else:
                # Try transformation
                try:
                    transformed = await self._apply_transformation(
                        source_value,
                        mapping.transformation,
                        mapping.custom_logic
                    )
                    result["sample_transformation"] = {
                        "input": source_value,
                        "output": transformed
                    }
                except Exception as e:
                    result["valid"] = False
                    result["issues"].append(
                        f"Transformation failed: {str(e)}"
                    )
            
            validation_results.append(result)
        
        return validation_results
    
    def get_transformation_stats(self) -> Dict[str, Any]:
        """Get statistics about transformations"""
        
        return {
            "cache_size": len(self.transformation_cache),
            "supported_types": [
                "category", "menu_item", "modifier", 
                "customer", "order"
            ],
            "transformation_types": [
                t.value for t in FieldTransformationType
            ]
        }