# Order Routing Rules Configuration Guide

## Overview

The Order Routing Rules system provides a flexible, rule-based engine for automatically routing orders to appropriate kitchen stations, staff members, teams, or work queues based on configurable conditions and priorities.

## Key Features

- **Rule-Based Routing**: Define conditions to match orders and route them accordingly
- **Priority System**: Rules are evaluated in priority order (highest first)
- **Conflict Detection**: Automatic detection of conflicting rules
- **Manual Overrides**: Ability to manually override routing decisions
- **Team Load Balancing**: Distribute orders among team members using various strategies
- **Staff Capabilities**: Define what each staff member can handle
- **Testing Mode**: Test rules with mock data before activation

## Rule Components

### 1. Conditions

Conditions determine when a rule matches an order. Multiple conditions can be combined using AND/OR logic.

#### Field Paths

- `order.type` - Order type (dine_in, takeout, delivery)
- `order.total` - Total order amount
- `order.item_count` - Number of items in order
- `order.status` - Current order status
- `order.priority` - Order priority level
- `order.scheduled_time` - Scheduled fulfillment time
- `customer.vip_status` - Whether customer is VIP
- `customer.order_count` - Customer's total order count
- `item.categories` - Categories of items in order
- `item.has_alcohol` - Whether order contains alcohol
- `context.time_of_day` - Current time period (breakfast, lunch, dinner, etc.)
- `context.day_of_week` - Current day of week
- `context.is_peak_hour` - Whether it's peak hours

#### Operators

- `equals` - Exact match
- `not_equals` - Not equal to value
- `contains` - Contains substring
- `not_contains` - Does not contain substring
- `in` - Value is in list
- `not_in` - Value is not in list
- `greater_than` - Numeric greater than
- `less_than` - Numeric less than
- `between` - Numeric between two values
- `regex` - Regular expression match

#### Condition Groups

Conditions can be grouped for complex logic:
- Conditions within a group use AND logic
- Different groups use OR logic

Example: (Group 0: high_value AND dinner_time) OR (Group 1: vip_customer)

### 2. Actions

Actions define what happens when a rule matches:

- **route** - Route to specific target
- **notify** - Send notifications
- **tag** - Add tags to order
- **priority** - Adjust order priority
- **split** - Split order into multiple parts
- **log** - Log specific information
- **webhook** - Trigger external webhook

### 3. Targets

Where orders can be routed:

- **station** - Kitchen station (grill, salad, bar, etc.)
- **staff** - Specific staff member
- **team** - Team with load balancing
- **queue** - Work queue for later processing

## Configuration Examples

### Example 1: Route High-Value Orders to Senior Staff

```json
{
  "name": "High Value Orders",
  "description": "Route orders over $100 to senior staff",
  "priority": 100,
  "target_type": "staff",
  "target_id": 123,
  "conditions": [
    {
      "field_path": "order.total",
      "operator": "greater_than",
      "value": 100.0,
      "condition_group": 0
    }
  ],
  "actions": [
    {
      "action_type": "route",
      "action_config": {"priority": "high"},
      "execution_order": 0
    },
    {
      "action_type": "notify",
      "action_config": {
        "channel": "slack",
        "message": "High value order assigned"
      },
      "execution_order": 1
    }
  ]
}
```

### Example 2: Route Alcohol Orders to Certified Staff

```json
{
  "name": "Alcohol Service",
  "description": "Route orders with alcohol to certified staff",
  "priority": 90,
  "target_type": "team",
  "target_id": 456,
  "conditions": [
    {
      "field_path": "item.has_alcohol",
      "operator": "equals",
      "value": true,
      "condition_group": 0
    }
  ],
  "actions": [
    {
      "action_type": "route",
      "action_config": {
        "require_capability": "alcohol_service"
      },
      "execution_order": 0
    }
  ]
}
```

### Example 3: Peak Hour Load Distribution

```json
{
  "name": "Peak Hour Distribution",
  "description": "Distribute orders during peak hours",
  "priority": 80,
  "target_type": "team",
  "target_id": 789,
  "conditions": [
    {
      "field_path": "context.is_peak_hour",
      "operator": "equals",
      "value": true,
      "condition_group": 0
    }
  ],
  "actions": [
    {
      "action_type": "route",
      "action_config": {
        "strategy": "least_loaded"
      },
      "execution_order": 0
    }
  ],
  "schedule_config": {
    "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
    "hours": {
      "start": "11:00",
      "end": "14:00"
    }
  }
}
```

## Team Configuration

### Routing Strategies

1. **round_robin** - Distribute orders evenly in sequence
2. **least_loaded** - Send to member with fewest active orders
3. **skill_based** - Match based on required capabilities
4. **priority_based** - Consider member weights and priorities
5. **random** - Random distribution

### Team Setup Example

```json
{
  "team_name": "Kitchen Brigade",
  "description": "Main kitchen team",
  "routing_strategy": "least_loaded",
  "max_concurrent_orders": 20,
  "specializations": ["grill", "saute", "salad"],
  "load_balancing_config": {
    "max_per_member": 5,
    "rebalance_interval": 300
  }
}
```

## Staff Capabilities

Define what each staff member can handle:

### Capability Types

- **category** - Menu categories (grill, salad, dessert)
- **station** - Kitchen stations they can work
- **skill** - Special skills (sushi_chef, bartender)
- **certification** - Required certifications (alcohol_service, allergen_handling)

### Capability Example

```json
{
  "staff_id": 123,
  "capability_type": "category",
  "capability_value": "grill",
  "max_concurrent_orders": 3,
  "skill_level": 4,
  "preference_weight": 1.5,
  "available_schedule": {
    "days": ["monday", "tuesday", "wednesday"],
    "hours": {
      "start": "10:00",
      "end": "18:00"
    }
  }
}
```

## Manual Overrides

Override automatic routing for specific orders:

```json
{
  "order_id": 12345,
  "override_type": "manual",
  "target_type": "staff",
  "target_id": 456,
  "reason": "Customer requested specific chef",
  "expires_at": "2024-12-25T18:00:00Z"
}
```

## Testing Rules

Test rules before activation using mock order data:

```json
{
  "rule_id": 123,
  "test_order_data": {
    "total": 125.50,
    "status": "pending",
    "table_no": 5,
    "customer": {
      "vip_status": true
    },
    "items": [
      {
        "menu_item_id": 1,
        "quantity": 2,
        "price": 25.00
      }
    ]
  }
}
```

## Conflict Resolution

### Priority Conflicts

When multiple rules have the same priority:
1. System logs a warning
2. First rule (by ID) is used
3. Conflict information is included in routing decision

### Avoiding Conflicts

1. Use unique priorities for rules
2. Make conditions mutually exclusive
3. Use the conflict detection endpoint regularly
4. Review rule analytics for overlaps

## Best Practices

1. **Start Simple**: Begin with basic rules and add complexity gradually
2. **Use Clear Names**: Give rules descriptive names for easy management
3. **Test First**: Always test rules with mock data before activation
4. **Monitor Performance**: Check rule analytics regularly
5. **Document Changes**: Keep notes on why rules were created/modified
6. **Regular Reviews**: Periodically review and optimize rules
7. **Handle Failures**: Always have a default routing strategy

## API Endpoints

### Rule Management
- `POST /api/v1/orders/routing/rules` - Create new rule
- `GET /api/v1/orders/routing/rules` - List all rules
- `GET /api/v1/orders/routing/rules/{id}` - Get specific rule
- `PUT /api/v1/orders/routing/rules/{id}` - Update rule
- `DELETE /api/v1/orders/routing/rules/{id}` - Delete rule

### Rule Evaluation
- `POST /api/v1/orders/routing/evaluate` - Evaluate routing for an order
- `POST /api/v1/orders/routing/test` - Test rules with mock data

### Conflict Detection
- `GET /api/v1/orders/routing/conflicts` - Check for rule conflicts

### Analytics
- `GET /api/v1/orders/routing/analytics/rule-performance` - Get rule performance metrics
- `POST /api/v1/orders/routing/logs/query` - Query routing logs

### Team Management
- `POST /api/v1/orders/routing/teams` - Create team
- `GET /api/v1/orders/routing/teams` - List teams
- `POST /api/v1/orders/routing/teams/{id}/members` - Add team member

### Staff Capabilities
- `POST /api/v1/orders/routing/staff/capabilities` - Create capability
- `GET /api/v1/orders/routing/staff/{id}/capabilities` - Get staff capabilities

## Troubleshooting

### Common Issues

1. **Rules Not Matching**
   - Check rule status (must be ACTIVE)
   - Verify condition field paths and values
   - Use test endpoint to debug
   - Check rule schedule if configured

2. **Unexpected Routing**
   - Check for priority conflicts
   - Look for active overrides
   - Review routing logs
   - Verify target availability

3. **Performance Issues**
   - Limit number of active rules
   - Optimize condition complexity
   - Use appropriate indexes
   - Monitor evaluation times

### Debug Mode

Enable detailed logging for troubleshooting:
- Include `debug: true` in evaluation requests
- Check routing logs for detailed evaluation results
- Use test mode to simulate without applying changes