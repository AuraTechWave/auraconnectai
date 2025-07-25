from abc import ABC, abstractmethod
from typing import Dict, Any, List
from datetime import datetime


class POSPaymentProvider(ABC):
    """Abstract base class for POS payment providers."""
    
    def __init__(self, credentials: Dict[str, Any]):
        self.credentials = credentials
    
    @abstractmethod
    async def get_payments(self, order_ids: List[int] = None,
                          from_date: datetime = None,
                          to_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Retrieve payments from POS system.
        
        Args:
            order_ids: Optional list of order IDs to filter by
            from_date: Optional start date filter
            to_date: Optional end date filter
            
        Returns:
            List of payment dictionaries with keys:
            - reference: External payment reference
            - order_reference: Associated order reference
            - amount: Payment amount
            - timestamp: Payment timestamp
            - payment_method: Payment method used
            - status: Payment status
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if credentials are valid and connection works."""
        pass
    
    @abstractmethod
    async def get_payment_by_reference(self, reference: str) -> Dict[str, Any]:
        """Get specific payment by reference."""
        pass


class SquarePOSProvider(POSPaymentProvider):
    """Square POS payment provider implementation."""
    
    async def get_payments(self, order_ids: List[int] = None,
                          from_date: datetime = None,
                          to_date: datetime = None) -> List[Dict[str, Any]]:
        mock_payments = []
        if order_ids:
            for order_id in order_ids[:len(order_ids)//2]:
                timestamp = datetime.utcnow().timestamp()
                mock_payments.append({
                    'reference': f"SQ_{order_id}_{timestamp}",
                    'order_reference': str(order_id),
                    'amount': 25.00,
                    'timestamp': datetime.utcnow(),
                    'payment_method': 'credit_card',
                    'status': 'completed'
                })
        return mock_payments
    
    async def test_connection(self) -> bool:
        return True
    
    async def get_payment_by_reference(self, reference: str) -> Dict[str, Any]:
        return {}


class MockPOSProvider(POSPaymentProvider):
    """Mock POS provider for testing and development."""
    
    async def get_payments(self, order_ids: List[int] = None,
                          from_date: datetime = None,
                          to_date: datetime = None) -> List[Dict[str, Any]]:
        mock_payments = []
        if order_ids:
            for order_id in order_ids[:len(order_ids)//2]:
                timestamp = datetime.utcnow().timestamp()
                mock_payments.append({
                    'reference': f"MOCK_{order_id}_{timestamp}",
                    'order_reference': str(order_id),
                    'amount': 30.00,
                    'timestamp': datetime.utcnow(),
                    'payment_method': 'cash',
                    'status': 'completed'
                })
        return mock_payments
    
    async def test_connection(self) -> bool:
        return True
    
    async def get_payment_by_reference(self, reference: str) -> Dict[str, Any]:
        return {
            'reference': reference,
            'order_reference': '1',
            'amount': 25.00,
            'timestamp': datetime.utcnow(),
            'payment_method': 'cash',
            'status': 'completed'
        }
