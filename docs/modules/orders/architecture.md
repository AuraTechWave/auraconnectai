# Orders Module Architecture

## Overview

The Orders module follows a domain-driven design (DDD) approach with clear separation between the API layer, business logic, and data persistence. It's designed for high throughput, real-time updates, and seamless integration with other AuraConnect modules.

## Architecture Principles

1. **Event-Driven**: All state changes trigger events for real-time updates
2. **Idempotent Operations**: Safe retry mechanisms for critical operations
3. **Eventual Consistency**: Asynchronous updates for non-critical paths
4. **Fault Tolerance**: Graceful degradation when dependencies are unavailable
5. **Scalability**: Horizontal scaling support through stateless design

## System Components

### 1. API Layer

```mermaid
graph LR
    subgraph "API Gateway"
        NGINX[Nginx]
        AUTH[Auth Middleware]
        RATE[Rate Limiter]
    end
    
    subgraph "Order API"
        ROUTES[FastAPI Routes]
        VALID[Request Validator]
        SERIAL[Serializers]
    end
    
    subgraph "Business Logic"
        SVC[Order Service]
        PROC[Order Processor]
        STATE[State Machine]
    end
    
    NGINX --> AUTH
    AUTH --> RATE
    RATE --> ROUTES
    ROUTES --> VALID
    VALID --> SERIAL
    SERIAL --> SVC
    SVC --> PROC
    PROC --> STATE
```

### 2. Core Services

#### Order Service
```python
class OrderService:
    def __init__(self, 
                 order_repo: OrderRepository,
                 menu_client: MenuServiceClient,
                 inventory_client: InventoryServiceClient,
                 payment_client: PaymentServiceClient):
        self.order_repo = order_repo
        self.menu_client = menu_client
        self.inventory_client = inventory_client
        self.payment_client = payment_client
        
    async def create_order(self, order_data: OrderCreate) -> Order:
        # Validate menu items
        # Check inventory
        # Calculate pricing
        # Create order
        # Publish event
        pass
```

#### State Management
```python
class OrderStateMachine:
    TRANSITIONS = {
        OrderStatus.PENDING: [OrderStatus.CONFIRMED, OrderStatus.CANCELLED],
        OrderStatus.CONFIRMED: [OrderStatus.PREPARING, OrderStatus.CANCELLED],
        OrderStatus.PREPARING: [OrderStatus.READY, OrderStatus.CANCELLED],
        OrderStatus.READY: [OrderStatus.COMPLETED],
        OrderStatus.COMPLETED: [],
        OrderStatus.CANCELLED: []
    }
    
    def transition(self, order: Order, new_status: OrderStatus) -> Order:
        if new_status not in self.TRANSITIONS[order.status]:
            raise InvalidStateTransition()
        
        order.status = new_status
        order.status_history.append(StatusChange(
            from_status=order.status,
            to_status=new_status,
            timestamp=datetime.utcnow()
        ))
        
        return order
```

### 3. Data Layer

#### Repository Pattern
```python
class OrderRepository:
    def __init__(self, db: Database, cache: Redis):
        self.db = db
        self.cache = cache
        
    async def create(self, order: Order) -> Order:
        # Save to database
        # Update cache
        # Return created order
        pass
        
    async def get_by_id(self, order_id: int) -> Optional[Order]:
        # Check cache first
        # Fallback to database
        # Update cache if found
        pass
```

#### Database Schema
```sql
-- Orders table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    order_number VARCHAR(50) UNIQUE NOT NULL,
    customer_id INTEGER,
    location_id INTEGER NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    subtotal DECIMAL(10,2) NOT NULL,
    tax_amount DECIMAL(10,2) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);

-- Indexes for performance
CREATE INDEX idx_orders_tenant_status ON orders(tenant_id, status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);
CREATE INDEX idx_orders_customer ON orders(customer_id);
```

### 4. Event System

```mermaid
graph TD
    subgraph "Order Events"
        CREATE[order.created]
        UPDATE[order.updated]
        STATUS[order.status_changed]
    end
    
    subgraph "Event Bus"
        REDIS[Redis Pub/Sub]
        CELERY[Celery Tasks]
    end
    
    subgraph "Subscribers"
        KITCHEN[Kitchen Service]
        INVENTORY[Inventory Service]
        ANALYTICS[Analytics Service]
        NOTIFY[Notification Service]
    end
    
    CREATE --> REDIS
    UPDATE --> REDIS
    STATUS --> REDIS
    
    REDIS --> KITCHEN
    REDIS --> INVENTORY
    REDIS --> ANALYTICS
    REDIS --> NOTIFY
    
    STATUS --> CELERY
    CELERY --> INVENTORY
```

#### Event Publishing
```python
class OrderEventPublisher:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        
    async def publish_order_created(self, order: Order):
        event = {
            "event_type": "order.created",
            "timestamp": datetime.utcnow().isoformat(),
            "data": {
                "order_id": order.id,
                "order_number": order.order_number,
                "customer_id": order.customer_id,
                "total_amount": str(order.total_amount),
                "items": [item.dict() for item in order.items]
            }
        }
        
        await self.redis.publish(
            f"orders:{order.tenant_id}",
            json.dumps(event)
        )
```

### 5. Integration Architecture

```mermaid
graph TB
    subgraph "Orders Module"
        ORDER_API[Order API]
        ORDER_SVC[Order Service]
        ORDER_DB[(Order DB)]
    end
    
    subgraph "External Services"
        MENU[Menu Service]
        INV[Inventory Service]
        PAY[Payment Service]
        CUST[Customer Service]
    end
    
    subgraph "Integration Layer"
        CLIENT[Service Clients]
        CIRCUIT[Circuit Breaker]
        RETRY[Retry Logic]
    end
    
    ORDER_SVC --> CLIENT
    CLIENT --> CIRCUIT
    CIRCUIT --> RETRY
    
    RETRY --> MENU
    RETRY --> INV
    RETRY --> PAY
    RETRY --> CUST
```

#### Service Client Example
```python
class MenuServiceClient:
    def __init__(self, base_url: str, timeout: int = 5):
        self.base_url = base_url
        self.timeout = timeout
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=30
        )
        
    @retry(max_attempts=3, backoff=exponential_backoff)
    async def validate_items(self, items: List[OrderItem]) -> ValidationResult:
        if not self.circuit_breaker.is_closed():
            raise ServiceUnavailable("Menu service is unavailable")
            
        try:
            response = await httpx.post(
                f"{self.base_url}/validate",
                json={"items": [item.dict() for item in items]},
                timeout=self.timeout
            )
            response.raise_for_status()
            return ValidationResult(**response.json())
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise
```

### 6. Caching Strategy

```mermaid
graph LR
    subgraph "Cache Layers"
        L1[Application Cache]
        L2[Redis Cache]
        L3[Database]
    end
    
    subgraph "Cache Patterns"
        ASIDE[Cache Aside]
        THROUGH[Write Through]
        BEHIND[Write Behind]
    end
    
    REQUEST[API Request] --> L1
    L1 -->|Miss| L2
    L2 -->|Miss| L3
    
    L3 -->|Data| L2
    L2 -->|Data| L1
    L1 -->|Response| REQUEST
    
    ASIDE --> L1
    THROUGH --> L2
    BEHIND --> L3
```

#### Cache Implementation
```python
class OrderCache:
    def __init__(self, redis: Redis, ttl: int = 1800):
        self.redis = redis
        self.ttl = ttl
        
    async def get(self, order_id: int) -> Optional[Order]:
        key = f"order:{order_id}"
        data = await self.redis.get(key)
        
        if data:
            return Order.parse_raw(data)
        return None
        
    async def set(self, order: Order):
        key = f"order:{order.id}"
        await self.redis.setex(
            key,
            self.ttl,
            order.json()
        )
        
    async def invalidate(self, order_id: int):
        key = f"order:{order_id}"
        await self.redis.delete(key)
```

### 7. Performance Optimization

#### Database Query Optimization
```python
class OptimizedOrderQueries:
    @staticmethod
    def get_orders_with_items(db: Database, filters: OrderFilters):
        # Use single query with joins instead of N+1
        query = """
        SELECT 
            o.*,
            json_agg(
                json_build_object(
                    'id', oi.id,
                    'menu_item_id', oi.menu_item_id,
                    'quantity', oi.quantity,
                    'price', oi.price,
                    'modifiers', oi.modifiers
                ) ORDER BY oi.id
            ) as items
        FROM orders o
        LEFT JOIN order_items oi ON o.id = oi.order_id
        WHERE o.tenant_id = :tenant_id
        """
        
        # Add dynamic filters
        if filters.status:
            query += " AND o.status = :status"
        if filters.date_from:
            query += " AND o.created_at >= :date_from"
            
        query += " GROUP BY o.id ORDER BY o.created_at DESC"
        
        return db.fetch_all(query, filters.dict())
```

#### Async Processing
```python
@app.post("/api/v1/orders")
async def create_order(order_data: OrderCreate):
    # Quick validation and order creation
    order = await order_service.create_order(order_data)
    
    # Async tasks for non-critical operations
    background_tasks.add_task(
        inventory_service.reserve_items,
        order.items
    )
    
    background_tasks.add_task(
        notification_service.send_confirmation,
        order
    )
    
    background_tasks.add_task(
        analytics_service.track_order,
        order
    )
    
    return order
```

### 8. Monitoring and Observability

```python
# Metrics collection
from prometheus_client import Counter, Histogram, Gauge

order_created_counter = Counter(
    'orders_created_total',
    'Total number of orders created',
    ['order_type', 'location']
)

order_processing_time = Histogram(
    'order_processing_seconds',
    'Time spent processing orders',
    ['operation']
)

active_orders_gauge = Gauge(
    'orders_active',
    'Number of active orders',
    ['status']
)

# Usage
@order_processing_time.labels(operation='create').time()
async def create_order(order_data: OrderCreate) -> Order:
    order = await process_order(order_data)
    
    order_created_counter.labels(
        order_type=order.order_type,
        location=order.location_id
    ).inc()
    
    active_orders_gauge.labels(
        status=order.status
    ).inc()
    
    return order
```

### 9. Security Considerations

#### Input Validation
```python
class OrderValidator:
    def validate_order_items(self, items: List[OrderItemCreate]):
        if not items:
            raise ValidationError("Order must contain at least one item")
            
        if len(items) > MAX_ITEMS_PER_ORDER:
            raise ValidationError(f"Order cannot exceed {MAX_ITEMS_PER_ORDER} items")
            
        for item in items:
            if item.quantity <= 0:
                raise ValidationError("Item quantity must be positive")
                
            if item.quantity > MAX_ITEM_QUANTITY:
                raise ValidationError(f"Item quantity cannot exceed {MAX_ITEM_QUANTITY}")
```

#### Authorization
```python
class OrderAuthorization:
    def can_view_order(self, user: User, order: Order) -> bool:
        # Admin can view all orders
        if user.role == UserRole.ADMIN:
            return True
            
        # Staff can view orders from their location
        if user.role == UserRole.STAFF:
            return order.location_id in user.location_ids
            
        # Customers can view their own orders
        if user.role == UserRole.CUSTOMER:
            return order.customer_id == user.customer_id
            
        return False
```

### 10. Deployment Architecture

```yaml
# docker-compose.yml
version: '3.8'

services:
  orders-api:
    build: ./modules/orders
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/orders
      - REDIS_URL=redis://redis:6379/0
      - MENU_SERVICE_URL=http://menu-api:8001
      - INVENTORY_SERVICE_URL=http://inventory-api:8003
    ports:
      - "8002:8000"
    depends_on:
      - postgres
      - redis
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

## Architecture Decision Records (ADRs)

### ADR-001: Event-Driven Architecture
**Decision**: Use event-driven architecture for order state changes
**Rationale**: Enables real-time updates, loose coupling, and scalability

### ADR-002: CQRS Pattern
**Decision**: Separate read and write models for orders
**Rationale**: Optimizes performance for different access patterns

### ADR-003: Saga Pattern for Distributed Transactions
**Decision**: Use saga pattern for multi-service operations
**Rationale**: Maintains consistency without distributed transactions

## Related Documentation

- [API Reference](./api-reference.md)
- [Database Schema](./database-schema.md)
- [Integration Guide](./integration-guide.md)
- [Performance Guide](../guides/performance.md)

---

*Last Updated: January 2025*