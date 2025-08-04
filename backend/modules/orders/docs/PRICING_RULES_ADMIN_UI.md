# Pricing Rules Admin UI Requirements

## Overview

The Pricing Rules Admin UI should provide an intuitive interface for restaurant managers to create, manage, and monitor pricing rules without requiring technical knowledge.

## Key Features

### 1. Rule Dashboard

**Main View:**
- Summary cards showing:
  - Total active rules
  - Rules applied today
  - Total discount given today
  - Top performing rules
- Quick actions:
  - Create new rule
  - View all rules
  - View metrics

**Rule List View:**
- Sortable/filterable table with columns:
  - Rule name
  - Type (icon + label)
  - Status (active/inactive/scheduled/expired)
  - Priority
  - Current uses / Max uses
  - Discount given (lifetime)
  - Actions (edit, clone, deactivate)
- Filters:
  - By status
  - By type
  - By date range
  - Search by name/code

### 2. Rule Builder

**Step 1: Basic Information**
```
Rule Name: [___________________]
Description: [___________________]
Rule Type: [Dropdown: Percentage/Fixed/BOGO/Bundle/etc]
Priority: [1-5 slider]
```

**Step 2: Discount Configuration**
- Dynamic form based on rule type:
  - Percentage: Discount % + optional max amount
  - Fixed: Discount amount
  - BOGO: Buy X Get Y configuration
  - Bundle: Item selection interface
  
**Step 3: Conditions Builder (Visual)**

*Time Conditions:*
- Day picker (Mon-Sun checkboxes)
- Time range picker (visual)
- Date range picker (calendar)
- Timezone selector

*Item Conditions:*
- Menu item selector (searchable multi-select)
- Category selector
- Exclude items option
- Quantity ranges

*Customer Conditions:*
- Loyalty tier checkboxes
- Order history sliders
- Customer tag selector
- New customer toggle

*Order Conditions:*
- Order type checkboxes
- Payment method selection
- Min/max order amount sliders

**Step 4: Validity & Limits**
```
Valid From: [Date/Time picker]
Valid Until: [Date/Time picker] (optional)
Max Total Uses: [Number input] (optional)
Max Uses Per Customer: [Number input] (optional)
```

**Step 5: Advanced Settings**
- Stackable toggle
- Exclude with other rules (multi-select)
- Requires promo code (toggle + input)
- Tags for organization

**Step 6: Preview & Test**
- Summary of rule configuration
- Test against sample order
- Estimated impact preview

### 3. Rule Testing Interface

**Debug Mode Panel:**
```
Test Order Details:
- Items: [Add test items]
- Customer: [Select test customer]
- Order Type: [Select]
- Time: [Override current time]

[Run Test]

Results:
✓ Rule "Happy Hour 20%" - Applied
  - Time condition: ✓ Met (14:00-17:00)
  - Item condition: ✓ Met (Contains drinks)
  - Discount: $5.00

✗ Rule "VIP Discount" - Skipped
  - Customer condition: ✗ Not met (Not VIP tier)
```

### 4. Metrics & Analytics

**Rule Performance Dashboard:**
- Line chart: Applications over time
- Bar chart: Discount by rule type
- Pie chart: Rule usage distribution
- Table: Top rules by revenue impact

**Individual Rule Analytics:**
- Usage timeline
- Customer breakdown
- Average discount amount
- Conversion impact
- Conflict/stacking frequency

### 5. Promo Code Management

**Promo Code List:**
- Code
- Associated rule
- Uses/Limit
- Status
- Quick copy button

**Bulk Generation:**
- Generate X unique codes
- Set prefix/suffix
- Export to CSV

### 6. Conflict Resolution Viewer

**Visual Conflict Map:**
- Shows which rules may conflict
- Highlights resolution method
- Suggests optimizations

## UI/UX Guidelines

### Visual Design
- Use color coding for rule types
- Status indicators (green=active, yellow=scheduled, red=expired)
- Clear iconography for each condition type
- Progress indicators for multi-step forms

### Interaction Patterns
- Drag-and-drop for priority ordering
- Inline editing for quick changes
- Bulk actions (activate/deactivate multiple)
- Undo/redo for rule builder
- Auto-save drafts

### Validation & Feedback
- Real-time validation as user builds rules
- Clear error messages with suggestions
- Warning for potential conflicts
- Success notifications with metrics

### Mobile Considerations
- Responsive design for tablet use
- Simplified mobile view for quick edits
- Touch-friendly controls
- Offline capability for viewing

## Technical Requirements

### Frontend Framework Options
1. **React + Material-UI/Ant Design**
   - Component library for rapid development
   - Built-in form validation
   - Date/time pickers
   - Data tables

2. **Vue.js + Vuetify**
   - Simpler learning curve
   - Great for forms
   - Built-in validation

3. **Angular + Angular Material**
   - Enterprise-ready
   - Strong typing
   - Comprehensive tooling

### Key Libraries Needed
- Date/time picker with timezone support
- Multi-select with search
- Drag-and-drop for priorities
- Chart library (Chart.js/D3.js)
- Form validation library
- JSON editor for advanced users

### API Integration
- Real-time validation endpoint
- Batch operations support
- WebSocket for live metrics
- Export capabilities

## Implementation Phases

### Phase 1: Basic CRUD
- Rule list view
- Basic rule creation form
- Edit/delete functionality
- Simple conditions

### Phase 2: Advanced Features
- Visual condition builder
- Rule testing interface
- Basic metrics display
- Promo code support

### Phase 3: Analytics & Optimization
- Full analytics dashboard
- Conflict resolution tools
- Bulk operations
- Advanced filtering

### Phase 4: Intelligence
- Rule recommendations
- Automated optimization
- A/B testing interface
- Predictive analytics

## Success Metrics
- Time to create a rule: < 2 minutes
- Error rate in rule creation: < 5%
- User satisfaction score: > 4.5/5
- Rules created per user per month
- Percentage of rules with errors

## Accessibility Requirements
- WCAG 2.1 AA compliance
- Keyboard navigation
- Screen reader support
- High contrast mode
- Clear focus indicators