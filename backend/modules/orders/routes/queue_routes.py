"""
API routes for order queue management.
"""

from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from sqlalchemy.orm import Session
import json
import asyncio
from datetime import datetime

from core.database import get_db
from core.decorators import handle_api_errors
from core.auth import get_current_user
from core.rbac_models import RBACUser as User
from ..models.queue_models import QueueType, QueueStatus, QueueItemStatus
from ..schemas.queue_schemas import (
    QueueCreate,
    QueueUpdate,
    QueueResponse,
    QueueItemCreate,
    QueueItemUpdate,
    QueueItemResponse,
    MoveItemRequest,
    BulkMoveRequest,
    TransferItemRequest,
    ExpediteItemRequest,
    HoldItemRequest,
    BatchStatusUpdateRequest,
    QueueMetricsRequest,
    QueueMetricsResponse,
    QueueStatusSummary,
    SequenceRuleCreate,
    SequenceRuleUpdate,
    SequenceRuleResponse,
    DisplayConfigCreate,
    DisplayConfigResponse,
    QueueUpdateMessage,
    QueueSubscriptionRequest,
)
from ..services.queue_service import QueueService

router = APIRouter(prefix="/api/v1/orders/queues", tags=["order-queues"])


# WebSocket connections manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, queue_id: str):
        await websocket.accept()
        if queue_id not in self.active_connections:
            self.active_connections[queue_id] = []
        self.active_connections[queue_id].append(websocket)

    def disconnect(self, websocket: WebSocket, queue_id: str):
        if queue_id in self.active_connections:
            self.active_connections[queue_id].remove(websocket)
            if not self.active_connections[queue_id]:
                del self.active_connections[queue_id]

    async def send_to_queue(self, queue_id: str, message: dict):
        if queue_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[queue_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)

            # Clean up disconnected clients
            for conn in disconnected:
                self.disconnect(conn, queue_id)


manager = ConnectionManager()


# Queue Management Endpoints
@router.post("/", response_model=QueueResponse)
@handle_api_errors
async def create_queue(
    queue_data: QueueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new order queue.

    Requires admin permissions.
    """
    # TODO: Add permission check
    service = QueueService(db)
    return service.create_queue(queue_data)


@router.get("/", response_model=List[QueueResponse])
@handle_api_errors
async def list_queues(
    queue_type: Optional[QueueType] = Query(None),
    status: Optional[QueueStatus] = Query(None),
    include_metrics: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all queues with optional filters.

    Parameters:
    - queue_type: Filter by queue type
    - status: Filter by queue status
    - include_metrics: Include performance metrics
    """
    service = QueueService(db)
    return service.list_queues(queue_type, status, include_metrics)


@router.get("/{queue_id}", response_model=QueueResponse)
@handle_api_errors
async def get_queue(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get queue details by ID."""
    service = QueueService(db)
    return service.get_queue(queue_id)


@router.put("/{queue_id}", response_model=QueueResponse)
@handle_api_errors
async def update_queue(
    queue_id: int,
    update_data: QueueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update queue configuration.

    Requires admin permissions.
    """
    service = QueueService(db)
    return service.update_queue(queue_id, update_data)


@router.get("/{queue_id}/status", response_model=QueueStatusSummary)
@handle_api_errors
async def get_queue_status(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current queue status summary with metrics."""
    service = QueueService(db)
    summary = service.get_queue_status_summary(queue_id)
    return QueueStatusSummary(**summary)


# Queue Item Management
@router.post("/{queue_id}/items", response_model=QueueItemResponse)
@handle_api_errors
async def add_to_queue(
    queue_id: int,
    item_data: QueueItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Add an order to the queue.

    The order will be automatically sequenced based on queue rules.
    """
    item_data.queue_id = queue_id
    service = QueueService(db)
    item = service.add_to_queue(item_data, current_user.id)

    # Send WebSocket update
    await manager.send_to_queue(
        str(queue_id),
        {
            "event_type": "item_added",
            "queue_id": queue_id,
            "item_id": item.id,
            "data": QueueItemResponse.from_orm(item).dict(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    return item


@router.get("/{queue_id}/items", response_model=List[QueueItemResponse])
@handle_api_errors
async def get_queue_items(
    queue_id: int,
    status: Optional[List[QueueItemStatus]] = Query(None),
    include_completed: bool = Query(False),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get items in the queue.

    Items are returned in priority/sequence order.
    """
    service = QueueService(db)
    return service.get_queue_items(queue_id, status, include_completed, limit, offset)


@router.get("/items/{item_id}", response_model=QueueItemResponse)
@handle_api_errors
async def get_queue_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get queue item details."""
    service = QueueService(db)
    return service.get_queue_item(item_id)


@router.put("/items/{item_id}", response_model=QueueItemResponse)
@handle_api_errors
async def update_queue_item(
    item_id: int,
    update_data: QueueItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a queue item.

    Status transitions are validated.
    """
    service = QueueService(db)
    item = service.update_queue_item(item_id, update_data, current_user.id)

    # Send WebSocket update
    await manager.send_to_queue(
        str(item.queue_id),
        {
            "event_type": "item_updated",
            "queue_id": item.queue_id,
            "item_id": item.id,
            "data": QueueItemResponse.from_orm(item).dict(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    return item


# Queue Operations
@router.post("/items/move", response_model=QueueItemResponse)
@handle_api_errors
async def move_item(
    move_request: MoveItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Move an item to a new position in the queue.

    Other items will be automatically resequenced.
    """
    service = QueueService(db)
    item = service.move_item(move_request, current_user.id)

    # Send WebSocket update
    await manager.send_to_queue(
        str(item.queue_id),
        {
            "event_type": "item_moved",
            "queue_id": item.queue_id,
            "item_id": item.id,
            "data": {
                "new_position": move_request.new_position,
                "item": QueueItemResponse.from_orm(item).dict(),
            },
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    return item


@router.post("/items/bulk-move", response_model=List[QueueItemResponse])
@handle_api_errors
async def bulk_move_items(
    bulk_request: BulkMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Move multiple items at once.

    Useful for reordering multiple items efficiently.
    """
    service = QueueService(db)
    moved_items = []

    for move in bulk_request.moves:
        move_request = MoveItemRequest(
            item_id=move["item_id"],
            new_position=move["new_position"],
            reason=bulk_request.reason,
        )
        item = service.move_item(move_request, current_user.id)
        moved_items.append(item)

    return moved_items


@router.post("/items/transfer", response_model=QueueItemResponse)
@handle_api_errors
async def transfer_item(
    transfer_request: TransferItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Transfer an item to another queue.

    The item will be added to the end of the target queue.
    """
    service = QueueService(db)
    item = service.transfer_item(transfer_request, current_user.id)

    # Send updates to both queues
    await manager.send_to_queue(
        str(transfer_request.target_queue_id),
        {
            "event_type": "item_transferred_in",
            "queue_id": transfer_request.target_queue_id,
            "item_id": item.id,
            "data": QueueItemResponse.from_orm(item).dict(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    return item


@router.post("/items/expedite", response_model=QueueItemResponse)
@handle_api_errors
async def expedite_item(
    expedite_request: ExpediteItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Expedite an item in the queue.

    Increases priority and optionally moves to front.
    """
    service = QueueService(db)
    item = service.expedite_item(expedite_request, current_user.id)

    await manager.send_to_queue(
        str(item.queue_id),
        {
            "event_type": "item_expedited",
            "queue_id": item.queue_id,
            "item_id": item.id,
            "data": QueueItemResponse.from_orm(item).dict(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    return item


@router.post("/items/hold", response_model=QueueItemResponse)
@handle_api_errors
async def hold_item(
    hold_request: HoldItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Put an item on hold.

    Specify either hold_until datetime or hold_minutes.
    """
    service = QueueService(db)
    item = service.hold_item(hold_request, current_user.id)

    await manager.send_to_queue(
        str(item.queue_id),
        {
            "event_type": "item_held",
            "queue_id": item.queue_id,
            "item_id": item.id,
            "data": QueueItemResponse.from_orm(item).dict(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    return item


@router.post("/items/{item_id}/release", response_model=QueueItemResponse)
@handle_api_errors
async def release_hold(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Release an item from hold."""
    service = QueueService(db)
    item = service.release_hold(item_id, current_user.id)

    await manager.send_to_queue(
        str(item.queue_id),
        {
            "event_type": "item_released",
            "queue_id": item.queue_id,
            "item_id": item.id,
            "data": QueueItemResponse.from_orm(item).dict(),
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    return item


@router.post("/items/batch-status", response_model=List[QueueItemResponse])
@handle_api_errors
async def batch_update_status(
    batch_request: BatchStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update status of multiple items at once.

    Useful for marking multiple items as ready or completed.
    """
    service = QueueService(db)
    items = service.batch_update_status(batch_request, current_user.id)

    # Send updates for each queue affected
    queue_updates = {}
    for item in items:
        if item.queue_id not in queue_updates:
            queue_updates[item.queue_id] = []
        queue_updates[item.queue_id].append(item)

    for queue_id, queue_items in queue_updates.items():
        await manager.send_to_queue(
            str(queue_id),
            {
                "event_type": "batch_status_update",
                "queue_id": queue_id,
                "data": {
                    "new_status": batch_request.new_status.value,
                    "items": [
                        QueueItemResponse.from_orm(item).dict() for item in queue_items
                    ],
                },
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    return items


# Analytics Endpoints
@router.post("/metrics", response_model=QueueMetricsResponse)
@handle_api_errors
async def get_queue_metrics(
    metrics_request: QueueMetricsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get queue performance metrics for specified period.

    Supports hour, day, week, and month granularity.
    """
    service = QueueService(db)
    metrics = service.get_queue_metrics(metrics_request)

    # Format response
    queue_name = "All Queues"
    if metrics_request.queue_id:
        queue = service.get_queue(metrics_request.queue_id)
        queue_name = queue.name

    return QueueMetricsResponse(
        queue_id=metrics_request.queue_id or 0, queue_name=queue_name, **metrics
    )


# Sequence Rules
@router.post("/{queue_id}/rules", response_model=SequenceRuleResponse)
@handle_api_errors
async def create_sequence_rule(
    queue_id: int,
    rule_data: SequenceRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a sequence rule for automatic prioritization.

    Rules are evaluated when items are added to the queue.
    """
    rule_data.queue_id = queue_id
    service = QueueService(db)
    return service.create_sequence_rule(rule_data)


@router.put("/rules/{rule_id}", response_model=SequenceRuleResponse)
@handle_api_errors
async def update_sequence_rule(
    rule_id: int,
    update_data: SequenceRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a sequence rule."""
    service = QueueService(db)
    return service.update_sequence_rule(rule_id, update_data)


# WebSocket endpoint for real-time updates
@router.websocket("/ws/{queue_id}")
async def websocket_endpoint(
    websocket: WebSocket, queue_id: str, db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time queue updates.

    Connect to receive live updates for a specific queue.
    """
    await manager.connect(websocket, queue_id)
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, queue_id)


# Bulk WebSocket subscription
@router.websocket("/ws/subscribe")
async def websocket_subscribe(websocket: WebSocket, db: Session = Depends(get_db)):
    """
    WebSocket endpoint for subscribing to multiple queues.

    Send a subscription request to receive updates for specific queues.
    """
    await websocket.accept()
    subscribed_queues = []

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message.get("action") == "subscribe":
                # Subscribe to requested queues
                request = QueueSubscriptionRequest(**message.get("data", {}))
                for queue_id in request.queue_ids:
                    await manager.connect(websocket, str(queue_id))
                    subscribed_queues.append(str(queue_id))

                await websocket.send_json(
                    {"status": "subscribed", "queues": subscribed_queues}
                )

            elif message.get("action") == "unsubscribe":
                # Unsubscribe from queues
                for queue_id in subscribed_queues:
                    manager.disconnect(websocket, queue_id)
                subscribed_queues.clear()

                await websocket.send_json({"status": "unsubscribed"})

    except WebSocketDisconnect:
        # Clean up all subscriptions
        for queue_id in subscribed_queues:
            manager.disconnect(websocket, queue_id)
