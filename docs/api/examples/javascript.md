# JavaScript SDK Examples

This page provides examples of using the AuraConnect API with JavaScript/TypeScript.

## Installation

```bash
npm install @auraconnect/sdk
# or
yarn add @auraconnect/sdk
# or
pnpm add @auraconnect/sdk
```

## Basic Usage

### Initialize Client

```javascript
import { AuraConnectClient } from '@auraconnect/sdk';

// Initialize with API key
const client = new AuraConnectClient({
  baseURL: 'https://api.auraconnect.ai',
  apiKey: 'your-api-key'
});

// Or with email/password authentication
const client = new AuraConnectClient({
  baseURL: 'https://api.auraconnect.ai'
});

await client.auth.login({
  email: 'admin@auraconnect.ai',
  password: 'your-password'
});
```

### TypeScript Configuration

```typescript
import { 
  AuraConnectClient, 
  Order, 
  MenuItem, 
  AuthResponse 
} from '@auraconnect/sdk';

const client = new AuraConnectClient({
  baseURL: process.env.AURACONNECT_API_URL!,
  apiKey: process.env.AURACONNECT_API_KEY
});
```

## Authentication

### Login and Token Management

```javascript
// Login with credentials
const authResponse = await client.auth.login({
  email: 'admin@auraconnect.ai',
  password: 'password'
});

console.log('Access token:', authResponse.accessToken);
console.log('Expires in:', authResponse.expiresIn, 'seconds');

// Get current user
const user = await client.auth.getCurrentUser();
console.log('Logged in as:', user.email);

// Refresh token
await client.auth.refreshToken();

// Logout
await client.auth.logout();
```

### Automatic Token Refresh

```javascript
// Configure auto-refresh
const client = new AuraConnectClient({
  baseURL: 'https://api.auraconnect.ai',
  autoRefreshToken: true,
  onTokenRefresh: (tokens) => {
    // Store tokens securely
    localStorage.setItem('accessToken', tokens.accessToken);
    localStorage.setItem('refreshToken', tokens.refreshToken);
  }
});
```

## Orders Management

### Create Order

```javascript
const order = await client.orders.create({
  orderType: 'dine_in',
  tableNumber: '12',
  customerId: 123,
  items: [
    {
      menuItemId: 10,
      quantity: 2,
      modifiers: [
        { modifierId: 5, quantity: 1 }
      ],
      specialInstructions: 'No onions please'
    },
    {
      menuItemId: 15,
      quantity: 1
    }
  ],
  notes: 'Birthday celebration'
});

console.log('Created order:', order.orderNumber);
console.log('Total:', `$${order.totalAmount}`);
```

### List Orders with Filtering

```javascript
// Get today's orders
const today = new Date();
const tomorrow = new Date(today);
tomorrow.setDate(tomorrow.getDate() + 1);

const orders = await client.orders.list({
  dateFrom: today.toISOString(),
  dateTo: tomorrow.toISOString(),
  status: 'pending',
  page: 1,
  pageSize: 50
});

orders.items.forEach(order => {
  console.log(`${order.orderNumber}: $${order.totalAmount} - ${order.status}`);
});

// Pagination info
console.log(`Page ${orders.meta.page} of ${orders.meta.totalPages}`);
```

### Update Order Status

```javascript
// Get order
const order = await client.orders.get(1001);

// Update status
const updatedOrder = await client.orders.update(order.id, {
  status: 'preparing'
});

// Cancel order
await client.orders.cancel(order.id, {
  reason: 'Customer request',
  notes: 'Had to leave unexpectedly'
});
```

### Real-time Order Updates

```javascript
// Subscribe to order updates
const unsubscribe = client.orders.subscribe({
  event: 'order.updated',
  callback: (order) => {
    console.log(`Order ${order.orderNumber} updated:`, order.status);
    // Update UI
    updateOrderDisplay(order);
  }
});

// Unsubscribe when done
// unsubscribe();
```

## Menu Management

### List Menu Items

```javascript
// Get all active menu items
const menuItems = await client.menu.listItems({
  isActive: true,
  category: 'Burgers'
});

menuItems.forEach(item => {
  console.log(`${item.name}: $${item.price}`);
  if (item.dietaryFlags?.length) {
    console.log(`  Dietary: ${item.dietaryFlags.join(', ')}`);
  }
});
```

### Create Menu Item with Recipe

```javascript
// Create menu item
const menuItem = await client.menu.createItem({
  name: 'Veggie Burger',
  description: 'Plant-based patty with avocado',
  category: 'Burgers',
  price: 11.99,
  dietaryFlags: ['vegetarian', 'vegan'],
  allergens: ['gluten', 'soy'],
  calories: 450,
  preparationTimeMinutes: 10
});

// Create recipe for the item
const recipe = await client.menu.createRecipe({
  menuItemId: menuItem.id,
  name: 'Veggie Burger Recipe',
  yieldQuantity: 1,
  yieldUnit: 'burger',
  prepTimeMinutes: 5,
  cookTimeMinutes: 5,
  ingredients: [
    {
      inventoryId: 201,
      quantity: 1,
      unit: 'piece',
      notes: 'Plant-based patty'
    },
    {
      inventoryId: 102,
      quantity: 1,
      unit: 'piece',
      notes: 'Whole wheat bun'
    }
  ],
  instructions: '1. Grill patty for 5 minutes\n2. Toast bun\n3. Assemble'
});

// Get cost analysis
const cost = await client.menu.getRecipeCost(recipe.id);
console.log('Cost per serving:', `$${cost.costPerServing}`);
console.log('Profit margin:', `$${cost.profitMargin}`);
```

## Staff Management

### Clock In/Out

```javascript
// Clock in
const clockIn = await client.staff.clockIn(1, {
  location: {
    latitude: 40.7128,
    longitude: -74.0060
  }
});
console.log('Clocked in at:', clockIn.timestamp);

// Clock out
const clockOut = await client.staff.clockOut(1, {
  notes: 'Completed shift'
});
console.log('Shift duration:', clockOut.durationHours, 'hours');
```

### Schedule Management

```javascript
// Create schedule
const schedule = await client.staff.createSchedule({
  employeeId: 1,
  shiftDate: '2025-01-15',
  startTime: '09:00',
  endTime: '17:00',
  breakDurationMinutes: 30,
  position: 'server',
  section: 'main_dining'
});

// Get weekly schedule
const weeklySchedule = await client.staff.getSchedules({
  startDate: '2025-01-13',
  endDate: '2025-01-19',
  employeeId: 1
});

weeklySchedule.forEach(shift => {
  console.log(`${shift.shiftDate}: ${shift.startTime} - ${shift.endTime}`);
});
```

## Analytics

### Sales Reports

```javascript
// Get today's sales
const sales = await client.analytics.getSales({ period: 'today' });
console.log('Today\'s revenue:', `$${sales.totalRevenue}`);
console.log('Orders:', sales.orderCount);
console.log('Average order:', `$${sales.averageOrderValue}`);

// Get monthly sales with daily breakdown
const monthlySales = await client.analytics.getSales({
  startDate: '2025-01-01',
  endDate: '2025-01-31',
  groupBy: 'day'
});

monthlySales.data.forEach(day => {
  console.log(`${day.date}: $${day.revenue} (${day.orderCount} orders)`);
});
```

### Custom Reports

```javascript
// Generate custom report
const report = await client.analytics.createReport({
  reportType: 'sales_by_category',
  dateRange: {
    start: '2025-01-01',
    end: '2025-01-31'
  },
  filters: {
    categories: ['Burgers', 'Pizza'],
    locations: [1, 2]
  },
  groupBy: ['category', 'day'],
  metrics: ['revenue', 'quantity', 'average_order_value']
});

// Export report
const csvData = await client.analytics.exportReport(report.id, {
  format: 'csv'
});

// Save to file (Node.js)
const fs = require('fs');
fs.writeFileSync('sales_report.csv', csvData);
```

## Error Handling

```javascript
import { 
  AuraConnectError,
  AuthenticationError,
  ValidationError,
  NotFoundError,
  RateLimitError 
} from '@auraconnect/sdk';

try {
  const order = await client.orders.create({...});
} catch (error) {
  if (error instanceof ValidationError) {
    console.error('Validation failed:', error.message);
    error.errors.forEach(err => {
      console.error(`  ${err.field}: ${err.message}`);
    });
  } else if (error instanceof AuthenticationError) {
    console.error('Authentication failed. Please login again.');
    await client.auth.refreshToken();
  } else if (error instanceof RateLimitError) {
    console.error(`Rate limited. Retry after ${error.retryAfter} seconds`);
  } else if (error instanceof NotFoundError) {
    console.error('Resource not found');
  } else if (error instanceof AuraConnectError) {
    console.error('API error:', error.message);
  }
}
```

## React Integration

### Custom Hook Example

```jsx
import { useState, useEffect } from 'react';
import { AuraConnectClient } from '@auraconnect/sdk';

// Create client instance
const client = new AuraConnectClient({
  baseURL: process.env.REACT_APP_API_URL
});

// Custom hook for orders
export function useOrders(filters = {}) {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchOrders = async () => {
      try {
        setLoading(true);
        const response = await client.orders.list(filters);
        setOrders(response.items);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    };

    fetchOrders();
  }, [JSON.stringify(filters)]);

  return { orders, loading, error };
}

// Usage in component
function OrderList() {
  const { orders, loading, error } = useOrders({ 
    status: 'pending',
    dateFrom: new Date().toISOString()
  });

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error: {error.message}</div>;

  return (
    <ul>
      {orders.map(order => (
        <li key={order.id}>
          {order.orderNumber} - ${order.totalAmount}
        </li>
      ))}
    </ul>
  );
}
```

### Context Provider

```jsx
import React, { createContext, useContext, useState, useEffect } from 'react';
import { AuraConnectClient } from '@auraconnect/sdk';

const AuraConnectContext = createContext();

export function AuraConnectProvider({ children }) {
  const [client] = useState(() => new AuraConnectClient({
    baseURL: process.env.REACT_APP_API_URL,
    autoRefreshToken: true
  }));

  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  const login = async (email, password) => {
    const response = await client.auth.login({ email, password });
    const currentUser = await client.auth.getCurrentUser();
    setUser(currentUser);
    setIsAuthenticated(true);
    return response;
  };

  const logout = async () => {
    await client.auth.logout();
    setUser(null);
    setIsAuthenticated(false);
  };

  return (
    <AuraConnectContext.Provider value={{
      client,
      user,
      isAuthenticated,
      login,
      logout
    }}>
      {children}
    </AuraConnectContext.Provider>
  );
}

export const useAuraConnect = () => {
  const context = useContext(AuraConnectContext);
  if (!context) {
    throw new Error('useAuraConnect must be used within AuraConnectProvider');
  }
  return context;
};
```

## Vue.js Integration

```javascript
// plugins/auraconnect.js
import { AuraConnectClient } from '@auraconnect/sdk';

export default {
  install(app, options) {
    const client = new AuraConnectClient({
      baseURL: options.baseURL || import.meta.env.VITE_API_URL,
      autoRefreshToken: true
    });

    app.config.globalProperties.$auraconnect = client;
    app.provide('auraconnect', client);
  }
};

// main.js
import { createApp } from 'vue';
import App from './App.vue';
import AuraConnectPlugin from './plugins/auraconnect';

const app = createApp(App);
app.use(AuraConnectPlugin, {
  baseURL: 'https://api.auraconnect.ai'
});
app.mount('#app');

// In components
import { inject } from 'vue';

export default {
  setup() {
    const client = inject('auraconnect');
    
    const fetchOrders = async () => {
      const orders = await client.orders.list();
      return orders.items;
    };

    return { fetchOrders };
  }
};
```

## File Uploads

```javascript
// Upload menu item image
const fileInput = document.getElementById('file-input');
const file = fileInput.files[0];

const imageUrl = await client.files.upload({
  file,
  type: 'menu_item_image',
  entityId: menuItem.id
});

// Update menu item with image
await client.menu.updateItem(menuItem.id, {
  imageUrl
});

// With progress tracking
const imageUrl = await client.files.upload({
  file,
  type: 'menu_item_image',
  entityId: menuItem.id,
  onProgress: (progress) => {
    console.log(`Upload progress: ${progress.percent}%`);
  }
});
```

## WebSocket Real-time Updates

```javascript
// Connect to WebSocket
await client.realtime.connect();

// Subscribe to order updates
const unsubscribe = client.realtime.subscribe('orders', {
  events: ['order.created', 'order.updated', 'order.completed'],
  callback: (event) => {
    console.log('Order event:', event.type, event.data);
    
    switch(event.type) {
      case 'order.created':
        addOrderToList(event.data);
        break;
      case 'order.updated':
        updateOrderInList(event.data);
        break;
      case 'order.completed':
        moveOrderToCompleted(event.data);
        break;
    }
  }
});

// Subscribe to kitchen display updates
client.realtime.subscribe('kitchen', {
  events: ['item.ready', 'item.delayed'],
  callback: (event) => {
    updateKitchenDisplay(event);
  }
});

// Cleanup on unmount
// unsubscribe();
// client.realtime.disconnect();
```

## Batch Operations

```javascript
// Batch create menu items
const items = [
  { name: 'Item 1', price: 10.99, category: 'Appetizers' },
  { name: 'Item 2', price: 12.99, category: 'Appetizers' },
  { name: 'Item 3', price: 8.99, category: 'Appetizers' }
];

const results = await client.menu.batchCreateItems(items);
console.log(`Created ${results.successful.length} items`);
if (results.failed.length > 0) {
  console.log(`Failed to create ${results.failed.length} items`);
  results.failed.forEach(failure => {
    console.error(`${failure.item.name}: ${failure.error}`);
  });
}
```

## Offline Support

```javascript
import { AuraConnectClient, OfflineSync } from '@auraconnect/sdk';

// Enable offline support
const client = new AuraConnectClient({
  baseURL: 'https://api.auraconnect.ai',
  offline: {
    enabled: true,
    storage: 'indexeddb', // or 'localstorage'
    syncInterval: 30000 // 30 seconds
  }
});

// Check online status
client.offline.on('statusChange', (isOnline) => {
  console.log('Connection status:', isOnline ? 'online' : 'offline');
});

// Queue operations when offline
try {
  const order = await client.orders.create({...});
  console.log('Order created:', order.orderNumber);
} catch (error) {
  if (error.code === 'OFFLINE') {
    console.log('Order queued for sync');
  }
}

// Manual sync
await client.offline.sync();

// Get pending operations
const pending = await client.offline.getPendingOperations();
console.log(`${pending.length} operations pending sync`);
```

## Configuration

```javascript
// Environment-based configuration
const client = new AuraConnectClient({
  baseURL: process.env.NODE_ENV === 'production' 
    ? 'https://api.auraconnect.ai'
    : 'http://localhost:8000',
  timeout: 30000, // 30 seconds
  retry: {
    attempts: 3,
    delay: 1000,
    maxDelay: 5000,
    backoff: 'exponential'
  },
  headers: {
    'X-Client-Version': '1.0.0',
    'X-Client-Platform': 'web'
  }
});

// Interceptors
client.interceptors.request.use((config) => {
  // Add custom headers
  config.headers['X-Request-ID'] = generateRequestId();
  return config;
});

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Auto refresh token
      await client.auth.refreshToken();
      return client.request(error.config);
    }
    return Promise.reject(error);
  }
);
```

## Testing

```javascript
// Using Jest
import { AuraConnectClient } from '@auraconnect/sdk';
import { mockClient } from '@auraconnect/sdk/testing';

describe('Order Service', () => {
  let client;

  beforeEach(() => {
    client = mockClient();
  });

  test('should create order', async () => {
    // Mock response
    client.orders.create.mockResolvedValue({
      id: 1001,
      orderNumber: 'ORD-2025-1001',
      totalAmount: 52.34
    });

    const order = await createCustomerOrder(client, { customerId: 123 });
    
    expect(order.orderNumber).toBe('ORD-2025-1001');
    expect(client.orders.create).toHaveBeenCalledWith(
      expect.objectContaining({ customerId: 123 })
    );
  });
});

// Using Cypress
describe('Order Flow', () => {
  beforeEach(() => {
    cy.intercept('POST', '/api/v1/orders', {
      statusCode: 201,
      body: {
        id: 1001,
        orderNumber: 'ORD-2025-1001',
        totalAmount: 52.34
      }
    }).as('createOrder');
  });

  it('should create new order', () => {
    cy.visit('/orders/new');
    cy.get('[data-testid="add-item"]').click();
    cy.get('[data-testid="submit-order"]').click();
    
    cy.wait('@createOrder');
    cy.contains('Order ORD-2025-1001 created successfully');
  });
});
```

## Complete Example

```javascript
import { AuraConnectClient } from '@auraconnect/sdk';

async function main() {
  // Initialize client
  const client = new AuraConnectClient({
    baseURL: 'https://api.auraconnect.ai'
  });

  try {
    // Authenticate
    await client.auth.login({
      email: 'manager@restaurant.com',
      password: 'password'
    });

    // Get current user
    const user = await client.auth.getCurrentUser();
    console.log(`Logged in as: ${user.firstName} ${user.lastName}`);

    // Get today's stats
    const today = new Date().toISOString().split('T')[0];
    
    // Get orders
    const orders = await client.orders.list({
      dateFrom: today,
      status: 'completed'
    });
    
    console.log(`\nToday's Orders: ${orders.items.length}`);
    const totalRevenue = orders.items.reduce(
      (sum, order) => sum + parseFloat(order.totalAmount), 
      0
    );
    console.log(`Total Revenue: $${totalRevenue.toFixed(2)}`);
    
    // Get low stock items
    const lowStock = await client.inventory.getLowStock();
    if (lowStock.length > 0) {
      console.log(`\nLow Stock Alert: ${lowStock.length} items`);
      lowStock.slice(0, 5).forEach(item => {
        console.log(`  - ${item.name}: ${item.currentQuantity} ${item.unit}`);
      });
    }
    
    // Get staff on duty
    const schedules = await client.staff.getSchedules({
      shiftDate: today
    });
    console.log(`\nStaff on duty: ${schedules.length}`);
    
    // Generate daily report
    const report = await client.analytics.getSales({ period: 'today' });
    console.log('\nDaily Summary:');
    console.log(`  Revenue: $${report.totalRevenue}`);
    console.log(`  Orders: ${report.orderCount}`);
    console.log(`  Avg Order: $${report.averageOrderValue}`);
    if (report.topItems?.length > 0) {
      console.log(`  Top Item: ${report.topItems[0].name}`);
    }
    
  } catch (error) {
    console.error('Error:', error.message);
  } finally {
    // Cleanup
    await client.auth.logout();
  }
}

// Run if called directly
if (require.main === module) {
  main();
}
```