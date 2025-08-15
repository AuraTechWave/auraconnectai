# backend/modules/analytics/schemas/ai_assistant_schemas.py

"""
Schemas for AI Analytics Assistant chat interface.

These schemas define the structure for chat messages, queries, and responses
between the user and the AI assistant for analytics queries.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    """Role of the message sender"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ERROR = "error"


class MessageType(str, Enum):
    """Type of message content"""

    TEXT = "text"
    QUERY_RESULT = "query_result"
    CHART = "chart"
    TABLE = "table"
    SUGGESTION = "suggestion"
    ERROR = "error"
    LOADING = "loading"


class QueryIntent(str, Enum):
    """Detected intent of user query"""

    SALES_REPORT = "sales_report"
    REVENUE_ANALYSIS = "revenue_analysis"
    STAFF_PERFORMANCE = "staff_performance"
    PRODUCT_ANALYSIS = "product_analysis"
    TREND_ANALYSIS = "trend_analysis"
    COMPARISON = "comparison"
    FORECAST = "forecast"
    GENERAL_QUESTION = "general_question"
    HELP = "help"
    UNKNOWN = "unknown"


class ChartType(str, Enum):
    """Types of charts for data visualization"""

    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    AREA = "area"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    GAUGE = "gauge"
    SPARKLINE = "sparkline"


class ChatMessage(BaseModel):
    """Individual chat message"""

    id: str = Field(..., description="Unique message ID")
    role: MessageRole
    content: str
    type: MessageType = MessageType.TEXT
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class QueryContext(BaseModel):
    """Context information for query processing"""

    session_id: str
    user_id: int
    conversation_history: List[ChatMessage] = []
    current_filters: Optional[Dict[str, Any]] = None
    preferred_visualization: Optional[ChartType] = None
    time_zone: Optional[str] = "UTC"
    language: str = "en"

    @validator("conversation_history")
    def limit_history_size(cls, v):
        """Keep only last 20 messages to prevent context overflow"""
        return v[-20:] if len(v) > 20 else v


class AnalyticsQuery(BaseModel):
    """Parsed analytics query from user input"""

    original_text: str
    intent: QueryIntent
    entities: Dict[str, Any] = {}
    time_range: Optional[Dict[str, Any]] = None
    filters: Optional[Dict[str, Any]] = None
    metrics: List[str] = []
    group_by: Optional[List[str]] = None
    sort_by: Optional[str] = None
    limit: Optional[int] = None
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)


class DataPoint(BaseModel):
    """Single data point for charts/tables"""

    label: str
    value: Union[float, int, str]
    metadata: Optional[Dict[str, Any]] = None


class ChartData(BaseModel):
    """Data structure for chart visualization"""

    type: ChartType
    title: str
    data: List[DataPoint]
    x_axis_label: Optional[str] = None
    y_axis_label: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class TableData(BaseModel):
    """Data structure for table visualization"""

    columns: List[
        Dict[str, str]
    ]  # [{"key": "name", "label": "Staff Name", "type": "string"}]
    rows: List[Dict[str, Any]]
    total_rows: Optional[int] = None
    page: Optional[int] = 1
    per_page: Optional[int] = 10


class QueryResult(BaseModel):
    """Result of an analytics query"""

    query_id: str
    status: str = "success"  # success, error, partial
    summary: str
    data: Optional[Union[ChartData, TableData, Dict[str, Any]]] = None
    insights: Optional[List[str]] = None
    suggestions: Optional[List[str]] = None
    execution_time_ms: Optional[int] = None
    error_message: Optional[str] = None


class ChatRequest(BaseModel):
    """User chat request"""

    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

    @validator("message")
    def clean_message(cls, v):
        """Clean and validate user message"""
        return v.strip()


class ChatResponse(BaseModel):
    """AI assistant response"""

    message: ChatMessage
    query_result: Optional[QueryResult] = None
    suggested_questions: Optional[List[str]] = None
    requires_clarification: bool = False
    clarification_options: Optional[List[str]] = None


class ChatSession(BaseModel):
    """Chat session information"""

    session_id: str
    user_id: int
    started_at: datetime
    last_activity: datetime
    message_count: int = 0
    context: QueryContext
    is_active: bool = True


class SuggestedQuery(BaseModel):
    """Suggested query for quick access"""

    text: str
    category: str
    description: Optional[str] = None
    icon: Optional[str] = None


class QueryTemplate(BaseModel):
    """Template for common queries"""

    id: str
    name: str
    description: str
    query_pattern: str
    parameters: List[Dict[str, Any]]
    category: str
    examples: List[str]


class ConversationSummary(BaseModel):
    """Summary of a conversation for history"""

    session_id: str
    user_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    message_count: int
    queries_executed: int
    topics_discussed: List[str]
    key_insights: List[str]


class AnalyticsInsight(BaseModel):
    """AI-generated insight from data analysis"""

    type: str  # trend, anomaly, recommendation, comparison
    title: str
    description: str
    severity: str = "info"  # info, warning, critical
    data_points: Optional[List[DataPoint]] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    action_items: Optional[List[str]] = None


class WebSocketMessage(BaseModel):
    """WebSocket message format for real-time chat"""

    type: str  # chat, typing, status, error
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AssistantCapabilities(BaseModel):
    """Capabilities and limitations of the AI assistant"""

    supported_queries: List[str]
    supported_metrics: List[str]
    supported_time_ranges: List[str]
    supported_visualizations: List[ChartType]
    max_results_per_query: int
    rate_limits: Dict[str, int]
    available_data_sources: List[str]


class FeedbackRequest(BaseModel):
    """User feedback on assistant response"""

    message_id: str
    session_id: str
    rating: int = Field(..., ge=1, le=5)
    feedback_text: Optional[str] = None
    was_helpful: bool
    improvement_suggestions: Optional[List[str]] = None
