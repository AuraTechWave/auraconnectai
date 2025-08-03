# backend/modules/orders/tests/test_database_retry.py

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.exc import OperationalError, DBAPIError

from ..utils.database_retry import (
    is_retryable_error, retry_on_deadlock, with_deadlock_retry,
    DatabaseRetryContext
)


@pytest.mark.unit
class TestDatabaseRetry:
    """Test database retry mechanisms"""
    
    def test_is_retryable_error_postgres_deadlock(self):
        """Test detection of PostgreSQL deadlock errors"""
        # Create mock PostgreSQL error with deadlock code
        pg_error = Mock()
        pg_error.pgcode = '40P01'  # deadlock_detected
        
        error = OperationalError("deadlock detected", None, pg_error)
        assert is_retryable_error(error) is True
    
    def test_is_retryable_error_postgres_serialization(self):
        """Test detection of PostgreSQL serialization errors"""
        pg_error = Mock()
        pg_error.pgcode = '40001'  # serialization_failure
        
        error = OperationalError("could not serialize", None, pg_error)
        assert is_retryable_error(error) is True
    
    def test_is_retryable_error_mysql_deadlock(self):
        """Test detection of MySQL deadlock errors"""
        mysql_error = Mock()
        mysql_error.args = (1213, "Deadlock found when trying to get lock")
        
        error = DBAPIError("statement", None, mysql_error)
        assert is_retryable_error(error) is True
    
    def test_is_retryable_error_sqlite_locked(self):
        """Test detection of SQLite lock errors"""
        error = OperationalError("database is locked", None, None)
        assert is_retryable_error(error) is True
    
    def test_is_not_retryable_error(self):
        """Test non-retryable errors are not marked for retry"""
        # Regular exception
        error = Exception("Some other error")
        assert is_retryable_error(error) is False
        
        # Non-deadlock database error
        error = OperationalError("connection refused", None, None)
        assert is_retryable_error(error) is False
    
    @pytest.mark.asyncio
    async def test_retry_on_deadlock_success_first_try(self):
        """Test successful execution on first try"""
        mock_func = AsyncMock(return_value="success")
        
        result = await retry_on_deadlock(mock_func, "arg1", kwarg1="value1")
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
    
    @pytest.mark.asyncio
    async def test_retry_on_deadlock_success_after_retry(self):
        """Test successful execution after retry"""
        pg_error = Mock()
        pg_error.pgcode = '40P01'
        deadlock_error = OperationalError("deadlock", None, pg_error)
        
        # Fail first, succeed second
        mock_func = AsyncMock(side_effect=[deadlock_error, "success"])
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await retry_on_deadlock(
                mock_func, 
                max_retries=2, 
                initial_delay=0.01
            )
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_on_deadlock_max_retries_exceeded(self):
        """Test failure when max retries exceeded"""
        pg_error = Mock()
        pg_error.pgcode = '40P01'
        deadlock_error = OperationalError("deadlock", None, pg_error)
        
        # Always fail
        mock_func = AsyncMock(side_effect=deadlock_error)
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            with pytest.raises(OperationalError):
                await retry_on_deadlock(
                    mock_func,
                    max_retries=2,
                    initial_delay=0.01
                )
        
        assert mock_func.call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_retry_on_deadlock_non_retryable_error(self):
        """Test non-retryable errors are raised immediately"""
        error = ValueError("Invalid value")
        mock_func = AsyncMock(side_effect=error)
        
        with pytest.raises(ValueError):
            await retry_on_deadlock(mock_func)
        
        mock_func.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_with_deadlock_retry_decorator(self):
        """Test the decorator version of retry logic"""
        call_count = 0
        
        @with_deadlock_retry(max_retries=2, initial_delay=0.01)
        async def test_func(value):
            nonlocal call_count
            call_count += 1
            
            if call_count < 2:
                pg_error = Mock()
                pg_error.pgcode = '40P01'
                raise OperationalError("deadlock", None, pg_error)
            
            return f"success_{value}"
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            result = await test_func("test")
        
        assert result == "success_test"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_exponential_backoff(self):
        """Test exponential backoff between retries"""
        pg_error = Mock()
        pg_error.pgcode = '40P01'
        deadlock_error = OperationalError("deadlock", None, pg_error)
        
        mock_func = AsyncMock(side_effect=[
            deadlock_error,
            deadlock_error,
            "success"
        ])
        
        sleep_calls = []
        
        async def mock_sleep(seconds):
            sleep_calls.append(seconds)
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            result = await retry_on_deadlock(
                mock_func,
                max_retries=3,
                initial_delay=0.1,
                backoff_factor=2.0,
                jitter=False  # Disable jitter for predictable testing
            )
        
        assert result == "success"
        assert len(sleep_calls) == 2
        # First retry: 0.1s, Second retry: 0.2s (0.1 * 2)
        assert sleep_calls[0] == pytest.approx(0.1)
        assert sleep_calls[1] == pytest.approx(0.2)
    
    @pytest.mark.asyncio
    async def test_retry_with_jitter(self):
        """Test retry with jitter adds randomness"""
        pg_error = Mock()
        pg_error.pgcode = '40P01'
        deadlock_error = OperationalError("deadlock", None, pg_error)
        
        mock_func = AsyncMock(side_effect=[deadlock_error, "success"])
        
        sleep_time = None
        
        async def mock_sleep(seconds):
            nonlocal sleep_time
            sleep_time = seconds
        
        with patch('asyncio.sleep', side_effect=mock_sleep):
            result = await retry_on_deadlock(
                mock_func,
                initial_delay=0.1,
                jitter=True
            )
        
        assert result == "success"
        # With jitter, sleep time should be between 0.1 and 0.125 (25% jitter)
        assert 0.1 <= sleep_time <= 0.125
    
    @pytest.mark.asyncio
    async def test_database_retry_context(self):
        """Test DatabaseRetryContext for manual retry handling"""
        mock_session = Mock()
        
        async with DatabaseRetryContext(mock_session) as ctx:
            ctx.log_action("test_action", "test_resource", 123)
        
        # Should complete without error
        assert ctx._start_time is not None
    
    @pytest.mark.asyncio
    async def test_database_retry_context_with_error(self):
        """Test DatabaseRetryContext error handling"""
        mock_session = Mock()
        
        with pytest.raises(ValueError):
            async with DatabaseRetryContext(mock_session) as ctx:
                raise ValueError("Test error")
        
        # Verify rollback was called
        mock_session.rollback.assert_called()


@pytest.mark.integration
class TestDatabaseRetryIntegration:
    """Integration tests for database retry with real database operations"""
    
    @pytest.mark.asyncio
    async def test_concurrent_inventory_update_with_retry(self, db):
        """Test concurrent inventory updates with retry logic"""
        from core.inventory_models import Inventory
        from tests.factories import InventoryFactory
        
        # Create test inventory
        inventory = InventoryFactory(quantity=100.0)
        inventory_id = inventory.id
        db.commit()
        
        # Simulate concurrent updates
        @with_deadlock_retry(max_retries=3)
        async def update_inventory(amount: float):
            # Get fresh session for each attempt
            item = db.query(Inventory).filter(
                Inventory.id == inventory_id
            ).with_for_update().first()
            
            # Simulate some processing time
            await asyncio.sleep(0.01)
            
            item.quantity -= amount
            db.commit()
            return item.quantity
        
        # Run concurrent updates
        tasks = [
            update_inventory(10.0),
            update_inventory(15.0),
            update_inventory(5.0)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should succeed
        assert all(not isinstance(r, Exception) for r in results)
        
        # Final quantity should be 100 - 10 - 15 - 5 = 70
        db.refresh(inventory)
        assert inventory.quantity == 70.0