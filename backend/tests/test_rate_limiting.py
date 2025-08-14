"""Tests for rate limiting functionality"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Test imports
from core.rate_limiter import (
    RateLimiter,
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimitMonitor,
    rate_limit
)
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse


class TestRateLimiter:
    """Test the core RateLimiter class"""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client"""
        redis_mock = MagicMock()
        redis_mock.pipeline.return_value = redis_mock
        redis_mock.execute.return_value = [1, True]  # incr result, expire result
        redis_mock.exists.return_value = 0
        redis_mock.ttl.return_value = -1
        return redis_mock
    
    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create a RateLimiter with mock Redis"""
        limiter = RateLimiter(redis_client=mock_redis)
        return limiter
    
    def test_check_rate_limit_allowed(self, rate_limiter, mock_redis):
        """Test rate limit check when under limit"""
        mock_redis.execute.return_value = [5, True]  # 5 requests so far
        
        allowed, metadata = rate_limiter.check_rate_limit(
            identifier="user:123",
            endpoint="/api/test",
            limit=10,
            window=60
        )
        
        assert allowed is True
        assert metadata["limit"] == 10
        assert metadata["remaining"] == 5
        assert metadata["current"] == 5
        assert "reset" in metadata
    
    def test_check_rate_limit_exceeded(self, rate_limiter, mock_redis):
        """Test rate limit check when over limit"""
        mock_redis.execute.return_value = [11, True]  # 11 requests (over limit of 10)
        
        allowed, metadata = rate_limiter.check_rate_limit(
            identifier="user:123",
            endpoint="/api/test",
            limit=10,
            window=60
        )
        
        assert allowed is False
        assert metadata["limit"] == 10
        assert metadata["remaining"] == 0
        assert metadata["current"] == 11
    
    def test_admin_bypass(self, rate_limiter):
        """Test that limit=0 bypasses rate limiting (admin)"""
        allowed, metadata = rate_limiter.check_rate_limit(
            identifier="admin:1",
            endpoint="/api/test",
            limit=0,  # No limit
            window=60
        )
        
        assert allowed is True
        assert metadata["limit"] == "unlimited"
        assert metadata["remaining"] == "unlimited"
        assert metadata["reset"] is None
    
    def test_blocked_identifier(self, rate_limiter, mock_redis):
        """Test that blocked identifiers are rejected"""
        mock_redis.exists.return_value = 1  # Identifier is blocked
        mock_redis.ttl.return_value = 300  # 5 minutes remaining
        
        allowed, metadata = rate_limiter.check_rate_limit(
            identifier="user:bad",
            endpoint="/api/test",
            limit=10,
            window=60
        )
        
        assert allowed is False
        assert metadata["blocked"] is True
        assert metadata["remaining"] == 0
    
    def test_burst_allowance(self, rate_limiter, mock_redis):
        """Test burst allowance when over normal limit"""
        # First call for normal limit check
        mock_redis.execute.return_value = [11, True]  # Over limit
        # Second call for burst check
        mock_redis.incr.return_value = 12
        mock_redis.expire.return_value = True
        
        # Mock burst check to return True
        with patch.object(rate_limiter, '_check_burst_allowance', return_value=True):
            allowed, metadata = rate_limiter.check_rate_limit(
                identifier="user:123",
                endpoint="/api/test",
                limit=10,
                window=60
            )
        
        assert allowed is True
        assert metadata.get("burst") is True
    
    def test_violation_tracking(self, rate_limiter, mock_redis):
        """Test that violations are tracked"""
        mock_redis.execute.return_value = [1, True]  # Violation count
        
        rate_limiter._track_violation("user:bad")
        
        # Verify violation was tracked
        mock_redis.pipeline.assert_called()
        mock_redis.incr.assert_called()
    
    def test_auto_blocking(self, rate_limiter, mock_redis):
        """Test automatic blocking after threshold violations"""
        # Set violation count to threshold
        mock_redis.execute.return_value = [3, True]  # Hit violation threshold
        
        with patch.object(rate_limiter, '_block_identifier') as mock_block:
            rate_limiter._track_violation("user:bad")
            mock_block.assert_called_once_with("user:bad")
    
    def test_reset_limits(self, rate_limiter, mock_redis):
        """Test resetting rate limits"""
        mock_redis.scan_iter.return_value = [
            "rate_limit:/api/test:user:123:1234567890"
        ]
        
        rate_limiter.reset_limits("user:123", "/api/test")
        
        # Verify keys were deleted
        mock_redis.pipeline.assert_called()
        mock_redis.delete.assert_called()


class TestRateLimitMiddleware:
    """Test the FastAPI middleware"""
    
    @pytest.fixture
    def middleware(self):
        """Create middleware with mock rate limiter"""
        app = Mock()
        middleware = RateLimitMiddleware(app)
        return middleware
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock request"""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.client = Mock(host="192.168.1.1")
        request.headers = {}
        request.state = Mock()
        return request
    
    @pytest.mark.asyncio
    async def test_middleware_allows_request(self, middleware):
        """Test middleware allows request under limit"""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.client = Mock(host="192.168.1.1")
        request.headers = {}
        request.state = Mock()
        
        # Mock rate limiter to allow
        with patch.object(middleware.rate_limiter, 'check_rate_limit') as mock_check:
            mock_check.return_value = (True, {
                "limit": 60,
                "remaining": 55,
                "reset": 1234567890
            })
            
            # Mock call_next
            async def call_next(req):
                response = Response(content="OK")
                return response
            
            response = await middleware.dispatch(request, call_next)
            
            # Verify response has rate limit headers
            assert response.headers.get("X-RateLimit-Limit") == "60"
            assert response.headers.get("X-RateLimit-Remaining") == "55"
    
    @pytest.mark.asyncio
    async def test_middleware_blocks_request(self, middleware):
        """Test middleware blocks request over limit"""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.client = Mock(host="192.168.1.1")
        request.headers = {}
        request.state = Mock()
        
        # Mock rate limiter to block
        with patch.object(middleware.rate_limiter, 'check_rate_limit') as mock_check:
            mock_check.return_value = (False, {
                "limit": 60,
                "remaining": 0,
                "reset": 1234567890,
                "current": 61
            })
            
            # Mock call_next (should not be called)
            call_next = Mock()
            
            response = await middleware.dispatch(request, call_next)
            
            # Verify 429 response
            assert response.status_code == 429
            assert call_next.not_called
    
    def test_get_identifier_anonymous(self, middleware, mock_request):
        """Test identifier extraction for anonymous user"""
        mock_request.state.user_id = None
        
        identifier, id_type = middleware._get_identifier(mock_request)
        
        assert identifier == "ip:192.168.1.1"
        assert id_type == "ip"
    
    def test_get_identifier_authenticated(self, middleware, mock_request):
        """Test identifier extraction for authenticated user"""
        mock_request.state.user_id = 123
        mock_request.state.user_role = "user"
        
        identifier, id_type = middleware._get_identifier(mock_request)
        
        assert identifier == "user:123"
        assert id_type == "user"
    
    def test_get_identifier_admin(self, middleware, mock_request):
        """Test identifier extraction for admin user"""
        mock_request.state.user_id = 1
        mock_request.state.user_role = "admin"
        
        identifier, id_type = middleware._get_identifier(mock_request)
        
        assert identifier == "admin:1"
        assert id_type == "admin"
    
    def test_get_identifier_with_proxy(self, middleware, mock_request):
        """Test identifier extraction with X-Forwarded-For header"""
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        mock_request.state.user_id = None
        
        identifier, id_type = middleware._get_identifier(mock_request)
        
        assert identifier == "ip:10.0.0.1"  # First IP in chain
        assert id_type == "ip"
    
    def test_endpoint_limit_config(self, middleware):
        """Test getting endpoint-specific limits"""
        config = RateLimitConfig()
        
        # Test specific endpoint
        limit = middleware._get_endpoint_limit("/api/v1/auth/login", "ip")
        assert limit["limit"] == 5  # Anonymous limit for login
        assert limit["window"] == 60
        
        # Test authenticated user
        limit = middleware._get_endpoint_limit("/api/v1/auth/login", "user")
        assert limit["limit"] == 10  # Authenticated limit for login
        
        # Test admin bypass
        limit = middleware._get_endpoint_limit("/api/v1/auth/login", "admin")
        assert limit["limit"] == 0  # No limit for admin
    
    def test_rate_limit_headers(self, middleware):
        """Test rate limit header generation"""
        metadata = {
            "limit": 60,
            "remaining": 45,
            "reset": 1234567890,
            "blocked": False
        }
        
        headers = middleware._get_rate_limit_headers(metadata)
        
        assert headers["X-RateLimit-Limit"] == "60"
        assert headers["X-RateLimit-Remaining"] == "45"
        assert headers["X-RateLimit-Reset"] == "1234567890"
        assert "X-RateLimit-Blocked" not in headers
        
        # Test blocked header
        metadata["blocked"] = True
        headers = middleware._get_rate_limit_headers(metadata)
        assert headers["X-RateLimit-Blocked"] == "true"


class TestRateLimitDecorator:
    """Test the rate_limit decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_allows_request(self):
        """Test decorator allows request under limit"""
        
        @rate_limit(requests=10, window=60)
        async def test_endpoint(request: Request):
            return {"status": "ok"}
        
        # Create mock request
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.client = Mock(host="192.168.1.1")
        request.state = Mock()
        request.state.user_id = None
        
        # Mock RateLimiter
        with patch('core.rate_limiter.RateLimiter') as MockLimiter:
            mock_limiter = MockLimiter.return_value
            mock_limiter.check_rate_limit.return_value = (True, {
                "limit": 10,
                "remaining": 9
            })
            mock_limiter._get_rate_limit_headers.return_value = {}
            
            result = await test_endpoint(request)
            assert result == {"status": "ok"}
    
    @pytest.mark.asyncio
    async def test_decorator_blocks_request(self):
        """Test decorator blocks request over limit"""
        
        @rate_limit(requests=10, window=60)
        async def test_endpoint(request: Request):
            return {"status": "ok"}
        
        # Create mock request
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.client = Mock(host="192.168.1.1")
        request.state = Mock()
        request.state.user_id = None
        
        # Mock RateLimiter
        with patch('core.rate_limiter.RateLimiter') as MockLimiter:
            mock_limiter = MockLimiter.return_value
            mock_limiter.check_rate_limit.return_value = (False, {
                "limit": 10,
                "remaining": 0
            })
            mock_limiter._get_rate_limit_headers.return_value = {
                "X-RateLimit-Limit": "10",
                "X-RateLimit-Remaining": "0"
            }
            
            with pytest.raises(HTTPException) as exc_info:
                await test_endpoint(request)
            
            assert exc_info.value.status_code == 429
            assert exc_info.value.detail == "Rate limit exceeded"
    
    @pytest.mark.asyncio
    async def test_decorator_admin_bypass(self):
        """Test decorator bypasses rate limiting for admin"""
        
        @rate_limit(requests=10, window=60, bypass_admin=True)
        async def test_endpoint(request: Request):
            return {"status": "ok"}
        
        # Create mock request for admin
        request = Mock(spec=Request)
        request.url.path = "/test"
        request.state = Mock()
        request.state.user_id = 1
        request.state.user_role = "admin"
        
        # Admin should bypass without checking rate limit
        result = await test_endpoint(request)
        assert result == {"status": "ok"}


class TestRateLimitMonitor:
    """Test the monitoring and alerting system"""
    
    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client"""
        redis_mock = MagicMock()
        redis_mock.lpush.return_value = 1
        redis_mock.expire.return_value = True
        redis_mock.llen.return_value = 5
        redis_mock.scan_iter.return_value = []
        redis_mock.lrange.return_value = []
        redis_mock.ttl.return_value = 300
        return redis_mock
    
    @pytest.fixture
    def monitor(self, mock_redis):
        """Create a RateLimitMonitor with mock Redis"""
        monitor = RateLimitMonitor(redis_client=mock_redis)
        return monitor
    
    def test_log_violation(self, monitor, mock_redis):
        """Test logging rate limit violations"""
        monitor.log_violation(
            identifier="user:123",
            endpoint="/api/test",
            metadata={"limit": 10, "current": 11}
        )
        
        # Verify violation was logged
        mock_redis.lpush.assert_called()
        mock_redis.expire.assert_called()
    
    def test_check_alerts_high_violations(self, monitor, mock_redis):
        """Test alert triggering for high violations"""
        # Mock high violation count
        mock_redis.scan_iter.return_value = ["key1", "key2"]
        mock_redis.lrange.return_value = [
            "user:bad" for _ in range(101)  # Over 100 violations
        ]
        
        with patch.object(monitor, '_send_alert') as mock_alert:
            monitor._check_alerts("user:bad", "/api/test")
            
            # Verify high severity alert was sent
            mock_alert.assert_called()
            call_args = mock_alert.call_args[0]
            assert "High rate limit violations" in call_args[0]
            assert mock_alert.call_args[1]["severity"] == "high"
    
    def test_get_statistics(self, monitor, mock_redis):
        """Test getting rate limit statistics"""
        mock_redis.llen.return_value = 42  # Today's violations
        mock_redis.scan_iter.return_value = [
            "rate_limit:blocked:user:123",
            "rate_limit:blocked:ip:1.2.3.4"
        ]
        mock_redis.ttl.side_effect = [300, 600]  # TTLs for blocked identifiers
        
        stats = monitor.get_statistics()
        
        assert stats["total_violations_today"] == 42
        assert len(stats["blocked_identifiers"]) == 2
        assert stats["blocked_identifiers"][0]["identifier"] == "user:123"
        assert stats["blocked_identifiers"][0]["expires_in"] == 300


class TestRateLimitConfig:
    """Test rate limit configuration"""
    
    def test_default_limits(self):
        """Test default rate limit values"""
        config = RateLimitConfig()
        
        assert config.DEFAULT_ANONYMOUS_LIMIT == 60
        assert config.DEFAULT_AUTHENTICATED_LIMIT == 300
        assert config.DEFAULT_ADMIN_LIMIT == 0
        
        assert config.BURST_MULTIPLIER == 1.5
        assert config.BURST_WINDOW == 10
        
        assert config.VIOLATION_PENALTY_MINUTES == 5
        assert config.VIOLATION_THRESHOLD == 3
    
    def test_endpoint_specific_limits(self):
        """Test endpoint-specific configurations"""
        config = RateLimitConfig()
        
        # Auth endpoints should be restrictive
        assert config.ENDPOINT_LIMITS["/api/v1/auth/login"]["anonymous"] == 5
        assert config.ENDPOINT_LIMITS["/api/v1/auth/login"]["authenticated"] == 10
        
        # Analytics endpoints should block anonymous
        assert config.ENDPOINT_LIMITS["/api/v1/analytics/sales-report"]["anonymous"] == 0
        
        # Order endpoints should allow high traffic for authenticated
        assert config.ENDPOINT_LIMITS["/api/v1/orders"]["authenticated"] == 600


class TestIntegration:
    """Integration tests for rate limiting"""
    
    @pytest.mark.asyncio
    async def test_full_flow_rate_limiting(self):
        """Test complete rate limiting flow"""
        # This would be an integration test with a real Redis instance
        # For now, we'll use mocks
        
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.execute.return_value = [1, True]
        mock_redis.exists.return_value = 0
        
        limiter = RateLimiter(redis_client=mock_redis)
        
        # Simulate multiple requests
        for i in range(1, 12):
            mock_redis.execute.return_value = [i, True]
            allowed, metadata = limiter.check_rate_limit(
                identifier="user:test",
                endpoint="/api/test",
                limit=10,
                window=60
            )
            
            if i <= 10:
                assert allowed is True
                assert metadata["remaining"] == max(0, 10 - i)
            else:
                # Should be blocked after 10 requests
                assert allowed is False
                assert metadata["remaining"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])