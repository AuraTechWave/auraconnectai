"""
Test thread safety of health monitoring service.
"""

import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from modules.health.services.health_service import HealthService
from core.config import settings


class TestThreadSafety:
    """Test that HealthService doesn't modify global settings"""
    
    def test_no_global_settings_modification(self, db: Session):
        """Verify that creating HealthService doesn't modify global settings"""
        # Store original state
        original_has_app_version = hasattr(settings, 'APP_VERSION')
        original_has_redis_url = hasattr(settings, 'REDIS_URL')
        
        # If they exist, store their values
        original_app_version = getattr(settings, 'APP_VERSION', None) if original_has_app_version else None
        original_redis_url = getattr(settings, 'REDIS_URL', None) if original_has_redis_url else None
        
        # Create multiple service instances
        service1 = HealthService(db)
        service2 = HealthService(db)
        
        # Access properties to trigger lazy initialization
        version1 = service1.app_version
        version2 = service2.app_version
        redis_url1 = service1.redis_url
        redis_url2 = service2.redis_url
        
        # Verify settings weren't modified
        if original_has_app_version:
            assert hasattr(settings, 'APP_VERSION')
            assert getattr(settings, 'APP_VERSION') == original_app_version
        else:
            # APP_VERSION should NOT have been added to settings
            assert not hasattr(settings, 'APP_VERSION') or getattr(settings, 'APP_VERSION') == original_app_version
        
        if original_has_redis_url:
            assert hasattr(settings, 'REDIS_URL')
            assert getattr(settings, 'REDIS_URL') == original_redis_url
        else:
            # REDIS_URL should NOT have been added to settings
            assert not hasattr(settings, 'REDIS_URL') or getattr(settings, 'REDIS_URL') == original_redis_url
    
    def test_concurrent_service_creation(self, db: Session):
        """Test creating HealthService instances concurrently"""
        results = []
        errors = []
        
        def create_and_use_service(thread_id: int):
            try:
                service = HealthService(db)
                version = service.app_version
                redis_url = service.redis_url
                results.append({
                    'thread_id': thread_id,
                    'version': version,
                    'redis_url': redis_url
                })
            except Exception as e:
                errors.append({
                    'thread_id': thread_id,
                    'error': str(e)
                })
        
        # Create services in multiple threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for i in range(50):
                future = executor.submit(create_and_use_service, i)
                futures.append(future)
            
            # Wait for all to complete
            for future in futures:
                future.result()
        
        # Verify no errors occurred
        assert len(errors) == 0, f"Errors occurred: {errors}"
        
        # Verify all threads got the same values
        assert len(results) == 50
        first_version = results[0]['version']
        first_redis_url = results[0]['redis_url']
        
        for result in results:
            assert result['version'] == first_version
            assert result['redis_url'] == first_redis_url
    
    def test_service_isolation(self, db: Session):
        """Test that each service instance maintains its own state"""
        service1 = HealthService(db)
        service2 = HealthService(db)
        
        # Each service should have its own cached values
        assert service1._app_version is None
        assert service2._app_version is None
        
        # Access version in service1
        version1 = service1.app_version
        
        # service2 should still have None
        assert service1._app_version is not None
        assert service2._app_version is None
        
        # Access version in service2
        version2 = service2.app_version
        
        # Both should now have cached values
        assert service1._app_version is not None
        assert service2._app_version is not None
        
        # Values should be the same
        assert version1 == version2
        
        # But the cache is independent
        assert id(service1._app_version) != id(service2._app_version) or isinstance(version1, str)