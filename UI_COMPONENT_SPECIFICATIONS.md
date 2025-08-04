# 🎨 AuraConnect UI Component Specifications

> **Note**: Component preview images referenced throughout this document (e.g., `docs/assets/components/*-preview.png`) are placeholders. These can be replaced with actual screenshots or design mockups as components are implemented.

## 📋 Table of Contents
1. [Design System Foundation](#design-system-foundation)
2. [Layout Components](#layout-components)
3. [Navigation Components](#navigation-components)
4. [Card Components](#card-components)
5. [Form Components](#form-components)
6. [Data Display Components](#data-display-components)
7. [Feedback Components](#feedback-components)
8. [Chart Components](#chart-components)
9. [Utility Components](#utility-components)
10. [Mobile-Specific Components](#mobile-specific-components)
11. [Page Templates](#page-templates)

---

## 🎨 Design System Foundation

### Color Palette
```css
/* Core Colors */
--primary: #3F51B5;        /* Indigo Blue */
--accent: #03A9F4;         /* Sky Blue */
--background: #F5F5F5;     /* Light Gray */
--surface: #FFFFFF;        /* White */
--text-primary: #212121;   /* Charcoal */
--text-secondary: #757575; /* Slate Gray */

/* Status Colors */
--success: #4CAF50;        /* Emerald Green */
--warning: #FFC107;        /* Amber */
--error: #F44336;          /* Crimson Red */

/* Neutrals */
--neutral-50: #FAFAFA;
--neutral-100: #EEEEEE;
--neutral-200: #E0E0E0;
--neutral-300: #BDBDBD;
```

### Typography
```css
/* Font Stack */
font-family: 'Inter', 'Roboto', -apple-system, system-ui, sans-serif;

/* Type Scale */
--text-xs: 0.75rem;     /* 12px */
--text-sm: 0.875rem;    /* 14px */
--text-base: 1rem;      /* 16px */
--text-lg: 1.125rem;    /* 18px */
--text-xl: 1.25rem;     /* 20px */
--text-2xl: 1.5rem;     /* 24px */
--text-3xl: 1.875rem;   /* 30px */
--text-4xl: 2.25rem;    /* 36px */

/* Font Weights */
--font-normal: 400;
--font-medium: 500;
--font-semibold: 600;
--font-bold: 700;
```

### Spacing System
```css
/* Spacing Scale */
--space-1: 0.25rem;   /* 4px */
--space-2: 0.5rem;    /* 8px */
--space-3: 0.75rem;   /* 12px */
--space-4: 1rem;      /* 16px */
--space-5: 1.25rem;   /* 20px */
--space-6: 1.5rem;    /* 24px */
--space-8: 2rem;      /* 32px */
--space-10: 2.5rem;   /* 40px */
--space-12: 3rem;     /* 48px */
--space-16: 4rem;     /* 64px */
```

### Border Radius
```css
--radius-sm: 4px;
--radius-md: 7px;     /* AdminMart standard */
--radius-lg: 12px;
--radius-xl: 16px;
--radius-full: 9999px;
```

### Shadows
```css
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
```

---

## 🏗️ Layout Components

### 1. App Shell
**Description**: Main application wrapper with sidebar, header, and content area.

```tsx
// Structure
<div className="app-shell">
  <Sidebar />
  <div className="main-wrapper">
    <Header />
    <main className="content-area">
      {children}
    </main>
  </div>
</div>

// Tailwind Classes
.app-shell: "min-h-screen bg-background flex"
.main-wrapper: "flex-1 flex flex-col ml-0 lg:ml-[270px] transition-all"
.content-area: "flex-1 p-4 md:p-6 lg:p-8"
```

### 2. Container
**Description**: Responsive content container with max-width constraints.

```tsx
// Variants
<Container size="sm|md|lg|xl|full">

// Tailwind Classes
.container-sm: "max-w-3xl mx-auto px-4"
.container-md: "max-w-5xl mx-auto px-4"
.container-lg: "max-w-7xl mx-auto px-4"
.container-xl: "max-w-[1440px] mx-auto px-4"
.container-full: "w-full px-4"
```

### 3. Grid System
**Description**: Flexible grid layout for responsive designs.

```tsx
// Basic Grid
<Grid cols={1|2|3|4|6|12} gap={2|4|6|8}>

// Tailwind Classes
"grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"

// Responsive Grid Item
<GridItem colSpan={1|2|3|4} rowSpan={1|2}>
"col-span-1 lg:col-span-2 row-span-1"
```

### 4. Stack
**Description**: Vertical or horizontal flex container with consistent spacing.

```tsx
// Variants
<Stack direction="horizontal|vertical" spacing={2|4|6|8}>

// Tailwind Classes
.stack-vertical: "flex flex-col space-y-4"
.stack-horizontal: "flex flex-row space-x-4 items-center"
```

---

## 🧭 Navigation Components

> **Note**: For detailed navigation structure per user role, see [NAV_STRUCTURE.md](NAV_STRUCTURE.md)

### 1. Sidebar
**Description**: Fixed sidebar navigation with collapsible menu items.

![Sidebar Preview](docs/assets/components/sidebar-preview.png)

```tsx
// Structure
<aside className="sidebar">
  <div className="sidebar-header">
    <Logo />
  </div>
  <nav className="sidebar-nav">
    <NavItem icon={Icon} label="Dashboard" active />
    <NavGroup label="Management">
      <NavItem />
    </NavGroup>
  </nav>
  <div className="sidebar-footer">
    <UserProfile />
  </div>
</aside>

// Tailwind Classes
.sidebar: "fixed left-0 top-0 h-full w-[270px] bg-surface border-r border-neutral-200 z-30 transform transition-transform lg:translate-x-0"
.sidebar-header: "h-16 px-6 flex items-center border-b border-neutral-200"
.sidebar-nav: "flex-1 overflow-y-auto py-4 px-4"
.sidebar-footer: "border-t border-neutral-200 p-4"

// NavItem Classes
.nav-item: "flex items-center px-4 py-3 mb-1 rounded-md hover:bg-primary/5 transition-colors cursor-pointer"
.nav-item-active: "bg-primary/10 text-primary"
.nav-item-icon: "w-5 h-5 mr-3 text-text-secondary"
.nav-item-label: "text-sm font-medium"
```

### 2. Header
**Description**: Top navigation bar with search, notifications, and user menu.

```tsx
// Structure
<header className="header">
  <div className="header-left">
    <MenuToggle />
    <SearchBar />
  </div>
  <div className="header-right">
    <NotificationDropdown />
    <UserDropdown />
  </div>
</header>

// Tailwind Classes
.header: "h-16 bg-surface border-b border-neutral-200 px-4 md:px-6 flex items-center justify-between sticky top-0 z-20"
.header-left: "flex items-center space-x-4"
.header-right: "flex items-center space-x-3"
```

### 3. Breadcrumb
**Description**: Hierarchical navigation showing current location.

```tsx
// Structure
<nav className="breadcrumb">
  <BreadcrumbItem href="/">Home</BreadcrumbItem>
  <BreadcrumbSeparator />
  <BreadcrumbItem href="/orders">Orders</BreadcrumbItem>
  <BreadcrumbSeparator />
  <BreadcrumbItem current>Order #12345</BreadcrumbItem>
</nav>

// Tailwind Classes
.breadcrumb: "flex items-center space-x-2 text-sm"
.breadcrumb-item: "text-text-secondary hover:text-primary transition-colors"
.breadcrumb-current: "text-text-primary font-medium"
.breadcrumb-separator: "text-neutral-300"
```

### 4. Tabs
**Description**: Horizontal tab navigation for content sections.

```tsx
// Structure
<div className="tabs">
  <div className="tab-list">
    <Tab active>Overview</Tab>
    <Tab>Analytics</Tab>
    <Tab>Reports</Tab>
  </div>
  <div className="tab-content">
    {activeTabContent}
  </div>
</div>

// Tailwind Classes
.tab-list: "flex border-b border-neutral-200"
.tab: "px-4 py-3 text-sm font-medium text-text-secondary hover:text-primary cursor-pointer transition-colors relative"
.tab-active: "text-primary after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-primary"
.tab-content: "py-6"
```

---

## 🎴 Card Components

### 1. Basic Card
**Description**: Container component with white background and subtle shadow.

```tsx
// Structure
<Card>
  <CardHeader>
    <CardTitle>Card Title</CardTitle>
    <CardAction>{actionButton}</CardAction>
  </CardHeader>
  <CardContent>
    {content}
  </CardContent>
  <CardFooter>
    {footerContent}
  </CardFooter>
</Card>

// Tailwind Classes
.card: "bg-surface rounded-md shadow-sm hover:shadow-md transition-shadow"
.card-header: "px-6 py-4 border-b border-neutral-100 flex items-center justify-between"
.card-title: "text-lg font-semibold text-text-primary"
.card-content: "p-6"
.card-footer: "px-6 py-4 bg-neutral-50 border-t border-neutral-100 rounded-b-md"
```

### 2. Stats Card
**Description**: Displays key metrics with icon, value, and trend.

![StatsCard Preview](docs/assets/components/statcard-preview.png)

```tsx
// Structure
<StatsCard
  icon={DollarIcon}
  title="Total Revenue"
  value="$45,832"
  trend="+12.5%"
  trendUp={true}
  color="primary"
/>

// Tailwind Classes
.stats-card: "bg-surface rounded-md shadow-sm p-6 hover:shadow-md transition-shadow"
.stats-icon-wrapper: "w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-4"
.stats-icon: "w-6 h-6 text-primary"
.stats-title: "text-sm text-text-secondary mb-1"
.stats-value: "text-2xl font-bold text-text-primary"
.stats-trend: "flex items-center mt-2 text-sm"
.stats-trend-up: "text-success"
.stats-trend-down: "text-error"
```

### 3. Widget Card
**Description**: Compact card for dashboard widgets.

```tsx
// Structure
<WidgetCard
  title="Recent Orders"
  subtitle="Last 24 hours"
  action={<Button size="sm">View All</Button>}
>
  {widgetContent}
</WidgetCard>

// Tailwind Classes
.widget-card: "bg-surface rounded-md shadow-sm"
.widget-header: "px-5 py-4 border-b border-neutral-100"
.widget-title: "text-base font-semibold text-text-primary"
.widget-subtitle: "text-sm text-text-secondary mt-0.5"
.widget-content: "p-5"
```

### 4. Feature Card
**Description**: Highlight card for features or services.

```tsx
// Structure
<FeatureCard
  icon={ChartIcon}
  title="Advanced Analytics"
  description="Get insights into your business performance"
  color="accent"
/>

// Tailwind Classes
.feature-card: "bg-surface rounded-md shadow-sm p-6 hover:shadow-lg transition-all hover:-translate-y-1"
.feature-icon: "w-16 h-16 rounded-md bg-accent/10 flex items-center justify-center mb-4"
.feature-title: "text-lg font-semibold text-text-primary mb-2"
.feature-description: "text-sm text-text-secondary leading-relaxed"
```

---

## 📝 Form Components

### 1. Input Field
**Description**: Text input with label, helper text, and validation states.

![FormField Preview](docs/assets/components/formfield-preview.png)

```tsx
// Structure
<FormField>
  <Label htmlFor="email" required>Email Address</Label>
  <Input
    id="email"
    type="email"
    placeholder="Enter your email"
    error={hasError}
  />
  <HelperText error={hasError}>
    {errorMessage || helperText}
  </HelperText>
</FormField>

// Tailwind Classes
.form-field: "mb-5"
.label: "block text-sm font-medium text-text-primary mb-2"
.label-required: "after:content-['*'] after:ml-0.5 after:text-error"
.input: "w-full px-4 py-2.5 bg-surface border border-neutral-200 rounded-md text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
.input-error: "border-error focus:ring-error/20 focus:border-error"
.helper-text: "mt-1.5 text-sm text-text-secondary"
.helper-text-error: "text-error"
```

### 2. Select Dropdown
**Description**: Dropdown selection with custom styling.

```tsx
// Structure
<FormField>
  <Label>Restaurant Location</Label>
  <Select
    options={locations}
    value={selectedLocation}
    onChange={handleChange}
    placeholder="Select location"
  />
</FormField>

// Tailwind Classes
.select: "w-full px-4 py-2.5 bg-surface border border-neutral-200 rounded-md text-text-primary appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
.select-wrapper: "relative"
.select-icon: "absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-text-secondary pointer-events-none"
```

### 3. Checkbox
**Description**: Custom styled checkbox with label.

```tsx
// Structure
<Checkbox
  id="terms"
  checked={isChecked}
  onChange={handleChange}
  label="I agree to the terms and conditions"
/>

// Tailwind Classes
.checkbox-wrapper: "flex items-start"
.checkbox-input: "w-5 h-5 mt-0.5 border-2 border-neutral-300 rounded text-primary focus:ring-2 focus:ring-primary/20 cursor-pointer"
.checkbox-label: "ml-3 text-sm text-text-primary cursor-pointer select-none"
```

### 4. Radio Button
**Description**: Radio button group for single selection.

```tsx
// Structure
<RadioGroup
  name="plan"
  value={selectedPlan}
  onChange={handleChange}
>
  <RadioOption value="basic" label="Basic Plan" />
  <RadioOption value="pro" label="Pro Plan" />
  <RadioOption value="enterprise" label="Enterprise Plan" />
</RadioGroup>

// Tailwind Classes
.radio-group: "space-y-3"
.radio-wrapper: "flex items-center"
.radio-input: "w-5 h-5 border-2 border-neutral-300 text-primary focus:ring-2 focus:ring-primary/20 cursor-pointer"
.radio-label: "ml-3 text-sm text-text-primary cursor-pointer"
```

### 5. Switch Toggle
**Description**: Toggle switch for boolean settings.

```tsx
// Structure
<Switch
  checked={isEnabled}
  onChange={handleToggle}
  label="Enable notifications"
/>

// Tailwind Classes
.switch-wrapper: "flex items-center"
.switch-track: "relative w-11 h-6 bg-neutral-300 rounded-full cursor-pointer transition-colors"
.switch-track-checked: "bg-primary"
.switch-thumb: "absolute top-0.5 left-0.5 w-5 h-5 bg-surface rounded-full shadow-sm transition-transform"
.switch-thumb-checked: "translate-x-5"
.switch-label: "ml-3 text-sm text-text-primary"
```

### 6. Textarea
**Description**: Multi-line text input.

```tsx
// Structure
<FormField>
  <Label>Description</Label>
  <Textarea
    rows={4}
    placeholder="Enter description..."
    maxLength={500}
  />
  <CharCount current={currentLength} max={500} />
</FormField>

// Tailwind Classes
.textarea: "w-full px-4 py-3 bg-surface border border-neutral-200 rounded-md text-text-primary placeholder:text-text-secondary resize-y min-h-[100px] focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-colors"
.char-count: "mt-1 text-xs text-text-secondary text-right"
```

---

## 📊 Data Display Components

### 1. Data Table
**Description**: Responsive table with sorting, filtering, and pagination.

![DataTable Preview](docs/assets/components/datatable-preview.png)

```tsx
// Structure
<DataTable
  columns={columns}
  data={data}
  sortable
  searchable
  paginated
/>

// Tailwind Classes
.table-container: "bg-surface rounded-md shadow-sm overflow-hidden"
.table: "w-full"
.table-header: "bg-neutral-50 border-b border-neutral-200"
.table-header-cell: "px-6 py-4 text-left text-sm font-medium text-text-primary"
.table-header-sortable: "cursor-pointer hover:bg-neutral-100 transition-colors"
.table-body: "divide-y divide-neutral-100"
.table-row: "hover:bg-neutral-50 transition-colors"
.table-cell: "px-6 py-4 text-sm text-text-primary"

// Mobile Responsive
.table-mobile-card: "block md:table-row bg-surface rounded-md shadow-sm p-4 mb-4"
```

### 2. List Item
**Description**: Versatile list item component for various content types.

```tsx
// Structure
<ListItem
  avatar={<Avatar src={user.avatar} />}
  title="John Doe"
  subtitle="john@example.com"
  meta="2 hours ago"
  actions={<Button size="sm">View</Button>}
/>

// Tailwind Classes
.list-item: "flex items-center px-4 py-3 hover:bg-neutral-50 transition-colors"
.list-item-avatar: "flex-shrink-0 mr-4"
.list-item-content: "flex-1 min-w-0"
.list-item-title: "text-sm font-medium text-text-primary truncate"
.list-item-subtitle: "text-sm text-text-secondary truncate"
.list-item-meta: "text-xs text-text-secondary"
.list-item-actions: "flex-shrink-0 ml-4"
```

### 3. Badge
**Description**: Small status indicator or label.

```tsx
// Variants
<Badge variant="primary|success|warning|error|neutral" size="sm|md">
  Active
</Badge>

// Tailwind Classes
.badge: "inline-flex items-center font-medium rounded-full"
.badge-sm: "px-2 py-0.5 text-xs"
.badge-md: "px-3 py-1 text-sm"

// Variants
.badge-primary: "bg-primary/10 text-primary"
.badge-success: "bg-success/10 text-success"
.badge-warning: "bg-warning/10 text-warning"
.badge-error: "bg-error/10 text-error"
.badge-neutral: "bg-neutral-100 text-text-secondary"
```

### 4. Avatar
**Description**: User profile image with fallback.

```tsx
// Sizes
<Avatar
  src={userImage}
  alt="User Name"
  size="xs|sm|md|lg|xl"
  fallback="JD"
/>

// Tailwind Classes
.avatar: "relative inline-flex items-center justify-center bg-primary/10 text-primary font-medium rounded-full overflow-hidden"
.avatar-xs: "w-6 h-6 text-xs"
.avatar-sm: "w-8 h-8 text-sm"
.avatar-md: "w-10 h-10 text-base"
.avatar-lg: "w-12 h-12 text-lg"
.avatar-xl: "w-16 h-16 text-xl"
.avatar-image: "w-full h-full object-cover"
```

### 5. Progress Bar
**Description**: Visual progress indicator.

```tsx
// Structure
<ProgressBar
  value={75}
  max={100}
  label="Upload Progress"
  showValue
  color="primary"
/>

// Tailwind Classes
.progress-container: "w-full"
.progress-label: "flex justify-between text-sm mb-2"
.progress-track: "w-full h-2 bg-neutral-200 rounded-full overflow-hidden"
.progress-bar: "h-full bg-primary rounded-full transition-all duration-300 ease-out"
.progress-value: "text-sm font-medium text-text-secondary"
```

---

## 💬 Feedback Components

### 1. Button
**Description**: Interactive button with multiple variants and sizes.

```tsx
// Variants & Sizes
<Button
  variant="primary|secondary|outline|ghost|danger"
  size="xs|sm|md|lg"
  icon={IconComponent}
  loading={isLoading}
  disabled={isDisabled}
  fullWidth
>
  Button Text
</Button>

// Tailwind Classes
.button: "inline-flex items-center justify-center font-medium rounded-md transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"

// Sizes
.button-xs: "px-2.5 py-1 text-xs"
.button-sm: "px-3 py-1.5 text-sm"
.button-md: "px-4 py-2 text-sm"
.button-lg: "px-6 py-3 text-base"

// Variants
.button-primary: "bg-primary text-white hover:bg-primary/90 focus:ring-primary"
.button-secondary: "bg-accent text-white hover:bg-accent/90 focus:ring-accent"
.button-outline: "border border-primary text-primary hover:bg-primary/5 focus:ring-primary"
.button-ghost: "text-text-primary hover:bg-neutral-100 focus:ring-neutral-300"
.button-danger: "bg-error text-white hover:bg-error/90 focus:ring-error"
```

### 2. Alert
**Description**: Contextual feedback messages.

![Alert Preview](docs/assets/components/alert-preview.png)

```tsx
// Structure
<Alert
  type="info|success|warning|error"
  title="Alert Title"
  description="Alert description text"
  closable
  icon={IconComponent}
/>

// Tailwind Classes
.alert: "relative p-4 rounded-md border"
.alert-info: "bg-accent/5 border-accent/20 text-accent"
.alert-success: "bg-success/5 border-success/20 text-success"
.alert-warning: "bg-warning/5 border-warning/20 text-warning"
.alert-error: "bg-error/5 border-error/20 text-error"
.alert-icon: "flex-shrink-0 w-5 h-5 mr-3"
.alert-content: "flex-1"
.alert-title: "font-medium mb-1"
.alert-description: "text-sm opacity-90"
.alert-close: "absolute top-3 right-3 p-1 rounded hover:bg-black/5"
```

### 3. Toast
**Description**: Temporary notification messages.

```tsx
// Structure
<Toast
  type="success|error|warning|info"
  message="Operation completed successfully"
  duration={5000}
  position="top-right"
/>

// Tailwind Classes
.toast-container: "fixed z-50 p-4 space-y-4"
.toast: "bg-surface rounded-md shadow-lg p-4 min-w-[300px] transform transition-all"
.toast-enter: "translate-x-full opacity-0"
.toast-enter-active: "translate-x-0 opacity-100"
.toast-icon: "flex-shrink-0 w-5 h-5 mr-3"
.toast-message: "flex-1 text-sm text-text-primary"
.toast-close: "ml-4 text-text-secondary hover:text-text-primary"
```

### 4. Modal
**Description**: Overlay dialog for important content.

```tsx
// Structure
<Modal
  open={isOpen}
  onClose={handleClose}
  title="Modal Title"
  size="sm|md|lg|xl"
>
  <ModalContent>
    {content}
  </ModalContent>
  <ModalFooter>
    <Button variant="ghost">Cancel</Button>
    <Button variant="primary">Confirm</Button>
  </ModalFooter>
</Modal>

// Tailwind Classes
.modal-overlay: "fixed inset-0 bg-black/50 z-40 flex items-center justify-center p-4"
.modal: "bg-surface rounded-lg shadow-xl max-h-[90vh] flex flex-col"
.modal-sm: "w-full max-w-md"
.modal-md: "w-full max-w-lg"
.modal-lg: "w-full max-w-2xl"
.modal-xl: "w-full max-w-4xl"
.modal-header: "px-6 py-4 border-b border-neutral-200"
.modal-title: "text-lg font-semibold text-text-primary"
.modal-content: "flex-1 overflow-y-auto px-6 py-4"
.modal-footer: "px-6 py-4 bg-neutral-50 border-t border-neutral-200 flex justify-end space-x-3"
```

### 5. Loading States
**Description**: Various loading indicators.

```tsx
// Spinner
<Spinner size="sm|md|lg" color="primary" />

// Skeleton
<Skeleton variant="text|rect|circle" width={200} height={20} />

// Loading Overlay
<LoadingOverlay message="Processing..." />

// Tailwind Classes
.spinner: "animate-spin rounded-full border-2 border-neutral-200"
.spinner-sm: "w-4 h-4 border-2"
.spinner-md: "w-8 h-8 border-3"
.spinner-lg: "w-12 h-12 border-4"
.spinner-primary: "border-t-primary"

.skeleton: "animate-pulse bg-neutral-200 rounded"
.skeleton-text: "h-4 rounded"
.skeleton-rect: "rounded-md"
.skeleton-circle: "rounded-full"

.loading-overlay: "fixed inset-0 bg-black/50 z-50 flex items-center justify-center"
.loading-content: "bg-surface rounded-lg p-6 flex flex-col items-center"
```

---

## 📈 Chart Components

**Chart Library Recommendation:**
- **Standard Charts**: Use Recharts for common visualizations (line, bar, pie, area)
- **Custom/Complex**: Use D3.js for specialized visualizations requiring fine control

### 1. Line Chart
**Description**: Time-series data visualization.

![LineChart Preview](docs/assets/components/linechart-preview.png)

```tsx
// Structure
<LineChart
  data={salesData}
  xAxis="date"
  yAxis="revenue"
  height={300}
  showGrid
  showTooltip
  color="primary"
/>

// Container Classes
.chart-container: "bg-surface rounded-md shadow-sm p-6"
.chart-header: "flex items-center justify-between mb-4"
.chart-title: "text-lg font-semibold text-text-primary"
.chart-legend: "flex items-center space-x-4 text-sm"
.chart-wrapper: "relative w-full"
```

### 2. Bar Chart
**Description**: Categorical data comparison.

```tsx
// Structure
<BarChart
  data={categoryData}
  categories={['Food', 'Drinks', 'Desserts']}
  vertical
  stacked={false}
  colors={['primary', 'accent', 'success']}
/>

// Styling
- Rounded bars with 4px radius
- Hover effect with opacity change
- Tooltip on hover with values
```

### 3. Donut Chart
**Description**: Proportion visualization.

```tsx
// Structure
<DonutChart
  data={proportionData}
  centerLabel="Total"
  centerValue="$45,832"
  colors={chartColors}
  size={200}
/>

// Features
- Center text display
- Interactive legend
- Hover animations
- Value tooltips
```

### 4. Stats Widget
**Description**: Mini chart with key metric.

```tsx
// Structure
<StatsWidget
  title="Daily Revenue"
  value="$4,832"
  change="+12.5%"
  sparklineData={last7Days}
  color="success"
/>

// Tailwind Classes
.stats-widget: "bg-surface rounded-md shadow-sm p-4"
.stats-widget-header: "flex items-start justify-between mb-3"
.stats-widget-value: "text-2xl font-bold text-text-primary"
.stats-widget-change: "text-sm font-medium"
.sparkline-container: "h-12 w-full"
```

---

## 🔧 Utility Components

### 1. Tooltip
**Description**: Contextual information on hover or focus.

![Tooltip Preview](docs/assets/components/tooltip-preview.png)

```tsx
// Structure
<Tooltip
  content="Helpful information"
  position="top|right|bottom|left"
  delay={500}
  theme="dark|light"
>
  <IconButton icon={InfoIcon} />
</Tooltip>

// Tailwind Classes
.tooltip-trigger: "relative inline-flex"
.tooltip: "absolute z-50 px-3 py-2 text-sm rounded-md shadow-lg pointer-events-none opacity-0 transition-opacity"
.tooltip-dark: "bg-gray-900 text-white"
.tooltip-light: "bg-surface text-text-primary border border-neutral-200"
.tooltip-visible: "opacity-100"
.tooltip-top: "bottom-full left-1/2 -translate-x-1/2 mb-2"
.tooltip-arrow: "absolute w-2 h-2 bg-inherit transform rotate-45"
```

### 2. Pagination
**Description**: Navigate through pages of content.

![Pagination Preview](docs/assets/components/pagination-preview.png)

```tsx
// Structure
<Pagination
  currentPage={currentPage}
  totalPages={totalPages}
  onPageChange={handlePageChange}
  showFirstLast
  maxPageButtons={7}
/>

// Tailwind Classes
.pagination: "flex items-center space-x-1"
.page-button: "min-w-[40px] h-10 px-3 flex items-center justify-center rounded-md border border-neutral-200 hover:bg-neutral-50 transition-colors"
.page-button-active: "bg-primary text-white border-primary hover:bg-primary/90"
.page-button-disabled: "opacity-50 cursor-not-allowed hover:bg-transparent"
.page-ellipsis: "px-2 text-text-secondary"
```

### 3. Tag/Chip
**Description**: Small labeled elements for categories or filters.

![Tag Preview](docs/assets/components/tag-preview.png)

```tsx
// Structure
<Tag
  label="Vegetarian"
  variant="solid|outlined|soft"
  color="primary|success|warning|error|info|neutral"
  size="sm|md|lg"
  icon={LeafIcon}
  onRemove={handleRemove}
  onClick={handleClick}
/>

// Tailwind Classes
.tag: "inline-flex items-center font-medium rounded-full transition-all"

// Sizes
.tag-sm: "text-xs px-2 py-0.5"
.tag-md: "text-sm px-3 py-1"
.tag-lg: "text-base px-4 py-1.5"

// Solid Variant
.tag-solid-primary: "bg-primary text-white"
.tag-solid-success: "bg-success text-white"
.tag-solid-warning: "bg-warning text-white"
.tag-solid-error: "bg-error text-white"

// Outlined Variant
.tag-outlined-primary: "border border-primary text-primary hover:bg-primary/5"
.tag-outlined-success: "border border-success text-success hover:bg-success/5"

// Soft Variant
.tag-soft-primary: "bg-primary/10 text-primary hover:bg-primary/20"
.tag-soft-success: "bg-success/10 text-success hover:bg-success/20"

// Remove Button
.tag-remove: "ml-1.5 -mr-1 p-0.5 rounded-full hover:bg-black/10"
```

### 4. Dropdown Menu
**Description**: Contextual overlay menu.

![Dropdown Preview](docs/assets/components/dropdown-preview.png)

```tsx
// Structure
<Dropdown
  trigger={<Button>Options</Button>}
  align="start|center|end"
>
  <DropdownItem icon={EditIcon}>Edit</DropdownItem>
  <DropdownItem icon={DuplicateIcon}>Duplicate</DropdownItem>
  <DropdownDivider />
  <DropdownItem icon={DeleteIcon} destructive>Delete</DropdownItem>
</Dropdown>

// Tailwind Classes
.dropdown-menu: "absolute mt-2 min-w-[200px] bg-surface rounded-md shadow-lg border border-neutral-200 py-1 z-50"
.dropdown-item: "flex items-center px-4 py-2 text-sm text-text-primary hover:bg-neutral-50 cursor-pointer"
.dropdown-item-destructive: "text-error hover:bg-error/5"
.dropdown-divider: "my-1 border-t border-neutral-200"
```

---

## 📱 Mobile-Specific Components

### 1. Mobile Navigation
**Description**: Bottom tab navigation for mobile apps.

```tsx
// Structure
<MobileNav>
  <NavTab icon={HomeIcon} label="Home" active />
  <NavTab icon={OrdersIcon} label="Orders" badge={3} />
  <NavTab icon={MenuIcon} label="Menu" />
  <NavTab icon={ProfileIcon} label="Profile" />
</MobileNav>

// Tailwind Classes
.mobile-nav: "fixed bottom-0 left-0 right-0 bg-surface border-t border-neutral-200 z-30"
.nav-tab: "flex-1 flex flex-col items-center py-2 px-1"
.nav-tab-icon: "w-6 h-6 text-text-secondary"
.nav-tab-active: "text-primary"
.nav-tab-label: "text-xs mt-1"
.nav-tab-badge: "absolute -top-1 -right-1 min-w-[18px] h-[18px] bg-error text-white text-xs rounded-full flex items-center justify-center"
```

### 2. Pull to Refresh
**Description**: Swipe down gesture to refresh content.

```tsx
// Structure
<PullToRefresh
  onRefresh={handleRefresh}
  threshold={60}
>
  <RefreshIndicator />
  {content}
</PullToRefresh>

// Visual States
- Pulling: Arrow icon rotates
- Refreshing: Spinner animation
- Complete: Checkmark icon
```

### 3. Swipeable Actions
**Description**: Swipe gestures for list item actions.

```tsx
// Structure
<SwipeableItem
  leftActions={[
    { icon: EditIcon, color: 'primary', action: handleEdit }
  ]}
  rightActions={[
    { icon: DeleteIcon, color: 'error', action: handleDelete }
  ]}
>
  <ListItem />
</SwipeableItem>

// Action Styling
.swipe-action: "flex items-center justify-center w-20 h-full"
.swipe-action-primary: "bg-primary text-white"
.swipe-action-error: "bg-error text-white"
```

### 4. Mobile Header
**Description**: Compact header for mobile screens.

```tsx
// Structure
<MobileHeader
  title="Orders"
  leftAction={<BackButton />}
  rightActions={[
    <IconButton icon={SearchIcon} />,
    <IconButton icon={FilterIcon} />
  ]}
/>

// Tailwind Classes
.mobile-header: "h-14 bg-surface border-b border-neutral-200 flex items-center justify-between px-4"
.mobile-header-title: "text-base font-semibold text-text-primary"
.mobile-header-actions: "flex items-center space-x-2"
```

### 5. Action Sheet
**Description**: Mobile-optimized modal for actions.

```tsx
// Structure
<ActionSheet
  open={isOpen}
  onClose={handleClose}
  title="Select Action"
>
  <ActionSheetItem icon={EditIcon}>Edit Order</ActionSheetItem>
  <ActionSheetItem icon={PrintIcon}>Print Receipt</ActionSheetItem>
  <ActionSheetItem icon={CancelIcon} destructive>Cancel Order</ActionSheetItem>
</ActionSheet>

// Tailwind Classes
.action-sheet: "fixed bottom-0 left-0 right-0 bg-surface rounded-t-xl shadow-xl z-50"
.action-sheet-header: "px-4 py-3 border-b border-neutral-200"
.action-sheet-item: "flex items-center px-4 py-4 hover:bg-neutral-50"
.action-sheet-destructive: "text-error"
```

---

## 📄 Page Templates

### 1. Dashboard Layout
```tsx
// Structure
<DashboardLayout>
  {/* Stats Row */}
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
    <StatsCard />
    <StatsCard />
    <StatsCard />
    <StatsCard />
  </div>
  
  {/* Charts Row */}
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
    <div className="lg:col-span-2">
      <Card title="Revenue Overview">
        <LineChart />
      </Card>
    </div>
    <div>
      <Card title="Order Distribution">
        <DonutChart />
      </Card>
    </div>
  </div>
  
  {/* Table Section */}
  <Card title="Recent Orders">
    <DataTable />
  </Card>
</DashboardLayout>
```

### 2. Form Layout
```tsx
// Structure
<FormLayout
  title="Add New Staff Member"
  breadcrumbs={breadcrumbItems}
>
  <form className="max-w-2xl">
    <Card>
      <CardContent className="space-y-6">
        {/* Personal Information */}
        <section>
          <h3 className="text-base font-semibold text-text-primary mb-4">
            Personal Information
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FormField />
            <FormField />
          </div>
        </section>
        
        {/* Contact Details */}
        <section>
          <h3 className="text-base font-semibold text-text-primary mb-4">
            Contact Details
          </h3>
          <div className="space-y-4">
            <FormField />
            <FormField />
          </div>
        </section>
      </CardContent>
      
      <CardFooter className="flex justify-end space-x-3">
        <Button variant="ghost">Cancel</Button>
        <Button variant="primary">Save Staff Member</Button>
      </CardFooter>
    </Card>
  </form>
</FormLayout>
```

### 3. List/Table Layout
```tsx
// Structure
<ListLayout
  title="Order Management"
  actions={
    <Button variant="primary" icon={PlusIcon}>
      New Order
    </Button>
  }
>
  {/* Filters Bar */}
  <Card className="mb-6">
    <CardContent className="flex flex-wrap gap-4">
      <Select placeholder="Status" />
      <Select placeholder="Date Range" />
      <Input placeholder="Search orders..." icon={SearchIcon} />
      <Button variant="outline">Apply Filters</Button>
    </CardContent>
  </Card>
  
  {/* Data Table */}
  <Card>
    <DataTable
      columns={orderColumns}
      data={orders}
      pagination
      sorting
    />
  </Card>
</ListLayout>
```

### 4. Detail/Profile Layout
```tsx
// Structure
<DetailLayout
  title="Order #12345"
  subtitle="Placed on Jan 15, 2024"
  breadcrumbs={breadcrumbItems}
  actions={
    <>
      <Button variant="outline" icon={PrintIcon}>Print</Button>
      <Button variant="primary" icon={EditIcon}>Edit</Button>
    </>
  }
>
  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
    {/* Main Content */}
    <div className="lg:col-span-2 space-y-6">
      <Card title="Order Items">
        {/* Order items list */}
      </Card>
      
      <Card title="Payment Information">
        {/* Payment details */}
      </Card>
    </div>
    
    {/* Sidebar */}
    <div className="space-y-6">
      <Card title="Customer">
        {/* Customer info */}
      </Card>
      
      <Card title="Delivery Details">
        {/* Delivery info */}
      </Card>
      
      <Card title="Order Timeline">
        {/* Status timeline */}
      </Card>
    </div>
  </div>
</DetailLayout>
```

### 5. Settings Layout
```tsx
// Structure
<SettingsLayout>
  <div className="flex flex-col lg:flex-row gap-6">
    {/* Settings Navigation */}
    <aside className="lg:w-64">
      <Card>
        <nav className="p-2">
          <SettingsNavItem active>General</SettingsNavItem>
          <SettingsNavItem>Security</SettingsNavItem>
          <SettingsNavItem>Notifications</SettingsNavItem>
          <SettingsNavItem>Integrations</SettingsNavItem>
        </nav>
      </Card>
    </aside>
    
    {/* Settings Content */}
    <div className="flex-1">
      <Card title="General Settings">
        <CardContent className="space-y-6">
          {/* Settings sections */}
        </CardContent>
      </Card>
    </div>
  </div>
</SettingsLayout>
```

---

## 🎯 Component Usage Guidelines

### Spacing Consistency
- Use spacing scale consistently: 4px, 8px, 12px, 16px, 24px, 32px, 48px
- Card padding: 24px (desktop), 16px (mobile)
- Form field spacing: 20px between fields
- Section spacing: 24px between sections

### Color Application
- Primary actions: Primary color (#3F51B5)
- Secondary actions: Accent color (#03A9F4)
- Destructive actions: Error color (#F44336)
- Disabled states: 50% opacity
- Hover states: 10% color overlay

### Typography Hierarchy
- Page titles: 24px (text-2xl), font-semibold
- Section headers: 18px (text-lg), font-semibold
- Card titles: 16px (text-base), font-semibold
- Body text: 14px (text-sm), normal weight
- Helper text: 12px (text-xs), text-secondary

### Responsive Breakpoints
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px
- Wide: > 1440px

### Animation Guidelines
- Transitions: 200ms ease-out for most interactions
- Hover effects: transform scale(1.02) for cards
- Loading states: pulse animation for skeletons
- Modal/drawer: slide and fade animations

---

This comprehensive specification document provides all the details needed to implement the AuraConnect UI using the AdminMart style with your custom color palette, without Material UI dependencies.