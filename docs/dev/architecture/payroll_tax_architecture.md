# Payroll Tax Architecture - AUR-275 Phase 1

## Overview

This document outlines the architecture for AUR-275 Phase 1, which implements the core payroll module with enhanced tax rule management, payroll policies, and employee payment tracking. This phase establishes the foundation for comprehensive payroll tax processing in the AuraConnect system.

## Architecture Components

### 1. TaxRule Model (`payroll_tax_rules`)

The `TaxRule` model provides granular control over tax calculations for payroll processing:

**Key Features:**
- **Multi-level Tax Types**: Supports federal, state, local, social security, and medicare taxes
- **Rate Management**: Flexible percentage-based tax rates with precision to 4 decimal places  
- **Income Thresholds**: Configurable minimum and maximum taxable amounts per rule
- **Split Contributions**: Separate employee and employer portions for taxes like Social Security
- **Time-based Rules**: Effective and expiry dates for tax rule lifecycle management
- **Location-based**: Tax rules tied to specific locations for multi-jurisdiction support

**Schema:**
```sql
payroll_tax_rules (
    id, rule_name, location, tax_type, rate_percent,
    max_taxable_amount, min_taxable_amount,
    employee_portion, employer_portion,
    effective_date, expiry_date, is_active,
    created_at, updated_at
)
```

### 2. PayrollPolicy Model (`payroll_policies`)

The `PayrollPolicy` model defines comprehensive payroll calculation rules per location:

**Key Features:**
- **Pay Frequency Management**: Weekly, biweekly, monthly, semi-monthly scheduling
- **Overtime Rules**: Configurable overtime thresholds and multipliers
- **Double-time Support**: Advanced overtime calculations for extended hours
- **Break Requirements**: Meal and rest break hour thresholds for compliance
- **Holiday Processing**: Holiday pay multipliers and special handling
- **Minimum Wage Enforcement**: Location-specific minimum wage requirements

**Schema:**
```sql
payroll_policies (
    id, policy_name, location, pay_frequency,
    overtime_threshold_hours, overtime_multiplier,
    double_time_threshold_hours, double_time_multiplier,
    pay_period_start_day, minimum_wage,
    meal_break_threshold_hours, rest_break_threshold_hours,
    holiday_pay_multiplier, description, is_active,
    created_at, updated_at
)
```

### 3. EmployeePayment Model (`employee_payments`)

The `EmployeePayment` model tracks individual payroll calculations and payment records:

**Key Features:**
- **Comprehensive Hour Tracking**: Regular, overtime, double-time, and holiday hours
- **Multi-rate Support**: Different pay rates for various hour types
- **Detailed Tax Calculations**: Federal, state, local, Social Security, Medicare taxes
- **Deduction Management**: Insurance, retirement, and other customizable deductions
- **Payment Status Tracking**: Full lifecycle from pending to paid
- **Audit Trail**: Processing timestamps and user tracking

**Schema:**
```sql
employee_payments (
    id, staff_id, payroll_policy_id,
    pay_period_start, pay_period_end, pay_date,
    regular_hours, overtime_hours, double_time_hours, holiday_hours,
    regular_rate, overtime_rate, double_time_rate, holiday_rate,
    regular_pay, overtime_pay, double_time_pay, holiday_pay,
    bonus_pay, commission_pay, gross_pay,
    federal_tax, state_tax, local_tax,
    social_security_tax, medicare_tax,
    insurance_deduction, retirement_deduction, other_deductions,
    total_deductions, net_pay,
    payment_status, payment_method, notes,
    processed_by, processed_at,
    created_at, updated_at
)
```

## Data Relationships

```
PayrollPolicy (1) --> (Many) EmployeePayment
    |
    |-- Defines calculation rules for payments
    |-- Controls overtime, breaks, and wage policies
    
TaxRule (Independent) --> (Applied to) EmployeePayment
    |
    |-- Multiple tax rules can apply to one payment
    |-- Location-based rule selection
    |-- Time-based rule applicability
```

## Integration Points

### With Existing Staff Module
- `EmployeePayment.staff_id` references existing staff members
- Integrates with current `staff_members` table
- Maintains compatibility with existing payroll workflows

### With Tax Module  
- Complements existing `tax_rules` table for order-based taxes
- New `payroll_tax_rules` table specifically for payroll calculations
- Separate tax contexts for different business processes

### With Time Tracking
- `EmployeePayment` stores calculated hours from time tracking systems
- Ready for integration with shift and attendance modules
- Supports multiple hour types and rate calculations

## Implementation Benefits

### Phase 1 Advantages
1. **Scalable Foundation**: Modular design supports future payroll enhancements
2. **Compliance Ready**: Built-in support for multi-jurisdiction tax requirements  
3. **Audit Trail**: Complete tracking of payroll calculations and processing
4. **Flexible Tax Rules**: Supports complex tax scenarios with time-based rules
5. **Policy Management**: Location-specific payroll policies for multi-site operations

### Future Extensibility
- Ready for integration with government compliance APIs
- Supports advanced payroll features like commissions and bonuses
- Extensible deduction system for custom payroll items
- Foundation for automated payroll processing workflows

## Security Considerations

- All payroll data includes comprehensive audit trails
- Time-based access control through effective/expiry dates
- Payment status tracking prevents duplicate processing
- Separate tax rule management for enhanced security

## Migration Strategy

The Alembic migration `20250725_0700_0007_create_payroll_tax_tables.py` creates:
1. `payroll_tax_rules` table with appropriate indexes
2. `payroll_policies` table with location-based indexing  
3. `employee_payments` table with foreign key relationships
4. All necessary indexes for optimal query performance

This Phase 1 implementation provides the essential foundation for comprehensive payroll tax processing while maintaining compatibility with existing AuraConnect systems.