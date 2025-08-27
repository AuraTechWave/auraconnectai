# backend/modules/pos_migration/routes/migration_routes.py

"""
API routes for POS data migration operations.
Provides endpoints for initiating, monitoring, and managing migrations.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import asyncio

from core.database import get_db
from modules.auth.middleware import AuthMiddleware
from modules.auth.models import User
from ..services import MigrationOrchestrator
from ..schemas.migration_schemas import (
    MigrationOptions,
    POSConnectionConfig,
    MigrationStatus,
    MigrationPlan,
    ValidationReport,
    FieldMapping,
    MappingSuggestion,
    TokenCostReport,
    ComplianceReport,
)

router = APIRouter(
    prefix="/api/v1/pos-migration",
    tags=["pos-migration"],
    dependencies=[Depends(AuthMiddleware.verify_token)]
)

# WebSocket connections for real-time updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, migration_id: str):
        await websocket.accept()
        if migration_id not in self.active_connections:
            self.active_connections[migration_id] = []
        self.active_connections[migration_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, migration_id: str):
        if migration_id in self.active_connections:
            self.active_connections[migration_id].remove(websocket)
            if not self.active_connections[migration_id]:
                del self.active_connections[migration_id]
    
    async def send_to_migration(self, migration_id: str, message: dict):
        if migration_id in self.active_connections:
            for connection in self.active_connections[migration_id]:
                await connection.send_json(message)

manager = ConnectionManager()


@router.post("/initiate", response_model=dict)
async def initiate_migration(
    pos_config: POSConnectionConfig,
    options: MigrationOptions,
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Initiate a new POS data migration.
    
    This endpoint starts the migration process which includes:
    - Connecting to the source POS system
    - Analyzing data structure
    - Creating field mappings using AI
    - Validating data quality
    - Importing data in batches
    - Verifying the import
    
    Returns a migration ID to track progress.
    """
    # Check user permissions
    if current_user.role not in ["super_admin", "restaurant_admin"]:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to initiate migration"
        )
    
    orchestrator = MigrationOrchestrator(db)
    
    try:
        migration_id = await orchestrator.initiate_migration(
            tenant_id=current_user.tenant_id,
            pos_config=pos_config,
            options=options,
            user_id=str(current_user.id)
        )
        
        return {
            "migration_id": migration_id,
            "status": "initiated",
            "message": "Migration started successfully. Monitor progress using the migration ID.",
            "websocket_url": f"/api/v1/pos-migration/{migration_id}/ws"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate migration: {str(e)}"
        )


@router.get("/{migration_id}/status", response_model=MigrationStatus)
async def get_migration_status(
    migration_id: str,
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """Get current status of a migration."""
    
    orchestrator = MigrationOrchestrator(db)
    
    try:
        status = await orchestrator.get_migration_status(migration_id)
        return status
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Migration not found: {str(e)}"
        )


@router.post("/{migration_id}/approve-mappings")
async def approve_field_mappings(
    migration_id: str,
    approved_mappings: List[FieldMapping],
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Approve or modify field mappings for a migration.
    
    This endpoint is used when manual review is required due to:
    - Low confidence scores in AI-generated mappings
    - Data validation issues
    - Custom business logic requirements
    """
    orchestrator = MigrationOrchestrator(db)
    
    try:
        await orchestrator.approve_migration_mappings(
            migration_id=migration_id,
            approved_mappings=[m.dict() for m in approved_mappings],
            user_id=str(current_user.id)
        )
        
        return {
            "status": "approved",
            "message": "Field mappings approved. Migration will continue."
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to approve mappings: {str(e)}"
        )


@router.get("/{migration_id}/validation-report", response_model=ValidationReport)
async def get_validation_report(
    migration_id: str,
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """Get the data validation report for a migration."""
    
    # This would fetch the validation report from storage
    # For now, return a sample
    return ValidationReport(
        anomalies=[],
        summary={
            "total_issues": 0,
            "requires_manual_review": False,
            "confidence": 0.95
        }
    )


@router.post("/{migration_id}/cancel")
async def cancel_migration(
    migration_id: str,
    reason: str = Query(..., description="Reason for cancellation"),
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel an active migration."""
    
    orchestrator = MigrationOrchestrator(db)
    
    try:
        await orchestrator.cancel_migration(
            migration_id=migration_id,
            user_id=str(current_user.id),
            reason=reason
        )
        
        return {
            "status": "cancelled",
            "message": "Migration cancelled successfully."
        }
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to cancel migration: {str(e)}"
        )


@router.post("/field-mappings/suggest")
async def suggest_field_mappings(
    source_fields: List[str],
    target_fields: List[str],
    pos_type: str,
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
) -> List[MappingSuggestion]:
    """
    Get AI-powered field mapping suggestions.
    
    This endpoint analyzes source and target fields to suggest
    the best mappings based on semantic similarity and common patterns.
    """
    from ..agents import MigrationCoachAgent
    
    coach = MigrationCoachAgent(db)
    
    try:
        suggestions = await coach.suggest_field_mappings(
            source_fields=source_fields,
            target_fields=target_fields,
            context={"pos_type": pos_type}
        )
        
        return suggestions
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate suggestions: {str(e)}"
        )


@router.post("/validate-sample-data")
async def validate_sample_data(
    sample_data: dict,
    pos_type: str,
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validate sample data before starting migration.
    
    This helps identify potential issues early and ensures
    the POS connection is returning expected data format.
    """
    from ..agents import MigrationCoachAgent
    
    coach = MigrationCoachAgent(db)
    
    try:
        # Validate menu items if present
        if "menu_items" in sample_data:
            validation_report = await coach.validate_pricing_data(
                items=sample_data["menu_items"],
                pos_type=pos_type
            )
            
            return {
                "valid": validation_report.summary.total_issues == 0,
                "report": validation_report.dict()
            }
        
        return {
            "valid": True,
            "message": "No menu items to validate"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Validation failed: {str(e)}"
        )


@router.get("/audit/{migration_id}")
async def get_audit_trail(
    migration_id: str,
    operation_filter: Optional[str] = None,
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """Get audit trail for a migration."""
    
    from ..services import AuditService
    
    audit_service = AuditService(db)
    
    try:
        logs = await audit_service.get_audit_trail(
            migration_id=migration_id,
            operation_filter=operation_filter
        )
        
        return {
            "migration_id": migration_id,
            "total_logs": len(logs),
            "logs": [log.dict() for log in logs]
        }
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Audit trail not found: {str(e)}"
        )


@router.get("/compliance/{migration_id}", response_model=ComplianceReport)
async def get_compliance_report(
    migration_id: str,
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """Get GDPR/CCPA compliance report for a migration."""
    
    from ..services import AuditService
    
    audit_service = AuditService(db)
    
    try:
        report = await audit_service.generate_compliance_report(migration_id)
        return report
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=f"Compliance report not found: {str(e)}"
        )


@router.get("/token-usage/{tenant_id}", response_model=TokenCostReport)
async def get_token_usage_report(
    tenant_id: str,
    period: str = Query("month", description="Period: day, week, month"),
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """Get AI token usage report for billing purposes."""
    
    # Check permissions
    if current_user.tenant_id != tenant_id and current_user.role != "super_admin":
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions"
        )
    
    # This would query actual usage data
    # For now, return sample data
    return TokenCostReport(
        tenant_id=tenant_id,
        period=period,
        total_cost="125.50",
        by_operation={
            "field_mapping": "45.20",
            "data_validation": "38.10",
            "analysis": "42.20"
        },
        by_model={
            "gpt-4": "100.00",
            "gpt-3.5-turbo": "25.50"
        },
        token_count={
            "input": 150000,
            "output": 50000
        },
        optimization_suggestions=[
            "Consider caching field mappings for similar POS types",
            "Batch validation requests to reduce API calls"
        ]
    )


@router.websocket("/{migration_id}/ws")
async def migration_websocket(
    websocket: WebSocket,
    migration_id: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time migration updates.
    
    Clients can connect to receive:
    - Progress updates
    - Phase changes
    - Error notifications
    - Completion status
    """
    await manager.connect(websocket, migration_id)
    
    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connection",
            "message": "Connected to migration updates",
            "migration_id": migration_id
        })
        
        # Keep connection alive and handle messages
        while True:
            # Wait for any messages from client (like ping/pong)
            data = await websocket.receive_text()
            
            # Handle ping
            if data == "ping":
                await websocket.send_text("pong")
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, migration_id)
    except Exception as e:
        manager.disconnect(websocket, migration_id)
        raise


@router.get("/supported-pos-types")
async def get_supported_pos_types():
    """Get list of supported POS systems."""
    
    return {
        "supported_types": [
            {
                "id": "square",
                "name": "Square",
                "description": "Square POS system",
                "required_credentials": ["access_token", "location_id"]
            },
            {
                "id": "toast",
                "name": "Toast",
                "description": "Toast POS system", 
                "required_credentials": ["client_id", "client_secret", "restaurant_guid"]
            },
            {
                "id": "clover",
                "name": "Clover",
                "description": "Clover POS system",
                "required_credentials": ["api_key", "merchant_id"]
            }
        ]
    }


@router.post("/test-connection")
async def test_pos_connection(
    pos_config: POSConnectionConfig,
    current_user: User = Depends(AuthMiddleware.get_current_user),
    db: Session = Depends(get_db)
):
    """Test connection to POS system before starting migration."""
    
    from modules.pos.adapters.adapter_factory import AdapterFactory
    
    try:
        # Create adapter
        adapter = AdapterFactory.create_adapter(
            pos_type=pos_config.pos_type,
            credentials=pos_config.credentials
        )
        
        # Test connection
        await adapter.test_connection()
        
        # Fetch sample data
        sample_items = await adapter.fetch_menu_items(limit=5)
        
        return {
            "connected": True,
            "message": "Connection successful",
            "sample_item_count": len(sample_items),
            "sample_data": sample_items[0] if sample_items else None
        }
        
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "message": "Connection failed. Please check your credentials."
        }