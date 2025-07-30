# backend/modules/analytics/tests/test_ai_assistant.py

"""
Comprehensive tests for AI Analytics Assistant.

These tests cover query processing, chat interactions, security,
and integration with analytics services.
"""

import pytest
import asyncio
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from typing import Dict, Any, List

from ..services.ai_query_processor import AIQueryProcessor
from ..services.ai_chat_service import AIChatService
from ..services.ai_security_service import AISecurityService
from ..services.ai_result_formatter import AIResultFormatter
from ..schemas.ai_assistant_schemas import (
    ChatRequest, ChatResponse, ChatMessage, MessageRole, MessageType,
    AnalyticsQuery, QueryIntent, QueryResult, ChartData, TableData,
    DataPoint, ChartType, WebSocketMessage
)


class TestAIQueryProcessor:
    """Test AI query processing functionality"""
    
    @pytest.fixture
    def query_processor(self):
        """Create query processor instance"""
        return AIQueryProcessor()
    
    def test_intent_detection_sales_report(self, query_processor):
        """Test sales report intent detection"""
        queries = [
            "Show me today's sales",
            "What's our revenue this month?",
            "Give me the sales report",
            "How much did we make today?"
        ]
        
        for query in queries:
            result = query_processor.process_query(query)
            assert result.intent == QueryIntent.SALES_REPORT
            assert result.confidence_score > 0.5
    
    def test_intent_detection_staff_performance(self, query_processor):
        """Test staff performance intent detection"""
        queries = [
            "Who are the top performers?",
            "Show staff productivity",
            "Which employee sold the most?",
            "Staff performance report"
        ]
        
        for query in queries:
            result = query_processor.process_query(query)
            assert result.intent == QueryIntent.STAFF_PERFORMANCE
            assert result.confidence_score > 0.5
    
    def test_time_range_extraction(self, query_processor):
        """Test time range extraction from queries"""
        # Test today
        result = query_processor.process_query("Show me today's sales")
        assert result.time_range is not None
        assert result.time_range.get('date') == date.today().isoformat()
        
        # Test yesterday
        result = query_processor.process_query("What were yesterday's numbers?")
        assert result.time_range is not None
        expected_date = (date.today() - timedelta(days=1)).isoformat()
        assert result.time_range.get('date') == expected_date
        
        # Test last X days
        result = query_processor.process_query("Show me sales for the last 7 days")
        assert result.time_range is not None
        assert 'start_date' in result.time_range
        assert 'end_date' in result.time_range
        
        # Test date range
        result = query_processor.process_query("Revenue between 2024-01-01 and 2024-01-31")
        assert result.time_range is not None
        assert result.time_range['start_date'] == '2024-01-01'
        assert result.time_range['end_date'] == '2024-01-31'
    
    def test_entity_extraction(self, query_processor):
        """Test entity extraction from queries"""
        # Test staff extraction
        result = query_processor.process_query("Show me sales for staff #123")
        assert 'staff' in result.entities
        assert result.entities['staff'] == '123'
        
        # Test product extraction  
        result = query_processor.process_query("How is product Coffee performing?")
        assert 'product' in result.entities
        assert result.entities['product'] == 'Coffee'
        
        # Test amount extraction
        result = query_processor.process_query("Orders above $100")
        assert 'amount' in result.entities
        assert result.entities['amount'] == '100'
    
    def test_metric_extraction(self, query_processor):
        """Test metric extraction from queries"""
        # Revenue metrics
        result = query_processor.process_query("Show me revenue trends")
        assert 'revenue' in result.metrics
        
        # Order metrics
        result = query_processor.process_query("How many orders did we get?")
        assert 'orders' in result.metrics
        
        # Multiple metrics
        result = query_processor.process_query("Compare revenue and orders")
        assert 'revenue' in result.metrics
        assert 'orders' in result.metrics
    
    def test_query_enhancement_with_context(self, query_processor):
        """Test query enhancement using conversation context"""
        from ..schemas.ai_assistant_schemas import QueryContext
        
        # Create context with previous query
        context = QueryContext(
            session_id="test-session",
            user_id=1,
            conversation_history=[
                ChatMessage(
                    id="1",
                    role=MessageRole.USER,
                    content="Show me sales for January",
                    metadata={
                        'query': {
                            'time_range': {'start_date': '2024-01-01', 'end_date': '2024-01-31'},
                            'filters': {'category_ids': [1, 2]}
                        }
                    }
                )
            ]
        )
        
        # Process follow-up query
        query = query_processor.process_query("How about for the same categories?", context)
        query = query_processor.enhance_with_context(query, context)
        
        # Should inherit time range and filters
        assert query.time_range is not None
        assert query.filters is not None
        assert query.filters.get('category_ids') == [1, 2]


class TestAIChatService:
    """Test AI chat service functionality"""
    
    @pytest.fixture
    def chat_service(self):
        """Create chat service instance"""
        return AIChatService()
    
    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()
    
    @pytest.mark.asyncio
    async def test_process_message_success(self, chat_service, mock_db):
        """Test successful message processing"""
        # Mock dependencies
        with patch.object(chat_service.security_service, 'validate_request', return_value=(True, None)), \
             patch.object(chat_service.security_service, 'is_query_allowed', return_value=(True, None)):
            
            # Create request
            request = ChatRequest(
                message="Show me today's sales",
                session_id="test-session"
            )
            
            # Mock query execution
            mock_result = QueryResult(
                query_id="test-query-id",
                status="success",
                summary="Today's sales report",
                data=ChartData(
                    type=ChartType.BAR,
                    title="Sales Summary",
                    data=[
                        DataPoint(label="Revenue", value=1000.0),
                        DataPoint(label="Orders", value=50)
                    ]
                ),
                insights=["Revenue is up 10% from yesterday"]
            )
            
            with patch.object(chat_service, '_execute_query', return_value=mock_result):
                response = await chat_service.process_message(request, user_id=1, db=mock_db)
                
                assert isinstance(response, ChatResponse)
                assert response.message.role == MessageRole.ASSISTANT
                assert response.query_result is not None
                assert response.query_result.status == "success"
                assert not response.requires_clarification
    
    @pytest.mark.asyncio
    async def test_process_message_security_validation(self, chat_service, mock_db):
        """Test message security validation"""
        # Mock security validation failure
        with patch.object(chat_service.security_service, 'validate_request', 
                         return_value=(False, "Malicious input detected")):
            
            request = ChatRequest(
                message="'; DROP TABLE users; --",
                session_id="test-session"
            )
            
            response = await chat_service.process_message(request, user_id=1, db=mock_db)
            
            assert response.message.role == MessageRole.ERROR
            assert "Malicious input detected" in response.message.content
    
    @pytest.mark.asyncio
    async def test_process_message_rate_limiting(self, chat_service, mock_db):
        """Test rate limiting enforcement"""
        # Mock rate limit exceeded
        with patch.object(chat_service.security_service, 'validate_request', return_value=(True, None)), \
             patch.object(chat_service.security_service, 'is_query_allowed', 
                         return_value=(False, "Rate limit exceeded")):
            
            request = ChatRequest(
                message="Show me complex forecast analysis",
                session_id="test-session"
            )
            
            response = await chat_service.process_message(request, user_id=1, db=mock_db)
            
            assert response.message.role == MessageRole.ERROR
            assert "Rate limit exceeded" in response.message.content
    
    @pytest.mark.asyncio
    async def test_session_management(self, chat_service):
        """Test chat session management"""
        # Create new session
        session = chat_service._get_or_create_session(None, user_id=1)
        assert session.user_id == 1
        assert session.session_id in chat_service.sessions
        
        # Get existing session
        existing_session = chat_service._get_or_create_session(session.session_id, user_id=1)
        assert existing_session.session_id == session.session_id
        
        # Clear session
        success = chat_service.clear_session(session.session_id)
        assert success
        assert session.session_id not in chat_service.sessions
    
    @pytest.mark.asyncio
    async def test_suggested_queries_generation(self, chat_service, mock_db):
        """Test suggested query generation"""
        with patch('backend.modules.analytics.services.ai_chat_service.realtime_metrics_service') as mock_service:
            mock_service.get_current_dashboard_snapshot = AsyncMock()
            
            suggestions = await chat_service.get_suggested_queries(user_id=1, db=mock_db)
            
            assert len(suggestions) > 0
            assert all(hasattr(s, 'text') for s in suggestions)
            assert all(hasattr(s, 'category') for s in suggestions)


class TestAISecurityService:
    """Test AI security service functionality"""
    
    @pytest.fixture
    def security_service(self):
        """Create security service instance"""
        return AISecurityService()
    
    def test_validate_request_sql_injection(self, security_service):
        """Test SQL injection detection"""
        malicious_requests = [
            "Show sales'; DROP TABLE orders; --",
            "Revenue WHERE 1=1 UNION SELECT * FROM users",
            "Sales for staff_id = 1 OR 1=1"
        ]
        
        for message in malicious_requests:
            request = ChatRequest(message=message)
            is_valid, error = security_service.validate_request(request, user_id=1)
            assert not is_valid
            assert "Invalid input detected" in error
    
    def test_validate_request_script_injection(self, security_service):
        """Test script injection detection"""
        malicious_requests = [
            "<script>alert('XSS')</script>",
            "Show sales <img src=x onerror=alert(1)>",
            "Revenue javascript:void(0)"
        ]
        
        for message in malicious_requests:
            request = ChatRequest(message=message)
            is_valid, error = security_service.validate_request(request, user_id=1)
            assert not is_valid
    
    def test_validate_request_sensitive_data(self, security_service):
        """Test sensitive data detection"""
        sensitive_requests = [
            "Process payment for card 4111111111111111",
            "Customer with SSN 123-45-6789",
            "Email user@example.com about sales"
        ]
        
        for message in sensitive_requests:
            request = ChatRequest(message=message)
            is_valid, error = security_service.validate_request(request, user_id=1)
            assert not is_valid
            assert "sensitive information" in error
    
    def test_rate_limiting(self, security_service):
        """Test rate limiting functionality"""
        user_id = 1
        
        # Test message rate limit
        for i in range(20):  # At limit
            is_allowed, _ = security_service.check_rate_limit(user_id, 'messages')
            assert is_allowed
        
        # 21st message should be blocked
        is_allowed, error = security_service.check_rate_limit(user_id, 'messages')
        assert not is_allowed
        assert "Rate limit exceeded" in error
    
    def test_query_complexity_calculation(self, security_service):
        """Test query complexity scoring"""
        # Simple query
        simple_query = AnalyticsQuery(
            original_text="Show today's sales",
            intent=QueryIntent.SALES_REPORT,
            time_range={'date': date.today().isoformat()},
            metrics=['revenue']
        )
        
        complexity = security_service.calculate_query_complexity(simple_query)
        assert complexity < 1.0
        
        # Complex query
        complex_query = AnalyticsQuery(
            original_text="Forecast next month's revenue",
            intent=QueryIntent.FORECAST,
            time_range={
                'start_date': date.today().isoformat(),
                'end_date': (date.today() + timedelta(days=30)).isoformat()
            },
            metrics=['revenue', 'orders', 'growth'],
            group_by=['date', 'category', 'staff']
        )
        
        complexity = security_service.calculate_query_complexity(complex_query)
        assert complexity > 3.0
    
    def test_input_sanitization(self, security_service):
        """Test input sanitization"""
        dirty_inputs = [
            "<b>Show sales</b>",
            "Revenue\n\n\n\nanalysis",
            "Sales   with    extra     spaces",
            "Report\x00with\x01control\x02chars"
        ]
        
        expected_outputs = [
            "Show sales",
            "Revenue analysis",
            "Sales with extra spaces",
            "Report with control chars"
        ]
        
        for dirty, expected in zip(dirty_inputs, expected_outputs):
            sanitized = security_service.sanitize_input(dirty)
            assert sanitized == expected


class TestAIResultFormatter:
    """Test AI result formatting functionality"""
    
    @pytest.fixture
    def formatter(self):
        """Create result formatter instance"""
        return AIResultFormatter()
    
    def test_value_formatting(self, formatter):
        """Test value formatting"""
        # Currency formatting
        assert formatter.format_value(1234.56, 'currency') == '$1,234.56'
        assert formatter.format_value(1000000, 'currency') == '$1,000,000.00'
        
        # Percentage formatting
        assert formatter.format_value(0.125, 'percentage') == '12.5%'
        assert formatter.format_value(1.5, 'percentage') == '150.0%'
        
        # Number formatting
        assert formatter.format_value(12345, 'number') == '12,345'
        assert formatter.format_value(12.345, 'decimal') == '12.35'
    
    def test_chart_type_recommendation(self, formatter):
        """Test chart type recommendations"""
        # Time series data
        time_data = [
            DataPoint(label="2024-01-01", value=100),
            DataPoint(label="2024-01-02", value=110),
            DataPoint(label="2024-01-03", value=120)
        ]
        
        query = AnalyticsQuery(
            original_text="Show trend",
            intent=QueryIntent.TREND_ANALYSIS
        )
        
        chart_type = formatter.recommend_chart_type(time_data, query)
        assert chart_type in [ChartType.LINE, ChartType.AREA]
        
        # Distribution data
        dist_data = [
            DataPoint(label="Product A", value=40),
            DataPoint(label="Product B", value=35),
            DataPoint(label="Product C", value=25)
        ]
        
        chart_type = formatter.recommend_chart_type(dist_data, query)
        assert chart_type == ChartType.PIE
    
    def test_summary_text_creation(self, formatter):
        """Test summary text creation"""
        chart_data = ChartData(
            type=ChartType.LINE,
            title="Revenue Trend",
            data=[
                DataPoint(label="2024-01-01", value=1000),
                DataPoint(label="2024-01-02", value=1200),
                DataPoint(label="2024-01-03", value=1100)
            ]
        )
        
        query_result = QueryResult(
            query_id="test",
            status="success",
            summary="Revenue analysis for last 3 days",
            data=chart_data,
            insights=["Revenue peaked on day 2"]
        )
        
        query = AnalyticsQuery(
            original_text="Show revenue trend",
            intent=QueryIntent.REVENUE_ANALYSIS
        )
        
        summary = formatter.create_summary_text(query_result, query)
        
        assert "Revenue analysis" in summary
        assert "Revenue peaked" in summary
        assert "Average:" in summary
        assert "Peak:" in summary
    
    def test_emoji_enhancement(self, formatter):
        """Test emoji enhancement"""
        text = "Revenue increased by 10%"
        enhanced = formatter.enhance_with_emojis(text, QueryIntent.REVENUE_ANALYSIS)
        
        assert "📈" in enhanced
        assert "⬆️" in enhanced
    
    def test_error_formatting(self, formatter):
        """Test error response formatting"""
        error = formatter.format_error_response(
            "Rate limit exceeded: Max 20 messages per minute",
            "Try spacing out your requests"
        )
        
        assert "❌" in error
        assert "Rate limit exceeded" in error
        assert "Try spacing out" in error
        assert "💡" in error


class TestWebSocketIntegration:
    """Test WebSocket integration for AI chat"""
    
    @pytest.mark.asyncio
    async def test_websocket_message_format(self):
        """Test WebSocket message formatting"""
        message = WebSocketMessage(
            type="chat",
            data={
                "message": "Test message",
                "query_result": None
            }
        )
        
        # Test JSON serialization
        json_str = message.json()
        parsed = json.loads(json_str)
        
        assert parsed["type"] == "chat"
        assert parsed["data"]["message"] == "Test message"
        assert "timestamp" in parsed
    
    @pytest.mark.asyncio
    async def test_chat_flow_integration(self):
        """Test complete chat flow"""
        chat_service = AIChatService()
        
        # Mock dependencies
        with patch.object(chat_service.security_service, 'validate_request', return_value=(True, None)), \
             patch.object(chat_service.security_service, 'is_query_allowed', return_value=(True, None)), \
             patch.object(chat_service, '_execute_query') as mock_execute:
            
            # Mock query result
            mock_execute.return_value = QueryResult(
                query_id="test",
                status="success",
                summary="Test result",
                insights=["Test insight"]
            )
            
            # Process message
            request = ChatRequest(message="Test query")
            response = await chat_service.process_message(request, user_id=1, db=Mock())
            
            # Verify response
            assert response.message.role == MessageRole.ASSISTANT
            assert "Test result" in response.message.content
            assert response.query_result is not None


class TestEndToEndScenarios:
    """Test end-to-end scenarios"""
    
    @pytest.mark.asyncio
    async def test_sales_report_scenario(self):
        """Test complete sales report query flow"""
        # Initialize services
        chat_service = AIChatService()
        
        # Mock database and services
        mock_db = Mock()
        
        with patch.object(chat_service.security_service, 'validate_request', return_value=(True, None)), \
             patch.object(chat_service.security_service, 'is_query_allowed', return_value=(True, None)), \
             patch('backend.modules.analytics.services.ai_chat_service.SalesReportService') as mock_sales:
            
            # Mock sales service
            mock_service_instance = Mock()
            mock_sales.return_value = mock_service_instance
            
            # Mock sales summary
            mock_summary = Mock()
            mock_summary.total_revenue = Decimal('5000.00')
            mock_summary.total_orders = 100
            mock_summary.unique_customers = 75
            mock_summary.average_order_value = Decimal('50.00')
            mock_summary.revenue_growth = 15.0
            mock_summary.order_growth = 10.0
            mock_summary.period_start = date.today()
            mock_summary.period_end = date.today()
            
            mock_service_instance.generate_sales_summary.return_value = mock_summary
            
            # Process query
            request = ChatRequest(message="Show me today's sales report")
            response = await chat_service.process_message(request, user_id=1, db=mock_db)
            
            # Verify response
            assert response.message.role == MessageRole.ASSISTANT
            assert not response.requires_clarification
            assert response.query_result is not None
            assert response.query_result.status == "success"
            
            # Check for data in response
            if response.query_result.data:
                assert isinstance(response.query_result.data, (ChartData, TableData))
    
    @pytest.mark.asyncio
    async def test_clarification_flow(self):
        """Test query clarification flow"""
        chat_service = AIChatService()
        
        with patch.object(chat_service.security_service, 'validate_request', return_value=(True, None)):
            # Ambiguous query
            request = ChatRequest(message="Show performance")
            
            # Mock low confidence query
            with patch.object(chat_service.query_processor, 'process_query') as mock_process:
                mock_query = AnalyticsQuery(
                    original_text="Show performance",
                    intent=QueryIntent.GENERAL_QUESTION,
                    confidence_score=0.4  # Low confidence
                )
                mock_process.return_value = mock_query
                
                with patch.object(chat_service.query_processor, 'suggest_clarifications') as mock_clarify:
                    mock_clarify.return_value = [
                        "Would you like to see staff performance or product performance?",
                        "What time period are you interested in?"
                    ]
                    
                    response = await chat_service.process_message(request, user_id=1, db=Mock())
                    
                    assert response.requires_clarification
                    assert response.clarification_options is not None
                    assert len(response.clarification_options) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])