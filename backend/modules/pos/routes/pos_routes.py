from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import hmac
import hashlib
import logging
from fastapi_limiter.depends import RateLimiter
from core.database import get_db
from ..models.pos_integration import POSIntegration
from ..models.pos_sync_log import POSSyncLog
from ..services.pos_bridge_service import POSBridgeService
from ..schemas.pos_schemas import (
    POSIntegrationCreate,
    POSIntegrationOut,
    POSSyncLogOut,
    SyncRequest,
    SyncResponse,
    POSOrderSyncRequest,
)
from ..enums.pos_enums import POSIntegrationStatus, POSVendor
from ..adapters.adapter_factory import AdapterFactory

router = APIRouter(prefix="/pos", tags=["POS Integration"])

logger = logging.getLogger(__name__)


@router.post("/integrations", response_model=POSIntegrationOut)
async def create_pos_integration(
    integration_data: POSIntegrationCreate, db: Session = Depends(get_db)
):
    """Create a new POS integration"""
    integration = POSIntegration(
        vendor=integration_data.vendor.value,
        credentials=integration_data.credentials,
        connected_on=datetime.utcnow(),
        status=POSIntegrationStatus.ACTIVE.value,
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


@router.get("/integrations", response_model=List[POSIntegrationOut])
async def list_pos_integrations(db: Session = Depends(get_db)):
    """List all POS integrations"""
    return db.query(POSIntegration).all()


@router.get("/integrations/{integration_id}", response_model=POSIntegrationOut)
async def get_pos_integration(integration_id: int, db: Session = Depends(get_db)):
    """Get a specific POS integration"""
    integration = (
        db.query(POSIntegration).filter(POSIntegration.id == integration_id).first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")
    return integration


@router.put("/integrations/{integration_id}/status")
async def update_integration_status(
    integration_id: int, status: POSIntegrationStatus, db: Session = Depends(get_db)
):
    """Update POS integration status"""
    integration = (
        db.query(POSIntegration).filter(POSIntegration.id == integration_id).first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    integration.status = status.value
    db.commit()
    return {"message": "Status updated successfully"}


@router.get("/integrations/{integration_id}/test")
async def test_pos_integration(integration_id: int, db: Session = Depends(get_db)):
    """Test POS integration connection"""
    service = POSBridgeService(db)
    is_connected = await service.test_integration(integration_id)
    return {"connected": is_connected}


@router.post("/sync", response_model=SyncResponse)
async def sync_order_to_pos(sync_request: SyncRequest, db: Session = Depends(get_db)):
    """Sync an order to POS system"""
    if not sync_request.order_id or not sync_request.integration_id:
        raise HTTPException(
            status_code=400, detail="order_id and integration_id are required"
        )

    service = POSBridgeService(db)
    return await service.sync_order_to_pos(
        sync_request.order_id, sync_request.integration_id
    )


@router.post("/sync/all/{order_id}")
async def sync_order_to_all_pos(order_id: int, db: Session = Depends(get_db)):
    """Sync an order to all active POS integrations"""
    service = POSBridgeService(db)
    return await service.sync_all_active_integrations(order_id)


@router.get("/sync-logs", response_model=List[POSSyncLogOut])
async def get_sync_logs(
    integration_id: Optional[int] = None,
    order_id: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get sync logs, optionally filtered by integration or order"""
    query = db.query(POSSyncLog)
    if integration_id:
        query = query.filter(POSSyncLog.integration_id == integration_id)
    if order_id:
        query = query.filter(POSSyncLog.order_id == order_id)
    return query.order_by(POSSyncLog.created_at.desc()).limit(limit).all()


@router.delete("/integrations/{integration_id}")
async def delete_pos_integration(integration_id: int, db: Session = Depends(get_db)):
    """Delete a POS integration"""
    integration = (
        db.query(POSIntegration).filter(POSIntegration.id == integration_id).first()
    )
    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    db.delete(integration)
    db.commit()
    return {"message": "Integration deleted successfully"}


@router.post("/webhook/{integration_id}")
async def pos_webhook_receiver(
    integration_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ratelimit: dict = Depends(RateLimiter(times=100, seconds=60)),
):
    """Receive webhook notifications from POS systems for new orders"""
    try:
        integration = (
            db.query(POSIntegration).filter(POSIntegration.id == integration_id).first()
        )

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        webhook_secret = integration.credentials.get("webhook_secret")
        if webhook_secret:
            signature = request.headers.get("X-Webhook-Signature")
            if not signature or not _verify_webhook_signature(
                await request.body(), webhook_secret, signature
            ):
                raise HTTPException(status_code=401, detail="Invalid webhook signature")

        payload = await request.json()

        service = POSBridgeService(db)
        result = await service._process_vendor_order(
            payload.get("order", payload), integration
        )

        return {"success": True, "result": result}

    except Exception as e:
        logger.error(f"Webhook processing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")


@router.post("/sync/pull/{integration_id}")
async def manual_sync_from_pos(
    integration_id: int,
    sync_request: POSOrderSyncRequest,
    db: Session = Depends(get_db),
):
    """Manually trigger sync to pull orders from POS system"""
    service = POSBridgeService(db)
    result = await service.sync_orders_from_vendor(
        integration_id=integration_id, since_timestamp=sync_request.since_timestamp
    )
    return result


@router.get("/integrations/{integration_id}/orders")
async def get_pos_orders(
    integration_id: int,
    since: Optional[datetime] = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get orders from POS system without creating them in AuraConnect"""
    integration = (
        db.query(POSIntegration).filter(POSIntegration.id == integration_id).first()
    )

    if not integration:
        raise HTTPException(status_code=404, detail="Integration not found")

    adapter = AdapterFactory.create_adapter(
        POSVendor(integration.vendor), integration.credentials
    )

    try:
        orders = await adapter.get_vendor_orders(since)
        return {"success": True, "orders": orders}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch orders: {str(e)}")


def _verify_webhook_signature(payload: bytes, secret: str, signature: str) -> bool:
    """Verify webhook signature for security"""
    expected_signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(f"sha256={expected_signature}", signature)
