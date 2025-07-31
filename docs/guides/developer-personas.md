# Developer Personas & Use Cases

This guide helps different types of developers quickly find the most relevant documentation for their needs.

## 🚀 Frontend Developer

**Goal**: Build user interfaces that connect to AuraConnect APIs

### Quick Links
- [API Reference](../api/README.md) - REST endpoints documentation
- [Authentication Guide](../api/auth.md) - JWT token handling
- [JavaScript SDK](../api/sdks.md#javascript) - Pre-built client library
- [WebSocket Events](../api/webhooks.md) - Real-time updates

### Common Tasks
1. **Set up authentication**
   ```javascript
   const client = new AuraConnectClient({
     apiKey: 'your-api-key',
     baseUrl: 'https://api.auraconnect.com'
   });
   ```

2. **Create an order**
   ```javascript
   const order = await client.orders.create({
     items: [...],
     customerId: 123
   });
   ```

3. **Subscribe to real-time updates**
   ```javascript
   client.orders.subscribe(orderId, (event) => {
     console.log('Order status:', event.status);
   });
   ```

## 🔧 Backend Developer

**Goal**: Extend AuraConnect functionality or integrate with existing systems

### Quick Links
- [Architecture Overview](../architecture/README.md) - System design
- [Module Development](../modules/README.md) - Creating new modules
- [Database Schema](../architecture/database.md) - Data models
- [Event System](../architecture/events.md) - Inter-module communication

### Common Tasks
1. **Create a custom module**
   ```python
   from auraconnect.core import BaseModule
   
   class CustomModule(BaseModule):
       def __init__(self):
           super().__init__("custom_module")
   ```

2. **Listen to system events**
   ```python
   @event_handler("order.created")
   async def on_order_created(order_data):
       # Custom logic here
       pass
   ```

## 🏪 Restaurant Owner/Manager

**Goal**: Deploy and configure AuraConnect for your restaurant

### Quick Links
- [Getting Started](getting-started.md) - Initial setup
- [Docker Deployment](../deployment/docker.md) - Quick deployment
- [Configuration Guide](configuration.md) - System settings
- [User Guides](users/README.md) - Day-to-day operations

### Common Tasks
1. **Deploy with Docker**
   ```bash
   docker-compose up -d
   ```

2. **Configure your restaurant**
   - Set up locations
   - Import menu items
   - Add staff members
   - Configure tax rates

## 🔌 Integration Developer

**Goal**: Connect AuraConnect with third-party systems

### Quick Links
- [POS Integration](../modules/pos/README.md) - Square, Clover, Toast
- [Webhooks](../api/webhooks.md) - Event notifications
- [API Authentication](../api/auth.md) - Secure access
- [Data Import/Export](../guides/data-migration.md) - Bulk operations

### Common Tasks
1. **Set up webhook listener**
   ```python
   @app.post("/webhook")
   async def handle_webhook(request: Request):
       event = await request.json()
       if event["type"] == "order.created":
           # Process new order
           pass
   ```

2. **Sync with POS system**
   ```python
   from auraconnect.integrations import POSAdapter
   
   adapter = POSAdapter("square", api_key="...")
   await adapter.sync_menu_items()
   ```

## 🔐 DevOps Engineer

**Goal**: Deploy, monitor, and scale AuraConnect infrastructure

### Quick Links
- [Deployment Guide](../deployment/README.md) - Production setup
- [Kubernetes Deployment](../deployment/kubernetes.md) - Container orchestration
- [Monitoring Setup](../deployment/monitoring.md) - Metrics and logging
- [Scaling Guide](../deployment/scaling.md) - Performance optimization

### Common Tasks
1. **Deploy to Kubernetes**
   ```bash
   kubectl apply -f k8s/
   ```

2. **Set up monitoring**
   ```yaml
   # prometheus values
   serviceMonitor:
     enabled: true
     interval: 30s
   ```

3. **Configure auto-scaling**
   ```yaml
   apiVersion: autoscaling/v2
   kind: HorizontalPodAutoscaler
   spec:
     minReplicas: 3
     maxReplicas: 10
   ```

## 📱 Mobile Developer

**Goal**: Build mobile apps that integrate with AuraConnect

### Quick Links
- [API Reference](../api/README.md) - REST endpoints
- [Authentication](../api/auth.md) - Mobile auth flow
- [Push Notifications](../api/notifications.md) - Mobile notifications
- [Offline Sync](../guides/offline-sync.md) - Handle connectivity issues

### Common Tasks
1. **Implement mobile authentication**
   ```swift
   let auth = AuraConnectAuth(
     clientId: "mobile-app",
     redirectUri: "auraconnect://callback"
   )
   ```

2. **Handle offline orders**
   ```kotlin
   val order = Order(items = listOf(...))
   orderQueue.add(order)
   syncManager.syncWhenOnline()
   ```

## 🧪 QA Engineer

**Goal**: Test AuraConnect implementations

### Quick Links
- [API Testing Guide](../guides/testing.md#api-testing) - Test strategies
- [Test Data Setup](../guides/test-data.md) - Sample data
- [Error Reference](../reference/errors.md) - Error codes
- [Performance Testing](../guides/performance-testing.md) - Load testing

### Common Tasks
1. **Set up test environment**
   ```bash
   docker-compose -f docker-compose.test.yml up
   ```

2. **Run API tests**
   ```bash
   pytest tests/api/ -v
   ```

3. **Load testing**
   ```bash
   locust -f tests/load/orders.py --host=http://localhost:8000
   ```

## Next Steps

Based on your role:

1. **Start with Quick Start**: [Getting Started Guide](getting-started.md)
2. **Explore your area**: Use the quick links above
3. **Join the community**: [Discord](https://discord.gg/auraconnect)
4. **Get help**: [Support](../support.md)

---

Can't find what you're looking for? Check our [FAQ](faq.md) or [contact support](../support.md).