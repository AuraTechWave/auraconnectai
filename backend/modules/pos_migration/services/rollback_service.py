# backend/modules/pos_migration/services/rollback_service.py

"""
Rollback service for undoing failed or cancelled migrations.
Tracks imported data and provides clean rollback functionality.
"""

import logging
from typing import Dict, Any, List, Set
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from modules.menu.models import MenuItem, Category, ModifierGroup, Modifier
from modules.customers.models import Customer
from modules.orders.models import Order, OrderItem
from ..schemas.migration_schemas import AuditLogEntry

logger = logging.getLogger(__name__)


class RollbackService:
    """Handles rollback of migration data"""
    
    def __init__(self, db: Session):
        self.db = db
        self.rollback_registry: Dict[str, Dict[str, Set[str]]] = {}
        
    def register_import(
        self,
        migration_id: str,
        entity_type: str,
        entity_id: str
    ):
        """Register an imported entity for potential rollback"""
        
        if migration_id not in self.rollback_registry:
            self.rollback_registry[migration_id] = {}
            
        if entity_type not in self.rollback_registry[migration_id]:
            self.rollback_registry[migration_id][entity_type] = set()
            
        self.rollback_registry[migration_id][entity_type].add(entity_id)
        
        logger.debug(
            f"Registered {entity_type} {entity_id} for migration {migration_id}"
        )
    
    def register_batch_import(
        self,
        migration_id: str,
        entity_type: str,
        entity_ids: List[str]
    ):
        """Register multiple imported entities"""
        
        for entity_id in entity_ids:
            self.register_import(migration_id, entity_type, entity_id)
    
    async def rollback_migration(
        self,
        migration_id: str,
        tenant_id: str,
        audit_callback=None
    ) -> Dict[str, Any]:
        """Rollback all data imported during a migration"""
        
        logger.info(f"Starting rollback for migration {migration_id}")
        
        rollback_stats = {
            "migration_id": migration_id,
            "started_at": datetime.utcnow(),
            "entities_deleted": {},
            "errors": []
        }
        
        if migration_id not in self.rollback_registry:
            logger.warning(f"No rollback data found for migration {migration_id}")
            return rollback_stats
        
        migration_data = self.rollback_registry[migration_id]
        
        # Order matters due to foreign key constraints
        rollback_order = [
            "order_items",
            "orders",
            "modifiers",
            "modifier_groups",
            "menu_items",
            "categories",
            "customers"
        ]
        
        for entity_type in rollback_order:
            if entity_type in migration_data:
                try:
                    count = await self._rollback_entity_type(
                        entity_type,
                        migration_data[entity_type],
                        tenant_id
                    )
                    
                    rollback_stats["entities_deleted"][entity_type] = count
                    
                    # Log rollback action
                    if audit_callback:
                        await audit_callback(
                            migration_id=migration_id,
                            operation=f"rollback_{entity_type}",
                            details={
                                "entity_type": entity_type,
                                "count": count
                            }
                        )
                        
                except Exception as e:
                    logger.error(f"Error rolling back {entity_type}: {e}")
                    rollback_stats["errors"].append({
                        "entity_type": entity_type,
                        "error": str(e)
                    })
        
        # Clean up registry
        del self.rollback_registry[migration_id]
        
        rollback_stats["completed_at"] = datetime.utcnow()
        rollback_stats["duration_seconds"] = (
            rollback_stats["completed_at"] - rollback_stats["started_at"]
        ).total_seconds()
        
        logger.info(
            f"Rollback completed for migration {migration_id}. "
            f"Deleted: {rollback_stats['entities_deleted']}"
        )
        
        return rollback_stats
    
    async def _rollback_entity_type(
        self,
        entity_type: str,
        entity_ids: Set[str],
        tenant_id: str
    ) -> int:
        """Rollback specific entity type"""
        
        model_map = {
            "categories": Category,
            "menu_items": MenuItem,
            "modifier_groups": ModifierGroup,
            "modifiers": Modifier,
            "customers": Customer,
            "orders": Order,
            "order_items": OrderItem
        }
        
        model = model_map.get(entity_type)
        if not model:
            raise ValueError(f"Unknown entity type: {entity_type}")
        
        # Convert string IDs to appropriate type
        try:
            # Try UUID conversion first
            import uuid
            typed_ids = [uuid.UUID(id_str) for id_str in entity_ids]
        except:
            # Fall back to strings/integers
            typed_ids = list(entity_ids)
        
        # Delete entities
        query = self.db.query(model).filter(
            and_(
                model.id.in_(typed_ids),
                # Most models have tenant_id
                getattr(model, 'tenant_id', None) == tenant_id
                if hasattr(model, 'tenant_id') else True
            )
        )
        
        count = query.count()
        query.delete(synchronize_session=False)
        self.db.commit()
        
        return count
    
    def create_rollback_checkpoint(
        self,
        migration_id: str
    ) -> Dict[str, Any]:
        """Create a checkpoint of current rollback state"""
        
        if migration_id not in self.rollback_registry:
            return {}
            
        checkpoint = {
            "migration_id": migration_id,
            "timestamp": datetime.utcnow().isoformat(),
            "entities": {}
        }
        
        for entity_type, ids in self.rollback_registry[migration_id].items():
            checkpoint["entities"][entity_type] = list(ids)
            
        return checkpoint
    
    def restore_from_checkpoint(
        self,
        checkpoint: Dict[str, Any]
    ):
        """Restore rollback registry from checkpoint"""
        
        migration_id = checkpoint["migration_id"]
        self.rollback_registry[migration_id] = {}
        
        for entity_type, ids in checkpoint["entities"].items():
            self.rollback_registry[migration_id][entity_type] = set(ids)
    
    async def selective_rollback(
        self,
        migration_id: str,
        entity_types: List[str],
        tenant_id: str
    ) -> Dict[str, Any]:
        """Rollback only specific entity types"""
        
        logger.info(
            f"Starting selective rollback for migration {migration_id}, "
            f"types: {entity_types}"
        )
        
        rollback_stats = {
            "migration_id": migration_id,
            "entity_types": entity_types,
            "entities_deleted": {},
            "errors": []
        }
        
        if migration_id not in self.rollback_registry:
            return rollback_stats
            
        migration_data = self.rollback_registry[migration_id]
        
        for entity_type in entity_types:
            if entity_type in migration_data:
                try:
                    count = await self._rollback_entity_type(
                        entity_type,
                        migration_data[entity_type],
                        tenant_id
                    )
                    
                    rollback_stats["entities_deleted"][entity_type] = count
                    
                    # Remove from registry
                    del migration_data[entity_type]
                    
                except Exception as e:
                    logger.error(f"Error in selective rollback of {entity_type}: {e}")
                    rollback_stats["errors"].append({
                        "entity_type": entity_type,
                        "error": str(e)
                    })
        
        # Clean up if all entities rolled back
        if not migration_data:
            del self.rollback_registry[migration_id]
            
        return rollback_stats
    
    def get_rollback_preview(
        self,
        migration_id: str
    ) -> Dict[str, Any]:
        """Get preview of what would be rolled back"""
        
        if migration_id not in self.rollback_registry:
            return {
                "migration_id": migration_id,
                "entities": {},
                "total_count": 0
            }
            
        preview = {
            "migration_id": migration_id,
            "entities": {},
            "total_count": 0
        }
        
        for entity_type, ids in self.rollback_registry[migration_id].items():
            count = len(ids)
            preview["entities"][entity_type] = {
                "count": count,
                "sample_ids": list(ids)[:5]  # Show first 5 IDs
            }
            preview["total_count"] += count
            
        return preview
    
    def clear_migration_data(self, migration_id: str):
        """Clear rollback data for a migration (after successful completion)"""
        
        if migration_id in self.rollback_registry:
            del self.rollback_registry[migration_id]
            logger.info(f"Cleared rollback data for migration {migration_id}")