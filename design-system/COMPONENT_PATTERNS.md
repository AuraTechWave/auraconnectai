# Component Patterns Documentation

> Comprehensive guide to AuraConnect's reusable component patterns across all platforms

## Table of Contents
1. [Navigation Components](#navigation-components)
2. [Form Components](#form-components)
3. [Feedback Components](#feedback-components)
4. [Data Display Components](#data-display-components)
5. [Action Components](#action-components)
6. [Layout Components](#layout-components)

---

## Navigation Components

### AppBar / Header

#### Anatomy
```
┌─────────────────────────────────────────┐
│ [Menu] Logo    Title         [Actions]  │
└─────────────────────────────────────────┘
```

#### Variants
- **Default**: Logo, title, action buttons
- **Search**: Integrated search bar
- **Tabs**: Tab navigation below
- **Minimal**: Title only

#### Platform Specifications

**Web (Admin)**
```jsx
<AppBar elevation={1}>
  <IconButton icon="menu" onClick={toggleDrawer} />
  <Logo size="small" />
  <Title>Dashboard</Title>
  <Spacer />
  <SearchBar />
  <NotificationBell count={3} />
  <UserMenu />
</AppBar>
```

**Mobile**
```jsx
<Header>
  <BackButton />
  <Title>Orders</Title>
  <IconButton icon="search" />
  <IconButton icon="filter" />
</Header>
```

### Navigation Drawer / Sidebar

#### Structure
```
┌──────────────┐
│ User Info    │
├──────────────┤
│ ▼ Dashboard  │
│ ▶ Orders     │
│ ▶ Menu       │
│ ▶ Staff      │
├──────────────┤
│ Settings     │
│ Help         │
└──────────────┘
```

#### States
- **Expanded**: Full width with labels
- **Collapsed**: Icons only
- **Mobile**: Full screen overlay

### Bottom Navigation (Mobile)

#### Guidelines
- Maximum 5 items
- Always visible on main screens
- Hide on scroll for content focus
- Badge support for notifications

```jsx
<BottomNavigation>
  <Tab icon="home" label="Home" />
  <Tab icon="orders" label="Orders" badge={2} />
  <Tab icon="menu" label="Menu" />
  <Tab icon="analytics" label="Analytics" />
  <Tab icon="more" label="More" />
</BottomNavigation>
```

### Breadcrumbs

#### Format
```
Home > Orders > #ORD-123 > Edit
```

#### Behavior
- Last item is current page (not clickable)
- Truncate middle items on mobile
- Show max 4 levels

---

## Form Components

### Input Field

#### Anatomy
```
Label *
┌─────────────────────────┐
│ Placeholder text        │
└─────────────────────────┘
Helper text
```

#### States Matrix

| State | Border | Background | Label | Helper |
|-------|--------|------------|-------|--------|
| Default | Neutral | White | Gray | Hidden |
| Focus | Primary | White | Primary | Visible |
| Error | Error | Error-light | Error | Error text |
| Success | Success | Success-light | Success | Success text |
| Disabled | Neutral | Gray | Gray | Hidden |

#### Variants

**Text Input**
```jsx
<TextField
  label="Email"
  type="email"
  placeholder="john@example.com"
  required
  helper="We'll never share your email"
  leftIcon="mail"
  rightIcon="info"
/>
```

**Select Dropdown**
```jsx
<Select
  label="Table"
  options={tables}
  placeholder="Choose a table"
  searchable
  clearable
/>
```

**Date/Time Picker**
```jsx
<DateTimePicker
  label="Reservation Date"
  min={today}
  max={nextMonth}
  format="MMM DD, YYYY"
  timeInterval={15}
/>
```

### Form Validation

#### Inline Validation
- Validate on blur for new entries
- Validate on change for corrections
- Show success for complex validations

#### Error Messages
```javascript
const errorMessages = {
  required: "This field is required",
  email: "Please enter a valid email",
  min: "Must be at least {min} characters",
  max: "Must be no more than {max} characters",
  pattern: "Please match the requested format",
  custom: "Specific error message here"
};
```

### Switch / Toggle

#### Usage
- Binary on/off settings
- Instant apply (no save button needed)
- Label on left, switch on right

```jsx
<Switch
  label="Enable notifications"
  description="Receive alerts for new orders"
  checked={enabled}
  onChange={handleToggle}
/>
```

### Radio Group

#### Layout
- Vertical for 2-5 options
- Grid for 6+ options
- Icons optional for clarity

```jsx
<RadioGroup
  label="Payment Method"
  value={selected}
  onChange={setSelected}
>
  <Radio value="cash" icon="cash">Cash</Radio>
  <Radio value="card" icon="credit-card">Card</Radio>
  <Radio value="digital" icon="phone">Digital</Radio>
</RadioGroup>
```

---

## Feedback Components

### Loading States

#### Skeleton Loader
```jsx
<Skeleton>
  <Skeleton.Avatar />
  <Skeleton.Text lines={3} />
  <Skeleton.Button />
</Skeleton>
```

#### Progress Indicators
```jsx
// Linear
<ProgressBar value={60} label="Processing..." />

// Circular
<CircularProgress size="large" />

// Step Progress
<StepProgress current={2} total={4} />
```

### Empty States

#### Structure
```
┌─────────────────────────┐
│                         │
│     [Illustration]      │
│                         │
│     No orders yet       │
│  Start by creating one  │
│                         │
│    [Create Order]       │
│                         │
└─────────────────────────┘
```

#### Content Guidelines
- Friendly, helpful tone
- Explain what's missing
- Provide next action
- Keep it brief

### Error States

#### Inline Errors
```jsx
<ErrorBoundary>
  <Alert severity="error" action={retry}>
    <AlertTitle>Unable to load orders</AlertTitle>
    <AlertDescription>
      Check your connection and try again
    </AlertDescription>
  </Alert>
</ErrorBoundary>
```

#### Full Page Errors
```jsx
<ErrorPage
  code={404}
  title="Page not found"
  description="The page you're looking for doesn't exist"
  action={{ label: "Go Home", onClick: goHome }}
  illustration="404"
/>
```

### Toast Notifications

#### Types & Duration
- **Success**: 3 seconds
- **Error**: 5 seconds or dismissible
- **Info**: 4 seconds
- **Warning**: 5 seconds

```jsx
toast.success("Order created successfully");
toast.error("Failed to process payment", { 
  duration: 5000,
  action: { label: "Retry", onClick: retry }
});
```

---

## Data Display Components

### Cards

#### Basic Card
```jsx
<Card>
  <CardHeader>
    <CardTitle>Today's Revenue</CardTitle>
    <CardAction icon="more-vert" />
  </CardHeader>
  <CardContent>
    <Metric value="$1,234" change="+12%" />
  </CardContent>
</Card>
```

#### Interactive Card
```jsx
<Card interactive onClick={handleClick}>
  <CardMedia image={dish.image} height={200} />
  <CardContent>
    <Typography variant="h6">{dish.name}</Typography>
    <Typography variant="body2">{dish.description}</Typography>
    <Price value={dish.price} />
  </CardContent>
  <CardActions>
    <Button size="small">Edit</Button>
    <Button size="small" variant="danger">Delete</Button>
  </CardActions>
</Card>
```

### Tables

#### Responsive Table
```jsx
<DataTable
  columns={[
    { key: 'id', label: 'Order #', sortable: true },
    { key: 'customer', label: 'Customer', searchable: true },
    { key: 'total', label: 'Total', align: 'right', format: 'currency' },
    { key: 'status', label: 'Status', render: StatusBadge },
    { key: 'actions', label: '', render: ActionMenu }
  ]}
  data={orders}
  pagination
  selectable
  onRowClick={handleRowClick}
/>
```

#### Mobile Table Adaptation
- Card layout for complex data
- Horizontal scroll for simple tables
- Expandable rows for details

### Lists

#### Simple List
```jsx
<List>
  <ListItem
    icon="restaurant"
    primary="Table 5"
    secondary="4 guests"
    action={<Badge>Occupied</Badge>}
  />
</List>
```

#### Swipeable List (Mobile)
```jsx
<SwipeableList>
  <SwipeableListItem
    leftActions={[
      { icon: 'check', color: 'success', onPress: complete }
    ]}
    rightActions={[
      { icon: 'delete', color: 'error', onPress: delete }
    ]}
  >
    <OrderItem order={order} />
  </SwipeableListItem>
</SwipeableList>
```

### Statistics

#### Metric Card
```jsx
<MetricCard
  title="Total Orders"
  value={1234}
  change={{ value: 12, period: 'vs last week' }}
  trend="up"
  icon="shopping-cart"
  color="primary"
/>
```

#### Chart Components
```jsx
// Line Chart
<LineChart
  data={revenueData}
  xAxis="date"
  yAxis="amount"
  curve="smooth"
  gradient
/>

// Bar Chart
<BarChart
  data={categoryData}
  orientation="vertical"
  stacked
  showValues
/>

// Donut Chart
<DonutChart
  data={orderTypes}
  centerLabel="Total"
  centerValue={sum}
  interactive
/>
```

---

## Action Components

### Buttons

#### Size Matrix
| Size | Height | Padding | Font | Use Case |
|------|--------|---------|------|----------|
| Small | 32px | 8px 12px | 14px | Tables, compact |
| Medium | 44px | 12px 20px | 16px | Default |
| Large | 56px | 16px 32px | 18px | Primary CTAs |

#### Variants
```jsx
// Primary - Main actions
<Button variant="primary">Create Order</Button>

// Secondary - Alternative actions
<Button variant="secondary">Export</Button>

// Tertiary - Less important
<Button variant="tertiary">Cancel</Button>

// Danger - Destructive
<Button variant="danger">Delete</Button>

// Ghost - Subtle
<Button variant="ghost">Learn More</Button>
```

#### Button Groups
```jsx
<ButtonGroup>
  <Button>Day</Button>
  <Button active>Week</Button>
  <Button>Month</Button>
</ButtonGroup>
```

### Floating Action Button (FAB)

#### Positioning
- Bottom right: Primary action
- Bottom center: Contextual action
- Mini FAB: Secondary actions

```jsx
<FAB
  icon="add"
  label="New Order"
  extended={scrolled}
  onClick={createOrder}
/>
```

### Icon Buttons

#### Usage
- Toolbar actions
- List item actions
- Inline actions

```jsx
<IconButton
  icon="edit"
  size="medium"
  tooltip="Edit order"
  onClick={handleEdit}
/>
```

### Menus

#### Dropdown Menu
```jsx
<DropdownMenu
  trigger={<IconButton icon="more-vert" />}
  items={[
    { label: 'Edit', icon: 'edit', onClick: edit },
    { label: 'Duplicate', icon: 'copy', onClick: duplicate },
    { divider: true },
    { label: 'Delete', icon: 'delete', onClick: delete, danger: true }
  ]}
/>
```

#### Context Menu (Right-click)
```jsx
<ContextMenu
  items={menuItems}
  onSelect={handleSelect}
>
  <TableRow>{content}</TableRow>
</ContextMenu>
```

---

## Layout Components

### Container

#### Breakpoints
```scss
.container {
  width: 100%;
  margin: 0 auto;
  padding: 0 16px;
  
  @media (min-width: 768px) {
    max-width: 750px;
    padding: 0 24px;
  }
  
  @media (min-width: 1024px) {
    max-width: 970px;
  }
  
  @media (min-width: 1440px) {
    max-width: 1400px;
    padding: 0 32px;
  }
}
```

### Grid System

#### Responsive Grid
```jsx
<Grid container spacing={3}>
  <Grid item xs={12} md={6} lg={4}>
    <Card>Content</Card>
  </Grid>
</Grid>
```

#### CSS Grid Alternative
```scss
.grid {
  display: grid;
  gap: 24px;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
}
```

### Stack

#### Vertical Stack
```jsx
<Stack spacing={2} divider>
  <Item>First</Item>
  <Item>Second</Item>
  <Item>Third</Item>
</Stack>
```

#### Horizontal Stack
```jsx
<Stack direction="horizontal" spacing={1} align="center">
  <Avatar />
  <Text>John Doe</Text>
  <Badge>Pro</Badge>
</Stack>
```

### Modal / Dialog

#### Structure
```jsx
<Modal open={open} onClose={handleClose}>
  <ModalHeader>
    <ModalTitle>Confirm Action</ModalTitle>
    <IconButton icon="close" onClick={handleClose} />
  </ModalHeader>
  <ModalContent>
    Are you sure you want to proceed?
  </ModalContent>
  <ModalActions>
    <Button variant="tertiary" onClick={handleClose}>
      Cancel
    </Button>
    <Button variant="primary" onClick={handleConfirm}>
      Confirm
    </Button>
  </ModalActions>
</Modal>
```

#### Sizes
- **Small**: 400px max-width
- **Medium**: 600px max-width (default)
- **Large**: 800px max-width
- **Full**: 90vw max-width

### Drawer / Sheet

#### Slide-out Panel
```jsx
<Drawer
  anchor="right"
  open={open}
  onClose={handleClose}
  width={400}
>
  <DrawerHeader>
    <DrawerTitle>Filters</DrawerTitle>
    <IconButton icon="close" onClick={handleClose} />
  </DrawerHeader>
  <DrawerContent>
    {/* Filter controls */}
  </DrawerContent>
  <DrawerFooter>
    <Button fullWidth>Apply Filters</Button>
  </DrawerFooter>
</Drawer>
```

#### Bottom Sheet (Mobile)
```jsx
<BottomSheet
  open={open}
  onClose={handleClose}
  snapPoints={[0.25, 0.5, 0.9]}
>
  <SheetHandle />
  <SheetContent>
    {/* Content */}
  </SheetContent>
</BottomSheet>
```

---

## Component Composition Examples

### Order Card Composition
```jsx
<Card interactive>
  <CardHeader>
    <Stack direction="horizontal" justify="between">
      <Stack>
        <Typography variant="h6">#ORD-123</Typography>
        <Typography variant="caption">5 min ago</Typography>
      </Stack>
      <Badge variant="primary">Preparing</Badge>
    </Stack>
  </CardHeader>
  
  <CardContent>
    <Stack spacing={1}>
      <Stack direction="horizontal" spacing={1}>
        <Avatar size="small">JD</Avatar>
        <Stack>
          <Typography>John Doe</Typography>
          <Typography variant="caption">Table 5</Typography>
        </Stack>
      </Stack>
      
      <Divider />
      
      <List dense>
        <ListItem>2x Margherita Pizza</ListItem>
        <ListItem>1x Caesar Salad</ListItem>
      </List>
    </Stack>
  </CardContent>
  
  <CardActions justify="between">
    <Typography variant="h6">$45.99</Typography>
    <Stack direction="horizontal" spacing={1}>
      <Button size="small" variant="secondary">View</Button>
      <Button size="small" variant="primary">Accept</Button>
    </Stack>
  </CardActions>
</Card>
```

---

*Component Patterns Documentation v1.0.0*
*Last Updated: August 19, 2025*