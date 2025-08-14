# Overtime Management System

## Overview

The Overtime Management System provides comprehensive overtime calculation, configuration, and analytics capabilities for the AuraConnect AI staff management platform.

## Features

### 1. Configurable Overtime Rules
- **Daily Overtime Threshold**: Configurable hours per day before overtime (default: 8 hours)
- **Weekly Overtime Threshold**: Configurable hours per week before overtime (default: 40 hours)
- **Overtime Multiplier**: Configurable overtime pay rate (default: 1.5x)
- **Double Time Threshold**: Configurable hours per day before double time (default: 12 hours)
- **Double Time Multiplier**: Configurable double time pay rate (default: 2.0x)

### 2. Advanced Overtime Calculation
- **Daily Overtime**: Hours worked beyond daily threshold
- **Weekly Overtime**: Hours worked beyond weekly threshold
- **Double Time**: Hours worked beyond double time threshold
- **Precision Handling**: Decimal arithmetic for financial accuracy
- **Edge Case Handling**: Proper handling of overlapping overtime rules

### 3. Analytics and Reporting
- **Staff Overtime Analytics**: Per-staff overtime breakdown
- **Location Analytics**: Location-based overtime reporting
- **Period Analytics**: Date range overtime analysis
- **Summary Statistics**: Aggregated overtime metrics

## API Endpoints

### Configuration Management

#### GET /overtime/rules
Get current overtime rules configuration.

**Parameters:**
- `location` (string, optional): Location identifier (default: "default")

**Response:**
```json
{
  "daily_threshold": 8.0,
  "weekly_threshold": 40.0,
  "overtime_multiplier": 1.5,
  "double_time_threshold": 12.0,
  "double_time_multiplier": 2.0
}
```

#### PUT /overtime/rules
Update overtime rules configuration.

**Parameters:**
- `rules` (object): Overtime rules to update
- `location` (string, optional): Location identifier
- `description` (string, optional): Description of the change

**Request Body:**
```json
{
  "daily_threshold": 8.5,
  "weekly_threshold": 42.0,
  "overtime_multiplier": 1.5
}
```

**Response:**
```json
{
  "message": "Overtime rules updated successfully",
  "rules": {
    "daily_threshold": 8.5,
    "weekly_threshold": 42.0,
    "overtime_multiplier": 1.5,
    "double_time_threshold": 12.0,
    "double_time_multiplier": 2.0
  }
}
```

#### POST /overtime/validate
Validate overtime rules without applying them.

**Request Body:**
```json
{
  "daily_threshold": 8.5,
  "weekly_threshold": 42.0,
  "overtime_multiplier": 1.5
}
```

**Response:**
```json
{
  "valid": true,
  "errors": []
}
```

### Analytics

#### GET /overtime/analytics
Get overtime analytics for a date range.

**Parameters:**
- `start_date` (date, required): Start date (YYYY-MM-DD)
- `end_date` (date, required): End date (YYYY-MM-DD)
- `location_id` (integer, optional): Filter by location
- `staff_id` (integer, optional): Filter by staff member

**Response:**
```json
{
  "period": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  },
  "analytics": [
    {
      "staff_id": 1,
      "staff_name": "John Doe",
      "total_hours": 180.0,
      "regular_hours": 160.0,
      "overtime_hours": 20.0,
      "double_time_hours": 0.0,
      "days_worked": 22,
      "average_hours_per_day": 8.18,
      "days_with_overtime": 5,
      "overtime_percentage": 11.11
    }
  ],
  "summary": {
    "total_staff": 1,
    "total_overtime_hours": 20.0,
    "average_overtime_percentage": 11.11,
    "staff_with_overtime": 1
  }
}
```

## Validation Rules

### Overtime Rules Validation
- **Daily Threshold**: Must be between 4 and 12 hours
- **Weekly Threshold**: Must be between 30 and 60 hours
- **Overtime Multiplier**: Must be between 1.0 and 3.0
- **Double Time Threshold**: Must be greater than daily threshold
- **Double Time Multiplier**: Must be greater than overtime multiplier

### Input Validation
- **Date Range**: End date must be after start date and within 1 year
- **Location ID**: Must be a positive integer
- **Staff ID**: Must be a positive integer
- **Description**: Sanitized to prevent injection attacks

## Security Features

### Rate Limiting
- **Update Rules**: 10 requests per minute
- **Validate Rules**: 20 requests per minute
- **Analytics**: 30 requests per minute

### Security Headers
- **X-Content-Type-Options**: nosniff
- **X-Frame-Options**: DENY
- **X-XSS-Protection**: 1; mode=block
- **Strict-Transport-Security**: max-age=31536000; includeSubDomains
- **Content-Security-Policy**: default-src 'self'

### Caching
- **ETag Support**: Cache validation using ETags
- **Cache-Control**: 5-minute cache for rules endpoint
- **Config Caching**: 5-minute cache for configuration data

## Permissions

### Required Permissions
- **view_overtime_rules**: View overtime rules configuration
- **manage_overtime_rules**: Update overtime rules configuration
- **view_overtime_analytics**: View overtime analytics

### Role-Based Access
- **Manager**: Full access to all overtime management features
- **Supervisor**: View access to rules and analytics
- **Staff**: No access to overtime management

## Error Handling

### Common Error Codes
- `400 Bad Request`: Invalid input data
- `403 Forbidden`: Insufficient permissions
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

### Error Response Format
```json
{
  "detail": {
    "message": "Invalid overtime rules configuration",
    "errors": [
      "Daily overtime threshold should be between 4 and 12 hours"
    ]
  }
}
```

## Performance Considerations

### Optimization Features
- **SQL Aggregation**: Efficient database queries using SQL aggregation
- **Batch Processing**: Process multiple staff members efficiently
- **Caching**: Configuration and analytics caching
- **Decimal Precision**: Accurate financial calculations

### Scalability
- **Multi-tenant Support**: Location-based configuration
- **Async Operations**: Non-blocking database operations
- **Memory Efficient**: Streaming processing for large datasets
- **Error Isolation**: Individual staff errors don't affect batch processing

## Compliance

### Labor Law Compliance
- **FLSA Compliance**: Follows Fair Labor Standards Act guidelines
- **State Variations**: Supports state-specific overtime rules
- **Audit Trail**: Complete calculation documentation
- **Validation**: Ensures rules comply with legal requirements

### Data Protection
- **Input Sanitization**: Prevents injection attacks
- **Access Control**: Role-based permissions
- **Audit Logging**: Complete operation logging
- **Data Encryption**: Sensitive data encryption

## Integration

### Payroll Integration
- **Enhanced Payroll Engine**: Direct integration with payroll calculations
- **Tax Services**: Integration with tax calculation services
- **Payment Records**: Automatic payment record generation
- **Historical Data**: Complete overtime history tracking

### Scheduling Integration
- **Schedule Analytics**: Overtime analysis for scheduling decisions
- **Conflict Detection**: Overtime-aware scheduling conflicts
- **Cost Estimation**: Real-time labor cost calculations
- **Compliance Checking**: Overtime compliance validation

## Testing

### Unit Tests
- **Configuration Validation**: Test rule validation logic
- **Overtime Calculation**: Test calculation accuracy
- **Edge Cases**: Test boundary conditions
- **Error Handling**: Test error scenarios

### Integration Tests
- **API Endpoints**: Test complete API workflows
- **Database Operations**: Test database interactions
- **Permission System**: Test access control
- **Performance**: Test with large datasets

## Monitoring

### Metrics
- **Calculation Accuracy**: Monitor calculation precision
- **Performance**: Track response times
- **Error Rates**: Monitor error frequencies
- **Usage Patterns**: Track API usage

### Alerts
- **Validation Failures**: Alert on invalid configurations
- **Performance Degradation**: Alert on slow responses
- **High Error Rates**: Alert on increased errors
- **Security Events**: Alert on security incidents

## Future Enhancements

### Planned Features
- **Advanced Policies**: More complex overtime rules
- **Union Integration**: Union-specific overtime rules
- **Multi-currency**: International overtime support
- **Real-time Analytics**: Live overtime monitoring
- **Predictive Analytics**: Overtime forecasting
- **Mobile Integration**: Mobile app support

### Integration Opportunities
- **HR Systems**: Employee lifecycle integration
- **Time Tracking**: Real-time time tracking integration
- **Accounting**: Direct accounting system integration
- **Reporting**: Advanced reporting dashboard
