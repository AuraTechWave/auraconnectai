# Order Prioritization Algorithms Guide

## Overview

The AuraConnect order prioritization system provides intelligent queue management through configurable algorithms that optimize order processing based on multiple factors. This system moves beyond simple FIFO (First-In-First-Out) to ensure VIP customers are served promptly, delivery windows are met, and kitchen efficiency is maximized.

## Key Features

- **Multiple Priority Algorithms**: Preparation time, delivery window, VIP status, order value, wait time, and complexity-based prioritization
- **Composite Scoring**: Combine multiple algorithms with customizable weights
- **Real-time Rebalancing**: Automatic queue reordering based on changing conditions
- **Fairness Monitoring**: Ensure equitable service while meeting business priorities
- **Performance Analytics**: Track algorithm effectiveness and business impact

## Architecture

### Core Components

1. **Priority Rules**: Individual algorithms that calculate scores based on specific factors
2. **Priority Profiles**: Collections of rules with weights that define overall prioritization strategy
3. **Queue Configuration**: Per-queue settings for priority boosts and rebalancing behavior
4. **Priority Service**: Core engine that calculates scores and manages queue rebalancing

### Data Models

```python
# Priority Rule
{
    "name": "Delivery Window Priority",
    "algorithm_type": "delivery_window",
    "weight": 3.0,
    "parameters": {
        "grace_minutes": 10,
        "critical_minutes": 30
    }
}

# Priority Profile
{
    "name": "Lunch Rush Profile",
    "rules": [
        {"rule_id": 1, "weight_override": 4.0},  # Delivery window
        {"rule_id": 2, "weight_override": 2.0},  # VIP status
        {"rule_id": 3, "weight_override": 1.0}   # Order value
    ],
    "normalize_scores": true
}

# Queue Configuration
{
    "queue_id": 1,
    "priority_profile_id": 1,
    "priority_boost_vip": 20.0,
    "rebalance_enabled": true,
    "rebalance_interval": 300
}
```

## Available Algorithms

### 1. Preparation Time Priority

Prioritizes orders based on estimated preparation time to optimize kitchen flow.

**Parameters:**
- `base_minutes`: Expected preparation time baseline
- `penalty_per_minute`: Score reduction for each minute over baseline

**Use Case:** Prioritize quick orders during rush hours to maximize throughput.

### 2. Delivery Window Priority

Ensures orders are completed by their promised time.

**Parameters:**
- `grace_minutes`: Time before delivery when priority increases
- `critical_minutes`: Time window for maximum priority boost

**Scoring:**
- Already late: Maximum priority (100)
- Within grace period: 90% of maximum
- Within critical period: Linear scale based on time remaining
- Plenty of time: Minimum priority

### 3. VIP Status Priority

Rewards loyal customers with faster service.

**Parameters:**
- `tier_scores`: Score for each customer tier
  - Bronze: 10
  - Silver: 20
  - Gold: 30
  - Platinum: 50
  - VIP: 100

**Additional Factors:**
- Customer lifetime value adds bonus points
- Recent order frequency can influence score

### 4. Order Value Priority

Prioritizes higher-value orders to maximize revenue per time unit.

**Parameters:**
- `min_value`: Minimum order value for scoring
- `max_value`: Order value for maximum score

**Use Case:** Ensure large catering orders receive appropriate attention.

### 5. Wait Time Priority

Prevents any order from waiting too long, ensuring fairness.

**Parameters:**
- `base_wait_minutes`: Acceptable wait time
- `max_wait_minutes`: Maximum wait before highest priority

**Purpose:** Acts as a fairness mechanism to prevent starvation.

### 6. Item Complexity Priority

Considers order complexity to balance kitchen workload.

**Parameters:**
- `item_weights`: Complexity weight for each menu category
- `complexity_threshold`: Threshold for simple vs. complex orders

**Note:** Lower complexity orders typically get higher priority for faster throughput.

## Implementation Guide

### 1. Create Priority Rules

```bash
POST /api/v1/priorities/rules
{
    "name": "Peak Hours Delivery Priority",
    "algorithm_type": "delivery_window",
    "weight": 3.0,
    "min_score": 0,
    "max_score": 100,
    "parameters": {
        "grace_minutes": 15,
        "critical_minutes": 45
    },
    "conditions": {
        "order_type": ["delivery", "takeout"],
        "time_ranges": [{
            "start_hour": 11,
            "end_hour": 14
        }]
    }
}
```

### 2. Create Priority Profile

```bash
POST /api/v1/priorities/profiles
{
    "name": "Weekend Brunch Profile",
    "is_active": true,
    "queue_types": ["kitchen", "bar"],
    "time_ranges": [{
        "days": [0, 6],  # Sunday and Saturday
        "start_hour": 9,
        "end_hour": 15
    }],
    "rule_assignments": [
        {
            "rule_id": 1,
            "weight_override": 2.0,
            "min_threshold": 20
        },
        {
            "rule_id": 2,
            "weight_override": 3.0
        }
    ]
}
```

### 3. Configure Queue Priority

```bash
POST /api/v1/priorities/queues/config
{
    "queue_id": 1,
    "priority_profile_id": 1,
    "priority_boost_vip": 25.0,
    "priority_boost_delayed": 20.0,
    "rebalance_enabled": true,
    "rebalance_interval": 300,
    "peak_hours": [{
        "days": [1, 2, 3, 4, 5],
        "start_hour": 11,
        "end_hour": 14
    }],
    "peak_multiplier": 1.5
}
```

### 4. Calculate Priority

```bash
POST /api/v1/priorities/calculate
{
    "order_id": 123,
    "queue_id": 1
}

Response:
{
    "order_id": 123,
    "queue_id": 1,
    "total_score": 156.5,
    "normalized_score": 78.25,
    "score_components": {
        "delivery_window": {
            "score": 65,
            "weight": 3.0,
            "weighted_score": 195
        },
        "vip_status": {
            "score": 30,
            "weight": 1.5,
            "weighted_score": 45
        }
    },
    "priority_tier": "high",
    "suggested_sequence": 2
}
```

## Scoring Functions

### Linear Scaling
Default scoring function that provides proportional scores.

### Exponential Scaling
Emphasizes differences at the high end of the scale.
```python
score = min_score + (exp(normalized) - 1) / (e - 1) * (max_score - min_score)
```

### Logarithmic Scaling
Compresses differences at the high end, expanding low-end differences.
```python
score = min_score + log(1 + normalized * 9) / log(10) * (max_score - min_score)
```

### Step Function
Discrete priority levels based on thresholds.
```python
thresholds = [25, 50, 75]
if value <= 25: return "low"
elif value <= 50: return "medium"
elif value <= 75: return "high"
else: return "critical"
```

## Queue Rebalancing

### Automatic Rebalancing

The system can automatically reorder queue items based on current priorities:

1. **Trigger**: Time-based (every N seconds) or event-based (new order, status change)
2. **Process**: 
   - Recalculate all active item priorities
   - Sort by priority score
   - Apply position change limits
   - Update sequence numbers
3. **Constraints**: Maximum position changes prevent drastic reordering

### Manual Priority Adjustment

Staff can manually override calculated priorities:

```bash
POST /api/v1/priorities/adjust
{
    "order_id": 123,
    "queue_id": 1,
    "new_priority": 95.0,
    "reason": "Customer complaint - expedite order"
}
```

## Fairness and Performance Metrics

### Fairness Index

Uses the Gini coefficient to measure wait time distribution:
- 1.0 = Perfect fairness (all orders wait equally)
- 0.0 = Complete unfairness (extreme wait time variation)

### Key Metrics Tracked

1. **Effectiveness Metrics**
   - Average wait time reduction vs. FIFO
   - On-time delivery rate
   - VIP satisfaction score

2. **Fairness Metrics**
   - Fairness index
   - Maximum wait time ratio
   - Priority override count

3. **Performance Metrics**
   - Average calculation time
   - Rebalance frequency
   - Average position changes

4. **Business Impact**
   - Revenue impact
   - Customer complaints
   - Staff override frequency

## Best Practices

### 1. Profile Design

- **Peak Hours**: Create separate profiles for rush periods with aggressive prioritization
- **Off-Peak**: Use balanced profiles that emphasize fairness
- **Special Events**: Design profiles for catering or large party scenarios

### 2. Weight Tuning

- Start with equal weights and adjust based on metrics
- Monitor fairness index to prevent excessive bias
- Use A/B testing to compare profile effectiveness

### 3. Rebalancing Strategy

- Enable rebalancing during peak hours for optimal flow
- Set reasonable position change limits (3-5 positions)
- Longer intervals (5-10 minutes) for stable operations

### 4. VIP Management

- Balance VIP benefits with overall fairness
- Use moderate boosts (15-25 points) rather than extreme values
- Consider VIP density in your customer base

## Integration Examples

### With Kitchen Display System

```python
# When order added to KDS
def add_order_to_kds(order_id: int):
    # Calculate priority
    priority_score = priority_service.calculate_order_priority(
        order_id=order_id,
        queue_id=kitchen_queue.id
    )
    
    # Add to queue with calculated position
    queue_service.add_to_queue(
        QueueItemCreate(
            queue_id=kitchen_queue.id,
            order_id=order_id,
            priority=priority_score.normalized_score
        )
    )
```

### With POS Systems

```python
# When order synced from POS
def sync_pos_order(pos_order: dict):
    # Create order
    order = create_order_from_pos(pos_order)
    
    # Check for VIP customer
    if pos_order.get("customer_tier") == "VIP":
        order.priority = OrderPriority.HIGH
    
    # Calculate and apply priority
    for queue in applicable_queues:
        priority_service.calculate_order_priority(
            order_id=order.id,
            queue_id=queue.id
        )
```

## Monitoring and Alerts

### Real-time Monitoring

```bash
GET /api/v1/priorities/metrics
{
    "queue_id": 1,
    "start_date": "2024-01-01T00:00:00Z",
    "end_date": "2024-01-01T23:59:59Z",
    "granularity": "hour"
}
```

### Alert Conditions

1. **Fairness Alert**: Fairness index drops below 0.6
2. **Wait Time Alert**: Maximum wait exceeds 2x average
3. **Override Alert**: Manual overrides exceed 10% of orders
4. **Performance Alert**: Rebalancing takes > 1 second

## Troubleshooting

### Common Issues

1. **Orders Not Prioritizing Correctly**
   - Verify profile is active and assigned to queue
   - Check rule conditions match order attributes
   - Ensure rebalancing is enabled

2. **Excessive Rebalancing**
   - Increase rebalance interval
   - Reduce position change limits
   - Review rule weights for stability

3. **Poor Fairness Metrics**
   - Add wait time priority rule
   - Reduce VIP/value boosts
   - Enable normalization in profile

4. **Performance Issues**
   - Reduce rebalance frequency
   - Limit active rules per profile
   - Index order attributes used in conditions

## Future Enhancements

1. **Machine Learning Integration**
   - Predict preparation times based on historical data
   - Dynamic weight adjustment based on outcomes
   - Anomaly detection for unusual patterns

2. **Advanced Algorithms**
   - Multi-objective optimization
   - Constraint-based scheduling
   - Predictive queue management

3. **Enhanced Analytics**
   - Real-time dashboards
   - Predictive wait time estimates
   - Customer satisfaction correlation

4. **Integration Expansions**
   - Calendar integration for event-based profiles
   - Weather API for demand prediction
   - Traffic data for delivery prioritization