# AuraConnect Testing Checklist

This checklist covers all features and modules that should be tested manually.

## Pre-Testing Setup

- [ ] Run `./check-dependencies.sh` to verify all dependencies
- [ ] Run `./setup-environment.sh` if any dependencies are missing
- [ ] Run `./start-all.sh` to start all services
- [ ] Verify all services are running:
  - [ ] Backend: http://localhost:8000/docs
  - [ ] Frontend: http://localhost:3000
  - [ ] Customer Web: http://localhost:3001
  - [ ] Mobile Metro: http://localhost:8081

## 1. Authentication & Authorization

### Login/Logout
- [ ] Login with admin credentials (admin/admin123)
- [ ] Login with manager credentials (manager/manager123)
- [ ] Login with staff credentials (staff/staff123)
- [ ] Login with invalid credentials
- [ ] Logout functionality
- [ ] Session timeout handling
- [ ] Remember me functionality

### Role-Based Access Control
- [ ] Admin can access all features
- [ ] Manager cannot access system settings
- [ ] Staff has read-only access to most features
- [ ] Unauthorized access shows proper error messages

### Password Management
- [ ] Change password
- [ ] Password strength validation
- [ ] Password reset via email

## 2. Staff Management

### Staff Profiles
- [ ] Create new staff member
- [ ] Edit staff information
- [ ] Upload staff photo
- [ ] Set hourly rate and benefits
- [ ] Assign roles and permissions
- [ ] Deactivate staff member

### Scheduling
- [ ] Create weekly schedule
- [ ] Copy schedule from previous week
- [ ] Assign shifts to staff
- [ ] Handle shift swaps
- [ ] View schedule calendar
- [ ] Print schedule

### Attendance
- [ ] Clock in/out
- [ ] View attendance history
- [ ] Mark late arrivals
- [ ] Handle overtime
- [ ] Generate attendance reports

### Payroll
- [ ] Calculate payroll for period
- [ ] Include overtime calculations
- [ ] Apply deductions
- [ ] Generate pay stubs
- [ ] Export payroll data
- [ ] Tax calculations (federal, state, local)

## 3. Menu Management

### Categories
- [ ] Create menu category
- [ ] Edit category details
- [ ] Set category order
- [ ] Enable/disable category
- [ ] Delete empty category

### Menu Items
- [ ] Create new menu item
- [ ] Upload item images
- [ ] Set pricing
- [ ] Add item description
- [ ] Set availability schedule
- [ ] Configure modifiers
- [ ] Clone existing item

### Recipe Management (BOM)
- [ ] Create recipe for menu item
- [ ] Add ingredients with quantities
- [ ] Calculate recipe cost
- [ ] Create sub-recipes
- [ ] View recipe history
- [ ] Export/import recipes
- [ ] Recipe compliance report

### Modifiers
- [ ] Create modifier groups
- [ ] Add modifiers to groups
- [ ] Set price adjustments
- [ ] Configure required/optional modifiers
- [ ] Set min/max selections

## 4. Order Management

### Create Orders
- [ ] Create dine-in order
- [ ] Create takeout order
- [ ] Create delivery order
- [ ] Add items to order
- [ ] Apply modifiers
- [ ] Add special instructions
- [ ] Apply discounts/promotions

### Order Processing
- [ ] View incoming orders
- [ ] Accept/reject orders
- [ ] Update order status
- [ ] Print order tickets
- [ ] Split bills
- [ ] Merge orders

### Kitchen Display System
- [ ] View orders by station
- [ ] Mark items as started
- [ ] Mark items as completed
- [ ] Handle order modifications
- [ ] View order timing
- [ ] Alert for delayed orders

### Payment Processing
- [ ] Process cash payment
- [ ] Process credit card
- [ ] Split payment methods
- [ ] Apply tips
- [ ] Process refunds
- [ ] Print receipts

## 5. Inventory Management

### Items
- [ ] Add inventory items
- [ ] Set reorder points
- [ ] Track unit costs
- [ ] View stock levels
- [ ] Low stock alerts
- [ ] Expired item alerts

### Vendors
- [ ] Add vendors
- [ ] Edit vendor information
- [ ] View vendor catalogs
- [ ] Track vendor performance

### Purchase Orders
- [ ] Create purchase order
- [ ] Send PO to vendor
- [ ] Receive shipments
- [ ] Handle partial deliveries
- [ ] Track discrepancies
- [ ] Update inventory on receipt

### Stock Management
- [ ] Perform stock counts
- [ ] Adjust stock levels
- [ ] Track waste/spillage
- [ ] Transfer between locations
- [ ] Generate inventory reports

## 6. Customer Management

### Customer Profiles
- [ ] Register new customer
- [ ] Edit customer information
- [ ] View order history
- [ ] Track preferences
- [ ] Add notes
- [ ] Merge duplicate profiles

### Loyalty Program
- [ ] Enroll in loyalty program
- [ ] Earn points on orders
- [ ] Redeem rewards
- [ ] View points balance
- [ ] Set point multipliers
- [ ] Birthday rewards

### Feedback
- [ ] Submit feedback
- [ ] Rate orders
- [ ] View feedback dashboard
- [ ] Respond to feedback
- [ ] Generate feedback reports

## 7. Table Management

### Table Layout
- [ ] Configure dining areas
- [ ] Add/remove tables
- [ ] Set table capacity
- [ ] Arrange table layout
- [ ] Group tables

### Real-time Status
- [ ] View table availability
- [ ] Seat customers
- [ ] Mark table as occupied
- [ ] Track dining duration
- [ ] Clean table status
- [ ] Combine/split tables

### Reservations
- [ ] Create reservation
- [ ] Edit reservation details
- [ ] Cancel reservation
- [ ] View reservation calendar
- [ ] Handle walk-ins
- [ ] Waitlist management

## 8. Analytics & Reports

### Sales Analytics
- [ ] Daily sales summary
- [ ] Sales by category
- [ ] Top selling items
- [ ] Sales trends
- [ ] Comparative analysis
- [ ] Export reports

### Performance Metrics
- [ ] Table turnover rate
- [ ] Average order value
- [ ] Staff performance
- [ ] Kitchen efficiency
- [ ] Customer satisfaction

### Financial Reports
- [ ] Profit & loss
- [ ] Cash flow
- [ ] Expense tracking
- [ ] Tax reports
- [ ] Payroll summary

## 9. POS Integration

### Menu Sync
- [ ] Sync menu from POS
- [ ] Map POS items to system
- [ ] Handle price updates
- [ ] Sync modifiers
- [ ] Conflict resolution

### Order Sync
- [ ] Import POS orders
- [ ] Export system orders
- [ ] Handle order updates
- [ ] Sync payment status

### Reconciliation
- [ ] Daily reconciliation
- [ ] Identify discrepancies
- [ ] Generate variance reports
- [ ] Audit trail

## 10. Settings & Configuration

### Restaurant Settings
- [ ] Update restaurant info
- [ ] Set operating hours
- [ ] Configure tax rates
- [ ] Set currency/timezone
- [ ] Upload logo/branding

### System Settings
- [ ] Configure order settings
- [ ] Set notification preferences
- [ ] Configure receipt templates
- [ ] API settings
- [ ] Security settings

### Integration Settings
- [ ] Configure POS integration
- [ ] Email settings
- [ ] SMS settings (Twilio)
- [ ] Payment gateway
- [ ] Third-party services

## 11. Notifications

### Email Notifications
- [ ] Order confirmation emails
- [ ] Staff schedule emails
- [ ] Low inventory alerts
- [ ] Daily summary emails

### SMS Notifications
- [ ] Order ready SMS
- [ ] Table ready SMS
- [ ] Staff alerts
- [ ] Promotional SMS

### Push Notifications (Mobile)
- [ ] Order updates
- [ ] Staff notifications
- [ ] System alerts
- [ ] Promotional messages

## 12. Mobile App Testing

### Customer App Features
- [ ] Browse menu
- [ ] Place order
- [ ] Track order status
- [ ] View order history
- [ ] Manage profile
- [ ] Loyalty features

### Staff App Features
- [ ] Clock in/out
- [ ] View schedule
- [ ] Swap shifts
- [ ] View notifications
- [ ] Update availability

### Offline Functionality
- [ ] Cache critical data
- [ ] Queue actions offline
- [ ] Sync when online
- [ ] Handle conflicts

## 13. Health Monitoring

### System Health
- [ ] View health dashboard
- [ ] Check service status
- [ ] Monitor performance metrics
- [ ] View error logs
- [ ] Set up alerts

### Performance Monitoring
- [ ] API response times
- [ ] Database performance
- [ ] Memory usage
- [ ] CPU utilization
- [ ] Disk space

## 14. Security Testing

### Authentication Security
- [ ] Test SQL injection on login
- [ ] Test XSS vulnerabilities
- [ ] Test CSRF protection
- [ ] Session hijacking prevention
- [ ] Rate limiting

### Data Security
- [ ] Verify HTTPS usage
- [ ] Check data encryption
- [ ] Test API authentication
- [ ] Verify permission checks
- [ ] Audit logging

## 15. Performance Testing

### Load Testing
- [ ] Multiple concurrent users
- [ ] Large order volumes
- [ ] Menu with many items
- [ ] Historical data queries
- [ ] Report generation

### Stress Testing
- [ ] Peak hours simulation
- [ ] Database connection limits
- [ ] Memory limits
- [ ] API rate limits
- [ ] Concurrent modifications

## Post-Testing Cleanup

- [ ] Stop all services with `./dev-helper.sh`
- [ ] Create database backup if needed
- [ ] Document any issues found
- [ ] Clear test data if needed

## Issue Tracking

Use this section to note any issues found during testing:

| Module | Issue Description | Severity | Status |
|--------|------------------|----------|---------|
| | | | |
| | | | |
| | | | |

## Notes

- Always test with different user roles
- Test both happy path and error scenarios
- Verify data persistence across sessions
- Check responsive design on different devices
- Test real-time features with multiple users