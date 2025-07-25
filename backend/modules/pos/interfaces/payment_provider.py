from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime


class POSPaymentProvider(ABC):
    """Abstract base class for POS payment integrations."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    @abstractmethod
    async def get_payments(
        self,
        order_ids: List[int] = None,
        date_range: Tuple[datetime, datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch payment records from POS system.

        Args:
            order_ids: Optional list of order IDs to filter by
            date_range: Optional tuple of (start_date, end_date) to filter by

        Returns:
            List of payment dictionaries with keys:
            - reference: Payment reference ID
            - order_reference: Associated order reference
            - amount: Payment amount
            - timestamp: Payment timestamp
            - payment_method: Payment method used
            - status: Payment status
        """
        pass

    @abstractmethod
    async def get_payment_by_reference(self, reference: str
                                       ) -> Optional[Dict[str, Any]]:
        """Get specific payment by reference ID."""
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate connection to POS system."""
        pass

    @abstractmethod
    async def get_payment_methods(self) -> List[str]:
        """Get list of supported payment methods."""
        pass


class SquarePOSProvider(POSPaymentProvider):
    """Square POS integration implementation."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get('api_key')
        self.environment = config.get('environment', 'sandbox')
        self.location_id = config.get('location_id')

    async def get_payments(
        self,
        order_ids: List[int] = None,
        date_range: Tuple[datetime, datetime] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve payments from Square API."""
        return []

    async def get_payment_by_reference(self, reference: str
                                       ) -> Optional[Dict[str, Any]]:
        """Get specific payment from Square by reference."""
        return None

    async def validate_connection(self) -> bool:
        """Validate Square API connection."""
        return True

    async def get_payment_methods(self) -> List[str]:
        """Get Square supported payment methods."""
        return ['CARD', 'CASH', 'SQUARE_GIFT_CARD', 'BANK_ACCOUNT']


class MockPOSProvider(POSPaymentProvider):
    """Mock implementation for testing and development."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)

    async def get_payments(
        self,
        order_ids: List[int] = None,
        date_range: Tuple[datetime, datetime] = None
    ) -> List[Dict[str, Any]]:
        """Return mock payment data for testing."""
        mock_payments = []
        if order_ids:
            for order_id in order_ids:
                mock_payments.append({
                    'reference': f'PAY_{order_id}_001',
                    'order_reference': str(order_id),
                    'amount': 25.99,
                    'timestamp': datetime.now(),
                    'payment_method': 'credit_card',
                    'status': 'completed'
                })
        return mock_payments

    async def get_payment_by_reference(self, reference: str
                                       ) -> Optional[Dict[str, Any]]:
        """Return mock payment data by reference."""
        return {
            'reference': reference,
            'order_reference': '123',
            'amount': 25.99,
            'timestamp': datetime.now(),
            'payment_method': 'credit_card',
            'status': 'completed'
        }

    async def validate_connection(self) -> bool:
        """Mock connection validation."""
        return True

    async def get_payment_methods(self) -> List[str]:
        """Get mock payment methods."""
        return ['credit_card', 'debit_card', 'cash', 'gift_card']
