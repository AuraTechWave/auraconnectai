# Payroll Module User Guide

Welcome to the AuraConnect Payroll Module User Guide. This document provides comprehensive instructions for using the payroll system to manage employee payments, taxes, and related operations.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard Overview](#dashboard-overview)
3. [Processing Payroll](#processing-payroll)
4. [Managing Employees](#managing-employees)
5. [Tax Configuration](#tax-configuration)
6. [Reports and Analytics](#reports-and-analytics)
7. [Common Tasks](#common-tasks)
8. [Troubleshooting](#troubleshooting)
9. [FAQs](#faqs)

## Getting Started

### Accessing the Payroll Module

1. Log in to AuraConnect at https://app.auraconnect.com
2. Navigate to the **Payroll** section from the main menu
3. Ensure you have the appropriate permissions:
   - **Payroll User**: View payroll data and run reports
   - **Payroll Manager**: Process payroll and manage configurations
   - **Payroll Admin**: Full access including system settings

### Initial Setup

Before processing your first payroll:

1. **Verify Company Information**
   - Company name and address
   - Federal EIN
   - State tax IDs
   - Bank account details

2. **Configure Pay Schedules**
   - Weekly, bi-weekly, semi-monthly, or monthly
   - Pay period dates
   - Pay dates

3. **Set Up Tax Tables**
   - Federal tax rates (updated automatically)
   - State tax configurations
   - Local tax requirements

## Dashboard Overview

The Payroll Dashboard provides a comprehensive view of your payroll operations:

### Key Metrics

![Payroll Dashboard](dashboard-screenshot.png)

1. **Upcoming Payrolls**
   - Next pay date
   - Number of employees
   - Estimated total

2. **Recent Activity**
   - Last processed payroll
   - Recent corrections
   - Pending approvals

3. **Compliance Status**
   - Tax filing deadlines
   - Required reports
   - Audit notifications

4. **Quick Actions**
   - Run Payroll
   - View Reports
   - Manage Employees
   - Configure Settings

## Processing Payroll

### Step-by-Step Payroll Processing

#### 1. Start Payroll Run

1. Click **"Run Payroll"** from the dashboard
2. Select the pay period:
   - Start Date: [Select date]
   - End Date: [Select date]
   - Pay Date: [Select date]

3. Choose processing options:
   - [ ] Include all active employees
   - [ ] Include overtime calculations
   - [ ] Apply scheduled changes
   - [ ] Process benefits and deductions

#### 2. Review Employee Hours

For hourly employees, verify timesheet data:

```
Employee Name         Regular  Overtime  Total    Status
─────────────────────────────────────────────────────────
John Smith           80.00    5.00      85.00    ✓ Approved
Jane Doe             75.50    0.00      75.50    ✓ Approved
Bob Johnson          80.00    10.00     90.00    ⚠ Pending
```

Actions:
- **Edit**: Modify hours if needed
- **Approve**: Approve pending timesheets
- **Exclude**: Remove from this payroll run

#### 3. Review Calculations

The system automatically calculates:

**Earnings:**
- Regular pay
- Overtime pay (1.5x or custom rate)
- Bonuses and commissions
- Other earnings

**Deductions:**
- Federal income tax
- State income tax
- Social Security (6.2%)
- Medicare (1.45%)
- Benefits (health, dental, vision)
- Retirement contributions
- Garnishments

**Example Calculation:**
```
John Smith - Software Engineer
───────────────────────────────────────
Regular Pay (80 hrs × $50/hr)    $4,000.00
Overtime Pay (5 hrs × $75/hr)       $375.00
                                  ─────────
Gross Pay                         $4,375.00

Federal Tax                         $656.25
State Tax (CA)                      $218.75
Social Security                     $271.25
Medicare                            $63.44
Health Insurance                    $200.00
401(k) (6%)                        $262.50
                                  ─────────
Total Deductions                  $1,672.19

Net Pay                          $2,702.81
```

#### 4. Make Adjustments

If adjustments are needed:

1. Click **"Adjust"** next to the employee
2. Select adjustment type:
   - Bonus
   - Commission
   - Reimbursement
   - Deduction
   - Garnishment

3. Enter details:
   - Amount: $___
   - Description: ___________
   - Tax treatment: [Taxable/Non-taxable]

#### 5. Approve and Process

1. Review summary:
   ```
   Payroll Summary
   ─────────────────────────────
   Total Employees:        45
   Total Gross Pay:   $156,250.00
   Total Net Pay:     $117,187.50
   Total Taxes:        $39,062.50
   
   Payment Method:
   Direct Deposit:     42 employees
   Paper Check:         3 employees
   ```

2. Click **"Approve Payroll"**
3. Enter approval code or use 2FA
4. Click **"Process Payments"**

### Batch Processing

For large organizations, use batch processing:

1. Navigate to **Payroll → Batch Processing**
2. Upload employee data (CSV format)
3. Configure batch options:
   - Processing priority
   - Error handling
   - Notification preferences

4. Monitor progress:
   ```
   Batch Status: Processing
   Progress: ████████░░ 82% (410/500 employees)
   Estimated Time: 5 minutes remaining
   ```

## Managing Employees

### Employee Payroll Settings

Access employee settings via **Employees → Payroll Settings**:

#### Compensation

1. **Pay Structure**
   - Pay type: [Salary/Hourly]
   - Base rate: $___ per [year/hour]
   - Effective date: ___

2. **Overtime Settings**
   - Overtime eligible: [Yes/No]
   - Overtime rate: [1.5x/2x/Custom]
   - Overtime threshold: ___ hours

#### Tax Information

1. **Federal Taxes**
   - Filing status: [Single/Married/Head of Household]
   - Allowances: ___
   - Additional withholding: $___

2. **State Taxes**
   - State: [Select state]
   - Filing status: ___
   - Allowances: ___
   - Additional withholding: $___

3. **Tax Exemptions**
   - [ ] Exempt from federal withholding
   - [ ] Exempt from state withholding
   - [ ] Exempt from FICA

#### Benefits and Deductions

1. **Benefits Enrollment**
   ```
   Benefit          Plan         Employee Cost   Employer Cost
   ──────────────────────────────────────────────────────────
   Health           Premium      $200.00/mo      $400.00/mo
   Dental           Standard     $25.00/mo       $25.00/mo
   Vision           Basic        $10.00/mo       $10.00/mo
   Life             2x Salary    $15.00/mo       $30.00/mo
   ```

2. **Retirement**
   - 401(k) contribution: ___% or $___
   - Employer match: ___% up to ___%
   - Vesting schedule: ___

3. **Other Deductions**
   - Garnishments
   - Union dues
   - Charitable contributions
   - Loan repayments

### Employee Self-Service

Employees can access their payroll information:

1. **View Pay Stubs**
   - Current and historical
   - Download PDF
   - Email copies

2. **Tax Documents**
   - W-2 forms
   - 1095-C (ACA)
   - State tax forms

3. **Update Information**
   - Direct deposit details
   - Tax withholdings
   - Benefit elections

## Tax Configuration

### Managing Tax Settings

Navigate to **Settings → Tax Configuration**:

#### Federal Tax Tables

Federal tax tables are updated automatically. View current rates:

```
2024 Federal Tax Brackets - Single
────────────────────────────────────
$0 - $11,000            10%
$11,001 - $44,725       12%
$44,726 - $95,375       22%
$95,376 - $182,050      24%
$182,051 - $231,250     32%
$231,251 - $578,125     35%
$578,126+               37%

Standard Deduction: $13,850
```

#### State Tax Configuration

Configure state-specific settings:

1. **Select State**: [Dropdown menu]
2. **Tax Rates**: View/edit if applicable
3. **Special Rules**:
   - Disability insurance (CA, HI, NJ, NY, RI)
   - Local taxes
   - Reciprocity agreements

#### Compliance Updates

Stay informed about tax law changes:

- **Alerts**: Automatic notifications
- **Updates**: One-click updates
- **History**: View change log

## Reports and Analytics

### Standard Reports

Access via **Reports** menu:

#### 1. Payroll Register

Detailed record of each payroll:

```
Payroll Register - Period: 01/01/2024 - 01/15/2024
─────────────────────────────────────────────────────
Employee         Gross    Fed Tax   State   FICA    Net Pay
Smith, John      4,375.00  656.25   218.75  334.69  2,702.81
Doe, Jane        3,200.00  480.00   160.00  244.80  1,976.20
...
─────────────────────────────────────────────────────
Totals:         156,250.00 23,437.50 7,812.50 11,953.13 117,187.50
```

#### 2. Tax Liability Report

Summary of tax obligations:

```
Tax Liability Report - Q1 2024
──────────────────────────────
Federal Income Tax:    $70,312.50
Social Security:       $38,775.00
Medicare:              $9,062.50
Federal Unemployment:  $1,875.00
State Income Tax:      $23,437.50
State Unemployment:    $4,687.50
─────────────────────────────
Total Tax Liability:   $148,150.00

Payment Schedule:
- Monthly deposits due by 15th
- Quarterly 941 due April 30
```

#### 3. Employee Earnings Report

Year-to-date earnings by employee:

```
Employee YTD Earnings - 2024
────────────────────────────────────
Employee         YTD Gross   YTD Tax    YTD Net
Smith, John      $26,250.00  $7,875.00  $18,375.00
Doe, Jane        $19,200.00  $5,760.00  $13,440.00
Johnson, Bob     $32,500.00  $9,750.00  $22,750.00
```

#### 4. Department Summary

Payroll costs by department:

```
Department Summary - January 2024
─────────────────────────────────
Department      Employees  Total Cost   Avg Cost
Engineering     25         $187,500     $7,500
Sales           15         $112,500     $7,500
Support         10         $50,000      $5,000
Admin           5          $37,500      $7,500
─────────────────────────────────
Total:          55         $387,500     $7,045
```

### Custom Reports

Create custom reports:

1. Click **"New Custom Report"**
2. Select data fields
3. Apply filters:
   - Date range
   - Departments
   - Locations
   - Employee types

4. Choose format:
   - Screen display
   - PDF export
   - Excel export
   - CSV export

### Analytics Dashboard

View real-time analytics:

- **Labor Cost Trends**: Monthly comparison
- **Overtime Analysis**: Department breakdown
- **Tax Liability**: Current vs projected
- **Benefits Utilization**: Enrollment and costs

## Common Tasks

### Processing Off-Cycle Payments

For bonuses or corrections outside regular payroll:

1. Go to **Payroll → Off-Cycle Payment**
2. Select employee(s)
3. Enter payment details:
   - Type: [Bonus/Commission/Correction]
   - Amount: $___
   - Tax treatment: [Standard/Supplemental]
4. Process payment

### Correcting Payments

To correct a processed payment:

1. Find the payment in **Payment History**
2. Click **"Create Correction"**
3. Select correction type:
   - Underpayment: Additional payment
   - Overpayment: Deduction from next payroll
   - Full reversal: Cancel and reprocess

4. Enter correction details
5. Process correction

### Year-End Processing

#### W-2 Preparation

1. **Review Employee Data**
   - Verify addresses
   - Confirm SSNs
   - Check YTD totals

2. **Run W-2 Reports**
   - Preview W-2s
   - Make corrections
   - Generate final W-2s

3. **Distribute W-2s**
   - Electronic delivery
   - Print and mail
   - File with SSA

#### 1099 Processing

For contractors:

1. **Verify Contractor Data**
   - Tax ID numbers
   - Addresses
   - Payment totals

2. **Generate 1099s**
   - Review payments ≥ $600
   - Create 1099-NEC forms
   - Distribute to contractors

### Setting Up Direct Deposit

For new employees:

1. Collect bank information:
   - Bank name
   - Account type
   - Routing number
   - Account number

2. Enter in system:
   - **Employee → Banking**
   - Add account details
   - Verify with prenote

3. Test transaction:
   - $0.01 test deposit
   - Confirm receipt
   - Activate for payroll

## Troubleshooting

### Common Issues and Solutions

#### 1. Missing Timesheet Data

**Problem**: Employee hours not showing
**Solution**:
- Check timesheet approval status
- Verify pay period dates
- Ensure employee is active

#### 2. Incorrect Tax Calculations

**Problem**: Taxes seem too high/low
**Solution**:
- Review employee tax settings
- Check for recent tax table updates
- Verify YTD amounts

#### 3. Direct Deposit Failures

**Problem**: Payment returned
**Solution**:
- Verify account numbers
- Check account status
- Contact employee for updated info

#### 4. Report Discrepancies

**Problem**: Reports don't match
**Solution**:
- Check report date ranges
- Verify filters applied
- Review recent corrections

### Getting Help

If you need assistance:

1. **In-App Help**
   - Click "?" icon
   - Search knowledge base
   - View video tutorials

2. **Support Contact**
   - Email: support@auraconnect.com
   - Phone: 1-800-PAYROLL
   - Chat: Available 8am-6pm PST

3. **Resources**
   - User manual (PDF)
   - Video training library
   - Monthly webinars

## FAQs

### General Questions

**Q: When should I run payroll?**
A: Run payroll 2-3 business days before the pay date to allow for processing and banking time.

**Q: Can I run payroll for just one employee?**
A: Yes, use the Off-Cycle Payment feature for individual payments.

**Q: How do I handle retroactive pay increases?**
A: Use the Adjustment feature to add the retroactive amount to the next regular payroll.

### Tax Questions

**Q: When are tax deposits due?**
A: Depends on your deposit schedule:
- Monthly: 15th of following month
- Semi-weekly: Wednesday or Friday
- Next-day: For large employers

**Q: How do I update tax tables?**
A: Tax tables update automatically. Check Settings → Tax Configuration for the last update date.

**Q: What if an employee claims exempt?**
A: Enter "Exempt" status in their tax settings. No federal income tax will be withheld, but FICA still applies.

### Compliance Questions

**Q: What reports do I need for audits?**
A: Key reports include:
- Payroll registers
- Tax liability reports
- Employee earnings records
- Bank reconciliations

**Q: How long should I keep payroll records?**
A: Federal requirement is 3 years, but some states require longer. The system retains records for 7 years.

**Q: What about ACA reporting?**
A: The system tracks ACA-required information and generates 1095-C forms annually.

### Technical Questions

**Q: Can I integrate with my time tracking system?**
A: Yes, we support integrations with major time tracking systems. Contact support for setup.

**Q: Is my data backed up?**
A: Yes, data is backed up continuously with point-in-time recovery available for 30 days.

**Q: Can I export data?**
A: Yes, all reports can be exported to PDF, Excel, or CSV formats.

## Best Practices

1. **Run Payroll Consistently**
   - Same day each pay period
   - Allow adequate processing time
   - Review before approving

2. **Keep Records Updated**
   - Employee information
   - Tax settings
   - Benefit enrollments

3. **Regular Reviews**
   - Monthly reconciliation
   - Quarterly tax review
   - Annual audit preparation

4. **Stay Informed**
   - Read system notifications
   - Attend training sessions
   - Review compliance updates

## Appendix

### Glossary

- **ACH**: Automated Clearing House (electronic payments)
- **EIN**: Employer Identification Number
- **FICA**: Federal Insurance Contributions Act (Social Security and Medicare)
- **FUTA**: Federal Unemployment Tax Act
- **Gross Pay**: Total earnings before deductions
- **Net Pay**: Take-home pay after all deductions
- **Pay Period**: Time period for which employees are paid
- **SUTA**: State Unemployment Tax Act
- **W-4**: Employee tax withholding form
- **YTD**: Year-to-Date

### Keyboard Shortcuts

- `Ctrl/Cmd + N`: New payroll run
- `Ctrl/Cmd + S`: Save current work
- `Ctrl/Cmd + P`: Print current screen
- `Ctrl/Cmd + F`: Find employee
- `Ctrl/Cmd + R`: Run report
- `Esc`: Cancel current action

### System Requirements

- **Browser**: Chrome, Firefox, Safari, or Edge (latest versions)
- **Screen Resolution**: 1280x720 minimum
- **Internet**: Broadband connection recommended
- **PDF Reader**: For viewing reports
- **Printer**: For check printing (if applicable)