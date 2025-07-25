from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from ..schemas.pos_schemas import SyncResponse


class BasePOSAdapter(ABC):
    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials

    @abstractmethod
    async def push_order(self, order_data: Dict[str, Any]) -> SyncResponse:
        """Push order data to POS system"""
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if credentials are valid and connection works"""
        pass

    @abstractmethod
    def transform_order_data(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Transform internal order format to POS-specific format"""
        pass

    @abstractmethod
    async def get_vendor_orders(self, since_timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """Pull orders from POS system, optionally filtered by timestamp"""
        pass
