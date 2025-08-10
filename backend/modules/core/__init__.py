# backend/modules/core/__init__.py
"""Core module containing fundamental models for the restaurant management system."""

from .models import Restaurant, Location, Floor, RestaurantStatus, FloorStatus
from .schemas import (
    RestaurantCreate, RestaurantUpdate, RestaurantResponse,
    LocationCreate, LocationUpdate, LocationResponse,
    FloorCreate, FloorUpdate, FloorResponse
)

__all__ = [
    # Models
    "Restaurant",
    "Location", 
    "Floor",
    "RestaurantStatus",
    "FloorStatus",
    # Schemas
    "RestaurantCreate",
    "RestaurantUpdate",
    "RestaurantResponse",
    "LocationCreate",
    "LocationUpdate",
    "LocationResponse",
    "FloorCreate",
    "FloorUpdate",
    "FloorResponse"
]