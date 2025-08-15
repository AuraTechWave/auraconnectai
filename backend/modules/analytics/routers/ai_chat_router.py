# backend/modules/analytics/routers/ai_chat_router.py

"""
AI Chat Router for Analytics Assistant.

This router handles WebSocket connections for real-time chat interactions
and REST endpoints for chat management.
"""

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    HTTPException,
    Query,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import json
import logging
import asyncio
import uuid
from datetime import datetime

from core.database import get_db
from core.auth import get_current_user, User, verify_token

# Custom exceptions replaced with standard Python exceptions

from ..services.permissions_service import (
    AnalyticsPermission,
    require_analytics_permission,
)
from ..services.ai_chat_service import AIChatService
from ..schemas.ai_assistant_schemas import (
    ChatRequest,
    ChatResponse,
    ChatMessage,
    WebSocketMessage,
    SuggestedQuery,
    AssistantCapabilities,
    FeedbackRequest,
    ConversationSummary,
    MessageRole,
    MessageType,
)

router = APIRouter(prefix="/analytics/ai-assistant", tags=["AI Analytics Assistant"])
logger = logging.getLogger(__name__)

# Global chat service instance
chat_service = AIChatService()


# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, client_id: str, user_info: dict):
        await websocket.accept()
        self.active_connections[client_id] = {
            "websocket": websocket,
            "user_id": user_info["id"],
            "connected_at": datetime.now(),
            "message_count": 0,
        }
        logger.info(f"Client {client_id} connected")

    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected")

    async def send_message(self, client_id: str, message: WebSocketMessage):
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]["websocket"]
            try:
                await websocket.send_text(message.json())
                self.active_connections[client_id]["message_count"] += 1
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                self.disconnect(client_id)

    async def broadcast_to_user(self, user_id: int, message: WebSocketMessage):
        """Send message to all connections for a specific user"""
        for client_id, conn_info in self.active_connections.items():
            if conn_info["user_id"] == user_id:
                await self.send_message(client_id, message)


manager = ConnectionManager()


@router.websocket("/chat")
async def chat_websocket_endpoint(
    websocket: WebSocket, token: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time AI chat interactions.

    Handles bidirectional communication for analytics queries.
    """
    client_id = str(uuid.uuid4())
    user_info = None

    try:
        # Authenticate via token
        if not token:
            await websocket.close(code=4001, reason="Authentication required")
            return

        try:
            # Decode token to get user info
            user_info = verify_token(token)
        except Exception as e:
            await websocket.close(code=4001, reason="Invalid token")
            return

        # Check permissions
        if not any(
            perm in user_info.get("permissions", [])
            for perm in [
                AnalyticsPermission.VIEW_DASHBOARD,
                AnalyticsPermission.VIEW_SALES_REPORTS,
            ]
        ):
            await websocket.close(code=4003, reason="Insufficient permissions")
            return

        # Connect client
        await manager.connect(websocket, client_id, user_info)

        # Send welcome message
        welcome_msg = WebSocketMessage(
            type="connected",
            data={
                "message": "Connected to AI Analytics Assistant",
                "session_id": client_id,
                "capabilities": _get_assistant_capabilities(),
            },
        )
        await manager.send_message(client_id, welcome_msg)

        # Get database session
        db = next(get_db())

        try:
            # Main message loop
            while True:
                # Receive message
                data = await websocket.receive_text()

                try:
                    message_data = json.loads(data)

                    # Send typing indicator
                    typing_msg = WebSocketMessage(
                        type="typing", data={"is_typing": True}
                    )
                    await manager.send_message(client_id, typing_msg)

                    # Process different message types
                    if message_data.get("type") == "chat":
                        # Process chat message
                        request = ChatRequest(
                            message=message_data.get("message", ""),
                            session_id=client_id,
                            context=message_data.get("context"),
                        )

                        # Get AI response
                        response = await chat_service.process_message(
                            request, user_info["id"], db
                        )

                        # Send response
                        response_msg = WebSocketMessage(
                            type="chat",
                            data={
                                "message": response.message.dict(),
                                "query_result": (
                                    response.query_result.dict()
                                    if response.query_result
                                    else None
                                ),
                                "suggested_questions": response.suggested_questions,
                                "requires_clarification": response.requires_clarification,
                                "clarification_options": response.clarification_options,
                            },
                        )
                        await manager.send_message(client_id, response_msg)

                    elif message_data.get("type") == "get_history":
                        # Get conversation history
                        history = chat_service.get_session_history(client_id)
                        history_msg = WebSocketMessage(
                            type="history",
                            data={
                                "messages": (
                                    [msg.dict() for msg in history] if history else []
                                )
                            },
                        )
                        await manager.send_message(client_id, history_msg)

                    elif message_data.get("type") == "clear_session":
                        # Clear chat session
                        chat_service.clear_session(client_id)
                        clear_msg = WebSocketMessage(
                            type="session_cleared",
                            data={"message": "Conversation history cleared"},
                        )
                        await manager.send_message(client_id, clear_msg)

                    elif message_data.get("type") == "get_suggestions":
                        # Get suggested queries
                        suggestions = await chat_service.get_suggested_queries(
                            user_info["id"], db
                        )
                        suggestions_msg = WebSocketMessage(
                            type="suggestions",
                            data={"suggestions": [s.dict() for s in suggestions]},
                        )
                        await manager.send_message(client_id, suggestions_msg)

                    # Clear typing indicator
                    typing_msg = WebSocketMessage(
                        type="typing", data={"is_typing": False}
                    )
                    await manager.send_message(client_id, typing_msg)

                except json.JSONDecodeError:
                    error_msg = WebSocketMessage(
                        type="error", data={"message": "Invalid message format"}
                    )
                    await manager.send_message(client_id, error_msg)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    error_msg = WebSocketMessage(
                        type="error", data={"message": "Error processing your request"}
                    )
                    await manager.send_message(client_id, error_msg)

        finally:
            db.close()

    except WebSocketDisconnect:
        manager.disconnect(client_id)
        if client_id:
            chat_service.clear_session(client_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(client_id)


@router.post("/batch", response_model=List[ChatResponse])
async def send_batch_messages(
    requests: List[ChatRequest],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Process multiple chat messages in batch.

    Useful for:
    - Processing multiple queries at once
    - Analyzing different aspects of data simultaneously
    - Improving performance for bulk operations

    Note: Messages are grouped by session to maintain context.
    """
    try:
        # Validate batch size
        if len(requests) > 10:
            raise HTTPException(status_code=400, detail="Maximum 10 messages per batch")

        responses = await chat_service.process_batch_messages(
            requests, user_id=current_user.id, db=db
        )
        return responses
    except Exception as e:
        logger.error(f"Batch processing error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process batch messages")


@router.post("/chat", response_model=ChatResponse)
async def chat_rest_endpoint(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)
    ),
):
    """
    REST endpoint for AI chat (fallback for non-WebSocket clients).

    Process a single chat message and return AI response.
    """
    try:
        response = await chat_service.process_message(request, current_user["id"], db)
        return response

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message",
        )


@router.get("/suggestions", response_model=List[SuggestedQuery])
async def get_suggested_queries(
    db: Session = Depends(get_db),
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)
    ),
):
    """
    Get suggested analytics queries for quick access.

    Returns contextual suggestions based on current data and user activity.
    """
    try:
        suggestions = await chat_service.get_suggested_queries(current_user["id"], db)
        return suggestions

    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get suggestions",
        )


@router.get("/capabilities", response_model=AssistantCapabilities)
async def get_assistant_capabilities(current_user: User = Depends(get_current_user)):
    """
    Get AI assistant capabilities and limitations.

    Returns information about what the assistant can do.
    """
    return _get_assistant_capabilities()


@router.get("/history/{session_id}", response_model=List[ChatMessage])
async def get_conversation_history(
    session_id: str,
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)
    ),
):
    """
    Get conversation history for a specific session.

    Returns all messages in the conversation.
    """
    history = chat_service.get_session_history(session_id)
    if not history:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return history


@router.delete("/session/{session_id}")
async def clear_session(
    session_id: str,
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.VIEW_DASHBOARD)
    ),
):
    """
    Clear a chat session and its history.

    Removes all conversation data for the session.
    """
    success = chat_service.clear_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )
    return {"message": "Session cleared successfully"}


@router.post("/feedback")
async def submit_feedback(
    feedback: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit feedback on AI assistant response.

    Helps improve the assistant's responses over time.
    """
    try:
        # Store feedback (would be implemented with a feedback table)
        logger.info(f"Feedback received: {feedback.dict()}")

        return {
            "message": "Thank you for your feedback!",
            "feedback_id": str(uuid.uuid4()),
        }

    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback",
        )


@router.get("/stats")
async def get_chat_statistics(
    current_user: dict = Depends(
        require_analytics_permission(AnalyticsPermission.ADMIN_ANALYTICS)
    ),
):
    """
    Get AI assistant usage statistics (admin only).

    Returns metrics about chat usage and performance.
    """
    try:
        # Calculate statistics
        total_sessions = len(chat_service.sessions)
        active_sessions = sum(1 for s in chat_service.sessions.values() if s.is_active)
        total_messages = sum(s.message_count for s in chat_service.sessions.values())

        # Get WebSocket statistics
        ws_connections = len(manager.active_connections)

        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "total_messages": total_messages,
            "websocket_connections": ws_connections,
            "average_messages_per_session": (
                total_messages / total_sessions if total_sessions > 0 else 0
            ),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting chat statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get statistics",
        )


def _get_assistant_capabilities() -> dict:
    """Get assistant capabilities configuration"""
    return {
        "supported_queries": [
            "Sales reports and summaries",
            "Revenue analysis and trends",
            "Staff performance metrics",
            "Product performance analysis",
            "Time-based comparisons",
            "Business insights and recommendations",
        ],
        "supported_metrics": [
            "revenue",
            "orders",
            "customers",
            "average_order_value",
            "growth",
            "efficiency",
            "popularity",
        ],
        "supported_time_ranges": [
            "today",
            "yesterday",
            "this week",
            "last week",
            "this month",
            "last month",
            "custom date ranges",
        ],
        "supported_visualizations": ["line", "bar", "pie", "area", "table"],
        "max_results_per_query": 1000,
        "rate_limits": {"messages_per_minute": 20, "queries_per_hour": 100},
        "available_data_sources": ["sales", "orders", "products", "staff", "customers"],
    }


# Health check endpoint
@router.get("/health")
async def health_check():
    """Health check for AI assistant service"""
    return {
        "status": "healthy",
        "service": "ai_assistant",
        "active_sessions": len(chat_service.sessions),
        "websocket_connections": len(manager.active_connections),
        "timestamp": datetime.now().isoformat(),
    }
