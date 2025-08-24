# Staff Scheduling Interface

A comprehensive staff scheduling system for AuraConnect with visual calendar, drag-and-drop functionality, and payroll integration.

## Features

### 1. Visual Schedule Calendar
- **Week/Month/Day Views**: Toggle between different calendar views
- **Color-Coded Shifts**: Different colors for regular, overtime, holiday, and training shifts
- **Staff Filtering**: View all staff or filter by individual staff members
- **Real-time Updates**: See changes immediately as shifts are created or modified

### 2. Drag-and-Drop Shift Assignment
- **Intuitive Interface**: Simply drag shifts between staff members and days
- **Visual Feedback**: See where shifts can be dropped with hover effects
- **Automatic Time Adjustment**: Shifts maintain duration when moved to different days
- **Undo Support**: Changes can be reverted if mistakes are made

### 3. Staff Availability Management
- **Weekly Availability**: Staff can set their availability for each day
- **Time Slot Selection**: Morning, afternoon, evening, or all-day availability
- **Visual Indicators**: Clear display of who's available when
- **Conflict Prevention**: System prevents scheduling when staff are unavailable

### 4. Automated Scheduling
- **Smart Generation**: Auto-generate schedules based on:
  - Shift templates
  - Staff availability
  - Overtime minimization
  - Hour balancing across staff
- **Customizable Options**: Toggle different optimization parameters
- **Preview Before Apply**: Review generated schedule before confirming

### 5. Schedule Conflict Detection
- **Real-time Validation**: Conflicts detected as shifts are created
- **Multiple Conflict Types**:
  - Double booking
  - Overtime violations
  - Unavailable staff
  - Missing required breaks
  - Insufficient rest periods
  - Skill mismatches
- **Resolution Wizard**: Step-by-step conflict resolution with multiple options

### 6. Export and Printing
- **Multiple Formats**: Export to PDF, Excel, or CSV
- **Print-Optimized Layout**: Special styling for printed schedules
- **Customizable Reports**: Include summary data and statistics
- **Batch Export**: Export multiple weeks at once

### 7. Payroll Integration
- **Automatic Calculations**:
  - Regular hours vs overtime
  - Holiday pay rates
  - Tax deductions
  - Benefits calculations
- **Payroll Preview**: Review payroll before processing
- **Export Payslips**: Generate individual or batch payslips
- **Integration Ready**: Connects with backend payroll processing

## Usage

### Creating a Shift
1. Click the "+ Add Shift" button in the toolbar
2. Select staff member and date
3. Set start and end times
4. Choose shift type (regular, overtime, etc.)
5. Add any notes if needed
6. Click "Create Shift"

### Moving a Shift
1. Click and hold on any shift in the calendar
2. Drag to a new staff member or day
3. Release to drop the shift
4. The shift will automatically update

### Managing Availability
1. Click "Staff Availability" in the toolbar
2. Select a staff member
3. Click "Edit Availability"
4. Toggle days and time slots
5. Save changes

### Generating Schedules
1. Click "Generate Schedule" dropdown
2. Select generation options
3. Click "Generate"
4. Review the generated schedule
5. Make manual adjustments if needed

### Publishing Schedules
1. Review the schedule for accuracy
2. Resolve any conflicts
3. Click "Publish Schedule"
4. Staff will be notified automatically

### Processing Payroll
1. Click "Payroll Integration"
2. Review calculated hours and pay
3. Select staff to include
4. Choose export format
5. Click "Process Payroll"

## API Integration

The interface integrates with the following backend endpoints:

- `/api/v1/staff/scheduling/shifts` - CRUD operations for shifts
- `/api/v1/staff/scheduling/templates` - Shift templates
- `/api/v1/staff/scheduling/availability` - Staff availability
- `/api/v1/staff/scheduling/generate` - Auto-generation
- `/api/v1/staff/scheduling/conflicts` - Conflict detection
- `/api/v1/staff/scheduling/publish` - Schedule publishing
- `/api/v1/staff/payroll/process` - Payroll processing

## Component Structure

```
scheduling/
├── StaffSchedulingInterface.js  # Main container component
├── ScheduleCalendar.js         # Visual calendar display
├── ScheduleToolbar.js          # Top navigation and actions
├── ShiftEditor.js              # Create/edit shift modal
├── StaffAvailability.js        # Availability management
├── ConflictResolver.js         # Conflict resolution wizard
├── PayrollIntegration.js       # Payroll calculations
├── ScheduleExporter.js         # Export utilities
└── SchedulePrint.css           # Print-specific styles
```

## Configuration

### Environment Variables
```
REACT_APP_API_URL=http://localhost:8000
```

### Customization Options
- Shift colors can be modified in `ScheduleCalendar.js`
- Working hours can be adjusted (default: 6 AM - 11 PM)
- Pay rates and deductions in `PayrollIntegration.js`
- Export formats in `ScheduleExporter.js`

## Performance Considerations

- Calendar uses virtualization for large datasets
- Drag-and-drop is optimized with React.memo
- API calls are debounced to prevent overload
- Print styles load only when needed

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Future Enhancements

- Mobile responsive design improvements
- Real-time collaboration with WebSockets
- Advanced analytics and reporting
- Integration with time clock systems
- Multi-location scheduling support