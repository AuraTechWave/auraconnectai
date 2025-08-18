# Real-Time Table Status Updates

This module implements comprehensive real-time table management with WebSocket support for live updates, turn time tracking, and heat map visualization.

## Features

### 1. WebSocket Real-Time Updates
- Live table status changes
- Turn time tracking
- Occupancy monitoring
- Heat map visualization
- Alert notifications

### 2. Analytics APIs
- Current occupancy metrics
- Historical turn time analysis
- Peak hours identification
- Table performance metrics
- Reservation analytics

### 3. Enhanced Table Management
- Real-time status synchronization
- Multi-floor support
- Session tracking
- Automatic alerts for long turn times

## WebSocket Endpoints

### `/api/v1/tables/ws/tables/{restaurant_id}`
Main WebSocket endpoint for table status updates.

**Query Parameters:**
- `floor_id` (optional): Filter updates by floor
- `token`: JWT authentication token

**Message Types:**
- `initial_state`: Sent on connection with current state
- `table_status`: Table status changes
- `occupancy_update`: Occupancy metrics
- `turn_time_update`: Turn time metrics
- `heat_map_update`: Heat map visualization data
- `alert`: System alerts

**Client Messages:**
- `heartbeat`: Keep connection alive
- `request_update`: Request current state
- `subscribe_table`: Subscribe to specific table updates
- `unsubscribe_table`: Unsubscribe from table updates

### `/api/v1/tables/ws/analytics/{restaurant_id}`
Analytics-focused WebSocket for dashboards.

## REST API Endpoints

### Analytics Endpoints

#### `GET /api/v1/tables/analytics/current`
Get current real-time analytics.

**Response:**
```json
{
  "overview": {
    "total_tables": 20,
    "occupied_tables": 12,
    "available_tables": 8,
    "occupancy_rate": 60.0,
    "total_guests_seated": 45
  },
  "turn_times": {
    "current_average_minutes": 67.5,
    "today_average_minutes": 72.3,
    "active_sessions": 12,
    "completed_today": 34
  },
  "status_breakdown": {
    "OCCUPIED": 12,
    "AVAILABLE": 8
  },
  "timestamp": "2024-01-15T14:30:00Z"
}
```

#### `GET /api/v1/tables/analytics/turn-times`
Get turn time analytics for a date range.

**Parameters:**
- `start_date`: Start date (YYYY-MM-DD)
- `end_date`: End date (YYYY-MM-DD)
- `floor_id` (optional): Filter by floor
- `group_by`: Grouping method (`day`, `hour`, `day_of_week`)

#### `GET /api/v1/tables/analytics/performance`
Get performance metrics for tables.

**Parameters:**
- `start_date`: Start date
- `end_date`: End date
- `table_id` (optional): Specific table

#### `GET /api/v1/tables/analytics/peak-hours`
Analyze peak hours for table occupancy.

**Parameters:**
- `lookback_days`: Days to analyze (7-90)

#### `GET /api/v1/tables/analytics/heat-map`
Get heat map data for visualization.

**Parameters:**
- `floor_id` (optional): Filter by floor
- `period_days`: Days to analyze (1-30)

## Implementation Details

### Real-Time Manager
The `RealtimeTableManager` handles:
- WebSocket connection management
- Background update tasks
- Cache management
- Alert monitoring

### Analytics Service
The `TableAnalyticsService` provides:
- Turn time calculations
- Occupancy analysis
- Performance metrics
- Peak hours detection

### Background Tasks
- Turn time updates (every 30 seconds)
- Heat map generation
- Alert checking
- Cache warming

## Usage Example

### WebSocket Client (JavaScript)
```javascript
const ws = new WebSocket(`ws://localhost:8000/api/v1/tables/ws/tables/1?token=${token}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch(data.type) {
    case 'table_status':
      updateTableStatus(data.table_id, data.data);
      break;
    case 'turn_time_update':
      updateTurnTimes(data.data);
      break;
    case 'alert':
      showAlert(data.alerts);
      break;
  }
};

// Subscribe to specific table
ws.send(JSON.stringify({
  type: 'subscribe_table',
  table_id: 5
}));
```

### REST API Client
```python
import httpx

# Get current analytics
response = await client.get(
    "http://localhost:8000/api/v1/tables/analytics/current",
    headers={"Authorization": f"Bearer {token}"}
)
analytics = response.json()

# Get turn time trends
response = await client.get(
    "http://localhost:8000/api/v1/tables/analytics/turn-times",
    params={
        "start_date": "2024-01-01",
        "end_date": "2024-01-15",
        "group_by": "day"
    },
    headers={"Authorization": f"Bearer {token}"}
)
turn_times = response.json()
```

## Security

- JWT authentication required for all endpoints
- Restaurant isolation enforced
- Role-based access control
- Rate limiting on WebSocket connections

## Performance Considerations

- WebSocket connections are managed per restaurant
- Background tasks run at configurable intervals
- Caching implemented for frequently accessed data
- Database queries optimized with proper indexes

## Monitoring

The system provides:
- Connection metrics
- Update frequency tracking
- Cache hit rates
- Alert statistics

## Future Enhancements

1. Mobile push notifications for alerts
2. Predictive turn time estimates
3. AI-powered table assignment optimization
4. Integration with reservation system for better forecasting