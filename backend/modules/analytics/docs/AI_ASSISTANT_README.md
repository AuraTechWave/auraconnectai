# AI Analytics Assistant Documentation

## Overview

The AI Analytics Assistant is a natural language processing (NLP) powered chat interface that allows users to query analytics data using conversational language. It integrates with the existing analytics services to provide insights, generate reports, and visualize data through an intuitive chat experience.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   User Interface                         │
│                 (Chat Widget/API)                        │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              WebSocket/REST API                          │
│            (ai_chat_router.py)                          │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│            AI Chat Service                               │
│         (ai_chat_service.py)                            │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────┐ │
│  │   Session   │ │    Query     │ │     Result      │ │
│  │ Management  │ │  Execution   │ │   Formatting    │ │
│  └─────────────┘ └──────────────┘ └─────────────────┘ │
└────────────────────┬────────────────────────────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
┌────▼──────┐ ┌─────▼──────┐ ┌─────▼──────┐
│  Query    │ │  Security  │ │   Result   │
│ Processor │ │  Service   │ │ Formatter  │
└───────────┘ └────────────┘ └────────────┘
```

## Core Components

### 1. AI Query Processor (`ai_query_processor.py`)

Handles natural language understanding and query parsing.

**Key Features:**
- Intent detection using regex patterns
- Entity extraction (dates, staff, products, amounts)
- Time range parsing (relative and absolute dates)
- Query enhancement with conversation context

**Supported Intents:**
- `SALES_REPORT`: Sales summaries and reports
- `REVENUE_ANALYSIS`: Revenue trends and analytics
- `STAFF_PERFORMANCE`: Staff productivity metrics
- `PRODUCT_ANALYSIS`: Product performance data
- `TREND_ANALYSIS`: Time-based trend analysis
- `COMPARISON`: Period-over-period comparisons
- `FORECAST`: Predictive analytics (placeholder)
- `HELP`: Usage instructions
- `GENERAL_QUESTION`: Catch-all for unclear queries

### 2. AI Chat Service (`ai_chat_service.py`)

Manages chat sessions and orchestrates query execution.

**Key Features:**
- Session management with conversation history
- Query execution routing based on intent
- Integration with existing analytics services
- Error handling and recovery
- Suggested follow-up questions

**Session Management:**
- Unique session IDs for each conversation
- Conversation history tracking
- Context preservation for follow-up queries
- Automatic session cleanup

### 3. AI Security Service (`ai_security_service.py`)

Provides security and rate limiting for the AI assistant.

**Security Features:**
- Input validation and sanitization
- SQL injection prevention
- XSS attack prevention
- Sensitive data detection (credit cards, SSN, etc.)
- Rate limiting per user

**Rate Limits:**
- Messages: 20 per minute
- Queries: 100 per hour
- Complex queries: 50 per day

### 4. AI Result Formatter (`ai_result_formatter.py`)

Formats query results for optimal user experience.

**Features:**
- Smart chart type recommendations
- Natural language summaries
- Value formatting (currency, percentages, numbers)
- Emoji enhancement for readability
- Error message formatting

### 5. WebSocket Router (`ai_chat_router.py`)

Provides real-time chat capabilities.

**Endpoints:**
- `GET /analytics/ai-assistant/chat` - WebSocket connection
- `POST /analytics/ai-assistant/message` - REST API for single messages
- `GET /analytics/ai-assistant/suggestions` - Get suggested queries
- `GET /analytics/ai-assistant/history/{session_id}` - Get chat history
- `DELETE /analytics/ai-assistant/session/{session_id}` - Clear session

## Usage Examples

### Basic Query Examples

```python
# Sales queries
"Show me today's sales"
"What's our revenue this month?"
"Give me the sales report for last week"

# Staff performance
"Who are the top performers?"
"Show staff productivity this month"
"Which employee sold the most?"

# Product analysis
"What are the best selling products?"
"Show me product performance"
"Which categories are trending?"

# Trend analysis
"How is revenue trending?"
"Show me the sales trend for last 30 days"
"Compare this week to last week"
```

### Advanced Query Examples

```python
# Time-based filtering
"Show me sales from January 1st to January 31st"
"Revenue for the last 7 days"
"Yesterday's performance metrics"

# Entity-specific queries
"Show me sales for staff #123"
"Product Coffee performance this month"
"Orders above $100 today"

# Complex queries
"Compare revenue between this month and last month"
"Show me top 5 products by revenue with their trends"
"Staff performance grouped by shift"
```

## Integration Guide

### Frontend Integration

See `ui/chat_integration_example.md` for complete examples.

```javascript
// Initialize connection
const chatClient = new AnalyticsChatClient(authToken);
await chatClient.connect();

// Send message
chatClient.sendMessage("Show me today's sales");

// Handle responses
chatClient.onMessage('chat', (data) => {
  console.log('Assistant:', data.message);
  if (data.query_result) {
    renderChart(data.query_result.data);
  }
});
```

### Backend Integration

```python
from backend.modules.analytics.services.ai_chat_service import AIChatService
from backend.modules.analytics.schemas.ai_assistant_schemas import ChatRequest

# Initialize service
chat_service = AIChatService()

# Process message
request = ChatRequest(
    message="Show me revenue trends",
    session_id="user-session-123"
)
response = await chat_service.process_message(
    request, 
    user_id=current_user.id,
    db=db_session
)
```

## Security Considerations

1. **Authentication**: All requests must include valid authentication tokens
2. **Input Validation**: All user inputs are sanitized and validated
3. **Rate Limiting**: Prevents abuse and ensures fair usage
4. **Data Access**: Respects user permissions and data access controls
5. **Sensitive Data**: Automatically detects and rejects sensitive information

## Performance Optimization

1. **Query Caching**: Frequently requested data is cached
2. **Efficient Routing**: Queries are routed to specific executors
3. **Batch Operations**: Multiple related queries are batched
4. **Connection Pooling**: WebSocket connections are efficiently managed
5. **Result Pagination**: Large results are paginated automatically

## Error Handling

The system provides user-friendly error messages:

- **Invalid Input**: "Please check your query format"
- **Rate Limit**: "You've exceeded the rate limit. Please try again later"
- **Database Error**: "Unable to fetch data. Please try again"
- **Timeout**: "Query took too long. Try narrowing your search"

## Testing

Comprehensive test coverage includes:

- Unit tests for each component
- Integration tests for the full flow
- Edge case testing for error scenarios
- Performance testing for scalability
- Security testing for vulnerabilities

Run tests:
```bash
pytest backend/modules/analytics/tests/test_ai_assistant.py -v
pytest backend/modules/analytics/tests/test_ai_edge_cases.py -v
```

## Monitoring and Logging

- All queries are logged with user ID and timestamp
- Error tracking for failed queries
- Performance metrics for query execution time
- Rate limit monitoring per user
- Security event logging

## Future Enhancements

1. **Machine Learning**: Implement ML-based intent detection
2. **Multi-language Support**: Add support for multiple languages
3. **Voice Input**: Add speech-to-text capabilities
4. **Advanced Analytics**: Implement forecasting and predictive analytics
5. **Custom Dashboards**: Allow users to save custom queries as dashboards

## Troubleshooting

### Common Issues

1. **WebSocket Connection Failed**
   - Check authentication token
   - Verify WebSocket endpoint URL
   - Check CORS configuration

2. **Rate Limit Exceeded**
   - Wait for rate limit reset
   - Check rate limit status endpoint
   - Consider query optimization

3. **Query Not Understood**
   - Rephrase query more clearly
   - Use suggested queries as examples
   - Check supported intent patterns

### Debug Mode

Enable debug logging:
```python
import logging
logging.getLogger('backend.modules.analytics').setLevel(logging.DEBUG)
```

## API Reference

See the schema definitions in `schemas/ai_assistant_schemas.py` for complete API documentation.