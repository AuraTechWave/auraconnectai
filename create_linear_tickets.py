#!/usr/bin/env python3
"""
Script to create Linear tickets from the audit report.
Requires Linear API key to be set as environment variable: LINEAR_API_KEY

Usage:
    export LINEAR_API_KEY="your-api-key-here"
    python3 create_linear_tickets.py
"""

import os
import json
import requests
from typing import Dict, List, Optional
from datetime import datetime

# Linear API Configuration
LINEAR_API_URL = "https://api.linear.app/graphql"
TEAM_KEY = "AUR"  # Update this with your actual team key

class LinearTicketCreator:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        self.team_id = None
        self.project_id = None
        self.label_ids = {}
        
    def create_query(self, query: str, variables: Dict = None) -> Dict:
        """Execute a GraphQL query against Linear API."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
            
        response = requests.post(
            LINEAR_API_URL,
            headers=self.headers,
            json=payload
        )
        
        if response.status_code != 200:
            raise Exception(f"API request failed: {response.text}")
            
        data = response.json()
        if "errors" in data:
            raise Exception(f"GraphQL errors: {data['errors']}")
            
        return data.get("data", {})
    
    def get_team_id(self) -> str:
        """Get the team ID for the AUR team."""
        query = """
        query Teams {
            teams {
                nodes {
                    id
                    key
                    name
                }
            }
        }
        """
        
        data = self.create_query(query)
        teams = data.get("teams", {}).get("nodes", [])
        
        for team in teams:
            if team["key"] == TEAM_KEY:
                self.team_id = team["id"]
                return team["id"]
                
        # If team not found, use first team
        if teams:
            self.team_id = teams[0]["id"]
            return teams[0]["id"]
            
        raise Exception("No teams found")
    
    def get_or_create_labels(self) -> Dict[str, str]:
        """Get or create labels for tickets."""
        query = """
        query Labels {
            issueLabels {
                nodes {
                    id
                    name
                }
            }
        }
        """
        
        data = self.create_query(query)
        labels = data.get("issueLabels", {}).get("nodes", [])
        
        label_map = {label["name"].lower(): label["id"] for label in labels}
        
        # Define labels we need
        needed_labels = {
            "audit": "#FF6B6B",
            "critical": "#FF0000", 
            "security": "#FFA500",
            "bug": "#FF4444",
            "frontend": "#4ECDC4",
            "backend": "#95E1D3",
            "mobile": "#3498DB",
            "performance": "#9B59B6",
            "tech-debt": "#95A5A6",
            "testing": "#F39C12",
        }
        
        # Create missing labels
        for label_name, color in needed_labels.items():
            if label_name not in label_map:
                create_mutation = """
                mutation CreateLabel($name: String!, $color: String!, $teamId: String!) {
                    issueLabelCreate(input: {
                        name: $name,
                        color: $color,
                        teamId: $teamId
                    }) {
                        issueLabel {
                            id
                            name
                        }
                    }
                }
                """
                
                try:
                    result = self.create_query(
                        create_mutation,
                        {
                            "name": label_name.title(),
                            "color": color,
                            "teamId": self.team_id
                        }
                    )
                    
                    label_data = result.get("issueLabelCreate", {}).get("issueLabel", {})
                    if label_data:
                        label_map[label_name] = label_data["id"]
                except Exception as e:
                    print(f"Warning: Could not create label {label_name}: {e}")
        
        self.label_ids = label_map
        return label_map
    
    def create_ticket(self, title: str, description: str, priority: int = 0, 
                     labels: List[str] = None, estimate: Optional[int] = None) -> str:
        """Create a single Linear ticket."""
        
        mutation = """
        mutation CreateIssue($title: String!, $description: String!, $teamId: String!, 
                           $priority: Int!, $labelIds: [String!], $estimate: Int) {
            issueCreate(input: {
                title: $title,
                description: $description,
                teamId: $teamId,
                priority: $priority,
                labelIds: $labelIds,
                estimate: $estimate
            }) {
                issue {
                    id
                    identifier
                    title
                    url
                }
            }
        }
        """
        
        # Map label names to IDs
        label_ids = []
        if labels:
            for label in labels:
                label_lower = label.lower()
                if label_lower in self.label_ids:
                    label_ids.append(self.label_ids[label_lower])
        
        variables = {
            "title": title,
            "description": description,
            "teamId": self.team_id,
            "priority": priority,
            "labelIds": label_ids if label_ids else None,
            "estimate": estimate
        }
        
        result = self.create_query(mutation, variables)
        issue = result.get("issueCreate", {}).get("issue", {})
        
        if issue:
            print(f"✅ Created: {issue['identifier']} - {issue['title']}")
            print(f"   URL: {issue['url']}")
            return issue["identifier"]
        else:
            print(f"❌ Failed to create: {title}")
            return None

def get_audit_tickets():
    """Define all tickets from the audit."""
    
    tickets = [
        # Critical Priority (P0)
        {
            "title": "Fix Database Session Management in Background Workers",
            "description": """## Bug: Database Session Management
            
Background workers (notification_worker.py, data_retention_worker.py) incorrectly use `async with get_db()` which causes database session cleanup failures and potential connection leaks.

### Affected Files
- `backend/workers/notification_worker.py`
- `backend/workers/data_retention_worker.py`

### Current Issue
```python
# Incorrect usage
async with get_db() as db:
    # operations
```

### Solution
```python
# Correct usage
db = SessionLocal()
try:
    # operations
finally:
    db.close()
```

### Acceptance Criteria
- [ ] Replace async context managers with proper synchronous session handling
- [ ] Use SessionLocal() directly with try/finally blocks  
- [ ] Add unit tests for worker database operations
- [ ] Verify no connection leaks in monitoring

### Severity
**CRITICAL** - Causes connection pool exhaustion in production""",
            "priority": 1,
            "labels": ["bug", "critical", "backend", "audit"],
            "estimate": 4
        },
        
        {
            "title": "Implement Comprehensive Tenant Isolation",
            "description": """## Security: Multi-Tenant Data Isolation

Multiple endpoints and queries don't properly filter by restaurant_id/location_id, creating potential data leakage between tenants.

### Affected Areas
- Menu recommendation service
- Customer segmentation queries  
- Analytics aggregations
- Report generation
- Order queries missing restaurant_id filter

### Security Impact
**CRITICAL** - Potential data breach between different restaurant accounts

### Acceptance Criteria
- [ ] Audit all database queries for tenant filtering
- [ ] Add middleware to enforce tenant context
- [ ] Create integration tests for multi-tenant scenarios
- [ ] Add logging for cross-tenant access attempts
- [ ] Implement query interceptor to automatically add tenant filter

### Technical Approach
1. Create base query class with automatic tenant filtering
2. Add request middleware to extract and validate tenant context
3. Implement audit logging for all data access
4. Add integration tests with multiple tenant scenarios""",
            "priority": 1,
            "labels": ["security", "critical", "backend", "audit"],
            "estimate": 16
        },
        
        {
            "title": "Add Rate Limiting to Public API Endpoints",
            "description": """## Security: API Rate Limiting

API endpoints lack rate limiting, making them vulnerable to abuse and DDoS attacks.

### Requirements
- Implement Redis-based rate limiting middleware
- Configure per-endpoint rate limits
- Add IP-based and user-based limits
- Implement rate limit headers in responses
- Create bypass mechanism for admin users

### Configuration
```python
RATE_LIMITS = {
    "auth/login": "5/minute",
    "auth/register": "3/hour",
    "public/*": "100/minute",
    "authenticated/*": "1000/minute",
    "admin/*": None  # No limit
}
```

### Acceptance Criteria
- [ ] Install and configure slowapi or similar
- [ ] Add rate limiting decorator to all endpoints
- [ ] Configure Redis for distributed rate limiting
- [ ] Add rate limit headers (X-RateLimit-*)
- [ ] Implement admin bypass
- [ ] Add monitoring and alerting""",
            "priority": 1,
            "labels": ["security", "critical", "backend", "audit"],
            "estimate": 8
        },
        
        {
            "title": "Build Frontend Authentication System",
            "description": """## Feature: Complete Frontend Authentication

Frontend completely lacks authentication UI and JWT token management.

### Components Needed
1. **Login Page**
   - Email/password form
   - Form validation
   - Error handling
   - Remember me option
   - Social login buttons (future)

2. **Logout Flow**
   - Clear tokens
   - Redirect to login
   - Clear local state

3. **Password Reset**
   - Request reset form
   - Email verification
   - New password form
   - Success confirmation

4. **Protected Routes**
   - HOC for route protection
   - Redirect to login
   - Preserve intended destination

5. **Token Management**
   - Store in httpOnly cookies
   - Automatic refresh
   - Expiry handling

### Acceptance Criteria
- [ ] Create login page with form validation
- [ ] Implement logout functionality
- [ ] Add password reset flow
- [ ] Build protected route HOC
- [ ] Implement token refresh mechanism
- [ ] Add session persistence
- [ ] Create user profile component
- [ ] Add loading states
- [ ] Implement error boundaries""",
            "priority": 1,
            "labels": ["frontend", "critical", "audit"],
            "estimate": 40
        },
        
        # High Priority (P1)
        {
            "title": "Standardize API Response Format",
            "description": """## Enhancement: API Response Standardization

API responses are inconsistent across endpoints.

### Current Issues
- Some return `{"data": {...}}`, others return direct objects
- Pagination uses different parameter names (page/size vs offset/limit)
- Error responses are inconsistent
- No standard envelope format

### Proposed Standard
```json
{
  "success": true,
  "data": {...},
  "meta": {
    "pagination": {
      "offset": 0,
      "limit": 50,
      "total": 150
    }
  },
  "errors": []
}
```

### Acceptance Criteria
- [ ] Define standard response envelope
- [ ] Update all endpoints to use consistent format
- [ ] Standardize pagination parameters
- [ ] Update API documentation
- [ ] Add response interceptor
- [ ] Update frontend to handle new format""",
            "priority": 2,
            "labels": ["backend", "tech-debt", "audit"],
            "estimate": 24
        },
        
        {
            "title": "Create Dashboard UI Components",
            "description": """## Feature: Main Dashboard Interface

Build comprehensive dashboard with real-time metrics.

### Components
1. **Metric Cards**
   - Revenue (daily/weekly/monthly)
   - Order count
   - Active customers
   - Average order value

2. **Charts**
   - Sales trend (line chart)
   - Category breakdown (pie chart)
   - Hourly sales (bar chart)
   - Table occupancy (heat map)

3. **Real-time Updates**
   - WebSocket connection
   - Live order feed
   - Kitchen status
   - Staff activity

### Acceptance Criteria
- [ ] Create responsive grid layout
- [ ] Implement metric cards
- [ ] Add chart components (Chart.js/Recharts)
- [ ] Integrate WebSocket for real-time updates
- [ ] Add date range selector
- [ ] Implement loading states
- [ ] Create empty state designs
- [ ] Add export functionality""",
            "priority": 2,
            "labels": ["frontend", "audit"],
            "estimate": 40
        },
        
        {
            "title": "Complete Mobile Offline Sync Implementation",
            "description": """## Feature: Offline Sync with Conflict Resolution

Mobile offline sync mechanism is incomplete.

### Missing Features
- Conflict resolution UI
- Sync queue management
- Network state handling
- Retry mechanism
- Manual sync trigger

### Technical Requirements
1. **Conflict Resolution**
   - Last-write-wins strategy
   - Manual resolution UI
   - Three-way merge for complex conflicts

2. **Sync Queue**
   - Priority queue for operations
   - Batch sync support
   - Progress tracking

3. **Error Recovery**
   - Exponential backoff
   - Persistent retry queue
   - Error reporting

### Acceptance Criteria
- [ ] Implement conflict resolution strategies
- [ ] Add sync queue management
- [ ] Create sync status UI indicators
- [ ] Handle network state changes
- [ ] Implement retry with exponential backoff
- [ ] Add manual sync trigger
- [ ] Create conflict resolution UI
- [ ] Add sync analytics""",
            "priority": 2,
            "labels": ["mobile", "audit"],
            "estimate": 40
        },
        
        {
            "title": "Fix N+1 Query Performance Issues",
            "description": """## Performance: Database Query Optimization

Multiple endpoints have N+1 query problems.

### Affected Endpoints
- `/api/v1/orders` - Loading customer for each order
- `/api/v1/customers` - Loading orders for each customer
- `/api/v1/menu/items` - Loading category for each item
- `/api/v1/staff/schedules` - Loading staff for each shift

### Solution Approach
```python
# Before (N+1)
orders = db.query(Order).all()
for order in orders:
    customer = order.customer  # Triggers query

# After (Eager Loading)
orders = db.query(Order).options(
    joinedload(Order.customer)
).all()
```

### Acceptance Criteria
- [ ] Add eager loading with joinedload/selectinload
- [ ] Implement query result caching
- [ ] Add database query logging in development
- [ ] Create performance tests
- [ ] Document query optimization patterns
- [ ] Add query performance monitoring""",
            "priority": 2,
            "labels": ["performance", "backend", "audit"],
            "estimate": 16
        },
        
        # Medium Priority (P2)
        {
            "title": "Implement Order Management UI",
            "description": """## Feature: Order Management Interface

Create comprehensive order management system.

### Features
- Order list with filters and search
- Order detail view with timeline
- Status update functionality
- Payment processing
- Print functionality
- Bulk actions

### Acceptance Criteria
- [ ] Create order list component
- [ ] Add filtering (status, date, customer)
- [ ] Implement search functionality
- [ ] Build order detail view
- [ ] Add status update workflow
- [ ] Integrate payment processing
- [ ] Add print functionality
- [ ] Implement bulk actions""",
            "priority": 3,
            "labels": ["frontend", "audit"],
            "estimate": 40
        },
        
        {
            "title": "Create Comprehensive Integration Test Suite",
            "description": """## Testing: Integration Tests

Build integration tests for critical flows.

### Test Scenarios
1. **Order Processing**
   - Create order
   - Process payment
   - Update status
   - Send to kitchen
   - Complete order

2. **User Authentication**
   - Registration
   - Login
   - Token refresh
   - Logout
   - Password reset

3. **Inventory Management**
   - Stock updates
   - Low stock alerts
   - Purchase orders
   - Waste tracking

### Acceptance Criteria
- [ ] Setup test database
- [ ] Create test fixtures
- [ ] Write order flow tests
- [ ] Write auth flow tests
- [ ] Write inventory tests
- [ ] Achieve 70% coverage
- [ ] Setup CI/CD integration""",
            "priority": 3,
            "labels": ["testing", "audit"],
            "estimate": 40
        },
        
        {
            "title": "Implement Redis Caching Strategy",
            "description": """## Performance: Caching Implementation

Add caching layer for frequently accessed data.

### Caching Targets
- Menu items and categories (1 hour)
- User permissions (5 minutes)
- Restaurant settings (10 minutes)
- Analytics aggregations (5 minutes)

### Implementation
```python
@cache.memoize(timeout=3600)
def get_menu_items(restaurant_id):
    return db.query(MenuItem).filter_by(
        restaurant_id=restaurant_id
    ).all()
```

### Acceptance Criteria
- [ ] Setup Redis connection pool
- [ ] Add caching decorators
- [ ] Implement cache invalidation
- [ ] Add cache warming
- [ ] Monitor cache hit rates
- [ ] Document caching patterns""",
            "priority": 3,
            "labels": ["performance", "backend", "audit"],
            "estimate": 24
        },
        
        {
            "title": "Build Staff Management Interface",
            "description": """## Feature: Staff Management UI

Create staff scheduling and management interface.

### Components
1. **Staff List**
   - Role filtering
   - Search functionality
   - Quick actions

2. **Schedule Calendar**
   - Monthly/weekly views
   - Drag-and-drop shifts
   - Conflict detection

3. **Time Management**
   - Clock in/out
   - Break tracking
   - Overtime alerts

### Acceptance Criteria
- [ ] Create staff list component
- [ ] Build calendar view
- [ ] Add shift management
- [ ] Implement time tracking
- [ ] Add payroll summary
- [ ] Create reports""",
            "priority": 3,
            "labels": ["frontend", "audit"],
            "estimate": 40
        }
    ]
    
    return tickets

def main():
    """Main function to create Linear tickets."""
    
    # Get API key from environment
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        print("❌ Error: LINEAR_API_KEY environment variable not set")
        print("Please set it with: export LINEAR_API_KEY='your-api-key-here'")
        print("\nYou can get your API key from:")
        print("https://linear.app/settings/api")
        return
    
    print("🚀 Starting Linear ticket creation...")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    try:
        # Initialize creator
        creator = LinearTicketCreator(api_key)
        
        # Get team
        print("📋 Getting team information...")
        creator.get_team_id()
        print(f"✅ Using team ID: {creator.team_id}")
        
        # Setup labels
        print("\n🏷️  Setting up labels...")
        creator.get_or_create_labels()
        print(f"✅ Labels ready: {len(creator.label_ids)} labels available")
        
        # Get tickets
        tickets = get_audit_tickets()
        print(f"\n📝 Creating {len(tickets)} tickets...")
        print("-" * 50)
        
        # Create tickets
        created_count = 0
        failed_count = 0
        
        for ticket in tickets:
            result = creator.create_ticket(
                title=ticket["title"],
                description=ticket["description"],
                priority=ticket["priority"],
                labels=ticket.get("labels", []),
                estimate=ticket.get("estimate")
            )
            
            if result:
                created_count += 1
            else:
                failed_count += 1
        
        # Summary
        print("-" * 50)
        print(f"\n✅ Successfully created: {created_count} tickets")
        if failed_count > 0:
            print(f"❌ Failed: {failed_count} tickets")
        
        print("\n📊 Summary:")
        print(f"  - Critical (P0): 4 tickets")
        print(f"  - High (P1): 4 tickets")
        print(f"  - Medium (P2): 4 tickets")
        print(f"\n🎯 Next steps:")
        print("  1. Review tickets in Linear")
        print("  2. Assign to team members")
        print("  3. Add to current sprint")
        print("  4. Update estimates if needed")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check your API key is valid")
        print("2. Ensure you have permissions to create issues")
        print("3. Verify team key 'AUR' exists in your workspace")

if __name__ == "__main__":
    main()