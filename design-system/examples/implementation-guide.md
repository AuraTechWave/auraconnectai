# Implementation Guide & Examples

> Practical examples for implementing the AuraConnect Design System across platforms

## Quick Start

### Installing Design Tokens

```bash
# Web Project
npm install @auraconnect/design-tokens
npm install @auraconnect/react-components

# Mobile Project
npm install @auraconnect/design-tokens
npm install @auraconnect/react-native-components

# Style Dictionary Setup
npm install style-dictionary
npx style-dictionary build
```

### Basic Setup

#### Web (React)
```jsx
// App.jsx
import { ThemeProvider } from '@auraconnect/react-components';
import { lightTheme, darkTheme } from '@auraconnect/design-tokens';

function App() {
  const [theme, setTheme] = useState('light');
  
  return (
    <ThemeProvider theme={theme === 'light' ? lightTheme : darkTheme}>
      <YourApp />
    </ThemeProvider>
  );
}
```

#### Mobile (React Native)
```jsx
// App.tsx
import { ThemeProvider } from '@auraconnect/react-native-components';
import { mobileLight, mobileDark } from '@auraconnect/design-tokens';

export default function App() {
  const colorScheme = useColorScheme();
  
  return (
    <ThemeProvider theme={colorScheme === 'dark' ? mobileDark : mobileLight}>
      <NavigationContainer>
        <RootNavigator />
      </NavigationContainer>
    </ThemeProvider>
  );
}
```

## Component Implementation Examples

### Order Card - Cross Platform

#### Design Token Usage
```javascript
// shared/tokens.js
export const orderCardTokens = {
  padding: tokens.spacing.md,
  borderRadius: tokens.borderRadius.lg,
  shadow: tokens.shadows.sm,
  
  header: {
    fontSize: tokens.typography.bodyLarge,
    fontWeight: tokens.typography.fontWeight.semiBold,
    color: tokens.colors.text.primary
  },
  
  status: {
    pending: tokens.colors.warning[500],
    preparing: tokens.colors.primary[500],
    ready: tokens.colors.success[500],
    delivered: tokens.colors.neutral[500]
  }
};
```

#### Web Implementation
```jsx
// components/OrderCard.web.jsx
import { Card, Badge, Avatar, Stack } from '@auraconnect/react-components';
import { orderCardTokens as styles } from '../shared/tokens';

export function OrderCard({ order }) {
  return (
    <Card 
      variant="elevated"
      onClick={() => navigateToOrder(order.id)}
      className="order-card"
    >
      <Card.Header>
        <Stack direction="horizontal" justify="between">
          <div>
            <h3 style={styles.header}>Order #{order.number}</h3>
            <time>{formatTime(order.createdAt)}</time>
          </div>
          <Badge color={styles.status[order.status]}>
            {order.status}
          </Badge>
        </Stack>
      </Card.Header>
      
      <Card.Content>
        <Stack spacing={2}>
          <Stack direction="horizontal" spacing={2}>
            <Avatar name={order.customerName} size="small" />
            <div>
              <p>{order.customerName}</p>
              <small>Table {order.tableNumber}</small>
            </div>
          </Stack>
          
          <ul className="order-items">
            {order.items.map(item => (
              <li key={item.id}>
                {item.quantity}x {item.name}
              </li>
            ))}
          </ul>
        </Stack>
      </Card.Content>
      
      <Card.Footer>
        <Stack direction="horizontal" justify="between">
          <span className="total">${order.total}</span>
          <Stack direction="horizontal" spacing={1}>
            <Button size="small" variant="secondary">View</Button>
            <Button size="small" variant="primary">Accept</Button>
          </Stack>
        </Stack>
      </Card.Footer>
    </Card>
  );
}
```

#### Mobile Implementation
```jsx
// components/OrderCard.mobile.jsx
import React from 'react';
import { View, Text, TouchableOpacity } from 'react-native';
import { Card, Badge, Avatar } from '@auraconnect/react-native-components';
import { orderCardTokens as tokens } from '../shared/tokens';

export function OrderCard({ order, onPress }) {
  return (
    <Card variant="elevated" onPress={() => onPress(order)}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.orderNumber}>
            Order #{order.number}
          </Text>
          <Text style={styles.time}>
            {formatTime(order.createdAt)}
          </Text>
        </View>
        <Badge 
          label={order.status}
          color={tokens.status[order.status]}
        />
      </View>
      
      <View style={styles.content}>
        <View style={styles.customer}>
          <Avatar 
            name={order.customerName}
            size="small"
          />
          <View style={styles.customerInfo}>
            <Text style={styles.customerName}>
              {order.customerName}
            </Text>
            <Text style={styles.table}>
              Table {order.tableNumber}
            </Text>
          </View>
        </View>
        
        <View style={styles.items}>
          {order.items.map(item => (
            <Text key={item.id} style={styles.item}>
              {item.quantity}x {item.name}
            </Text>
          ))}
        </View>
      </View>
      
      <View style={styles.footer}>
        <Text style={styles.total}>${order.total}</Text>
        <View style={styles.actions}>
          <Button 
            title="View"
            size="small"
            variant="secondary"
            onPress={() => viewOrder(order)}
          />
          <Button
            title="Accept"
            size="small"
            variant="primary"
            onPress={() => acceptOrder(order)}
            style={{ marginLeft: 8 }}
          />
        </View>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingBottom: tokens.spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: tokens.colors.border.light
  },
  // ... more styles
});
```

### Form Pattern - Multi-Step

#### Shared Logic
```typescript
// shared/formSteps.ts
export interface FormStep {
  id: string;
  title: string;
  description?: string;
  fields: FormField[];
  validation: ValidationRules;
}

export const orderFormSteps: FormStep[] = [
  {
    id: 'customer',
    title: 'Customer Information',
    fields: [
      { name: 'name', type: 'text', label: 'Name', required: true },
      { name: 'phone', type: 'tel', label: 'Phone', required: true },
      { name: 'email', type: 'email', label: 'Email' }
    ],
    validation: {
      name: { required: true, minLength: 2 },
      phone: { required: true, pattern: /^\d{10}$/ },
      email: { type: 'email' }
    }
  },
  {
    id: 'items',
    title: 'Order Items',
    fields: [
      // Dynamic item selection
    ]
  },
  {
    id: 'payment',
    title: 'Payment',
    fields: [
      { name: 'method', type: 'radio', options: ['cash', 'card', 'digital'] },
      { name: 'tip', type: 'number', label: 'Tip Amount' }
    ]
  }
];
```

#### Web Multi-Step Form
```jsx
// components/MultiStepForm.web.jsx
export function MultiStepForm({ steps, onComplete }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [formData, setFormData] = useState({});
  const [errors, setErrors] = useState({});
  
  return (
    <div className="multi-step-form">
      <StepIndicator 
        steps={steps}
        current={currentStep}
      />
      
      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -20 }}
        >
          <Card>
            <Card.Header>
              <h2>{steps[currentStep].title}</h2>
              {steps[currentStep].description && (
                <p>{steps[currentStep].description}</p>
              )}
            </Card.Header>
            
            <Card.Content>
              <Form
                fields={steps[currentStep].fields}
                values={formData}
                errors={errors}
                onChange={setFormData}
              />
            </Card.Content>
            
            <Card.Footer>
              <Stack direction="horizontal" justify="between">
                <Button
                  variant="tertiary"
                  onClick={() => setCurrentStep(curr => curr - 1)}
                  disabled={currentStep === 0}
                >
                  Previous
                </Button>
                
                {currentStep === steps.length - 1 ? (
                  <Button
                    variant="primary"
                    onClick={() => onComplete(formData)}
                  >
                    Complete
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    onClick={() => {
                      if (validateStep(currentStep)) {
                        setCurrentStep(curr => curr + 1);
                      }
                    }}
                  >
                    Next
                  </Button>
                )}
              </Stack>
            </Card.Footer>
          </Card>
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
```

### Dashboard Layout Pattern

#### Admin Dashboard Layout
```jsx
// layouts/AdminLayout.jsx
import { useState } from 'react';
import { 
  Sidebar, 
  Header, 
  Container,
  useTheme,
  useBreakpoint
} from '@auraconnect/react-components';

export function AdminLayout({ children }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const theme = useTheme();
  const isMobile = useBreakpoint('mobile');
  
  return (
    <div className="admin-layout">
      <Sidebar
        open={sidebarOpen}
        collapsed={isMobile}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      >
        <Sidebar.Header>
          <Logo />
        </Sidebar.Header>
        
        <Sidebar.Nav>
          <NavItem icon="dashboard" label="Dashboard" href="/" />
          <NavItem icon="orders" label="Orders" href="/orders" badge={3} />
          <NavItem icon="menu" label="Menu" href="/menu" />
          <NavItem icon="users" label="Staff" href="/staff" />
          <NavItem icon="inventory" label="Inventory" href="/inventory" />
          <NavItem icon="analytics" label="Analytics" href="/analytics" />
        </Sidebar.Nav>
        
        <Sidebar.Footer>
          <UserProfile />
        </Sidebar.Footer>
      </Sidebar>
      
      <div className="main-content">
        <Header>
          <Header.Left>
            <IconButton 
              icon="menu"
              onClick={() => setSidebarOpen(!sidebarOpen)}
            />
            <Breadcrumbs />
          </Header.Left>
          
          <Header.Right>
            <SearchBar />
            <NotificationBell />
            <ThemeToggle />
            <UserMenu />
          </Header.Right>
        </Header>
        
        <Container>
          {children}
        </Container>
      </div>
    </div>
  );
}
```

### Real-time Updates Pattern

#### WebSocket Integration
```jsx
// hooks/useRealtimeOrders.js
export function useRealtimeOrders() {
  const [orders, setOrders] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  
  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
      setConnectionStatus('connected');
      ws.send(JSON.stringify({ type: 'subscribe', channel: 'orders' }));
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'order:new':
          setOrders(prev => [data.order, ...prev]);
          showNotification('New order received!', 'success');
          playSound('new-order');
          break;
          
        case 'order:updated':
          setOrders(prev => prev.map(order => 
            order.id === data.order.id ? data.order : order
          ));
          break;
          
        case 'order:deleted':
          setOrders(prev => prev.filter(order => order.id !== data.orderId));
          break;
      }
    };
    
    ws.onerror = () => setConnectionStatus('error');
    ws.onclose = () => setConnectionStatus('disconnected');
    
    return () => ws.close();
  }, []);
  
  return { orders, connectionStatus };
}

// Usage in component
function OrdersDashboard() {
  const { orders, connectionStatus } = useRealtimeOrders();
  
  return (
    <div>
      <ConnectionStatus status={connectionStatus} />
      <OrdersList orders={orders} />
    </div>
  );
}
```

### Accessibility Implementation

#### Keyboard Navigation
```jsx
// components/AccessibleMenu.jsx
export function AccessibleMenu({ items }) {
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const itemRefs = useRef([]);
  
  const handleKeyDown = (e) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex(prev => 
          prev < items.length - 1 ? prev + 1 : 0
        );
        break;
        
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex(prev => 
          prev > 0 ? prev - 1 : items.length - 1
        );
        break;
        
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (focusedIndex >= 0) {
          items[focusedIndex].onClick();
        }
        break;
        
      case 'Escape':
        setFocusedIndex(-1);
        break;
    }
  };
  
  useEffect(() => {
    if (focusedIndex >= 0 && itemRefs.current[focusedIndex]) {
      itemRefs.current[focusedIndex].focus();
    }
  }, [focusedIndex]);
  
  return (
    <ul
      role="menu"
      onKeyDown={handleKeyDown}
      className="accessible-menu"
    >
      {items.map((item, index) => (
        <li
          key={item.id}
          role="menuitem"
          tabIndex={index === focusedIndex ? 0 : -1}
          ref={el => itemRefs.current[index] = el}
          onClick={item.onClick}
          onFocus={() => setFocusedIndex(index)}
          aria-label={item.label}
          className={`menu-item ${index === focusedIndex ? 'focused' : ''}`}
        >
          {item.icon && <Icon name={item.icon} />}
          <span>{item.label}</span>
          {item.shortcut && (
            <kbd className="shortcut">{item.shortcut}</kbd>
          )}
        </li>
      ))}
    </ul>
  );
}
```

### Performance Optimization

#### Virtual List Implementation
```jsx
// components/VirtualOrderList.jsx
import { FixedSizeList } from 'react-window';

export function VirtualOrderList({ orders, height = 600 }) {
  const itemHeight = 120;
  
  const Row = ({ index, style }) => {
    const order = orders[index];
    
    return (
      <div style={style}>
        <OrderCard order={order} />
      </div>
    );
  };
  
  return (
    <FixedSizeList
      height={height}
      itemCount={orders.length}
      itemSize={itemHeight}
      width="100%"
      overscanCount={3}
    >
      {Row}
    </FixedSizeList>
  );
}
```

### Testing Patterns

#### Component Testing
```javascript
// __tests__/OrderCard.test.jsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ThemeProvider } from '@auraconnect/react-components';
import { OrderCard } from '../OrderCard';

describe('OrderCard', () => {
  const mockOrder = {
    id: '123',
    number: 'ORD-001',
    customerName: 'John Doe',
    status: 'pending',
    total: 45.99
  };
  
  it('renders order information correctly', () => {
    render(
      <ThemeProvider>
        <OrderCard order={mockOrder} />
      </ThemeProvider>
    );
    
    expect(screen.getByText('Order #ORD-001')).toBeInTheDocument();
    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('$45.99')).toBeInTheDocument();
  });
  
  it('handles click events', () => {
    const handleClick = jest.fn();
    
    render(
      <ThemeProvider>
        <OrderCard order={mockOrder} onClick={handleClick} />
      </ThemeProvider>
    );
    
    fireEvent.click(screen.getByRole('article'));
    expect(handleClick).toHaveBeenCalledWith(mockOrder);
  });
  
  it('applies correct status styling', () => {
    render(
      <ThemeProvider>
        <OrderCard order={{ ...mockOrder, status: 'ready' }} />
      </ThemeProvider>
    );
    
    const badge = screen.getByText('ready');
    expect(badge).toHaveClass('badge-success');
  });
});
```

---

*Implementation Guide v1.0.0*
*Last Updated: August 19, 2025*