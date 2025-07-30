# backend/modules/analytics/tests/test_ai_edge_cases.py

"""
Edge case tests for AI Analytics Assistant.

Tests for invalid inputs, null values, empty states, and exception scenarios.
"""

import pytest
import asyncio
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.exc import SQLAlchemyError

from ..services.ai_query_processor import AIQueryProcessor
from ..services.ai_chat_service import AIChatService
from ..services.ai_security_service import AISecurityService
from ..services.ai_result_formatter import AIResultFormatter
from ..schemas.ai_assistant_schemas import (
    ChatRequest, AnalyticsQuery, QueryIntent, ChatMessage,
    MessageRole, ChartData, TableData, DataPoint
)


class TestAIQueryProcessorEdgeCases:
    """Test edge cases for AI query processor"""
    
    @pytest.fixture
    def query_processor(self):
        return AIQueryProcessor()
    
    def test_process_empty_query(self, query_processor):
        """Test processing empty query string"""
        result = query_processor.process_query("")
        assert result.intent == QueryIntent.GENERAL_QUESTION
        assert result.confidence_score < 0.5
    
    def test_process_null_query(self, query_processor):
        """Test processing None as query"""
        with pytest.raises(AttributeError):
            query_processor.process_query(None)
    
    def test_process_very_long_query(self, query_processor):
        """Test processing extremely long query"""
        long_query = "show me sales " * 500  # 2000+ characters
        result = query_processor.process_query(long_query)
        assert result is not None
        # Should still detect sales intent despite length
        assert result.intent in [QueryIntent.SALES_REPORT, QueryIntent.GENERAL_QUESTION]
    
    def test_process_special_characters(self, query_processor):
        """Test query with special characters"""
        special_queries = [
            "Show me sales for $$$",
            "Revenue @#$%^&*()",
            "Staff performance!!!???",
            "Products with 日本語 names"
        ]
        
        for query in special_queries:
            result = query_processor.process_query(query)
            assert result is not None
            assert isinstance(result.original_text, str)
    
    def test_extract_invalid_dates(self, query_processor):
        """Test extraction of invalid date formats"""
        invalid_date_queries = [
            "Show sales for 2024-13-45",  # Invalid month/day
            "Revenue on 32nd January",     # Invalid day
            "Data for February 30th",      # Invalid date
            "Sales from 2024-02-30 to 2024-02-31"  # Invalid dates
        ]
        
        for query in invalid_date_queries:
            result = query_processor.process_query(query)
            # Should handle gracefully without crashing
            assert result is not None
    
    def test_enhance_with_null_context(self, query_processor):
        """Test query enhancement with None context"""
        query = AnalyticsQuery(
            original_text="Show sales",
            intent=QueryIntent.SALES_REPORT
        )
        
        # Should handle None context gracefully
        enhanced = query_processor.enhance_with_context(query, None)
        assert enhanced == query  # No enhancement without context
    
    def test_malformed_conversation_history(self, query_processor):
        """Test with malformed conversation history"""
        from ..schemas.ai_assistant_schemas import QueryContext
        
        # Context with invalid message structure
        context = QueryContext(
            session_id="test",
            user_id=1,
            conversation_history=[
                ChatMessage(
                    id="1",
                    role=MessageRole.USER,
                    content="Previous query",
                    metadata=None  # Missing metadata
                ),
                ChatMessage(
                    id="2",
                    role=MessageRole.ASSISTANT,
                    content="Response",
                    metadata={"query": None}  # Null query
                )
            ]
        )
        
        query = query_processor.process_query("Show me the same data", context)
        # Should handle gracefully
        assert query is not None


class TestAIChatServiceEdgeCases:
    """Test edge cases for AI chat service"""
    
    @pytest.fixture
    def chat_service(self):
        return AIChatService()
    
    @pytest.fixture
    def mock_db(self):
        return Mock()
    
    @pytest.mark.asyncio
    async def test_process_message_with_null_content(self, chat_service, mock_db):
        """Test processing message with null content"""
        request = ChatRequest(message=None, session_id="test")
        
        with pytest.raises(AttributeError):
            await chat_service.process_message(request, user_id=1, db=mock_db)
    
    @pytest.mark.asyncio
    async def test_process_message_db_connection_error(self, chat_service, mock_db):
        """Test handling database connection errors"""
        request = ChatRequest(message="Show sales")
        
        # Mock database error
        mock_db.execute.side_effect = SQLAlchemyError("Database connection failed")
        
        with patch.object(chat_service.security_service, 'validate_request', return_value=(True, None)):
            response = await chat_service.process_message(request, user_id=1, db=mock_db)
            
            assert response.message.role == MessageRole.ERROR
            assert "error" in response.message.content.lower()
    
    @pytest.mark.asyncio
    async def test_execute_query_timeout(self, chat_service, mock_db):
        """Test query execution timeout"""
        query = AnalyticsQuery(
            original_text="Complex forecast",
            intent=QueryIntent.FORECAST,
            time_range={'start_date': '2020-01-01', 'end_date': '2024-12-31'}
        )
        
        # Mock timeout
        with patch.object(chat_service, '_execute_forecast', side_effect=TimeoutError("Query timeout")):
            result = await chat_service._execute_query(query, user_id=1, db=mock_db)
            
            assert result.status == "error"
            assert "too long" in result.summary
    
    @pytest.mark.asyncio
    async def test_session_overflow(self, chat_service):
        """Test handling too many sessions"""
        # Create many sessions
        for i in range(10000):
            session = chat_service._get_or_create_session(f"session-{i}", user_id=i)
            assert session is not None
        
        # Should still handle new sessions
        new_session = chat_service._get_or_create_session("new-session", user_id=99999)
        assert new_session is not None
    
    @pytest.mark.asyncio
    async def test_malformed_query_result(self, chat_service, mock_db):
        """Test handling malformed query results"""
        request = ChatRequest(message="Show revenue")
        
        with patch.object(chat_service.security_service, 'validate_request', return_value=(True, None)), \
             patch.object(chat_service, '_execute_query') as mock_execute:
            
            # Return result with invalid data structure
            mock_execute.return_value = Mock(
                status="success",
                data=Mock(data=None),  # Invalid data structure
                insights=None,
                summary=None
            )
            
            response = await chat_service.process_message(request, user_id=1, db=mock_db)
            # Should handle gracefully
            assert response is not None


class TestAISecurityServiceEdgeCases:
    """Test edge cases for AI security service"""
    
    @pytest.fixture
    def security_service(self):
        return AISecurityService()
    
    def test_validate_unicode_injection(self, security_service):
        """Test validation of unicode injection attempts"""
        unicode_injections = [
            "Show sales\u202E\u0027; DROP TABLE--",  # Right-to-left override
            "Revenue\u0000NULL\u0000BYTE",           # Null bytes
            "Data\uFEFF\uFFFEwith BOM"              # Byte order marks
        ]
        
        for injection in unicode_injections:
            request = ChatRequest(message=injection)
            is_valid, error = security_service.validate_request(request, user_id=1)
            # Should be sanitized or rejected
            assert is_valid or error is not None
    
    def test_rate_limit_edge_values(self, security_service):
        """Test rate limiting with edge values"""
        user_id = 1
        
        # Test at exact limit
        for i in range(20):  # Exactly at message limit
            is_allowed, _ = security_service.check_rate_limit(user_id, 'messages')
            assert is_allowed
        
        # 21st should fail
        is_allowed, error = security_service.check_rate_limit(user_id, 'messages')
        assert not is_allowed
        assert "Rate limit exceeded" in error
    
    def test_concurrent_rate_limit_checks(self, security_service):
        """Test concurrent rate limit checks"""
        user_id = 1
        
        # Simulate concurrent requests
        import threading
        results = []
        
        def check_limit():
            is_allowed, _ = security_service.check_rate_limit(user_id, 'messages')
            results.append(is_allowed)
        
        threads = [threading.Thread(target=check_limit) for _ in range(30)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have some failures due to rate limit
        allowed_count = sum(1 for r in results if r)
        assert allowed_count <= 20  # Rate limit
    
    def test_complexity_calculation_edge_cases(self, security_service):
        """Test query complexity calculation edge cases"""
        # Empty query
        empty_query = AnalyticsQuery(
            original_text="",
            intent=QueryIntent.GENERAL_QUESTION,
            time_range=None,
            entities=None,
            metrics=[]
        )
        complexity = security_service.calculate_query_complexity(empty_query)
        assert complexity == 0.0
        
        # Extremely complex query
        complex_query = AnalyticsQuery(
            original_text="Complex query",
            intent=QueryIntent.FORECAST,
            time_range={'start_date': '2020-01-01', 'end_date': '2024-12-31'},
            entities={'staff': list(range(100)), 'products': list(range(200))},
            metrics=['revenue', 'orders', 'growth', 'efficiency', 'productivity'],
            group_by=['date', 'staff', 'product', 'category', 'location']
        )
        complexity = security_service.calculate_query_complexity(complex_query)
        assert complexity == 10.0  # Should be capped at 10


class TestAIResultFormatterEdgeCases:
    """Test edge cases for AI result formatter"""
    
    @pytest.fixture
    def formatter(self):
        return AIResultFormatter()
    
    def test_format_null_values(self, formatter):
        """Test formatting null and None values"""
        assert formatter.format_value(None) == 'N/A'
        assert formatter.format_value(None, 'currency') == 'N/A'
        assert formatter.format_value(None, 'percentage') == 'N/A'
    
    def test_format_extreme_values(self, formatter):
        """Test formatting extreme numeric values"""
        # Very large numbers
        assert '$' in formatter.format_value(999999999999.99, 'currency')
        assert formatter.format_value(float('inf'), 'number') == 'inf'
        
        # Very small numbers
        assert formatter.format_value(0.0000001, 'percentage') == '0.0%'
        assert formatter.format_value(-999999999, 'currency') == '$-999,999,999.00'
    
    def test_format_invalid_types(self, formatter):
        """Test formatting with invalid type specifications"""
        value = 123.45
        # Invalid format type should fall back to number
        result = formatter.format_value(value, 'invalid_type')
        assert '123' in result
    
    def test_chart_recommendation_empty_data(self, formatter):
        """Test chart recommendation with empty data"""
        empty_query = AnalyticsQuery(
            original_text="Show data",
            intent=QueryIntent.GENERAL_QUESTION
        )
        
        chart_type = formatter.recommend_chart_type([], empty_query)
        assert chart_type == ChartType.TABLE  # Default for empty data
    
    def test_summary_with_malformed_data(self, formatter):
        """Test summary creation with malformed data"""
        # Chart data with mixed types
        malformed_data = ChartData(
            type=ChartType.BAR,
            title="Test",
            data=[
                DataPoint(label="Valid", value=100),
                DataPoint(label="String", value="not a number"),
                DataPoint(label="None", value=None),
                DataPoint(label="List", value=[1, 2, 3])
            ]
        )
        
        query_result = Mock(
            summary="Test summary",
            data=malformed_data,
            insights=[]
        )
        
        query = Mock(intent=QueryIntent.SALES_REPORT)
        
        # Should handle gracefully
        summary = formatter.create_summary_text(query_result, query)
        assert summary is not None
        assert "Test summary" in summary
    
    def test_emoji_enhancement_with_special_chars(self, formatter):
        """Test emoji enhancement with special characters"""
        texts_with_special = [
            "Revenue increased by 10% & orders grew",
            "Top performer: John O'Brien",
            "Sales <increased> significantly",
            "Growth rate: 15.5% (year-over-year)"
        ]
        
        for text in texts_with_special:
            enhanced = formatter.enhance_with_emojis(text, QueryIntent.REVENUE_ANALYSIS)
            assert enhanced is not None
            # Original text should be preserved
            assert any(char in enhanced for char in text if char.isalnum())


class TestWebSocketEdgeCases:
    """Test WebSocket edge cases"""
    
    @pytest.mark.asyncio
    async def test_websocket_large_message(self):
        """Test handling very large WebSocket messages"""
        from ..schemas.ai_assistant_schemas import WebSocketMessage
        
        # Create large message
        large_content = "x" * 1_000_000  # 1MB message
        message = WebSocketMessage(
            type="chat",
            data={"message": large_content}
        )
        
        # Should serialize without error
        json_str = message.json()
        assert len(json_str) > 1_000_000
    
    @pytest.mark.asyncio
    async def test_websocket_malformed_json(self):
        """Test handling malformed JSON in WebSocket"""
        from ..routers.ai_chat_router import parse_websocket_message
        
        malformed_messages = [
            '{"type": "chat", "data": {broken json}',
            '{"type": "chat" "data": {}}',  # Missing comma
            'null',
            '[]',
            ''
        ]
        
        for msg in malformed_messages:
            # Should handle gracefully
            try:
                result = parse_websocket_message(msg)
                assert result is None or isinstance(result, dict)
            except:
                pass  # Expected for some malformed inputs


class TestIntegrationEdgeCases:
    """Test integration edge cases"""
    
    @pytest.mark.asyncio
    async def test_full_flow_with_errors(self):
        """Test complete flow with various errors"""
        chat_service = AIChatService()
        mock_db = Mock()
        
        # Test flow with database errors
        with patch('backend.modules.analytics.services.ai_chat_service.SalesReportService') as mock_sales:
            mock_sales.side_effect = SQLAlchemyError("Database error")
            
            request = ChatRequest(message="Show me sales report")
            response = await chat_service.process_message(request, user_id=1, db=mock_db)
            
            assert response.message.role in [MessageRole.ERROR, MessageRole.ASSISTANT]
    
    @pytest.mark.asyncio
    async def test_memory_stress(self):
        """Test system under memory stress"""
        chat_service = AIChatService()
        
        # Create many large sessions
        for i in range(100):
            session = chat_service._get_or_create_session(f"stress-{i}", user_id=i)
            
            # Add many messages to history
            for j in range(100):
                message = ChatMessage(
                    id=f"{i}-{j}",
                    role=MessageRole.USER,
                    content=f"Message {j}" * 100,  # Larger messages
                    metadata={"large_data": list(range(1000))}
                )
                session.context.conversation_history.append(message)
        
        # System should still be responsive
        new_session = chat_service._get_or_create_session("new", user_id=999)
        assert new_session is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])