# backend/modules/analytics/services/pos/base_service.py

"""
Base service class for POS analytics.

Provides common functionality and utilities.
"""

from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from functools import lru_cache

from modules.orders.models.external_pos_models import ExternalPOSProvider
from modules.analytics.models.pos_analytics_models import (
    POSAnalyticsSnapshot, POSTerminalHealth
)

logger = logging.getLogger(__name__)


class POSAnalyticsBaseService:
    """Base service for POS analytics operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def validate_provider_exists(self, provider_id: int) -> bool:
        """Check if provider exists"""
        return self.db.query(ExternalPOSProvider).filter(
            ExternalPOSProvider.id == provider_id
        ).count() > 0
    
    def validate_terminal_exists(self, terminal_id: str) -> bool:
        """Check if terminal exists"""
        return self.db.query(POSTerminalHealth).filter(
            POSTerminalHealth.terminal_id == terminal_id
        ).count() > 0
    
    def get_provider_or_404(self, provider_id: int) -> ExternalPOSProvider:
        """Get provider or raise KeyError"""
        provider = self.db.query(ExternalPOSProvider).filter(
            ExternalPOSProvider.id == provider_id
        ).first()
        
        if not provider:
            raise KeyError(f"POS provider {provider_id} not found")
        
        return provider
    
    def get_terminal_or_404(self, terminal_id: str) -> POSTerminalHealth:
        """Get terminal or raise KeyError"""
        terminal = self.db.query(POSTerminalHealth).filter(
            POSTerminalHealth.terminal_id == terminal_id
        ).first()
        
        if not terminal:
            raise KeyError(f"POS terminal {terminal_id} not found")
        
        return terminal
    
    @lru_cache(maxsize=128)
    def get_cache_key(
        self,
        operation: str,
        start_date: datetime,
        end_date: datetime,
        provider_ids: Optional[tuple] = None,
        terminal_ids: Optional[tuple] = None
    ) -> str:
        """Generate cache key for operations"""
        parts = [
            operation,
            start_date.isoformat(),
            end_date.isoformat()
        ]
        
        if provider_ids:
            parts.append(f"providers:{','.join(map(str, provider_ids))}")
        
        if terminal_ids:
            parts.append(f"terminals:{','.join(terminal_ids)}")
        
        return ":".join(parts)
    
    def calculate_percentage_change(
        self,
        current: float,
        previous: float
    ) -> Optional[float]:
        """Calculate percentage change between two values"""
        if previous == 0:
            return None if current == 0 else 100.0
        
        return ((current - previous) / previous) * 100
    
    def format_duration(self, minutes: int) -> str:
        """Format duration in minutes to human-readable string"""
        if minutes < 60:
            return f"{minutes} minutes"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        
        if hours < 24:
            if remaining_minutes > 0:
                return f"{hours}h {remaining_minutes}m"
            return f"{hours} hours"
        
        days = hours // 24
        remaining_hours = hours % 24
        
        if remaining_hours > 0:
            return f"{days}d {remaining_hours}h"
        return f"{days} days"