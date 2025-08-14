"""backend/workers/tests/test_worker_database_sessions.py

Unit tests to verify proper database session management in background workers.
Tests ensure no connection leaks and proper cleanup on errors.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from workers.notification_worker import NotificationWorker
from workers.data_retention_worker import DataRetentionWorker


class TestNotificationWorkerSessions:
    """Test database session management in notification worker"""
    
    @pytest.mark.asyncio
    async def test_process_retry_queue_session_cleanup(self):
        """Test that database session is properly closed after processing retries"""
        
        mock_session = Mock()
        mock_session.close = Mock()
        
        with patch('workers.notification_worker.SessionLocal', return_value=mock_session):
            with patch('workers.notification_worker.NotificationRetryService') as MockService:
                # Setup mock service
                mock_service_instance = MockService.return_value
                mock_service_instance.get_retry_stats.return_value = {
                    "pending": 5,
                    "failed": 2
                }
                mock_service_instance.process_retry_queue = Mock()
                
                # Execute the worker task
                ctx = {}
                result = await NotificationWorker.process_retry_queue(ctx)
                
                # Verify session was closed
                mock_session.close.assert_called_once()
                
                # Verify result structure
                assert "task" in result
                assert result["task"] == "process_retry_queue"
                assert "processed" in result
                assert "errors" in result
                assert "duration_ms" in result
    
    @pytest.mark.asyncio
    async def test_process_retry_queue_session_cleanup_on_error(self):
        """Test that database session is closed even when an error occurs"""
        
        mock_session = Mock()
        mock_session.close = Mock()
        
        with patch('workers.notification_worker.SessionLocal', return_value=mock_session):
            with patch('workers.notification_worker.NotificationRetryService') as MockService:
                # Make the service raise an error
                MockService.side_effect = Exception("Test error")
                
                # Execute the worker task
                ctx = {}
                result = await NotificationWorker.process_retry_queue(ctx)
                
                # Verify session was still closed despite the error
                mock_session.close.assert_called_once()
                
                # Verify error was handled
                assert result["errors"] == 1
    
    @pytest.mark.asyncio
    async def test_check_notification_health_session_cleanup(self):
        """Test that database session is properly closed after health check"""
        
        mock_session = Mock()
        mock_session.close = Mock()
        mock_session.query.return_value.filter.return_value.all.return_value = []
        
        with patch('workers.notification_worker.SessionLocal', return_value=mock_session):
            with patch('workers.notification_worker.NotificationHealthChecker'):
                # Execute the worker task
                ctx = {}
                result = await NotificationWorker.check_notification_health(ctx)
                
                # Verify session was closed
                mock_session.close.assert_called_once()
                
                # Verify result structure
                assert "task" in result
                assert result["task"] == "check_notification_health"
                assert "channels_checked" in result
                assert "healthy_channels" in result
    
    @pytest.mark.asyncio
    async def test_cleanup_old_notifications_session_cleanup(self):
        """Test that database session is properly closed after cleanup"""
        
        mock_session = Mock()
        mock_session.close = Mock()
        mock_session.commit = Mock()
        mock_session.query.return_value.filter.return_value.delete.return_value = 10
        
        with patch('workers.notification_worker.SessionLocal', return_value=mock_session):
            with patch('workers.notification_worker.NotificationRetryService') as MockService:
                mock_service_instance = MockService.return_value
                mock_service_instance.cleanup_old_retries = Mock()
                
                # Execute the worker task
                ctx = {}
                result = await NotificationWorker.cleanup_old_notifications(ctx)
                
                # Verify session was closed
                mock_session.close.assert_called_once()
                
                # Verify commit was called
                mock_session.commit.assert_called_once()
                
                # Verify result structure
                assert "task" in result
                assert result["task"] == "cleanup_old_notifications"
    
    @pytest.mark.asyncio
    async def test_collect_notification_stats_session_cleanup(self):
        """Test that database session is properly closed after collecting stats"""
        
        mock_session = Mock()
        mock_session.close = Mock()
        mock_session.commit = Mock()
        mock_session.add = Mock()
        
        # Setup query mock
        mock_query_result = []
        mock_session.query.return_value.filter.return_value.group_by.return_value.all.return_value = mock_query_result
        
        with patch('workers.notification_worker.SessionLocal', return_value=mock_session):
            # Execute the worker task
            ctx = {}
            result = await NotificationWorker.collect_notification_stats(ctx)
            
            # Verify session was closed
            mock_session.close.assert_called_once()
            
            # Verify result structure
            assert "task" in result
            assert result["task"] == "collect_notification_stats"
            assert "duration_ms" in result


class TestDataRetentionWorkerSessions:
    """Test database session management in data retention worker"""
    
    @pytest.mark.asyncio
    async def test_cleanup_biometric_data_session_cleanup(self):
        """Test that database session is properly closed after biometric cleanup"""
        
        mock_session = Mock()
        mock_session.close = Mock()
        
        with patch('workers.data_retention_worker.SessionLocal', return_value=mock_session):
            with patch('workers.data_retention_worker.BiometricService') as MockService:
                # Setup mock service
                mock_service_instance = MockService.return_value
                mock_service_instance.cleanup_expired_data.return_value = (5, 10)
                
                # Execute the worker task
                ctx = {}
                result = await DataRetentionWorker.cleanup_biometric_data(ctx)
                
                # Verify session was closed
                mock_session.close.assert_called_once()
                
                # Verify result structure
                assert "task" in result
                assert result["task"] == "cleanup_biometric_data"
                assert result["biometrics_deleted"] == 5
                assert result["audit_deleted"] == 10
    
    @pytest.mark.asyncio
    async def test_cleanup_biometric_data_session_cleanup_on_error(self):
        """Test that database session is closed even when an error occurs"""
        
        mock_session = Mock()
        mock_session.close = Mock()
        
        with patch('workers.data_retention_worker.SessionLocal', return_value=mock_session):
            with patch('workers.data_retention_worker.BiometricService') as MockService:
                # Make the service raise an error
                MockService.side_effect = Exception("Test error")
                
                # Execute the worker task
                ctx = {}
                
                # The worker should handle the exception internally
                # and still close the session
                try:
                    result = await DataRetentionWorker.cleanup_biometric_data(ctx)
                except:
                    pass  # Worker might re-raise the exception
                
                # Verify session was still closed despite the error
                mock_session.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_no_db_needed(self):
        """Test that cleanup_expired_sessions doesn't need a database session"""
        
        with patch('workers.data_retention_worker.SessionManager') as MockManager:
            mock_manager_instance = MockManager.return_value
            mock_manager_instance.cleanup_expired_sessions.return_value = 15
            
            # Execute the worker task
            ctx = {}
            result = await DataRetentionWorker.cleanup_expired_sessions(ctx)
            
            # Verify result structure
            assert "task" in result
            assert result["task"] == "cleanup_expired_sessions"
            assert result["cleaned"] == 15


class TestRedisConfiguration:
    """Test Redis configuration uses centralized config"""
    
    def test_notification_worker_redis_config(self):
        """Test that notification worker uses centralized Redis config"""
        
        with patch('workers.notification_worker.config') as mock_config:
            mock_config.REDIS_URL = "redis://prod-redis:6379/0"
            mock_config.ENVIRONMENT = "production"
            
            # Import the function to test
            from workers.notification_worker import get_redis_dsn
            
            # Verify it returns the configured URL
            assert get_redis_dsn() == "redis://prod-redis:6379/0"
    
    def test_notification_worker_redis_fallback_dev(self):
        """Test Redis fallback in development environment"""
        
        with patch('workers.notification_worker.config') as mock_config:
            mock_config.REDIS_URL = None
            mock_config.ENVIRONMENT = "development"
            
            # Import the function to test
            from workers.notification_worker import get_redis_dsn
            
            # Verify it returns the fallback URL
            assert get_redis_dsn() == "redis://localhost:6379"
    
    def test_notification_worker_redis_error_prod(self):
        """Test that missing Redis URL raises error in production"""
        
        with patch('workers.notification_worker.config') as mock_config:
            mock_config.REDIS_URL = None
            mock_config.ENVIRONMENT = "production"
            
            # Import the function to test
            from workers.notification_worker import get_redis_dsn
            
            # Verify it raises an error
            with pytest.raises(ValueError, match="REDIS_URL is required"):
                get_redis_dsn()
    
    def test_data_retention_worker_redis_config(self):
        """Test that data retention worker uses centralized Redis config"""
        
        with patch('workers.data_retention_worker.config') as mock_config:
            mock_config.REDIS_URL = "redis://prod-redis:6379/0"
            mock_config.ENVIRONMENT = "production"
            
            # Import the function to test
            from workers.data_retention_worker import get_redis_dsn
            
            # Verify it returns the configured URL
            assert get_redis_dsn() == "redis://prod-redis:6379/0"


class TestSessionLeakDetection:
    """Test that we can detect session leaks"""
    
    @pytest.mark.asyncio
    async def test_no_session_leak_in_notification_worker(self):
        """Verify no database connections are leaked in notification worker"""
        
        # Track all session instances
        created_sessions = []
        closed_sessions = []
        
        def mock_session_factory():
            session = Mock()
            created_sessions.append(session)
            
            def close_tracker():
                closed_sessions.append(session)
            
            session.close = close_tracker
            session.query.return_value.filter.return_value.all.return_value = []
            session.query.return_value.filter.return_value.delete.return_value = 0
            session.commit = Mock()
            
            return session
        
        with patch('workers.notification_worker.SessionLocal', side_effect=mock_session_factory):
            # Run all worker tasks
            ctx = {}
            
            # Process retry queue
            with patch('workers.notification_worker.NotificationRetryService'):
                await NotificationWorker.process_retry_queue(ctx)
            
            # Check health
            with patch('workers.notification_worker.NotificationHealthChecker'):
                await NotificationWorker.check_notification_health(ctx)
            
            # Cleanup old notifications
            with patch('workers.notification_worker.NotificationRetryService'):
                await NotificationWorker.cleanup_old_notifications(ctx)
            
            # Collect stats
            await NotificationWorker.collect_notification_stats(ctx)
        
        # Verify all created sessions were closed
        assert len(created_sessions) == 4, "Expected 4 sessions to be created"
        assert len(closed_sessions) == 4, "Expected all 4 sessions to be closed"
        assert set(created_sessions) == set(closed_sessions), "All created sessions should be closed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])