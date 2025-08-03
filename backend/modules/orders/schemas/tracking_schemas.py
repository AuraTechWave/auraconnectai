# backend/modules/orders/schemas/tracking_schemas.py

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class CustomerTrackingCreate(BaseModel):
    """Schema for creating customer tracking"""
    notification_email: Optional[EmailStr] = None
    notification_phone: Optional[str] = None
    enable_notifications: bool = True
    

class NotificationPreferencesUpdate(BaseModel):
    """Schema for updating notification preferences"""
    access_token: Optional[str] = Field(None, description="Required if not authenticated")
    enable_push: Optional[bool] = None
    enable_email: Optional[bool] = None
    enable_sms: Optional[bool] = None
    notification_email: Optional[EmailStr] = None
    notification_phone: Optional[str] = None
    push_token: Optional[str] = None


class LocationData(BaseModel):
    """Location information for tracking"""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None


class TrackingEventResponse(BaseModel):
    """Response schema for tracking events"""
    event_id: int
    event_type: str
    description: Optional[str] = None
    created_at: datetime
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    estimated_completion_time: Optional[datetime] = None
    location: Optional[LocationData] = None
    triggered_by: Optional[Dict[str, str]] = None
    
    class Config:
        from_attributes = True


class OrderTrackingResponse(BaseModel):
    """Response schema for order tracking info"""
    order_id: int
    tracking_code: str
    current_status: str
    created_at: datetime
    estimated_completion_time: Optional[datetime] = None
    events: List[TrackingEventResponse]
    
    class Config:
        from_attributes = True


class ActiveOrdersResponse(BaseModel):
    """Response schema for active orders list"""
    order_id: int
    status: str
    created_at: datetime
    tracking_code: Optional[str] = None
    estimated_completion_time: Optional[datetime] = None
    latest_event: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


class WebSocketMessage(BaseModel):
    """Base schema for WebSocket messages"""
    type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class OrderUpdateMessage(WebSocketMessage):
    """WebSocket message for order updates"""
    type: str = "order_update"
    order_id: int
    event: Dict[str, Any]


class LocationUpdateMessage(WebSocketMessage):
    """WebSocket message for location updates"""
    type: str = "location_update"
    latitude: float
    longitude: float
    accuracy: Optional[float] = None


class ConnectionMessage(WebSocketMessage):
    """WebSocket connection status message"""
    type: str = "connection_established"
    order_id: int
    session_id: str


class ErrorMessage(WebSocketMessage):
    """WebSocket error message"""
    type: str = "error"
    message: str
    code: Optional[int] = None