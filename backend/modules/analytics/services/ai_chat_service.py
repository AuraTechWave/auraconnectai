# backend/modules/analytics/services/ai_chat_service.py

"""
AI Chat Service for Analytics Assistant.

This service manages chat sessions, processes messages, executes analytics queries,
and formats responses for the chat interface.
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text, func, and_

from backend.core.database import get_db
from ..schemas.ai_assistant_schemas import (
    ChatMessage, ChatRequest, ChatResponse, ChatSession, QueryContext,
    AnalyticsQuery, QueryResult, QueryIntent, MessageRole, MessageType,
    ChartData, TableData, DataPoint, ChartType, AnalyticsInsight,
    SuggestedQuery
)
from ..schemas.analytics_schemas import SalesFilterRequest
from .ai_query_processor import AIQueryProcessor
from .ai_security_service import AISecurityService
from .ai_result_formatter import AIResultFormatter
from .sales_report_service import SalesReportService
from .trend_service import TrendService
from .realtime_metrics_service import realtime_metrics_service

logger = logging.getLogger(__name__)


class AIChatService:
    """Service for managing AI analytics chat interactions"""
    
    def __init__(self):
        self.query_processor = AIQueryProcessor()
        self.security_service = AISecurityService()
        self.result_formatter = AIResultFormatter()
        self.sessions: Dict[str, ChatSession] = {}
        self.query_executors = self._initialize_query_executors()
        
    def _initialize_query_executors(self) -> Dict[QueryIntent, callable]:
        """Initialize query execution handlers for each intent"""
        return {
            QueryIntent.SALES_REPORT: self._execute_sales_report,
            QueryIntent.REVENUE_ANALYSIS: self._execute_revenue_analysis,
            QueryIntent.STAFF_PERFORMANCE: self._execute_staff_performance,
            QueryIntent.PRODUCT_ANALYSIS: self._execute_product_analysis,
            QueryIntent.TREND_ANALYSIS: self._execute_trend_analysis,
            QueryIntent.COMPARISON: self._execute_comparison,
            QueryIntent.FORECAST: self._execute_forecast,
            QueryIntent.GENERAL_QUESTION: self._execute_general_question,
            QueryIntent.HELP: self._execute_help_query,
        }
    
    async def process_message(
        self,
        request: ChatRequest,
        user_id: int,
        db: Session
    ) -> ChatResponse:
        """
        Process a user message and generate AI response.
        
        Args:
            request: Chat request with user message
            user_id: ID of the user
            db: Database session
            
        Returns:
            AI assistant response with query results
        """
        try:
            # Validate request for security
            is_valid, error_message = self.security_service.validate_request(request, user_id)
            if not is_valid:
                return self._create_error_response(error_message)
            
            # Sanitize input
            request.message = self.security_service.sanitize_input(request.message)
            
            # Get or create session
            session = self._get_or_create_session(request.session_id, user_id)
            
            # Create user message
            user_message = ChatMessage(
                id=str(uuid.uuid4()),
                role=MessageRole.USER,
                content=request.message,
                type=MessageType.TEXT,
                metadata=request.context
            )
            
            # Add to conversation history
            session.context.conversation_history.append(user_message)
            session.message_count += 1
            session.last_activity = datetime.now()
            
            # Process query
            query = self.query_processor.process_query(
                request.message,
                session.context
            )
            
            # Enhance with context
            query = self.query_processor.enhance_with_context(query, session.context)
            
            # Check if clarification is needed
            clarifications = self.query_processor.suggest_clarifications(query)
            if clarifications and query.confidence_score < 0.7:
                return self._create_clarification_response(
                    session.session_id,
                    query,
                    clarifications
                )
            
            # Check if query is allowed (complexity and rate limits)
            is_allowed, limit_message = self.security_service.is_query_allowed(query, user_id)
            if not is_allowed:
                return self._create_error_response(limit_message)
            
            # Execute query
            query_result = await self._execute_query(query, user_id, db)
            
            # Generate insights
            insights = await self._generate_insights(query, query_result, db)
            
            # Create assistant response
            response_text = self._format_response_text(query, query_result, insights)
            
            assistant_message = ChatMessage(
                id=str(uuid.uuid4()),
                role=MessageRole.ASSISTANT,
                content=response_text,
                type=MessageType.QUERY_RESULT if query_result.data else MessageType.TEXT,
                metadata={
                    'query': query.dict(),
                    'execution_time_ms': query_result.execution_time_ms
                }
            )
            
            # Add to conversation history
            session.context.conversation_history.append(assistant_message)
            
            # Generate suggested questions
            suggested_questions = self._generate_suggested_questions(query, query_result)
            
            return ChatResponse(
                message=assistant_message,
                query_result=query_result,
                suggested_questions=suggested_questions,
                requires_clarification=False
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return self._create_error_response(str(e))
    
    def _get_or_create_session(self, session_id: Optional[str], user_id: int) -> ChatSession:
        """Get existing session or create new one"""
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.last_activity = datetime.now()
            return session
        
        # Create new session
        new_session_id = session_id or str(uuid.uuid4())
        session = ChatSession(
            session_id=new_session_id,
            user_id=user_id,
            started_at=datetime.now(),
            last_activity=datetime.now(),
            context=QueryContext(
                session_id=new_session_id,
                user_id=user_id
            )
        )
        
        self.sessions[new_session_id] = session
        return session
    
    async def _execute_query(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute the analytics query based on intent"""
        start_time = datetime.now()
        
        try:
            # Get appropriate executor
            executor = self.query_executors.get(
                query.intent,
                self._execute_general_question
            )
            
            # Execute query
            result = await executor(query, user_id, db)
            
            # Calculate execution time
            execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            result.execution_time_ms = execution_time_ms
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return QueryResult(
                query_id=str(uuid.uuid4()),
                status="error",
                summary="Failed to execute query",
                error_message=str(e),
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000)
            )
    
    async def _execute_sales_report(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute sales report query"""
        try:
            # Build filters from query
            filters = SalesFilterRequest(
                date_from=query.time_range.get('start_date') if query.time_range else None,
                date_to=query.time_range.get('end_date') if query.time_range else None,
                staff_ids=query.filters.get('staff_ids') if query.filters else None,
                product_ids=query.filters.get('product_ids') if query.filters else None,
                category_ids=query.filters.get('category_ids') if query.filters else None
            )
            
            # Get sales summary
            service = SalesReportService(db)
            summary = service.generate_sales_summary(filters)
            
            # Format as chart data
            chart_data = ChartData(
                type=ChartType.BAR,
                title="Sales Summary",
                data=[
                    DataPoint(label="Revenue", value=float(summary.total_revenue)),
                    DataPoint(label="Orders", value=summary.total_orders),
                    DataPoint(label="Customers", value=summary.unique_customers),
                    DataPoint(label="Avg Order Value", value=float(summary.average_order_value))
                ],
                x_axis_label="Metrics",
                y_axis_label="Values"
            )
            
            # Build insights
            insights = []
            if summary.revenue_growth:
                insights.append(f"Revenue {'increased' if summary.revenue_growth > 0 else 'decreased'} by {abs(summary.revenue_growth):.1f}%")
            if summary.order_growth:
                insights.append(f"Order volume {'increased' if summary.order_growth > 0 else 'decreased'} by {abs(summary.order_growth):.1f}%")
            
            return QueryResult(
                query_id=str(uuid.uuid4()),
                status="success",
                summary=f"Sales report for {summary.period_start} to {summary.period_end}",
                data=chart_data,
                insights=insights
            )
            
        except Exception as e:
            logger.error(f"Error executing sales report: {e}")
            raise
    
    async def _execute_revenue_analysis(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute revenue analysis query"""
        try:
            # Get revenue trends
            trend_service = TrendService(db)
            
            start_date = date.fromisoformat(query.time_range['start_date'])
            end_date = date.fromisoformat(query.time_range['end_date'])
            
            # Determine granularity based on date range
            days_diff = (end_date - start_date).days
            granularity = "hourly" if days_diff <= 1 else "daily" if days_diff <= 30 else "weekly"
            
            trends = trend_service.get_revenue_trend(start_date, end_date, granularity)
            
            # Format as line chart
            chart_data = ChartData(
                type=ChartType.LINE,
                title="Revenue Trend Analysis",
                data=[
                    DataPoint(
                        label=point.date.strftime("%Y-%m-%d" if granularity == "daily" else "%H:00"),
                        value=float(point.value),
                        metadata={"change": point.change_percentage}
                    )
                    for point in trends
                ],
                x_axis_label="Time Period",
                y_axis_label="Revenue ($)"
            )
            
            # Calculate insights
            total_revenue = sum(p.value for p in trends)
            avg_revenue = total_revenue / len(trends) if trends else 0
            max_revenue = max(p.value for p in trends) if trends else 0
            min_revenue = min(p.value for p in trends) if trends else 0
            
            insights = [
                f"Total revenue: ${total_revenue:,.2f}",
                f"Average {granularity} revenue: ${avg_revenue:,.2f}",
                f"Peak revenue: ${max_revenue:,.2f}",
                f"Lowest revenue: ${min_revenue:,.2f}"
            ]
            
            return QueryResult(
                query_id=str(uuid.uuid4()),
                status="success",
                summary=f"Revenue analysis from {start_date} to {end_date}",
                data=chart_data,
                insights=insights
            )
            
        except Exception as e:
            logger.error(f"Error executing revenue analysis: {e}")
            raise
    
    async def _execute_staff_performance(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute staff performance query"""
        try:
            # Build filters
            filters = SalesFilterRequest(
                date_from=query.time_range.get('start_date') if query.time_range else None,
                date_to=query.time_range.get('end_date') if query.time_range else None,
                staff_ids=query.filters.get('staff_ids') if query.filters else None
            )
            
            # Get staff performance
            service = SalesReportService(db)
            performance = service.generate_staff_performance_report(filters, page=1, per_page=10)
            
            # Format as table
            table_data = TableData(
                columns=[
                    {"key": "name", "label": "Staff Member", "type": "string"},
                    {"key": "revenue", "label": "Revenue", "type": "currency"},
                    {"key": "orders", "label": "Orders", "type": "number"},
                    {"key": "efficiency", "label": "Efficiency Score", "type": "percentage"}
                ],
                rows=[
                    {
                        "name": staff.staff_name,
                        "revenue": float(staff.total_revenue_generated),
                        "orders": staff.total_orders_handled,
                        "efficiency": float(staff.efficiency_score) if staff.efficiency_score else 0
                    }
                    for staff in performance
                ],
                total_rows=len(performance)
            )
            
            # Generate insights
            if performance:
                top_performer = performance[0]
                insights = [
                    f"Top performer: {top_performer.staff_name} with ${top_performer.total_revenue_generated:,.2f} in revenue",
                    f"Average orders per staff: {sum(s.total_orders_handled for s in performance) / len(performance):.1f}",
                    f"Total team revenue: ${sum(s.total_revenue_generated for s in performance):,.2f}"
                ]
            else:
                insights = ["No staff performance data available for the selected period"]
            
            return QueryResult(
                query_id=str(uuid.uuid4()),
                status="success",
                summary="Staff performance report",
                data=table_data,
                insights=insights
            )
            
        except Exception as e:
            logger.error(f"Error executing staff performance: {e}")
            raise
    
    async def _execute_product_analysis(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute product analysis query"""
        try:
            # Build filters
            filters = SalesFilterRequest(
                date_from=query.time_range.get('start_date') if query.time_range else None,
                date_to=query.time_range.get('end_date') if query.time_range else None,
                product_ids=query.filters.get('product_ids') if query.filters else None,
                category_ids=query.filters.get('category_ids') if query.filters else None
            )
            
            # Get product performance
            service = SalesReportService(db)
            products = service.generate_product_performance_report(filters, page=1, per_page=10)
            
            # Format as pie chart for top products
            chart_data = ChartData(
                type=ChartType.PIE,
                title="Top Products by Revenue",
                data=[
                    DataPoint(
                        label=product.product_name,
                        value=float(product.revenue_generated),
                        metadata={"quantity": product.quantity_sold}
                    )
                    for product in products[:5]  # Top 5 products
                ]
            )
            
            # Generate insights
            if products:
                total_revenue = sum(p.revenue_generated for p in products)
                total_quantity = sum(p.quantity_sold for p in products)
                
                insights = [
                    f"Best selling product: {products[0].product_name} ({products[0].quantity_sold} units)",
                    f"Total products sold: {total_quantity} units",
                    f"Total product revenue: ${total_revenue:,.2f}",
                    f"Average revenue per product: ${total_revenue / len(products):,.2f}"
                ]
            else:
                insights = ["No product data available for the selected period"]
            
            return QueryResult(
                query_id=str(uuid.uuid4()),
                status="success",
                summary="Product performance analysis",
                data=chart_data,
                insights=insights
            )
            
        except Exception as e:
            logger.error(f"Error executing product analysis: {e}")
            raise
    
    async def _execute_trend_analysis(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute trend analysis query"""
        try:
            # Determine which metric to analyze
            metric = query.metrics[0] if query.metrics else "revenue"
            
            # Get trend data
            trend_service = TrendService(db)
            start_date = date.fromisoformat(query.time_range['start_date'])
            end_date = date.fromisoformat(query.time_range['end_date'])
            
            if metric == "revenue":
                trends = trend_service.get_revenue_trend(start_date, end_date, "daily")
            elif metric == "orders":
                trends = trend_service.get_order_trend(start_date, end_date, "daily")
            else:
                trends = trend_service.get_customer_trend(start_date, end_date, "daily")
            
            # Calculate trend statistics
            stats = trend_service.get_trend_statistics(trends)
            
            # Format as area chart
            chart_data = ChartData(
                type=ChartType.AREA,
                title=f"{metric.capitalize()} Trend Analysis",
                data=[
                    DataPoint(
                        label=point.date.strftime("%Y-%m-%d"),
                        value=float(point.value),
                        metadata={"change": point.change_percentage}
                    )
                    for point in trends
                ],
                x_axis_label="Date",
                y_axis_label=metric.capitalize()
            )
            
            # Generate insights based on statistics
            insights = []
            if stats['average_change'] > 0:
                insights.append(f"{metric.capitalize()} is trending upward with {stats['average_change']:.1f}% average daily growth")
            elif stats['average_change'] < 0:
                insights.append(f"{metric.capitalize()} is trending downward with {abs(stats['average_change']):.1f}% average daily decline")
            
            insights.extend([
                f"Peak {metric}: {stats['max_value']:.2f} on {stats['max_date']}",
                f"Lowest {metric}: {stats['min_value']:.2f} on {stats['min_date']}",
                f"Volatility: {stats['volatility']:.1f}%"
            ])
            
            return QueryResult(
                query_id=str(uuid.uuid4()),
                status="success",
                summary=f"{metric.capitalize()} trend analysis",
                data=chart_data,
                insights=insights
            )
            
        except Exception as e:
            logger.error(f"Error executing trend analysis: {e}")
            raise
    
    async def _execute_comparison(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute comparison query"""
        # This would implement period-over-period comparisons
        # For now, return a placeholder
        return QueryResult(
            query_id=str(uuid.uuid4()),
            status="success",
            summary="Comparison analysis",
            insights=["Comparison functionality will be implemented soon"]
        )
    
    async def _execute_forecast(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute forecast query"""
        # This would implement ML-based forecasting
        # For now, return a placeholder
        return QueryResult(
            query_id=str(uuid.uuid4()),
            status="success",
            summary="Forecast analysis",
            insights=["Forecasting functionality will be implemented soon"]
        )
    
    async def _execute_general_question(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute general question"""
        # Get current dashboard metrics as general response
        snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
        
        return QueryResult(
            query_id=str(uuid.uuid4()),
            status="success",
            summary="Current business overview",
            insights=[
                f"Today's revenue: ${snapshot.revenue_today:,.2f}",
                f"Orders today: {snapshot.orders_today}",
                f"Customers served: {snapshot.customers_today}",
                f"Average order value: ${snapshot.average_order_value:,.2f}"
            ]
        )
    
    async def _execute_help_query(
        self,
        query: AnalyticsQuery,
        user_id: int,
        db: Session
    ) -> QueryResult:
        """Execute help query"""
        help_text = """
        I can help you analyze your business data in various ways:
        
        📊 **Sales Reports**: "Show me today's sales" or "What's our revenue this month?"
        📈 **Trends**: "Show revenue trends for last week" or "How are sales trending?"
        👥 **Staff Performance**: "Who are the top performers?" or "Show staff productivity"
        📦 **Product Analysis**: "What are the best selling products?" or "Product performance report"
        🔄 **Comparisons**: "Compare this week vs last week" or "Revenue comparison by month"
        
        You can also specify filters like dates, staff members, or product categories.
        """
        
        return QueryResult(
            query_id=str(uuid.uuid4()),
            status="success",
            summary="How can I help you?",
            insights=[help_text]
        )
    
    def _format_response_text(
        self,
        query: AnalyticsQuery,
        result: QueryResult,
        insights: List[AnalyticsInsight]
    ) -> str:
        """Format response text for the chat"""
        # Use the formatter for enhanced formatting
        formatted_text = self.result_formatter.create_summary_text(result, query)
        
        # Add AI-generated insights if not already included
        if insights and not any("Analysis:" in formatted_text for _ in [1]):
            parts = [formatted_text]
            parts.append("\n**AI Analysis:**")
            for insight in insights[:2]:  # Top 2 AI insights
                parts.append(f"• {insight.description}")
            formatted_text = "\n".join(parts)
        
        # Enhance with emojis
        formatted_text = self.result_formatter.enhance_with_emojis(formatted_text, query.intent)
        
        return formatted_text
    
    async def _generate_insights(
        self,
        query: AnalyticsQuery,
        result: QueryResult,
        db: Session
    ) -> List[AnalyticsInsight]:
        """Generate AI insights based on query results"""
        insights = []
        
        # Generate insights based on data patterns
        if result.data and isinstance(result.data, ChartData):
            # Analyze trends in chart data
            if result.data.type == ChartType.LINE:
                values = [point.value for point in result.data.data if isinstance(point.value, (int, float))]
                if values:
                    trend = "increasing" if values[-1] > values[0] else "decreasing"
                    change_pct = ((values[-1] - values[0]) / values[0] * 100) if values[0] else 0
                    
                    insights.append(AnalyticsInsight(
                        type="trend",
                        title="Trend Detection",
                        description=f"The data shows a {trend} trend with {abs(change_pct):.1f}% change",
                        severity="info",
                        confidence=0.8
                    ))
        
        return insights
    
    def _generate_suggested_questions(
        self,
        query: AnalyticsQuery,
        result: QueryResult
    ) -> List[str]:
        """Generate suggested follow-up questions"""
        suggestions = []
        
        # Based on intent, suggest related queries
        intent_suggestions = {
            QueryIntent.SALES_REPORT: [
                "How does this compare to last month?",
                "Which products contributed most to revenue?",
                "Show me the hourly sales breakdown"
            ],
            QueryIntent.STAFF_PERFORMANCE: [
                "What's the average performance across all staff?",
                "Show me performance trends over time",
                "Which shifts are most productive?"
            ],
            QueryIntent.PRODUCT_ANALYSIS: [
                "What's the profit margin on these products?",
                "Show me sales by category",
                "Which products are trending up?"
            ],
            QueryIntent.TREND_ANALYSIS: [
                "What factors might be causing this trend?",
                "Forecast next week's performance",
                "Show me the same trend for last year"
            ]
        }
        
        suggestions = intent_suggestions.get(query.intent, [
            "Show me today's sales summary",
            "What are the top products?",
            "How is staff performing?"
        ])
        
        return suggestions[:3]  # Return top 3 suggestions
    
    def _create_clarification_response(
        self,
        session_id: str,
        query: AnalyticsQuery,
        clarifications: List[str]
    ) -> ChatResponse:
        """Create response asking for clarification"""
        message = ChatMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.ASSISTANT,
            content=f"I need a bit more information to help you better. {clarifications[0]}",
            type=MessageType.TEXT,
            metadata={'needs_clarification': True}
        )
        
        return ChatResponse(
            message=message,
            requires_clarification=True,
            clarification_options=clarifications[:3]
        )
    
    def _create_error_response(self, error_message: str) -> ChatResponse:
        """Create error response"""
        message = ChatMessage(
            id=str(uuid.uuid4()),
            role=MessageRole.ERROR,
            content=f"I encountered an error while processing your request: {error_message}",
            type=MessageType.ERROR
        )
        
        return ChatResponse(
            message=message,
            requires_clarification=False
        )
    
    def get_session_history(self, session_id: str) -> Optional[List[ChatMessage]]:
        """Get conversation history for a session"""
        if session_id in self.sessions:
            return self.sessions[session_id].context.conversation_history
        return None
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a chat session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    async def get_suggested_queries(self, user_id: int, db: Session) -> List[SuggestedQuery]:
        """Get suggested queries for quick access"""
        # Get current metrics for context
        snapshot = await realtime_metrics_service.get_current_dashboard_snapshot()
        
        suggestions = [
            SuggestedQuery(
                text="Show me today's sales report",
                category="Sales",
                description="Get a comprehensive overview of today's sales performance",
                icon="📊"
            ),
            SuggestedQuery(
                text="How is revenue trending this week?",
                category="Trends",
                description="Analyze revenue patterns and trends",
                icon="📈"
            ),
            SuggestedQuery(
                text="Who are the top performing staff members?",
                category="Staff",
                description="See staff performance rankings",
                icon="👥"
            ),
            SuggestedQuery(
                text="What are the best selling products today?",
                category="Products",
                description="Analyze product performance",
                icon="📦"
            ),
            SuggestedQuery(
                text="Compare this week to last week",
                category="Comparison",
                description="Week-over-week performance comparison",
                icon="🔄"
            )
        ]
        
        return suggestions
    
    def get_rate_limit_status(self, user_id: int) -> Dict[str, Any]:
        """Get rate limit status for a user"""
        return self.security_service.get_rate_limit_status(user_id)