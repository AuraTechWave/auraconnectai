# Insights Dashboard Frontend Requirements

## Overview
The Insights Dashboard provides a comprehensive view of AI-generated business insights, allowing restaurant staff to monitor, track, and act on opportunities for improvement.

## Dashboard Components

### 1. Main Dashboard View

#### Header Section
- **Insight Summary Cards**
  - Total Active Insights (with severity breakdown)
  - Insights Requiring Action
  - Total Estimated Value
  - Acceptance Rate (last 30 days)
  - Average Time to Acknowledge

#### Filters and Controls
- **Time Range Selector**: Today, 7 days, 30 days, Custom
- **Domain Filter**: Sales, Inventory, Staff, Customer, Operations, Finance, Marketing
- **Type Filter**: Performance, Trend, Anomaly, Optimization, Warning, Opportunity
- **Severity Filter**: Critical, High, Medium, Low, Info
- **Status Filter**: Active, Acknowledged, Resolved, Dismissed

#### Insights List/Grid
- **Card View** (default)
  - Title with severity indicator (color-coded)
  - Domain and type badges
  - Impact score visualization (progress bar)
  - Estimated value
  - Key metrics preview
  - Quick actions (Acknowledge, Rate, View Details)
  - Thread indicator if part of a thread

- **Table View** (alternative)
  - Sortable columns: Date, Title, Domain, Type, Severity, Impact, Value, Status
  - Inline actions
  - Bulk selection for batch operations

### 2. Insight Detail View

#### Header
- Title with severity badge
- Status indicator with timeline
- Thread navigation (if applicable)

#### Main Content
- **Description**: Full insight description
- **Impact Analysis**
  - Impact score with visualization
  - Estimated monetary value
  - Affected metrics with charts

- **Recommendations**
  - Actionable steps list
  - Priority indicators
  - Implementation complexity

- **Data Visualization**
  - Relevant charts/graphs based on insight type
  - Trend lines for historical context
  - Comparison data if available

#### Sidebar
- **Actions Panel**
  - Acknowledge button
  - Mark as Resolved
  - Dismiss with reason
  - Share via email/Slack
  - Export to PDF

- **Rating Widget**
  - Quick rating buttons: Useful, Irrelevant, Needs Follow-up
  - Comment field

- **Activity Timeline**
  - Creation timestamp
  - User interactions
  - Status changes
  - Related actions

### 3. Insight Threads View

#### Thread List
- Thread title with category
- Total insights count
- Total value accumulated
- Recurrence indicator
- Latest activity timestamp

#### Thread Timeline
- Visual timeline of insights
- Cumulative value chart
- Pattern indicators
- Resolution progress

#### Thread Actions
- Merge threads
- Split insights
- Export thread history
- Set thread alerts

### 4. Analytics Dashboard

#### Performance Metrics
- **Insight Generation**
  - Volume by domain/type
  - Generation trends
  - Generator performance

- **User Engagement**
  - Rating distribution
  - Acknowledgment times
  - Action completion rates

- **Business Impact**
  - Total value captured
  - Value by domain
  - ROI tracking

#### Visualizations
- Heatmap of insight activity
- Sankey diagram for insight flow
- Time series for trends
- Pie charts for distributions

### 5. Notification Settings

#### Rule Configuration
- Domain selection
- Type selection
- Severity threshold
- Impact/value thresholds
- Channel configuration (Email, Slack, Webhook)
- Recipient management
- Schedule settings (immediate vs batch)

#### Rate Limiting
- Per-hour limits
- Per-day limits
- Quiet hours configuration

## Technical Requirements

### State Management
```typescript
interface InsightState {
  insights: Insight[];
  activeFilters: FilterState;
  selectedInsight: Insight | null;
  threads: Thread[];
  analytics: AnalyticsData;
  notifications: NotificationRule[];
}
```

### API Integration
- WebSocket for real-time updates
- REST endpoints for CRUD operations
- Batch operations support
- Export functionality

### Component Library
- Card components with severity theming
- Timeline visualization
- Chart components (line, bar, pie, heatmap)
- Rating widget
- Action buttons with loading states
- Filter components
- Notification badges

### Performance
- Virtualized lists for large datasets
- Lazy loading for detail views
- Optimistic updates for actions
- Caching strategy for analytics

### Responsive Design
- Mobile-friendly card layout
- Touch-optimized actions
- Collapsible sidebar on mobile
- Swipe gestures for navigation

## User Flows

### 1. Daily Review Flow
1. User opens dashboard
2. Views new insights since last visit
3. Acknowledges critical insights
4. Rates useful insights
5. Dismisses irrelevant ones
6. Reviews threads for patterns

### 2. Deep Dive Flow
1. User filters by specific domain
2. Sorts by estimated value
3. Opens high-value insight
4. Reviews recommendations
5. Exports for team discussion
6. Marks for implementation

### 3. Trend Analysis Flow
1. User navigates to threads
2. Selects recurring thread
3. Views timeline visualization
4. Analyzes pattern data
5. Sets up alerts for future

## Accessibility Requirements
- ARIA labels for all interactive elements
- Keyboard navigation support
- Screen reader compatibility
- High contrast mode support
- Focus indicators

## Security Considerations
- Role-based access control
- Audit logging for actions
- Secure export handling
- XSS prevention in user content

## Integration Points
- Order Management: Link to relevant orders
- Inventory: Show affected products
- Staff: Display team performance insights
- Customer: Link to customer segments
- Financial: Connect to revenue reports

## Future Enhancements
1. AI-powered insight clustering
2. Predictive insight forecasting
3. Custom insight generators
4. Mobile app with push notifications
5. Voice interface for insight review
6. Collaborative annotation tools
7. A/B testing for recommendations
8. Machine learning feedback loop