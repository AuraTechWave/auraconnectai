# Staff Scheduling Notification System - Implementation Plan

## Ticket: AUR-330 - Implement Notification System for Staff Scheduling

### Overview
Implement a comprehensive notification system for the staff scheduling module to notify staff members about schedule changes, shift assignments, and swap requests.

### Priority
Medium

### Dependencies
- Staff Scheduling System (AUR-329) - COMPLETED
- Notification Service Infrastructure (if not already implemented)

### Requirements

#### 1. Notification Types
- **Schedule Published**: Notify staff when their schedule is published
- **Shift Assigned**: Notify when a new shift is assigned
- **Shift Modified**: Notify when shift details change
- **Shift Cancelled**: Notify when a shift is cancelled
- **Swap Request**: Notify when someone requests to swap shifts
- **Swap Approved/Rejected**: Notify about swap decisions
- **Reminder**: Send shift reminders (configurable timing)

#### 2. Delivery Channels
- [ ] Email notifications
- [ ] SMS notifications (optional)
- [ ] In-app notifications
- [ ] Push notifications (mobile app)

#### 3. Implementation Tasks

##### Backend Tasks
1. **Create Notification Templates**
   ```python
   # backend/modules/notifications/templates/scheduling/
   - schedule_published.html
   - shift_assigned.html
   - shift_modified.html
   - shift_cancelled.html
   - swap_request.html
   - swap_decision.html
   - shift_reminder.html
   ```

2. **Update SchedulingService**
   ```python
   # In scheduling_service.py
   def send_schedule_published_notifications(self, shifts: List[EnhancedShift]):
       """Send notifications to all affected staff"""
       # Group shifts by staff member
       # Send batch notifications
       pass
   
   def send_shift_notification(self, shift: EnhancedShift, notification_type: str):
       """Send notification for a specific shift event"""
       pass
   ```

3. **Add Notification Preferences**
   ```python
   # New model: StaffNotificationPreferences
   class StaffNotificationPreferences(Base):
       __tablename__ = "staff_notification_preferences"
       
       staff_id = Column(Integer, ForeignKey("staff_members.id"))
       email_enabled = Column(Boolean, default=True)
       sms_enabled = Column(Boolean, default=False)
       push_enabled = Column(Boolean, default=True)
       reminder_hours_before = Column(Integer, default=24)
       # Specific preferences for each notification type
   ```

4. **Create Notification Queue Worker**
   ```python
   # backend/workers/notification_worker.py
   - Process notification queue
   - Handle retries
   - Log delivery status
   ```

##### Integration Points

1. **Update publish_schedule() in SchedulingService**
   ```python
   def publish_schedule(self, location_id: int, start_date: date, end_date: date, notify: bool = True):
       # ... existing code ...
       
       if notify and shifts:
           # Queue notifications
           notification_service.queue_bulk_notifications(
               notification_type="schedule_published",
               recipients=affected_staff,
               context={
                   "start_date": start_date,
                   "end_date": end_date,
                   "shift_count": len(shifts)
               }
           )
   ```

2. **Update shift swap methods**
   ```python
   def create_swap_request(self, ...):
       # ... existing code ...
       
       # Notify target staff member
       notification_service.send_notification(
           staff_id=target_staff_id,
           type="swap_request",
           context={
               "requester_name": requester.name,
               "shift_date": shift.date,
               "shift_time": f"{shift.start_time} - {shift.end_time}"
           }
       )
   ```

3. **Add shift reminder cron job**
   ```python
   # backend/cron/shift_reminders.py
   def send_shift_reminders():
       """Send reminders for upcoming shifts"""
       tomorrow = date.today() + timedelta(days=1)
       shifts = get_tomorrow_shifts()
       
       for shift in shifts:
           if should_send_reminder(shift):
               send_reminder_notification(shift)
   ```

### Database Migrations

```sql
-- Add notification tracking
CREATE TABLE notification_logs (
    id SERIAL PRIMARY KEY,
    staff_id INTEGER REFERENCES staff_members(id),
    notification_type VARCHAR(50),
    channel VARCHAR(20),
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    context JSONB,
    error_message TEXT
);

-- Add notification preferences
CREATE TABLE staff_notification_preferences (
    id SERIAL PRIMARY KEY,
    staff_id INTEGER REFERENCES staff_members(id) UNIQUE,
    email_enabled BOOLEAN DEFAULT true,
    sms_enabled BOOLEAN DEFAULT false,
    push_enabled BOOLEAN DEFAULT true,
    reminder_hours_before INTEGER DEFAULT 24,
    schedule_published_email BOOLEAN DEFAULT true,
    schedule_published_push BOOLEAN DEFAULT true,
    shift_assigned_email BOOLEAN DEFAULT true,
    shift_assigned_push BOOLEAN DEFAULT true,
    -- ... other preferences
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### API Endpoints

```http
# Get notification preferences
GET /api/v1/staff/notifications/preferences

# Update notification preferences
PUT /api/v1/staff/notifications/preferences

# Get notification history
GET /api/v1/staff/notifications/history

# Mark notification as read
PUT /api/v1/staff/notifications/{notification_id}/read
```

### Testing Requirements

1. **Unit Tests**
   - Test notification template rendering
   - Test preference filtering
   - Test notification queuing

2. **Integration Tests**
   - Test end-to-end notification flow
   - Test delivery channel fallbacks
   - Test batch notification performance

3. **Manual Testing**
   - Verify email formatting
   - Test SMS delivery
   - Verify push notifications on mobile

### Success Criteria

- [ ] All notification types implemented
- [ ] Email notifications working
- [ ] Notification preferences configurable
- [ ] Delivery tracking implemented
- [ ] Performance: Can handle 1000+ notifications per minute
- [ ] Error handling and retry logic
- [ ] Documentation updated

### Estimated Effort
- Backend implementation: 3-4 days
- Frontend preferences UI: 2 days
- Testing: 2 days
- Total: 7-8 days

### Notes
- Consider using existing notification service if available
- Implement rate limiting to prevent notification spam
- Add unsubscribe links to emails for compliance
- Consider notification batching for efficiency