# Order Queue Management System Guide

## Overview

The Order Queue Management System provides a centralized interface for managing active orders, adjusting their sequence, and monitoring preparation status across different service areas (kitchen, bar, delivery, etc.). It supports real-time updates, priority management, and comprehensive analytics.

## Key Features

- **Multiple Queue Types**: Kitchen, Bar, Delivery, Takeout, Dine-in, Catering, Drive-thru
- **Priority & Sequencing**: Automatic and manual priority adjustments
- **Real-time Updates**: WebSocket support for live queue status
- **Hold Management**: Temporary holds with automatic release
- **Transfer Operations**: Move orders between queues
- **Analytics Dashboard**: Performance metrics and insights
- **Capacity Management**: Queue limits and overflow handling
- **Staff Assignment**: Assign orders to specific staff members

## Queue Types

### 1. Kitchen Queue
Main preparation queue for food orders
```json
{
  "queue_type": "kitchen",
  "typical_prep_time": 15,
  "max_capacity": 50
}
```

### 2. Bar Queue
Beverage preparation queue
```json
{
  "queue_type": "bar",
  "typical_prep_time": 5,
  "max_capacity": 20
}
```

### 3. Delivery Queue
Orders ready for delivery dispatch
```json
{
  "queue_type": "delivery",
  "typical_prep_time": 30,
  "includes_travel_time": true
}
```

### 4. Takeout Queue
Customer pickup orders
```json
{
  "queue_type": "takeout",
  "display_customer_name": true,
  "notification_enabled": true
}
```

## API Endpoints

### Queue Management

#### Create Queue
```http
POST /api/v1/orders/queues
{
  "name": "Main Kitchen",
  "queue_type": "kitchen",
  "display_name": "Kitchen Orders",
  "max_capacity": 50,
  "default_prep_time": 15,
  "warning_threshold": 5,
  "critical_threshold": 10,
  "color_code": "#FF5733"
}
```

#### List Queues
```http
GET /api/v1/orders/queues?queue_type=kitchen&status=active
```

#### Get Queue Status
```http
GET /api/v1/orders/queues/{queue_id}/status
```

Response:
```json
{
  "queue_id": 1,
  "queue_name": "Main Kitchen",
  "status": "active",
  "current_size": 12,
  "active_items": 8,
  "ready_items": 3,
  "on_hold_items": 1,
  "avg_wait_time": 12.5,
  "longest_wait_time": 25.0,
  "next_ready_time": "2024-01-20T14:30:00Z",
  "staff_assigned": 4,
  "capacity_percentage": 24.0
}
```

### Queue Item Operations

#### Add to Queue
```http
POST /api/v1/orders/queues/{queue_id}/items
{
  "order_id": 12345,
  "priority": 5,
  "is_expedited": false,
  "display_name": "Table 5 - 2x Burger, 1x Salad",
  "customer_name": "John Doe",
  "estimated_ready_time": "2024-01-20T14:45:00Z"
}
```

#### Update Item Status
```http
PUT /api/v1/orders/queues/items/{item_id}
{
  "status": "in_preparation",
  "assigned_to_id": 123,
  "station_id": 1
}
```

Status Flow:
```
queued → in_preparation → ready → completed
   ↓           ↓             ↓
on_hold    on_hold      on_hold
   ↓           ↓             
cancelled  cancelled
```

#### Move Item in Queue
```http
POST /api/v1/orders/queues/items/move
{
  "item_id": 456,
  "new_position": 1,
  "reason": "VIP customer"
}
```

#### Transfer Between Queues
```http
POST /api/v1/orders/queues/items/transfer
{
  "item_id": 456,
  "target_queue_id": 2,
  "maintain_priority": true,
  "reason": "Moved to bar for drinks"
}
```

#### Expedite Item
```http
POST /api/v1/orders/queues/items/expedite
{
  "item_id": 456,
  "priority_boost": 20,
  "move_to_front": true,
  "reason": "Customer complaint - urgent"
}
```

#### Hold Item
```http
POST /api/v1/orders/queues/items/hold
{
  "item_id": 456,
  "hold_until": "2024-01-20T15:00:00Z",
  "reason": "Customer requested later pickup"
}
```

Or with duration:
```http
{
  "item_id": 456,
  "hold_minutes": 30,
  "reason": "Waiting for special ingredient"
}
```

#### Batch Status Update
```http
POST /api/v1/orders/queues/items/batch-status
{
  "item_ids": [456, 457, 458],
  "new_status": "ready",
  "reason": "Batch completed"
}
```

## Sequence Rules

Define automatic prioritization rules:

```http
POST /api/v1/orders/queues/{queue_id}/rules
{
  "name": "VIP Customer Priority",
  "description": "Boost priority for VIP customers",
  "is_active": true,
  "priority": 100,
  "conditions": {
    "customer.vip_status": true
  },
  "priority_adjustment": 15,
  "auto_expedite": true
}
```

### Rule Conditions

Available condition fields:
- `order.type`: Order type (dine_in, takeout, delivery)
- `order.total_amount_gt`: Order total greater than value
- `customer.vip_status`: Customer VIP status
- `customer.order_count_gt`: Customer order history
- `item.categories`: Item categories included
- `context.time_of_day`: Current time period
- `context.is_peak_hour`: Peak hour detection

### Rule Actions

- `priority_adjustment`: Add/subtract from priority (-50 to +50)
- `sequence_adjustment`: Move up/down in queue (-10 to +10)
- `auto_expedite`: Automatically mark as expedited
- `assign_to_station`: Route to specific station

## Real-time Updates

### WebSocket Connection

Connect to receive live updates:
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/orders/queues/ws/1');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log('Queue update:', update);
};
```

### Update Events

- `item_added`: New item added to queue
- `item_updated`: Item status or details changed
- `item_moved`: Item position changed
- `item_removed`: Item removed from queue
- `queue_updated`: Queue configuration changed

### Multi-Queue Subscription

Subscribe to multiple queues:
```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/orders/queues/ws/subscribe');

ws.onopen = () => {
  ws.send(JSON.stringify({
    action: 'subscribe',
    data: {
      queue_ids: [1, 2, 3],
      event_types: ['item_added', 'item_updated']
    }
  }));
};
```

## Analytics

### Dashboard View
```http
GET /api/v1/orders/queues/analytics/dashboard?time_range=today
```

Response includes:
- Current queue status for all queues
- Performance metrics (wait times, completion rates)
- Volume trends
- Staff utilization

### Queue Performance
```http
GET /api/v1/orders/queues/analytics/performance/{queue_id}?days=7
```

Returns:
- Wait time distribution
- Hourly performance patterns
- Daily trends
- Bottleneck identification
- Recommendations

### Staff Utilization
```http
GET /api/v1/orders/queues/analytics/staff-utilization?start_date=2024-01-01&end_date=2024-01-20
```

Shows:
- Items processed per staff member
- Average handling time
- Efficiency scores

### Peak Analysis
```http
GET /api/v1/orders/queues/analytics/peak-analysis?days=7
```

Provides:
- Heat map of busy periods
- Peak hour identification
- Staffing recommendations

## Queue Display Configuration

Configure display screens:

```http
POST /api/v1/orders/queues/displays
{
  "name": "Kitchen Display 1",
  "display_type": "kitchen",
  "queues_shown": [1, 2],
  "layout": "grid",
  "items_per_page": 20,
  "refresh_interval": 30,
  "status_filter": ["queued", "in_preparation"],
  "hide_completed_after": 300,
  "theme": "dark",
  "show_prep_time": true,
  "enable_sound": true,
  "alert_new_item": true,
  "alert_delayed": true
}
```

## Background Tasks

The system runs automatic background tasks:

### 1. Hold Release Monitor
- Checks every minute for expired holds
- Automatically releases items back to queue
- Logs all automatic releases

### 2. Metrics Updater
- Updates queue performance metrics every 5 minutes
- Calculates rolling averages
- Tracks capacity utilization

### 3. Delay Monitor
- Checks for delayed items every 2 minutes
- Updates delay status
- Triggers alerts for significant delays

## Best Practices

### 1. Queue Configuration
- Set appropriate capacity limits
- Configure warning/critical thresholds
- Use meaningful display names
- Assign distinct colors for visual identification

### 2. Priority Management
- Use priority levels 0-100
- Reserve high priorities (80+) for urgent cases
- Implement sequence rules for automation
- Document priority guidelines

### 3. Hold Usage
- Always provide clear hold reasons
- Set reasonable hold durations
- Monitor held items regularly
- Release holds promptly when ready

### 4. Status Updates
- Update status promptly at each stage
- Assign staff when starting preparation
- Mark items ready immediately
- Complete items when delivered/picked up

### 5. Performance Monitoring
- Review daily analytics
- Identify peak periods
- Monitor wait time trends
- Adjust staffing based on data

## Error Handling

Common errors and solutions:

### Queue at Capacity
```json
{
  "error": "Queue 'Main Kitchen' is at capacity",
  "solution": "Clear completed items or increase capacity"
}
```

### Invalid Status Transition
```json
{
  "error": "Invalid status transition from queued to completed",
  "solution": "Follow proper status flow: queued → in_preparation → ready → completed"
}
```

### Order Already in Queue
```json
{
  "error": "Order 12345 is already in queue",
  "solution": "Check existing queue items before adding"
}
```

## Integration Examples

### Adding Order After Creation
```python
# After creating order
order = create_order(...)

# Add to appropriate queue
queue_item = {
    "order_id": order.id,
    "priority": calculate_priority(order),
    "display_name": generate_display_name(order),
    "customer_name": order.customer.name
}

# Determine queue based on order type
if has_food_items(order):
    add_to_queue(kitchen_queue_id, queue_item)
if has_drink_items(order):
    add_to_queue(bar_queue_id, queue_item)
```

### Monitoring Queue Performance
```python
# Get hourly metrics
metrics = get_queue_metrics(
    queue_id=kitchen_queue_id,
    start_date=today_start,
    end_date=now,
    granularity="hour"
)

# Check for issues
if metrics["avg_wait_time"] > 20:
    send_alert("Kitchen queue wait time exceeds 20 minutes")
    
if metrics["capacity_percentage"] > 80:
    send_alert("Kitchen queue approaching capacity")
```

### Handling Rush Periods
```python
# Detect rush period
if is_peak_hour():
    # Adjust queue settings
    update_queue(kitchen_queue_id, {
        "warning_threshold": 10,  # Increase from 5
        "critical_threshold": 15  # Increase from 10
    })
    
    # Activate rush hour rules
    activate_sequence_rule("rush_hour_routing")
```

## Troubleshooting

### Queue Not Updating
1. Check WebSocket connection
2. Verify queue status is ACTIVE
3. Check for database locks
4. Review background task logs

### Items Stuck in Status
1. Check for failed status transitions
2. Review item history
3. Manually update if needed
4. Check staff assignments

### Performance Issues
1. Monitor queue sizes
2. Check database indexes
3. Review rule complexity
4. Optimize display queries

## Security Considerations

- Authenticate all API requests
- Validate queue permissions
- Audit all queue operations
- Encrypt sensitive customer data
- Rate limit API endpoints
- Monitor for unusual patterns