# Payroll & Tax Module Glossary

This glossary defines key terms used throughout the Payroll & Tax Module documentation.

## A

**ACH (Automated Clearing House)**
: Electronic network for financial transactions in the US, used for direct deposit of payroll.

**ADR (Architecture Decision Record)**
: Document that captures an important architectural decision made along with its context and consequences.

**API (Application Programming Interface)**
: Set of protocols and tools for building software applications, defining how different software components should interact.

**Audit Trail**
: Chronological record of system activities that provides documentary evidence of the sequence of activities.

## B

**Batch Processing**
: Method of processing payroll for multiple employees simultaneously rather than individually.

**Benefits**
: Non-wage compensation provided to employees, including health insurance, retirement plans, and other perks.

**Biweekly**
: Pay schedule where employees are paid every two weeks, resulting in 26 pay periods per year.

## C

**Calculation Engine**
: Core component that computes gross pay, taxes, deductions, and net pay based on employee data and rules.

**Celery**
: Distributed task queue used for handling background jobs and asynchronous processing.

**Compensation**
: Total of all wages, salaries, bonuses, and benefits paid to an employee.

**Cutover**
: Process of switching from a legacy system to a new system.

## D

**Deductions**
: Amounts subtracted from gross pay, including taxes, benefits, and other withholdings.

**Direct Deposit**
: Electronic transfer of payroll funds directly into an employee's bank account.

**Docker**
: Platform for developing, shipping, and running applications in containers.

## E

**EIN (Employer Identification Number)**
: Federal tax identification number assigned by the IRS to identify a business entity.

**Employee Payment**
: Record of compensation paid to an employee for a specific pay period.

**Encryption**
: Process of encoding sensitive data to prevent unauthorized access.

## F

**FastAPI**
: Modern, fast web framework for building APIs with Python, used for the payroll module's REST API.

**Federal Income Tax**
: Tax levied by the federal government on an individual's earnings.

**FICA (Federal Insurance Contributions Act)**
: US federal payroll tax that funds Social Security and Medicare.

**Filing Status**
: Classification that defines the type of tax return form an individual will use (single, married, etc.).

## G

**Garnishment**
: Legal process where a portion of an employee's wages is withheld to pay a debt.

**Gross Pay**
: Total earnings before any deductions are taken out.

**GraphQL**
: Query language for APIs, planned for future implementation.

## H

**HSTS (HTTP Strict Transport Security)**
: Web security policy mechanism that helps protect against protocol downgrade attacks.

**Hourly Employee**
: Employee paid based on the number of hours worked.

## I

**Integration**
: Connection between the payroll module and other systems (Staff, Tax, Accounting, etc.).

**IRS (Internal Revenue Service)**
: US federal agency responsible for tax collection and tax law enforcement.

## J

**JWT (JSON Web Token)**
: Compact, URL-safe means of representing claims to be transferred between two parties, used for authentication.

**Journal Entry**
: Record of financial transactions in the accounting system.

## K

**Kubernetes (K8s)**
: Open-source container orchestration platform for automating deployment, scaling, and management.

## L

**Leave Balance**
: Amount of paid time off (vacation, sick leave) available to an employee.

**Legacy System**
: Older payroll system being replaced by AuraConnect.

## M

**Medicare**
: Federal health insurance program, funded partly through payroll taxes (1.45% of wages).

**Microservices**
: Architectural style where applications are built as a collection of small, independent services.

**Migration**
: Process of moving data and functionality from a legacy system to AuraConnect.

## N

**Net Pay**
: Amount an employee receives after all deductions are subtracted from gross pay (take-home pay).

**Notification Service**
: System component that sends alerts and communications to employees and administrators.

## O

**ORM (Object-Relational Mapping)**
: Programming technique for converting data between incompatible type systems (SQLAlchemy in this module).

**Overtime**
: Hours worked beyond the standard work week, typically paid at 1.5x the regular rate.

## P

**Pay Period**
: Recurring length of time over which employee time is recorded and paid.

**Pay Schedule**
: Frequency and dates on which employees are paid (weekly, biweekly, semimonthly, monthly).

**PostgreSQL**
: Open-source relational database management system used for data storage.

**Pre-tax Deduction**
: Deduction taken from gross pay before taxes are calculated (e.g., 401k contributions).

## Q

**Queue**
: Data structure used for managing background tasks and asynchronous operations.

## R

**RBAC (Role-Based Access Control)**
: Method of restricting system access based on user roles and permissions.

**Redis**
: In-memory data structure store used for caching and message queuing.

**Reconciliation**
: Process of ensuring payroll calculations and payments match expected values.

**RLS (Row-Level Security)**
: Database feature that restricts which rows a user can access in a table.

**Rollback**
: Process of reverting to a previous system state if migration fails.

## S

**Salaried Employee**
: Employee paid a fixed amount regardless of hours worked.

**Semimonthly**
: Pay schedule with two pay periods per month, typically on the 15th and last day.

**Social Security**
: Federal program funded through payroll taxes (6.2% of wages up to wage base limit).

**SQLAlchemy**
: Python SQL toolkit and ORM used for database operations.

**SSN (Social Security Number)**
: Nine-digit number issued to US citizens for tracking Social Security benefits.

**State Income Tax**
: Tax levied by individual states on employee earnings.

## T

**Tax Withholding**
: Amount deducted from an employee's paycheck for income taxes.

**Tenant**
: Isolated instance of the application serving a specific organization (multi-tenancy).

**TLS (Transport Layer Security)**
: Cryptographic protocol for secure communications.

## U

**UAT (User Acceptance Testing)**
: Testing performed by end users to verify the system meets business requirements.

**UTC (Coordinated Universal Time)**
: Primary time standard used for consistent timestamp storage.

## V

**Validation**
: Process of checking data accuracy and completeness during migration or calculation.

**Variance**
: Difference between expected and actual values in calculations or reconciliation.

## W

**W-2**
: IRS tax form reporting annual wages and tax withholdings for employees.

**W-4**
: IRS form employees complete to indicate tax withholding preferences.

**Webhook**
: HTTP callback that occurs when something happens; used for event notifications.

**Worker**
: Background process that executes asynchronous tasks (Celery worker).

## Y

**Year-to-Date (YTD)**
: Cumulative totals from the beginning of the year to the current date.

**YTD Gross**
: Total gross earnings from January 1 to the current date.

**YTD Withholding**
: Total taxes withheld from January 1 to the current date.

## Acronyms Quick Reference

| Acronym | Full Form |
|---------|-----------|
| API | Application Programming Interface |
| CRUD | Create, Read, Update, Delete |
| DB | Database |
| DD | Direct Deposit |
| DI | Dependency Injection |
| EFT | Electronic Funds Transfer |
| GL | General Ledger |
| HR | Human Resources |
| HTTPS | Hypertext Transfer Protocol Secure |
| JSON | JavaScript Object Notation |
| OT | Overtime |
| PTO | Paid Time Off |
| REST | Representational State Transfer |
| SLA | Service Level Agreement |
| SQL | Structured Query Language |
| UI/UX | User Interface/User Experience |
| UUID | Universally Unique Identifier |
| XML | Extensible Markup Language |