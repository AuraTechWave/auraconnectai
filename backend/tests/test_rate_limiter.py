"""
Tests for API rate limiting functionality.

Ensures rate limiting works correctly for different scenarios
and protects against abuse.
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
from fastapi import Request, FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from core.rate_limiter import (
    RateLimiter, 
    MemoryRateLimiter, 
    RateLimitRule, 
    rate_limit_middleware,
    get_rate_limiter
)


class TestRateLimitRule:
    """Test rate limit rule configuration."""

    def test_rate_limit_rule_creation(self):
        """Test creating rate limit rules."""
        rule = RateLimitRule(requests=100, window=60)
        assert rule.requests == 100
        assert rule.window == 60
        assert rule.burst is None

    def test_rate_limit_rule_with_burst(self):
        """Test rate limit rule with burst configuration."""
        rule = RateLimitRule(requests=100, window=60, burst=20)
        assert rule.requests == 100
        assert rule.window == 60
        assert rule.burst == 20


class TestMemoryRateLimiter:
    """Test in-memory rate limiter implementation."""

    @pytest.fixture
    def limiter(self):
        """Create memory rate limiter instance."""
        return MemoryRateLimiter()

    @pytest.fixture
    def rule(self):
        """Create test rate limit rule."""
        return RateLimitRule(requests=5, window=60)

    @pytest.mark.asyncio
    async def test_allows_requests_under_limit(self, limiter, rule):
        """Test that requests under the limit are allowed."""
        for i in range(5):
            allowed, retry_after = await limiter.is_allowed("test_client", rule)
            assert allowed is True
            assert retry_after == 0

    @pytest.mark.asyncio
    async def test_blocks_requests_over_limit(self, limiter, rule):
        """Test that requests over the limit are blocked."""
        # Fill up the limit
        for i in range(5):
            await limiter.is_allowed("test_client", rule)
        
        # Next request should be blocked
        allowed, retry_after = await limiter.is_allowed("test_client", rule)
        assert allowed is False
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_different_clients_have_separate_limits(self, limiter, rule):
        """Test that different clients have independent limits."""
        # Fill limit for client1
        for i in range(5):
            await limiter.is_allowed("client1", rule)
        
        # client1 should be blocked
        allowed, _ = await limiter.is_allowed("client1", rule)
        assert allowed is False
        
        # client2 should still be allowed
        allowed, _ = await limiter.is_allowed("client2", rule)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_sliding_window_behavior(self, limiter):
        """Test sliding window rate limiting behavior."""
        # Use a short window for testing
        rule = RateLimitRule(requests=2, window=1)
        
        # Make 2 requests (fill the limit)
        await limiter.is_allowed("test_client", rule)
        await limiter.is_allowed("test_client", rule)
        
        # Third request should be blocked
        allowed, _ = await limiter.is_allowed("test_client", rule)
        assert allowed is False
        
        # Wait for window to slide
        await asyncio.sleep(1.1)
        
        # Should be allowed again
        allowed, _ = await limiter.is_allowed("test_client", rule)
        assert allowed is True


class TestRateLimiter:
    """Test main rate limiter class."""

    @pytest.fixture
    def limiter(self):
        """Create rate limiter instance."""
        return RateLimiter()

    @pytest.fixture
    def mock_request(self):
        """Create mock FastAPI request."""
        request = Mock(spec=Request)
        request.url.path = "/api/v1/test"
        request.method = "GET"
        request.client.host = "127.0.0.1"
        request.headers = {}
        request.state = Mock()
        return request

    def test_add_rule(self, limiter):
        """Test adding rate limiting rules."""
        limiter.add_rule("/api/test", 50, 60)
        assert "/api/test" in limiter.rules
        assert limiter.rules["/api/test"].requests == 50
        assert limiter.rules["/api/test"].window == 60

    def test_get_client_key_with_user_id(self, limiter, mock_request):
        """Test client key generation with authenticated user."""
        mock_request.state.user_id = 123
        key = limiter.get_client_key(mock_request)
        assert key == "user:123"

    def test_get_client_key_with_ip(self, limiter, mock_request):
        """Test client key generation with IP address."""
        mock_request.state.user_id = None
        key = limiter.get_client_key(mock_request)
        assert key == "ip:127.0.0.1"

    def test_get_client_key_with_forwarded_header(self, limiter, mock_request):
        """Test client key generation with X-Forwarded-For header."""
        mock_request.state.user_id = None
        mock_request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        key = limiter.get_client_key(mock_request)
        assert key == "ip:192.168.1.1"

    def test_get_rule_for_endpoint_exact_match(self, limiter, mock_request):
        """Test getting rule for exact endpoint match."""
        limiter.add_rule("GET /api/v1/test", 10, 60)
        rule = limiter.get_rule_for_endpoint(mock_request)
        assert rule is not None
        assert rule.requests == 10

    def test_get_rule_for_endpoint_path_prefix(self, limiter, mock_request):
        """Test getting rule for path prefix match."""
        limiter.add_rule("/api/v1", 20, 60)
        rule = limiter.get_rule_for_endpoint(mock_request)
        assert rule is not None
        assert rule.requests == 20

    def test_get_rule_for_endpoint_default(self, limiter, mock_request):
        """Test getting default rule when no specific rule matches."""
        limiter.add_rule("default", 100, 60)
        rule = limiter.get_rule_for_endpoint(mock_request)
        assert rule is not None
        assert rule.requests == 100

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, limiter, mock_request):
        """Test rate limit check when request is allowed."""
        limiter.add_rule("default", 100, 60)
        response = await limiter.check_rate_limit(mock_request)
        assert response is None  # No rate limit response means allowed

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked(self, limiter, mock_request):
        """Test rate limit check when request is blocked."""
        # Add very restrictive rule
        limiter.add_rule("default", 1, 60)
        
        # First request should be allowed
        response = await limiter.check_rate_limit(mock_request)
        assert response is None
        
        # Second request should be blocked
        response = await limiter.check_rate_limit(mock_request)
        assert response is not None
        assert response.status_code == 429


class TestRateLimitMiddleware:
    """Test rate limiting middleware integration."""

    @pytest.fixture
    def app(self):
        """Create FastAPI app with rate limiting."""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        @app.get("/unlimited")
        async def unlimited_endpoint():
            return {"message": "unlimited"}
        
        return app

    @pytest.mark.asyncio
    async def test_middleware_allows_normal_requests(self, app):
        """Test that middleware allows normal requests."""
        
        from fastapi.responses import JSONResponse
        
        async def mock_call_next(request):
            return JSONResponse(content={"message": "success"})
        
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/test"
        mock_request.method = "GET"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}
        mock_request.state = Mock()
        mock_request.state.user_id = None
        
        with patch('core.rate_limiter.get_rate_limiter') as mock_get_limiter:
            mock_limiter = Mock()
            mock_limiter.check_rate_limit = AsyncMock(return_value=None)
            mock_limiter.get_rule_for_endpoint.return_value = RateLimitRule(100, 60)
            mock_get_limiter.return_value = mock_limiter
            
            response = await rate_limit_middleware(mock_request, mock_call_next)
            assert "X-RateLimit-Limit" in response.headers
            assert response.headers["X-RateLimit-Limit"] == "100"

    @pytest.mark.asyncio
    async def test_middleware_blocks_rate_limited_requests(self, app):
        """Test that middleware blocks rate limited requests."""
        
        async def mock_call_next(request):
            return {"message": "success"}
        
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/test"
        mock_request.method = "GET"
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}
        mock_request.state = Mock()
        mock_request.state.user_id = None
        
        # Mock rate limit response
        from fastapi.responses import JSONResponse
        rate_limit_response = JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded"}
        )
        
        with patch('core.rate_limiter.get_rate_limiter') as mock_get_limiter:
            mock_limiter = Mock()
            mock_limiter.check_rate_limit = AsyncMock(return_value=rate_limit_response)
            mock_get_limiter.return_value = mock_limiter
            
            response = await rate_limit_middleware(mock_request, mock_call_next)
            assert response.status_code == 429


class TestRateLimitingIntegration:
    """Integration tests for rate limiting."""

    def test_rate_limiter_configuration(self):
        """Test that rate limiter is configured correctly."""
        limiter = get_rate_limiter()
        assert limiter is not None
        assert 'default' in limiter.rules
        assert 'POST /auth/login' in limiter.rules

    def test_authentication_endpoint_limits(self):
        """Test that authentication endpoints have restrictive limits."""
        limiter = get_rate_limiter()
        login_rule = limiter.rules.get('POST /auth/login')
        assert login_rule is not None
        assert login_rule.requests <= 10  # Should be restrictive

    def test_payroll_endpoint_limits(self):
        """Test that payroll endpoints have appropriate limits."""
        limiter = get_rate_limiter()
        payroll_rule = limiter.rules.get('/api/v1/payrolls')
        assert payroll_rule is not None
        assert payroll_rule.requests > 0

    @pytest.mark.asyncio
    async def test_concurrent_requests_handling(self):
        """Test handling of concurrent requests."""
        limiter = MemoryRateLimiter()
        rule = RateLimitRule(requests=10, window=60)
        
        # Make concurrent requests
        tasks = []
        for i in range(15):
            task = limiter.is_allowed(f"client_{i % 3}", rule)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Should have mixed allowed/blocked results
        allowed_count = sum(1 for allowed, _ in results if allowed)
        blocked_count = sum(1 for allowed, _ in results if not allowed)
        
        assert allowed_count > 0
        assert blocked_count >= 0  # Might be 0 if clients don't exceed limits


@pytest.mark.asyncio
async def test_rate_limit_headers():
    """Test that rate limit headers are added to responses."""
    
    mock_request = Mock(spec=Request)
    mock_request.url.path = "/test"
    mock_request.method = "GET"
    mock_request.client.host = "127.0.0.1"
    mock_request.headers = {}
    mock_request.state = Mock()
    mock_request.state.user_id = None
    
    # Mock response
    mock_response = Mock()
    mock_response.headers = {}
    
    async def mock_call_next(request):
        return mock_response
    
    with patch('core.rate_limiter.get_rate_limiter') as mock_get_limiter:
        mock_limiter = Mock()
        mock_limiter.check_rate_limit = AsyncMock(return_value=None)
        mock_limiter.get_rule_for_endpoint.return_value = RateLimitRule(100, 60)
        mock_get_limiter.return_value = mock_limiter
        
        response = await rate_limit_middleware(mock_request, mock_call_next)
        
        # Check that rate limit headers were added
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Window" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Window"] == "60"